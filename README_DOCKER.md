# ReadLater Docker 部署

## 文件说明

```
readlater/
├── Dockerfile           # Docker 镜像构建文件
├── docker-compose.yml   # Docker Compose 配置
├── .dockerignore        # Docker 构建忽略文件
├── build.sh             # 构建脚本
├── start.sh             # 启动脚本
├── stop.sh              # 停止脚本
└── DOCKER.md            # 详细文档
```

## 快速部署

### 方式一：一键启动（推荐）

```bash
./start.sh
```

脚本会自动：
1. 检查 Docker 环境
2. 构建镜像（如果不存在）
3. 启动容器
4. 检查服务状态

### 方式二：手动操作

```bash
# 1. 构建镜像
./build.sh

# 2. 启动容器
docker-compose up -d

# 或使用 Docker 命令
docker run -d \
  --name readlater \
  -p 8000:8000 \
  -v readlater_data:/data \
  readlater:latest
```

### 方式三：绿联NAS部署

1. 在电脑上构建镜像：
   ```bash
   ./build.sh
   ```

2. 导出镜像：
   ```bash
   docker save readlater:latest | gzip > readlater.tar.gz
   ```

3. 在绿联NAS上导入镜像并运行

## 常用命令

```bash
# 查看日志
docker logs -f readlater

# 重启服务
docker restart readlater

# 停止服务
./stop.sh

# 进入容器
docker exec -it readlater /bin/bash

# 备份数据
docker cp readlater:/data/readlater.db ./backup/
docker cp readlater:/data/images ./backup/

# 恢复数据
docker cp ./backup/readlater.db readlater:/data/
docker cp ./backup/images readlater:/data/
```

## 访问

启动后访问: http://localhost:8000

## 浏览器扩展配置

扩展默认服务器地址：`http://192.168.31.5:8000`

如果部署在其他地址，请在扩展设置中修改。