# ReadLater Docker 部署

## 文件说明

```
readlater/
├── Dockerfile           # Docker 镜像构建文件（多阶段构建）
├── docker-compose.yml   # Docker Compose 配置
├── .dockerignore        # Docker 构建忽略文件
├── deploy.sh            # 一键部署脚本
└── DOCKER_README.md     # 详细部署文档
```

## 快速部署

### 方式一：一键部署（推荐）

```bash
chmod +x deploy.sh
./deploy.sh
```

### 方式二：手动部署

```bash
# 1. 构建镜像
docker build -t readlater:latest .

# 2. 启动容器
docker run -d \
  --name readlater \
  -p 8000:8000 \
  -v readlater_data:/data \
  -e TZ=Asia/Shanghai \
  --restart unless-stopped \
  readlater:latest
```

### 方式三：Docker Compose

```bash
# 如果有 docker-compose
docker-compose up -d

# 或者新版 docker compose
docker compose up -d
```

## 访问应用

启动成功后访问: **http://localhost:8000**

## 数据持久化

数据库和图片存储在 Docker 卷 `readlater_data` 中：
- **数据库**: `/data/readlater.db`
- **图片**: `/data/images/`

容器重启数据不会丢失。

### 备份

```bash
# 备份数据库
docker cp readlater:/data/readlater.db ./backup/
# 备份图片
docker cp readlater:/data/images/ ./backup/images/
```

### 恢复

```bash
docker cp ./backup/readlater.db readlater:/data/
docker cp ./backup/images/ readlater:/data/
```

## 常用命令

```bash
# 查看日志
docker logs -f readlater

# 停止服务
docker stop readlater

# 重启服务
docker restart readlater

# 进入容器
docker exec -it readlater bash

# 删除容器
docker rm -f readlater

# 删除镜像
docker rmi readlater:latest
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TZ` | `Asia/Shanghai` | 时区 |
| `DB_PATH` | `/data/readlater.db` | 数据库路径 |
| `IMAGES_DIR` | `/data/images` | 图片存储目录 |

## 修改端口

```bash
# 映射到 9000 端口
docker run -d --name readlater -p 9000:8000 -v readlater_data:/data readlater:latest
```

## 更新应用

```bash
docker stop readlater && docker rm readlater
docker build -t readlater:latest .
docker run -d --name readlater -p 8000:8000 -v readlater_data:/data --restart unless-stopped readlater:latest
```

## 故障排查

```bash
# 查看容器日志
docker logs readlater

# 检查容器状态
docker ps -a | grep readlater

# 进入容器排查
docker exec -it readlater bash
ls -la /data/
```
