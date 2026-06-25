#!/bin/bash
# ReadLater Android APP 打包脚本
# 将项目打包成zip文件，方便用户下载和构建

echo "=========================================="
echo "ReadLater Android APP 打包工具"
echo "=========================================="

# 检查当前目录
if [ ! -d "app" ]; then
    echo "❌ 错误: 请在 android 目录下运行此脚本"
    exit 1
fi

# 创建输出目录
OUTPUT_DIR="/opt/data/workspace/readlater/dist"
mkdir -p "$OUTPUT_DIR"

# 打包项目
echo "📦 正在打包项目..."
cd /opt/data/workspace/readlater
zip -r "$OUTPUT_DIR/readlater-android.zip" android/ -x "android/.gradle/*" "android/app/build/*" "android/build/*"

if [ $? -eq 0 ]; then
    echo "✅ 打包成功！"
    echo "📁 文件位置: $OUTPUT_DIR/readlater-android.zip"
    ls -lh "$OUTPUT_DIR/readlater-android.zip"
else
    echo "❌ 打包失败"
    exit 1
fi

echo ""
echo "=========================================="
echo "打包完成！"
echo "=========================================="
echo ""
echo "📥 下载文件: $OUTPUT_DIR/readlater-android.zip"
echo ""
echo "📋 用户构建说明:"
echo "1. 解压 readlater-android.zip"
echo "2. 安装 Java JDK 17+ (https://adoptium.net/)"
echo "3. 安装 Android Studio (https://developer.android.com/studio)"
echo "4. 用 Android Studio 打开 android 目录"
echo "5. 等待 Gradle 同步完成"
echo "6. 菜单: Build → Build Bundle(s) / APK(s) → Build APK(s)"
echo ""
echo "或者使用命令行:"
echo "cd android"
echo "./gradlew assembleRelease"
echo ""
