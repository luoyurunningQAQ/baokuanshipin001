# AutoViral AI - PyInstaller Spec (macOS 完全自包含版)
# 包含：Python 解释器 + 所有依赖库 + ffmpeg 二进制
# 用户安装后无需安装任何额外软件

import os
import glob
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None
SRC = os.path.abspath(".")

# ── 收集 Streamlit 全部资源 ──────────────────────────────────────────
st_datas, st_binaries, st_hidden = collect_all("streamlit")

# ── 收集其他有静态资源的包 ────────────────────────────────────────────
def safe_collect(pkg):
    try:
        d, b, h = collect_all(pkg)
        return d, b, h
    except Exception:
        return [], [], []

altair_d,  altair_b,  altair_h  = safe_collect("altair")
pydeck_d,  pydeck_b,  pydeck_h  = safe_collect("pydeck")
pyarrow_d, pyarrow_b, pyarrow_h = safe_collect("pyarrow")
ytdlp_d,   ytdlp_b,   ytdlp_h  = safe_collect("yt_dlp")

# ── 应用源码与静态文件 ───────────────────────────────────────────────
app_datas = [
    (os.path.join(SRC, "app.py"),      "app"),
    (os.path.join(SRC, "modules"),     "app/modules"),
]
if os.path.isfile(os.path.join(SRC, "autoviral_h5.html")):
    app_datas.append((os.path.join(SRC, "autoviral_h5.html"), "app"))

# ── 内置 ffmpeg（由 build 脚本下载到 bin/ 目录）────────────────────
ffmpeg_binaries = []
for name in ("ffmpeg", "ffprobe"):
    p = os.path.join(SRC, "bin", name)
    if os.path.isfile(p):
        ffmpeg_binaries.append((p, "bin"))

all_datas = (
    app_datas
    + st_datas
    + altair_d + pydeck_d + pyarrow_d + ytdlp_d
)

all_binaries = st_binaries + altair_b + pydeck_b + pyarrow_b + ytdlp_b

# ── 隐式导入 ────────────────────────────────────────────────────────
hidden_imports = list(set(
    st_hidden + altair_h + pydeck_h + pyarrow_h + ytdlp_h + [
        # Streamlit 核心
        "streamlit.web.cli",
        "streamlit.runtime.scriptrunner.magic_funcs",
        "streamlit.components.v1",
        # 项目模块
        "modules.ai_analysis",
        "modules.local_analysis",
        "modules.video_input",
        "modules.koc_profiler",
        "modules.report_generator",
        "modules.cookie_helper",
        # AI
        "openai", "openai.types", "openai._models",
        "google.generativeai",
        "google.ai.generativelanguage_v1beta",
        # 视频/音频
        "cv2",
        "librosa", "librosa.core", "librosa.feature", "librosa.util",
        "moviepy", "moviepy.editor", "moviepy.video.io.ffmpeg_tools",
        "imageio", "imageio_ffmpeg",
        "soundfile", "audioread", "resampy",
        "scipy", "scipy.signal", "scipy.fft", "scipy.io",
        "sklearn", "sklearn.preprocessing",
        # 数据
        "numpy", "pandas",
        "PIL", "PIL.Image", "PIL.ImageDraw",
        # 工具
        "yt_dlp", "yt_dlp.extractor",
        "browser_cookie3",
        "dotenv",
        # 网络/异步
        "httpx", "httpcore", "anyio", "sniffio",
        "aiohttp", "asyncio",
        "tornado", "tornado.web", "tornado.websocket",
        # 序列化
        "toml", "tomli", "click", "rich",
        "protobuf", "google.protobuf",
        "packaging", "typing_extensions",
    ]
))

a = Analysis(
    ["launcher.py"],
    pathex=[SRC],
    binaries=all_binaries + ffmpeg_binaries,
    datas=all_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython", "jupyter", "notebook", "test"],
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
    strip=False,
    upx=False,
    console=False,           # 不显示黑色终端窗口
    argv_emulation=True,     # macOS 专用，处理文件关联事件
    target_arch=None,        # None=当前架构；"universal2"=同时支持Intel+M系列
    codesign_identity=None,
    icon="icon.icns" if os.path.isfile("icon.icns") else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="AutoViral AI",
)

app = BUNDLE(
    coll,
    name="AutoViral AI.app",
    icon="icon.icns" if os.path.isfile("icon.icns") else None,
    bundle_identifier="com.autoviral.ai",
    version="3.0.0",
    info_plist={
        "NSPrincipalClass":         "NSApplication",
        "NSHighResolutionCapable":  True,
        "CFBundleDisplayName":      "AutoViral AI",
        "CFBundleShortVersionString": "3.0.0",
        "CFBundleVersion":          "3.0.0",
        "NSHumanReadableCopyright": "AutoViral AI v3",
        "LSMinimumSystemVersion":   "12.0",
        # 允许访问网络（下载视频需要）
        "NSAppTransportSecurity": {
            "NSAllowsArbitraryLoads": True,
        },
    },
)
