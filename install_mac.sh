#!/usr/bin/env bash
# =============================================================================
#  AutoViral AI - macOS 一键安装脚本（无需打包，直接安装运行环境）
#
#  此脚本更简单：不生成 .app，而是在用户 Mac 上安装好运行环境
#  并创建一个双击即可启动的 .command 启动器放到桌面
#
#  适合场景：向其他 Mac 用户分发整个项目目录时使用
#
#  使用方法（在 Mac 上）：
#    chmod +x install_mac.sh
#    ./install_mac.sh
# =============================================================================

set -e

APP_NAME="AutoViral AI"
APP_DIR="$HOME/Applications/AutoViral_AI"
VENV_DIR="${APP_DIR}/.venv"
DESKTOP="$HOME/Desktop"

# 颜色
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}►${NC} $*"; }
success() { echo -e "${GREEN}✓${NC} $*"; }
warn()    { echo -e "${YELLOW}!${NC} $*"; }
error()   { echo -e "${RED}✗ 错误:${NC} $*"; exit 1; }

clear
echo ""
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║    AutoViral AI v3 — macOS 安装程序        ║"
echo "  ║    汽车爆款视频分析 · KOC 人设引擎           ║"
echo "  ╚═══════════════════════════════════════════╝"
echo ""

# ── 1. 检查 macOS ────────────────────────────────────────────────────────────
[[ "$(uname)" == "Darwin" ]] || error "此安装脚本只支持 macOS"
info "macOS 版本：$(sw_vers -productVersion)"

# ── 2. 检查/安装 Homebrew ────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
    info "安装 Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Apple Silicon 路径
    [[ -f /opt/homebrew/bin/brew ]] && eval "$(/opt/homebrew/bin/brew shellenv)"
fi
success "Homebrew 已就绪"

# ── 3. 检查/安装 Python 3.11 ─────────────────────────────────────────────────
if ! command -v python3.11 &>/dev/null; then
    info "安装 Python 3.11..."
    brew install python@3.11
fi
PYTHON_BIN=$(command -v python3.11)
success "Python: $($PYTHON_BIN --version)"

# ── 4. 检查 ffmpeg（moviepy 需要）────────────────────────────────────────────
if ! command -v ffmpeg &>/dev/null; then
    info "安装 ffmpeg..."
    brew install ffmpeg
fi
success "ffmpeg 已就绪"

# ── 5. 创建安装目录，复制项目文件 ────────────────────────────────────────────
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
info "复制应用文件到：${APP_DIR}"
mkdir -p "$APP_DIR"
rsync -av --exclude='.venv*' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='.git' --exclude='build' --exclude='dist' \
    "${SRC_DIR}/" "${APP_DIR}/" >/dev/null
success "文件复制完成"

# ── 6. 创建 Python 虚拟环境 ──────────────────────────────────────────────────
info "创建 Python 虚拟环境..."
"$PYTHON_BIN" -m venv "$VENV_DIR"
source "${VENV_DIR}/bin/activate"
pip install --upgrade pip -q
success "虚拟环境创建完成"

# ── 7. 安装 Python 依赖 ──────────────────────────────────────────────────────
info "安装 Python 依赖包（首次安装约需 3~5 分钟）..."
pip install -r "${APP_DIR}/requirements.txt" -q
success "依赖安装完成"

# ── 8. 可选：安装 Whisper（语音转文字）──────────────────────────────────────
echo ""
read -rp "  是否安装 Whisper 语音识别？（增强台词分析，需额外下载 ~150MB）[y/N] " INSTALL_WHISPER
if [[ "${INSTALL_WHISPER,,}" == "y" ]]; then
    info "安装 openai-whisper..."
    pip install openai-whisper -q
    success "Whisper 安装完成"
fi

# ── 9. 可选：安装 EasyOCR（字幕识别）───────────────────────────────────────
read -rp "  是否安装 EasyOCR 文字识别？（识别视频字幕，需额外下载 ~200MB）[y/N] " INSTALL_OCR
if [[ "${INSTALL_OCR,,}" == "y" ]]; then
    info "安装 easyocr..."
    pip install easyocr -q
    success "EasyOCR 安装完成"
fi
echo ""

deactivate

# ── 10. 创建桌面启动器 .command ───────────────────────────────────────────────
LAUNCHER="${DESKTOP}/AutoViral AI.command"
info "创建桌面启动器：${LAUNCHER}"

cat > "$LAUNCHER" <<LAUNCHER_EOF
#!/usr/bin/env bash
# AutoViral AI - 启动器
# 双击此文件即可启动应用

APP_DIR="${APP_DIR}"
VENV_DIR="${VENV_DIR}"

# 激活虚拟环境
source "\${VENV_DIR}/bin/activate"

# 切换到应用目录
cd "\${APP_DIR}"

echo ""
echo "  启动 AutoViral AI..."
echo "  浏览器将自动打开 http://localhost:8501"
echo "  关闭此终端窗口即可停止应用"
echo ""

# 延迟打开浏览器
(sleep 2.5 && open "http://localhost:8501") &

# 启动 Streamlit
streamlit run app.py \\
    --server.headless true \\
    --browser.gatherUsageStats false \\
    --server.port 8501
LAUNCHER_EOF

chmod +x "$LAUNCHER"
success "桌面启动器创建完成"

# ── 11. 创建应用目录快捷方式 ─────────────────────────────────────────────────
APP_SHORTCUT="${DESKTOP}/AutoViral AI 文件夹.command"
cat > "$APP_SHORTCUT" <<SHORTCUT_EOF
#!/usr/bin/env bash
open "${APP_DIR}"
SHORTCUT_EOF
chmod +x "$APP_SHORTCUT"

# ── 12. 完成提示 ─────────────────────────────────────────────────────────────
echo ""
echo "  ╔═══════════════════════════════════════════════════════╗"
echo "  ║                 🎉  安装成功！                         ║"
echo "  ╠═══════════════════════════════════════════════════════╣"
echo "  ║  启动方式：                                            ║"
echo "  ║    双击桌面上的「AutoViral AI.command」               ║"
echo "  ║    （首次打开需右键→打开，允许执行）                  ║"
echo "  ╠═══════════════════════════════════════════════════════╣"
echo "  ║  应用目录：                                            ║"
printf "  ║    %-52s║\n" "${APP_DIR}"
echo "  ║  报告保存位置：                                        ║"
printf "  ║    %-52s║\n" "${APP_DIR}/reports/"
echo "  ╚═══════════════════════════════════════════════════════╝"
echo ""
echo "  提示：如需卸载，删除以下内容即可："
echo "    - ${APP_DIR}"
echo "    - 桌面上的 AutoViral AI 相关文件"
echo ""
