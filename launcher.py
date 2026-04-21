"""
AutoViral AI - Mac 启动器（自包含版）
打包后包含 Python 解释器 + 所有依赖 + ffmpeg，无需用户预装任何软件
"""

import os
import sys
import threading
import webbrowser
import time


def _setup_env():
    """在导入任何第三方库之前，先配置好内置 ffmpeg 和工作目录"""

    # ── 定位 bundle 内部路径 ──────────────────────────────────────────
    if getattr(sys, "frozen", False):
        # PyInstaller 打包后：可执行文件在 .app/Contents/MacOS/
        macos_dir = os.path.dirname(sys.executable)
        # .app/Contents/Resources/_internal（PyInstaller 6.x 默认位置）
        internal = os.path.join(macos_dir, "_internal")
        if not os.path.isdir(internal):
            internal = getattr(sys, "_MEIPASS", macos_dir)

        # app 源码目录（app.py / modules/ 放在这里）
        app_src = os.path.join(internal, "app")
        if not os.path.isdir(app_src):
            app_src = internal

        # ffmpeg 二进制路径
        ffmpeg_bin = os.path.join(internal, "bin", "ffmpeg")
        ffprobe_bin = os.path.join(internal, "bin", "ffprobe")
    else:
        # 直接运行（开发模式）
        app_src = os.path.dirname(os.path.abspath(__file__))
        ffmpeg_bin = "ffmpeg"
        ffprobe_bin = "ffprobe"

    # ── 工作目录切换到 app 源码目录 ───────────────────────────────────
    os.chdir(app_src)
    # 让 Python 能找到 modules/ 包
    if app_src not in sys.path:
        sys.path.insert(0, app_src)

    # ── 创建必要的运行时目录 ──────────────────────────────────────────
    for d in ("reports", "temp", "cookies", "koc_profiles"):
        os.makedirs(os.path.join(app_src, d), exist_ok=True)

    # ── 配置 ffmpeg 路径（moviepy / yt-dlp 都会读这两个环境变量）─────
    if os.path.isfile(ffmpeg_bin):
        os.environ["FFMPEG_BINARY"] = ffmpeg_bin
        os.environ["FFPROBE_BINARY"] = ffprobe_bin
        # moviepy 1.x 通过此环境变量定位 ffmpeg
        os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_bin

    return app_src


def _open_browser(url: str, delay: float = 3.0):
    time.sleep(delay)
    webbrowser.open(url)


def main():
    app_src = _setup_env()
    app_path = os.path.join(app_src, "app.py")

    if not os.path.isfile(app_path):
        # 最后尝试：当前目录
        app_path = "app.py"

    port = 8501
    threading.Thread(
        target=_open_browser, args=(f"http://localhost:{port}",), daemon=True
    ).start()

    import streamlit.web.cli as stcli

    sys.argv = [
        "streamlit", "run", app_path,
        f"--server.port={port}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
    ]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
