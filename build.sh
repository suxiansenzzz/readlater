#!/bin/bash
# ReadLater Docker 构建脚本

set -e

echo "🚀 开始构建 ReadLater Docker 镜像..."

# 检查 Docker 是否可用
if ! command -v docker &> /dev/null; then
    echo "❌ 错误: 未安装 Docker"
    echo "请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查 Docker 守护进程是否运行
if ! docker info &> /dev/null; then
    echo "❌ 错误: Docker 守护进程未运行"
    echo "请启动 Docker 服务"
    exit 1
fi

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 构建镜像
echo "📦 构建 Docker 镜像..."
docker build -t readlater:latest .

# 检查构建结果
if [ $? -eq 0 ]; then
    echo "✅ 构建成功！"
    echo ""
    echo "📖 使用方法："
    echo ""
    echo "  方式一：Docker Compose（推荐）"
    echo "    docker-compose up -d"
    echo ""
    echo "  方式二：Docker 命令"
    echo "    docker run -d \\"
    echo "      --name readlater \\"
    echo "      -p 8000:8000 \\"
    echo "      -v readlater_data:/data \\"
    echo "      readlater:latest"
    echo ""
    echo "🌐 启动后访问: http://localhost:8000"
else
    echo "❌ 构建失败"
    exit 1
fi