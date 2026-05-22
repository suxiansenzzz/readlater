#!/bin/bash
# ReadLater 安装后脚本

APP_DIR="$1"
DATA_DIR="$2"

echo "正在初始化 ReadLater..."

# 确保Python3可用
if ! command -v python3 &> /dev/null; then
    echo "错误：需要Python3环境"
    exit 1
fi

# 安装依赖
if [ -f "$APP_DIR/requirements.txt" ]; then
    pip3 install -r "$APP_DIR/requirements.txt" -q
fi

# 创建数据目录
mkdir -p "$DATA_DIR"

# 复制数据库（如果不存在）
if [ ! -f "$DATA_DIR/readlater.db" ]; then
    touch "$DATA_DIR/readlater.db"
fi

echo "ReadLater 安装完成！"
