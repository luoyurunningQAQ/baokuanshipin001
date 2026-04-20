"""
AutoViral AI - Mac 启动器
PyInstaller 打包入口：启动 Streamlit 服务并自动打开浏览器
"""

import sys
import os
import threading
import webbrowser
import time


def _open_browser(url: str, delay: float = 2.5):
    """延迟打开浏览器，等待 Streamlit 服务就绪"""
    time.sleep(delay)
    webbrowser.open(url)


def _get_app_dir() -> str:
    """获取 app.py 所在目录（兼容 PyInstaller bundle 和直接运行）"""
    if getattr(sys, "frozen", False):
        # PyInstaller .app bundle：可执行文件在 MacOS/，Resources 在上级
        exe_dir = os.path.dirname(sys.executable)
        # 尝试 .app 标准结构: Contents/MacOS -> Contents/Resources/app
        resources_app = os.path.normpath(
            os.path.join(exe_dir, "..", "Resources", "app")
        )
        if os.path.isfile(os.path.join(resources_app, "app.py")):
            return resources_app
        # 回退：直接解包目录（onedir 模式）
        meipass = getattr(sys, "_MEIPASS", exe_dir)
        if os.path.isfile(os.path.join(meipass, "app.py")):
            return meipass
        return exe_dir
    else:
        return os.path.dirname(os.path.abspath(__file__))


def main():
    app_dir = _get_app_dir()
    app_path = os.path.join(app_dir, "app.py")

    if not os.path.isfile(app_path):
        print(f"[AutoViral] 错误：找不到 app.py，路径：{app_path}")
        sys.exit(1)

    # 切换工作目录，保证相对路径（modules/, reports/, temp/ 等）正常工作
    os.chdir(app_dir)

    # 创建必要的目录
    for d in ("reports", "temp", "cookies", "koc_profiles"):
        os.makedirs(os.path.join(app_dir, d), exist_ok=True)

    port = 8501
    url = f"http://localhost:{port}"

    # 在后台线程延迟打开浏览器
    t = threading.Thread(target=_open_browser, args=(url,), daemon=True)
    t.start()

    # 启动 Streamlit
    import streamlit.web.cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        app_path,
        f"--server.port={port}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
    ]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
