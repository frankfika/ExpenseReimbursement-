#!/bin/bash
# 报销助手 - macOS 打包脚本

set -e

# 获取脚本所在目录的父目录（项目根目录）
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."

echo "===================================="
echo "报销助手 - macOS 打包工具"
echo "===================================="
echo ""

# 读取版本号
VERSION=$(cat VERSION)
VERSION_TAG="v${VERSION}"

echo "版本: ${VERSION_TAG}"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 Python3，请先安装 Python 3.9+"
    exit 1
fi

echo "[1/5] 安装依赖..."
python3 -m pip install -r requirements.txt -q --user 2>/dev/null || true

echo ""
echo "[2/5] 清理旧的构建文件..."
rm -rf build/build
rm -rf dist

echo ""
echo "[3/5] 开始打包..."
python3 -m PyInstaller --clean build/build_mac.spec

echo ""
if [ -d "dist/ExpenseHelper.app" ]; then
    echo "[4/5] 打包成功！创建 DMG..."

    APP_NAME="ExpenseHelper"
    DMG_NAME="ExpenseHelper-${VERSION}"
    TEMP_DIR="dist/dmg_temp"
    RELEASE_DIR="releases/${VERSION_TAG}"

    # 清理并创建临时目录
    rm -rf "$TEMP_DIR"
    mkdir -p "$TEMP_DIR"

    # 复制 .app 到临时目录
    cp -R "dist/${APP_NAME}.app" "$TEMP_DIR/"

    # 创建 Applications 链接
    ln -s /Applications "$TEMP_DIR/Applications"

    # 创建 DMG
    rm -f "dist/${DMG_NAME}.dmg"
    hdiutil create -volname "$APP_NAME" \
        -srcfolder "$TEMP_DIR" \
        -ov -format UDZO \
        -imagekey zlib-level=9 \
        "dist/${DMG_NAME}.dmg"

    # 清理临时目录
    rm -rf "$TEMP_DIR"

    # 创建 releases 目录并复制
    echo ""
    echo "[5/5] 复制到 releases 目录..."
    mkdir -p "$RELEASE_DIR"
    cp "dist/${DMG_NAME}.dmg" "${RELEASE_DIR}/"
    SIZE=$(du -h "${RELEASE_DIR}/${DMG_NAME}.dmg" | cut -f1)

    echo ""
    echo "===================================="
    echo "完成！"
    echo "===================================="
    echo ""
    echo "版本: ${VERSION_TAG}"
    echo "DMG:  ${RELEASE_DIR}/${DMG_NAME}.dmg (${SIZE})"
    echo ""
    echo "如需发布到 GitHub，运行:"
    echo "  gh release create ${VERSION_TAG} ${RELEASE_DIR}/*.dmg"
else
    echo "[错误] 打包失败，请检查错误信息"
    exit 1
fi

echo ""
