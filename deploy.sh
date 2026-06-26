#!/bin/bash
# ReadLater Docker 一键部署脚本
# 用法: ./deploy.sh

set -e

echo "🚀 ReadLater Docker 部署脚本"
echo "=============================="

# 检查Docker
if ! command -v docker &> /dev/null; then
    echo "❌ 未安装Docker，请先安装"
    exit 1
fi

# 检查docker compose（V2）或 docker-compose（V1）
COMPOSE_CMD=""
if docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "⚠️  未安装Docker Compose，将使用docker run方式启动"
    echo ""
    echo "🔨 构建镜像..."
    docker build -t readlater:latest .
    echo ""
    echo "🚀 启动服务..."
    docker run -d \
        --name readlater \
        -p 8000:8000 \
        -v readlater_data:/data \
        -e TZ=Asia/Shanghai \
        -e DB_PATH=/data/readlater.db \
        -e IMAGES_DIR=/data/images \
        --restart unless-stopped \
        readlater:latest
    echo ""
    echo "✅ ReadLater 已启动！访问: http://localhost:8000"
    exit 0
fi

echo "📦 使用 $COMPOSE_CMD 构建..."
$COMPOSE_CMD build

echo "🚀 启动服务..."
$COMPOSE_CMD up -d

echo "⏳ 等待服务启动..."
sleep 5

if docker ps | grep -q readlater; then
    echo ""
    echo "✅ ReadLater 部署成功！"
    echo "   访问地址: http://localhost:8000"
    echo ""
    echo "📋 常用命令:"
    echo "   查看日志: $COMPOSE_CMD logs -f"
    echo "   停止服务: $COMPOSE_CMD down"
    echo "   重启服务: $COMPOSE_CMD restart"
else
    echo "❌ 启动失败，请查看日志:"
    docker logs readlater
fi
