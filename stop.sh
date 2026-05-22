#!/bin/bash
# ReadLater Docker 停止脚本

echo "🛑 停止 ReadLater..."

# 检查 Docker 是否可用
if ! command -v docker &> /dev/null; then
    echo "❌ 错误: 未安装 Docker"
    exit 1
fi

# 停止并删除容器
if docker ps -a | grep -q readlater; then
    docker stop readlater 2>/dev/null && echo "✅ 已停止容器"
    docker rm readlater 2>/dev/null && echo "✅ 已删除容器"
else
    echo "ℹ️  容器不存在"
fi

echo ""
echo "💡 提示: 数据卷未删除，数据已保留"
echo "   如需删除数据: docker volume rm readlater_data"