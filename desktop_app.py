#!/usr/bin/env python3
"""
报销助手 - 桌面版
使用 pywebview 将 Flask 应用包装成原生桌面应用
"""

import os
import sys
import webview
from webview import FileDialog
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

    def __init__(self, window):
        self.window = window

    def select_folder(self):
        """打开文件夹选择对话框，返回文件夹中的所有支持的文件"""
        try:
            result = self.window.create_file_dialog(
                FileDialog.FOLDER,
                directory=os.path.expanduser('~'),
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
                        try:
                            files.append({
                                'name': filename,
                                'path': file_path,
                                'size': os.path.getsize(file_path)
                            })
                        except OSError:
                            pass

            logger.info(f"select_folder: 找到 {len(files)} 个文件")
            return files
        except Exception as e:
            logger.error(f"select_folder 错误: {e}")
            return []

    def select_files(self):
        """打开文件选择对话框"""
        try:
            result = self.window.create_file_dialog(
                FileDialog.OPEN,
                directory=os.path.expanduser('~'),
                allow_multiple=True,
                file_types=('图片文件 (*.jpg;*.jpeg;*.png;*.bmp;*.tiff;*.webp)', 'PDF文件 (*.pdf)', '所有文件 (*.*)')
            )

            if not result:
                return []

            files = []
            for file_path in result:
                try:
                    files.append({
                        'name': os.path.basename(file_path),
                        'path': file_path,
                        'size': os.path.getsize(file_path)
                    })
                except OSError:
                    pass

            logger.info(f"select_files: 选择了 {len(files)} 个文件")
            return files
        except Exception as e:
            logger.error(f"select_files 错误: {e}")
            return []

    def download_file(self, url, default_filename='报销结果.zip'):
        """下载文件到用户指定位置"""
        import requests
        import shutil

        try:
            # 让用户选择保存位置
            save_result = self.window.create_file_dialog(
                FileDialog.SAVE,
                directory=os.path.expanduser('~'),
                save_filename=default_filename
            )

            if not save_result or len(save_result) == 0:
                logger.info("download_file: 用户取消了下载")
                return {'success': False, 'cancelled': True}

            save_path = save_result[0]

            # 从 Flask 服务器下载文件
            flask_url = f'http://127.0.0.1:{flask_port}{url}'
            logger.info(f"download_file: 正在下载 {flask_url} 到 {save_path}")

            response = requests.get(flask_url, stream=True, timeout=300)
            response.raise_for_status()

            # 写入文件
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            logger.info(f"download_file: 下载完成 {save_path}")
            return {'success': True, 'path': save_path}

        except Exception as e:
            logger.error(f"download_file 错误: {e}")
            return {'success': False, 'error': str(e)}


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


def on_webview_loaded():
    """WebView 加载完成后的回调"""
    logger.info("WebView 已加载完成")


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

    # 先创建窗口（不带 API）
    main_window = webview.create_window(
        title='报销助手',
        url=f'http://127.0.0.1:{flask_port}',
        width=1200,
        height=800,
        min_size=(800, 600),
        resizable=True,
        frameless=False,
        easy_drag=False,
        background_color='#FFFFFF'
    )

    # 创建 API 实例并绑定到窗口
    api = Api(main_window)
    main_window.expose(api.select_folder)
    main_window.expose(api.select_files)
    main_window.expose(api.download_file)

    logger.info("报销助手桌面版已启动")
    webview.start(debug=False)


if __name__ == '__main__':
    main()
