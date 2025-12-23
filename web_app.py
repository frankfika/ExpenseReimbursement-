#!/usr/bin/env python3
"""
报销助手 - Web 版
提供网页界面，用户上传发票后自动处理并下载结果
"""

import os
import sys
import uuid
import shutil
import tempfile
import zipfile
import threading
import time
import atexit
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, after_this_request

# 导入现有模块
from config import DEEPSEEK_API_KEY, INVOICE_CATEGORIES, is_configured, setup_wizard
from ocr_handler import extract_text_from_file, is_supported_file
from invoice_analyzer import analyze_invoice, InvoiceInfo
from file_organizer import FileOrganizer
from report_generator import generate_report

app = Flask(__name__)

# 配置
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB 总上传限制
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'bmp', 'tiff', 'webp', 'pdf'}

# 任务存储（内存中）
tasks = {}
# 任务操作锁（保护 tasks 字典的并发访问）
tasks_lock = threading.Lock()


def allowed_file(filename):
    """检查文件类型是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def cleanup_task(task_id, delay=1800):
    """延迟清理任务数据（默认30分钟后）"""
    def do_cleanup():
        time.sleep(delay)
        with tasks_lock:
            if task_id in tasks:
                task = tasks[task_id]
                # 删除临时目录
                if 'temp_dir' in task and os.path.exists(task['temp_dir']):
                    shutil.rmtree(task['temp_dir'], ignore_errors=True)
                if 'output_dir' in task and os.path.exists(task['output_dir']):
                    shutil.rmtree(task['output_dir'], ignore_errors=True)
                if 'zip_path' in task and os.path.exists(task['zip_path']):
                    os.remove(task['zip_path'])
                del tasks[task_id]
                print(f"[清理] 已删除任务 {task_id} 的临时文件")

    thread = threading.Thread(target=do_cleanup, daemon=True)
    thread.start()


def cleanup_all_tasks():
    """服务器关闭时清理所有任务"""
    with tasks_lock:
        for task_id, task in list(tasks.items()):
            if 'temp_dir' in task and os.path.exists(task['temp_dir']):
                shutil.rmtree(task['temp_dir'], ignore_errors=True)
            if 'output_dir' in task and os.path.exists(task['output_dir']):
                shutil.rmtree(task['output_dir'], ignore_errors=True)
            if 'zip_path' in task and os.path.exists(task['zip_path']):
                os.remove(task['zip_path'])
        tasks.clear()
        print("[清理] 已清理所有临时文件")


# 注册退出时清理
atexit.register(cleanup_all_tasks)


def process_task(task_id):
    """后台处理上传的文件"""
    task = tasks[task_id]
    temp_dir = task['temp_dir']
    output_dir = task['output_dir']

    try:
        # 获取 API Key
        api_key = DEEPSEEK_API_KEY
        if not api_key:
            task['status'] = 'error'
            task['error'] = '服务器未配置 API Key，请联系管理员'
            return

        # 扫描文件
        files = []
        for f in Path(temp_dir).rglob("*"):
            if f.is_file() and is_supported_file(str(f)):
                files.append(str(f))

        if not files:
            task['status'] = 'error'
            task['error'] = '未找到有效的发票文件'
            return

        task['total'] = len(files)
        task['status'] = 'processing'

        # 处理每个文件
        invoice_infos = []
        for idx, file_path in enumerate(files, 1):
            task['current'] = idx
            task['current_file'] = Path(file_path).name

            try:
                # OCR 提取
                ocr_text = extract_text_from_file(file_path)
                # AI 分析
                info = analyze_invoice(ocr_text, file_path, api_key)
                invoice_infos.append(info)
            except Exception as e:
                # 创建错误记录
                invoice_infos.append(InvoiceInfo(
                    type="other",
                    subtype="处理失败",
                    amount=0.0,
                    date="",
                    service_date="",
                    merchant="",
                    invoice_number="",
                    is_invoice=False,
                    description=f"处理失败: {str(e)}",
                    raw_text="",
                    file_path=file_path,
                    order_number=""
                ))

        # 分类和整理
        task['status'] = 'organizing'
        organizer = FileOrganizer(output_dir, copy_mode=True)
        categorized = organizer.organize(invoice_infos)

        # 生成报表
        task['status'] = 'generating_report'
        report_path = generate_report(output_dir, categorized)

        # 计算汇总
        summary = {}
        total_amount = 0.0
        for category_name in ['打车票', '火车飞机票', '住宿费', '餐费', '其他']:
            if category_name in categorized:
                infos = categorized[category_name]
                invoice_amount = sum(i.amount for i in infos if i.is_invoice)
                invoice_count = len([i for i in infos if i.is_invoice])
                summary[category_name] = {
                    'count': invoice_count,
                    'amount': invoice_amount
                }
                total_amount += invoice_amount

        task['summary'] = summary
        task['total_amount'] = total_amount

        # 打包为 ZIP
        task['status'] = 'packing'
        zip_filename = f"报销结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_path = os.path.join(tempfile.gettempdir(), f"{task_id}_{zip_filename}")

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, output_dir)
                    zipf.write(file_path, arcname)

        task['zip_path'] = zip_path
        task['zip_filename'] = zip_filename
        task['status'] = 'completed'

        # 立即清理输入文件（保护隐私）
        shutil.rmtree(temp_dir, ignore_errors=True)

        # 启动延迟清理（30分钟后清理输出和ZIP）
        cleanup_task(task_id, delay=1800)

    except Exception as e:
        task['status'] = 'error'
        task['error'] = str(e)
        import traceback
        traceback.print_exc()
        # 异常时也启动延迟清理
        cleanup_task(task_id, delay=300)  # 5分钟后清理


@app.route('/')
def index():
    """首页"""
    configured = is_configured()
    return render_template('index.html', configured=configured)


@app.route('/privacy')
def privacy():
    """隐私政策页面"""
    return render_template('privacy.html')


@app.route('/upload', methods=['POST'])
def upload():
    """处理文件上传"""
    if 'files[]' not in request.files:
        return jsonify({'error': '没有上传文件'}), 400

    files = request.files.getlist('files[]')

    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': '没有选择文件'}), 400

    # 检查 API 配置
    if not DEEPSEEK_API_KEY:
        return jsonify({'error': '服务器未配置 API Key'}), 500

    # 创建任务
    task_id = str(uuid.uuid4())
    temp_dir = tempfile.mkdtemp(prefix=f"reimbursement_input_{task_id}_")
    output_dir = tempfile.mkdtemp(prefix=f"reimbursement_output_{task_id}_")

    # 保存上传的文件
    saved_count = 0
    seen_filenames = set()
    for file in files:
        if file and file.filename and allowed_file(file.filename):
            # 使用安全的文件名（去除路径）
            filename = os.path.basename(file.filename)
            # 避免空文件名
            if not filename:
                continue
            # 处理同名文件：添加序号
            original_filename = filename
            counter = 1
            while filename in seen_filenames:
                name, ext = os.path.splitext(original_filename)
                filename = f"{name}_{counter}{ext}"
                counter += 1
            seen_filenames.add(filename)
            file_path = os.path.join(temp_dir, filename)
            file.save(file_path)
            saved_count += 1

    if saved_count == 0:
        shutil.rmtree(temp_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)
        return jsonify({'error': '没有有效的文件（仅支持 jpg/png/pdf）'}), 400

    # 初始化任务状态
    with tasks_lock:
        tasks[task_id] = {
            'status': 'queued',
            'temp_dir': temp_dir,
            'output_dir': output_dir,
            'total': saved_count,
            'current': 0,
            'created_at': datetime.now().isoformat()
        }

    # 启动后台处理
    thread = threading.Thread(target=process_task, args=(task_id,), daemon=True)
    thread.start()

    return jsonify({
        'task_id': task_id,
        'file_count': saved_count
    })


@app.route('/status/<task_id>')
def status(task_id):
    """查询任务状态"""
    if task_id not in tasks:
        return jsonify({'error': '任务不存在或已过期'}), 404

    task = tasks[task_id]

    response = {
        'status': task['status'],
        'total': task.get('total', 0),
        'current': task.get('current', 0),
        'current_file': task.get('current_file', '')
    }

    if task['status'] == 'completed':
        response['summary'] = task.get('summary', {})
        response['total_amount'] = task.get('total_amount', 0)

    if task['status'] == 'error':
        response['error'] = task.get('error', '未知错误')

    return jsonify(response)


@app.route('/download/<task_id>')
def download(task_id):
    """下载处理结果"""
    if task_id not in tasks:
        return jsonify({'error': '任务不存在或已过期'}), 404

    task = tasks[task_id]

    if task['status'] != 'completed':
        return jsonify({'error': '任务尚未完成'}), 400

    zip_path = task.get('zip_path')
    if not zip_path or not os.path.exists(zip_path):
        return jsonify({'error': '文件已被清理'}), 404

    # 下载后立即清理
    @after_this_request
    def cleanup(response):
        # 启动快速清理（下载后1分钟清理）
        def quick_cleanup():
            time.sleep(60)
            with tasks_lock:
                if task_id in tasks:
                    t = tasks[task_id]
                    if 'output_dir' in t and os.path.exists(t['output_dir']):
                        shutil.rmtree(t['output_dir'], ignore_errors=True)
                    if 'zip_path' in t and os.path.exists(t['zip_path']):
                        os.remove(t['zip_path'])
                    del tasks[task_id]
                    print(f"[清理] 下载后已删除任务 {task_id}")
        threading.Thread(target=quick_cleanup, daemon=True).start()
        return response

    return send_file(
        zip_path,
        mimetype='application/zip',
        as_attachment=True,
        download_name=task.get('zip_filename', '报销结果.zip')
    )


def main():
    """启动 Web 服务器"""
    # 检查配置
    if not is_configured():
        print("\n" + "=" * 50)
        print("首次运行，需要配置 API Key")
        print("=" * 50)
        setup_wizard()

    print("\n" + "=" * 50)
    print("报销助手 - 网页版")
    print("=" * 50)
    print("访问地址: http://localhost:5000")
    print("按 Ctrl+C 停止服务")
    print("=" * 50 + "\n")

    # 自动打开浏览器
    import webbrowser
    webbrowser.open('http://localhost:5000')

    # 启动服务器
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)


if __name__ == '__main__':
    main()
