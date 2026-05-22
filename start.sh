#!/bin/bash
# ReadLater Docker 启动脚本

set -e

echo "🚀 启动 ReadLater..."

# 检查 Docker 是否可用
if ! command -v docker &> /dev/null; then
    echo "❌ 错误: 未安装 Docker"
    exit 1
fi

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 检查镜像是否存在
if ! docker image inspect readlater:latest &> /dev/null; then
    echo "⚠️  镜像不存在，开始构建..."
    ./build.sh
fi

# 停止并删除旧容器（如果存在）
if docker ps -a | grep -q readlater; then
    echo "🛑 停止旧容器..."
    docker stop readlater 2>/dev/null || true
    docker rm readlater 2>/dev/null || true
fi

# 启动新容器
echo "🎯 启动新容器..."
docker run -d \
    --name readlater \
    -p 8000:8000 \
    -v readlater_data:/data \
    --restart unless-stopped \
    -e TZ=Asia/Shanghai \
    readlater:latest

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 3

# 检查服务是否正常
if curl -s http://localhost:8000/api/stats &> /dev/null; then
    echo "✅ 启动成功！"
    echo ""
    echo "🌐 访问地址: http://localhost:8000"
    echo "📊 查看日志: docker logs -f readlater"
    echo "🛑 停止服务: docker stop readlater"
else
    echo "⚠️  服务可能未正常启动，请检查日志:"
    echo "   docker logs readlater"
fi