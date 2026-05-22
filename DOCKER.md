# ReadLater Docker 部署指南

## 快速开始

### 方式一：使用 Docker Compose（推荐）

```bash
# 克隆项目
git clone <your-repo-url>
cd readlater

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 方式二：使用 Docker 命令

```bash
# 构建镜像
docker build -t readlater:latest .

# 运行容器
docker run -d \
  --name readlater \
  -p 8000:8000 \
  -v readlater_data:/data \
  --restart unless-stopped \
  readlater:latest

# 查看日志
docker logs -f readlater

# 停止容器
docker stop readlater

# 删除容器
docker rm readlater
```

## 访问应用

启动后，访问 http://localhost:8000 即可使用。

## 数据持久化

应用数据存储在 `/data` 目录中，包括：
- `readlater.db` - SQLite 数据库
- `images/` - 下载的图片

使用 Docker 卷 `readlater_data` 进行数据持久化。

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| DB_PATH | 数据库路径 | /data/readlater.db |
| IMAGES_DIR | 图片存储目录 | /data/images |
| TZ | 时区 | Asia/Shanghai |

## 更新应用

```bash
# 拉取最新代码
git pull

# 重新构建并启动
docker-compose up -d --build
```

## 备份数据

```bash
# 备份数据库
docker cp readlater:/data/readlater.db ./backup/

# 备份图片
docker cp readlater:/data/images ./backup/
```

## 浏览器扩展配置

浏览器扩展默认连接 `http://192.168.31.5:8000`，如果部署在其他地址，请在扩展设置中修改服务器地址。