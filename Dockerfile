# ReadLater - 稍后阅读应用
# 多阶段构建，减小镜像体积

# 构建阶段
FROM python:3.11-slim as builder

WORKDIR /build

# 安装系统依赖（用于编译Python包）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# 运行阶段
FROM python:3.11-slim

WORKDIR /app

# 安装运行时系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制已安装的依赖
COPY --from=builder /install /usr/local

# 复制应用代码
COPY backend/ ./backend/
COPY static/ ./static/

# 创建必要的目录
RUN mkdir -p /app/backend/images /data /data/images

# 设置环境变量
ENV DB_PATH=/data/readlater.db
ENV IMAGES_DIR=/data/images
ENV PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/stats || exit 1

# 启动应用
CMD ["python", "backend/main.py"]
