# AutoViral AI - PyInstaller Spec (macOS)
# 用法（在 Mac 上运行）：
#   pip install pyinstaller
#   pyinstaller AutoViral.spec

import os
from PyInstaller.utils.hooks import collect_data_files, collect_all

block_cipher = None

# ── 收集 Streamlit 所有资源（静态文件、模板等）──────────────────────
streamlit_datas, streamlit_binaries, streamlit_hiddenimports = collect_all("streamlit")

# ── 应用源码目录 ────────────────────────────────────────────────────
SRC = os.path.abspath(".")

# ── 需要一起打包的数据文件/目录 ─────────────────────────────────────
app_datas = [
    # 核心源码
    (os.path.join(SRC, "app.py"),         "app"),
    (os.path.join(SRC, "modules"),        "app/modules"),
    # 静态资源（如果有）
]
# 可选：打包已有的 HTML 报告模板
html_file = os.path.join(SRC, "autoviral_h5.html")
if os.path.isfile(html_file):
    app_datas.append((html_file, "app"))

all_datas = app_datas + streamlit_datas

# ── 隐式导入（避免 PyInstaller 遗漏动态导入的模块）─────────────────
hidden_imports = streamlit_hiddenimports + [
    # Streamlit 运行时
    "streamlit.web.cli",
    "streamlit.runtime.scriptrunner.magic_funcs",
    # 项目模块
    "modules.ai_analysis",
    "modules.local_analysis",
    "modules.video_input",
    "modules.koc_profiler",
    "modules.report_generator",
    "modules.cookie_helper",
    # 核心依赖
    "openai",
    "google.generativeai",
    "cv2",
    "librosa",
    "moviepy",
    "moviepy.editor",
    "yt_dlp",
    "numpy",
    "pandas",
    "dotenv",
    "browser_cookie3",
    # 音频/数字信号
    "soundfile",
    "audioread",
    "resampy",
    "scipy",
    "sklearn",
    # 图像
    "PIL",
    "PIL.Image",
    # 异步
    "asyncio",
    "aiohttp",
    "altair",
    "pydeck",
    "pyarrow",
    "tornado",
    "click",
    "rich",
    "toml",
]

a = Analysis(
    ["launcher.py"],
    pathex=[SRC],
    binaries=streamlit_binaries,
    datas=all_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "IPython",
        "jupyter",
        "notebook",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AutoViral AI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # macOS 上不用 UPX
    console=False,      # 不显示终端窗口
    disable_windowed_traceback=False,
    argv_emulation=True,  # macOS 专用
    target_arch=None,   # None = 当前架构；或 "universal2" 同时支持 Intel/Apple Silicon
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.icns" if os.path.isfile("icon.icns") else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AutoViral AI",
)

app = BUNDLE(
    coll,
    name="AutoViral AI.app",
    icon="icon.icns" if os.path.isfile("icon.icns") else None,
    bundle_identifier="com.autoviral.ai",
    version="3.0.0",
    info_plist={
        "NSPrincipalClass": "NSApplication",
        "NSHighResolutionCapable": True,
        "CFBundleDisplayName": "AutoViral AI",
        "CFBundleShortVersionString": "3.0.0",
        "CFBundleVersion": "3.0.0",
        "NSHumanReadableCopyright": "AutoViral AI v3",
        "LSMinimumSystemVersion": "12.0",  # macOS Monterey+
    },
)
