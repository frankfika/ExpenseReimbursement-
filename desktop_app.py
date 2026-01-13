#!/usr/bin/env python3
"""
报销助手 - 桌面版
使用 pywebview 将 Flask 应用包装成原生桌面应用
"""

import os
import sys
import webview
import threading
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 全局窗口引用
main_window = None


class Api:
    """暴露给 JavaScript 的 API"""

    def select_folder(self):
        """打开文件夹选择对话框，返回文件夹中的所有支持的文件"""
        global main_window
        if not main_window:
            return []

        result = main_window.create_file_dialog(
            webview.FOLDER_DIALOG,
            directory='',
            allow_multiple=False
        )

        if not result or len(result) == 0:
            return []

        folder_path = result[0]
        supported_ext = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp', '.pdf'}
        files = []

        for root, dirs, filenames in os.walk(folder_path):
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext in supported_ext:
                    file_path = os.path.join(root, filename)
                    files.append({
                        'name': filename,
                        'path': file_path,
                        'size': os.path.getsize(file_path)
                    })

        return files

    def select_files(self):
        """打开文件选择对话框"""
        global main_window
        if not main_window:
            return []

        result = main_window.create_file_dialog(
            webview.OPEN_DIALOG,
            directory='',
            allow_multiple=True,
            file_types=('Image Files (*.jpg;*.jpeg;*.png;*.bmp;*.tiff;*.webp)', 'PDF Files (*.pdf)', 'All Files (*.*)')
        )

        if not result:
            return []

        files = []
        for file_path in result:
            files.append({
                'name': os.path.basename(file_path),
                'path': file_path,
                'size': os.path.getsize(file_path)
            })

        return files


def find_free_port(start_port=5000, max_retries=10):
    """查找可用端口"""
    import socket
    for i in range(max_retries):
        port = start_port + i
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    return start_port


# 全局端口变量
flask_port = 5000


def start_flask():
    """在后台线程中启动 Flask 服务器"""
    global flask_port

    from web_app import app

    # 桌面应用中跳过命令行配置向导（用户通过网页界面配置）
    # 不再调用 setup_wizard()

    # 禁用 Flask 的日志输出
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    # 查找可用端口
    flask_port = find_free_port(5000)

    try:
        app.run(host='127.0.0.1', port=flask_port, debug=False, threaded=True, use_reloader=False)
    except Exception as e:
        logger.error(f"Flask 启动失败: {e}")


def main():
    """启动桌面应用"""
    global flask_port, main_window

    # 确保资源文件路径正确
    if getattr(sys, 'frozen', False):
        # 打包后的可执行文件运行
        application_path = sys._MEIPASS
    else:
        # 正常 Python 脚本运行
        application_path = str(Path(__file__).parent)

    # 在后台线程中启动 Flask
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    # 等待 Flask 启动
    import time
    time.sleep(2)

    # 创建 API 实例
    api = Api()

    # 创建 WebView 窗口
    main_window = webview.create_window(
        title='报销助手',
        url=f'http://127.0.0.1:{flask_port}',
        width=1200,
        height=800,
        min_size=(800, 600),
        resizable=True,
        frameless=False,
        easy_drag=False,
        background_color='#FFFFFF',
        js_api=api
    )

    logger.info("报销助手桌面版已启动")
    webview.start(debug=False)


if __name__ == '__main__':
    main()
