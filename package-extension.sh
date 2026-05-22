#!/bin/bash
# ReadLater 浏览器扩展打包脚本

set -e

echo "📦 打包 ReadLater 浏览器扩展..."

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 创建输出目录
mkdir -p dist

# 打包为 zip 文件（用于 Chrome 和 Edge）
echo "📦 打包 Chrome/Edge 扩展..."
cd extension
zip -r ../dist/readlater-extension.zip . -x "*.git*" -x "*__pycache__*" -x "*.DS_Store"
cd ..

echo "✅ 打包完成！"
echo ""
echo "📁 输出文件："
echo "  - dist/readlater-extension.zip (Chrome/Edge)"
echo ""
echo "📖 安装方法："
echo ""
echo "  Chrome/Edge:"
echo "    1. 打开 chrome://extensions/ 或 edge://extensions/"
echo "    2. 开启「开发者模式」"
echo "    3. 将 zip 文件拖入页面"
echo "    4. 或点击「加载已解压的扩展程序」选择 extension 目录"
echo ""
echo "  Firefox:"
echo "    1. 打开 about:debugging#/runtime/this-firefox"
echo "    2. 点击「临时加载附加组件」"
echo "    3. 选择 extension 目录中的 manifest.json"