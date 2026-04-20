#!/usr/bin/env bash
# =============================================================================
#  AutoViral AI - macOS 打包脚本
#  生成物：dist/AutoViral AI.app  +  AutoViral_AI_v3.dmg
#
#  前置要求（在 Mac 上运行）：
#    - macOS 12+（Monterey 及以上）
#    - Python 3.10 或 3.11（推荐 3.11）
#    - Xcode Command Line Tools：xcode-select --install
#    - Homebrew（用于安装 create-dmg）：https://brew.sh
#
#  使用方法：
#    chmod +x build_mac.sh
#    ./build_mac.sh
# =============================================================================

set -e  # 任何命令失败立即退出

# ── 配置 ────────────────────────────────────────────────────────────────────
APP_NAME="AutoViral AI"
APP_VERSION="3.0.0"
DMG_NAME="AutoViral_AI_v${APP_VERSION}"
PYTHON_MIN="3.10"
VENV_DIR=".venv_build"

# 颜色输出
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║       AutoViral AI v3 — macOS 打包工具               ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── 1. 检查系统环境 ──────────────────────────────────────────────────────────
info "检查系统环境..."

# 检查 macOS
[[ "$(uname)" == "Darwin" ]] || error "此脚本只能在 macOS 上运行"

# 检查 Python 版本
PYTHON_BIN=""
for bin in python3.11 python3.10 python3; do
    if command -v "$bin" &>/dev/null; then
        # 版本比较：需要 >= 3.10
        if "$bin" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
            PYTHON_BIN="$bin"
            break
        fi
    fi
done
[[ -n "$PYTHON_BIN" ]] || error "未找到 Python ${PYTHON_MIN}+，请先安装：https://www.python.org/downloads/"
success "使用 Python: $($PYTHON_BIN --version)"

# ── 2. 创建构建虚拟环境 ──────────────────────────────────────────────────────
info "创建构建虚拟环境 (${VENV_DIR})..."
if [[ -d "$VENV_DIR" ]]; then
    warn "已存在 ${VENV_DIR}，删除重建..."
    rm -rf "$VENV_DIR"
fi
"$PYTHON_BIN" -m venv "$VENV_DIR"
source "${VENV_DIR}/bin/activate"
pip install --upgrade pip setuptools wheel -q
success "虚拟环境就绪"

# ── 3. 安装项目依赖 ──────────────────────────────────────────────────────────
info "安装项目依赖（requirements.txt）..."
pip install -r requirements.txt -q
success "项目依赖安装完成"

# ── 4. 安装打包工具 ──────────────────────────────────────────────────────────
info "安装 PyInstaller..."
pip install "pyinstaller>=6.0" -q
success "PyInstaller 安装完成"

# ── 5. 生成应用图标（如果没有 .icns）───────────────────────────────────────
if [[ ! -f "icon.icns" ]]; then
    info "未找到 icon.icns，尝试自动生成占位图标..."
    if command -v sips &>/dev/null && command -v iconutil &>/dev/null; then
        # 创建一个简单的 PNG 占位图标
        ICONSET_DIR="AutoViral.iconset"
        mkdir -p "$ICONSET_DIR"
        # 使用 Python 生成一个简单的图标
        python3 - <<'PYEOF'
try:
    from PIL import Image, ImageDraw, ImageFont
    sizes = [16,32,64,128,256,512,1024]
    for s in sizes:
        img = Image.new('RGBA', (s, s), (0, 120, 212, 255))
        d = ImageDraw.Draw(img)
        font_size = max(s // 3, 8)
        d.text((s//4, s//3), "AV", fill=(255,255,255,255))
        img.save(f'AutoViral.iconset/icon_{s}x{s}.png')
        if s <= 512:
            img2 = img.resize((s*2, s*2), Image.LANCZOS)
            img2.save(f'AutoViral.iconset/icon_{s}x{s}@2x.png')
    print("图标生成成功")
except Exception as e:
    print(f"跳过图标生成: {e}")
PYEOF
        if ls "$ICONSET_DIR"/*.png 1>/dev/null 2>&1; then
            iconutil -c icns "$ICONSET_DIR" -o icon.icns 2>/dev/null && success "图标生成完成" || warn "图标生成失败，将使用默认图标"
        fi
        rm -rf "$ICONSET_DIR"
    else
        warn "跳过图标生成（sips/iconutil 不可用）"
    fi
fi

# ── 6. 清理旧构建 ────────────────────────────────────────────────────────────
info "清理旧构建文件..."
rm -rf build dist __pycache__
success "清理完成"

# ── 7. 执行 PyInstaller 打包 ─────────────────────────────────────────────────
info "开始 PyInstaller 打包（这可能需要 5~15 分钟）..."
pyinstaller AutoViral.spec \
    --clean \
    --noconfirm \
    --log-level WARN

APP_PATH="dist/${APP_NAME}.app"
[[ -d "$APP_PATH" ]] || error "打包失败：找不到 ${APP_PATH}"
success "打包完成：${APP_PATH}"

# ── 8. 签名（如果有开发者证书）──────────────────────────────────────────────
if security find-identity -v -p codesigning 2>/dev/null | grep -q "Developer ID Application"; then
    CERT=$(security find-identity -v -p codesigning | grep "Developer ID Application" | head -1 | awk -F'"' '{print $2}')
    info "使用证书签名：${CERT}"
    codesign --deep --force --verify --verbose \
        --sign "$CERT" \
        --options runtime \
        "$APP_PATH" && success "签名完成" || warn "签名失败，App 仍可使用但会有 Gatekeeper 警告"
else
    warn "未找到 Developer ID 证书，跳过签名（用户需要在首次运行时右键→打开）"
fi

# ── 9. 创建 DMG 安装包 ───────────────────────────────────────────────────────
info "创建 DMG 安装包..."

# 安装 create-dmg（如果有 Homebrew）
if command -v brew &>/dev/null; then
    brew list create-dmg &>/dev/null || brew install create-dmg -q
fi

DMG_PATH="${DMG_NAME}.dmg"

if command -v create-dmg &>/dev/null; then
    # 使用 create-dmg 创建漂亮的 DMG
    create-dmg \
        --volname "${APP_NAME}" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "${APP_NAME}.app" 175 190 \
        --hide-extension "${APP_NAME}.app" \
        --app-drop-link 425 190 \
        --no-internet-enable \
        "${DMG_PATH}" \
        "dist/" \
    && success "DMG 创建完成：${DMG_PATH}" \
    || warn "create-dmg 失败，尝试使用 hdiutil..."
fi

# 回退：使用系统自带 hdiutil
if [[ ! -f "$DMG_PATH" ]]; then
    info "使用 hdiutil 创建 DMG..."
    hdiutil create \
        -volname "${APP_NAME}" \
        -srcfolder "dist/" \
        -ov \
        -format UDZO \
        "${DMG_PATH}" \
    && success "DMG 创建完成：${DMG_PATH}" \
    || error "DMG 创建失败"
fi

# ── 10. 退出虚拟环境，输出结果 ───────────────────────────────────────────────
deactivate

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    🎉  打包成功！                             ║"
echo "╠══════════════════════════════════════════════════════════════╣"
printf "║  .app 应用：  %-47s║\n" "dist/${APP_NAME}.app"
printf "║  DMG 安装包： %-47s║\n" "${DMG_PATH}"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  安装方法：                                                   ║"
echo "║    双击 DMG → 将 AutoViral AI 拖入 Applications 文件夹       ║"
echo "║  首次运行（未签名）：                                         ║"
echo "║    右键点击 App → 选择「打开」→ 确认打开                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
