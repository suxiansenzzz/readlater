# ReadLater - 稍后阅读

> 一个轻量级的网页内容抓取和阅读应用，支持全文抓取、离线阅读、标签管理和浏览器扩展一键保存。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688.svg)](https://fastapi.tiangolo.com/)

## ✨ 功能特性

### 📖 阅读管理
- 🔄 网页内容智能抓取（基于 trafilatura）
- 📱 响应式阅读界面
- 🌓 暗色/亮色模式切换
- 📊 阅读进度跟踪
- ⏱️ 字数统计和阅读时间估算

### 📁 内容组织
- 🏷️ 标签分类管理
- ⭐ 收藏功能
- 📦 存档功能
- 🔍 全文搜索
- 📅 多维度排序（时间、标题、字数）

### 🖼️ 图片处理
- 自动下载文章图片到本地
- 图片离线存储和显示
- 封面图自动提取

### 📝 笔记功能
- 文本高亮
- 添加笔记
- 批量操作（标记已读、收藏、删除等）

### 🌐 浏览器扩展
- 一键保存当前页面
- 右键菜单快速保存
- 快捷键 `Alt+S` 快速保存
- 标签输入
- 跨浏览器支持（Chrome/Edge/Firefox）

### 📤 数据管理
- 文章导出（Markdown、HTML、CSV）
- 数据备份和恢复
- 批量导入

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                     用户界面层                           │
├─────────────────┬─────────────────┬─────────────────────┤
│   Web 前端      │  浏览器扩展     │      API 接口        │
│  (HTML/CSS/JS)  │  (Manifest V3)  │    (RESTful)        │
└────────┬────────┴────────┬────────┴──────────┬──────────┘
         │                 │                   │
         ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────┐
│                   应用服务层                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   FastAPI    │  │  trafilatura │  │   httpx      │   │
│  │   (Web框架)  │  │  (内容提取)  │  │  (HTTP客户端) │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    数据存储层                            │
│  ┌────────────────────────────────────────────────────┐ │
│  │              SQLite + 文件系统                      │ │
│  │   readlater.db  │  images/  │  exports/           │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## 📁 项目结构

```
ReadLater/
├── backend/                  # 后端服务
│   ├── main.py              # 主程序（v0.3.0）
│   ├── main_v3.py           # 增强版（实验性）
│   └── images/              # 图片存储目录
│
├── static/                   # 前端文件
│   ├── index.html           # 主界面
│   └── index_v3.html        # 增强版界面
│
├── extension/                # 浏览器扩展
│   ├── manifest.json        # 扩展配置
│   ├── background.js        # 后台脚本
│   ├── popup/               # 弹出窗口
│   │   ├── popup.html
│   │   └── popup.js
│   └── icons/               # 图标
│
├── Dockerfile               # Docker 镜像构建
├── docker-compose.yml       # Docker Compose 配置
├── requirements.txt         # Python 依赖
│
├── build.sh                 # Docker 构建脚本
├── start.sh                 # 启动脚本
├── stop.sh                  # 停止脚本
├── package.py               # 项目打包脚本
├── package_extension.py     # 扩展打包脚本
│
├── README.md                # 项目文档
├── SETUP.md                 # 部署指南
└── DOCKER.md                # Docker 文档
```

## 🚀 快速开始

### 方式一：Docker 部署（推荐）

```bash
# 1. 解压项目
unzip ReadLater-*.zip
cd ReadLater

# 2. 一键启动
./start.sh

# 3. 访问应用
# http://localhost:8000
```

### 方式二：手动部署

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务
cd backend
python main.py

# 3. 访问应用
# http://localhost:8000
```

### 安装浏览器扩展

1. 打开浏览器扩展管理页面
   - Chrome: `chrome://extensions/`
   - Edge: `edge://extensions/`

2. 开启「开发者模式」

3. 加载扩展
   - 拖拽 `extension` 目录到页面
   - 或点击「加载已解压的扩展程序」选择 `extension` 目录

4. 配置服务器地址
   - 点击扩展图标
   - 底部输入框填写服务器地址

详细步骤请参考 [SETUP.md](SETUP.md)

## ⚙️ 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DB_PATH` | 数据库路径 | `readlater.db` |
| `IMAGES_DIR` | 图片存储目录 | `images/` |

### 服务端口

默认端口：`8000`

修改端口：
```bash
# 命令行启动时
python main.py --port 8080

# Docker 部署时修改 docker-compose.yml
ports:
  - "8080:8000"
```

## 🔌 API 接口

### 文章管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/save` | 保存文章 |
| GET | `/api/articles` | 获取文章列表 |
| GET | `/api/articles/{id}` | 获取文章详情 |
| PUT | `/api/articles/{id}` | 更新文章 |
| DELETE | `/api/articles/{id}` | 删除文章 |

### 其他接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stats` | 获取统计信息 |
| GET | `/api/tags` | 获取所有标签 |
| POST | `/api/articles/batch` | 批量操作 |
| GET | `/api/export` | 导出数据 |

### 请求示例

```bash
# 保存文章
curl -X POST http://localhost:8000/api/save \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "tags": ["技术"]}'

# 获取文章列表
curl http://localhost:8000/api/articles?page=1&per_page=20

# 获取统计信息
curl http://localhost:8000/api/stats
```

## 🐳 Docker 部署

### 构建镜像

```bash
./build.sh
```

### 运行容器

```bash
# 使用 Docker Compose
docker-compose up -d

# 或使用 Docker 命令
docker run -d \
  --name readlater \
  -p 8000:8000 \
  -v readlater_data:/data \
  readlater:latest
```

### 数据持久化

数据存储在 Docker 卷 `readlater_data` 中，包括：
- 数据库文件
- 下载的图片

详细说明请参考 [DOCKER.md](DOCKER.md)

## 🔧 浏览器打包

```bash
# 打包扩展
./package_extension.py

# 打包完整项目
./package.py
```

## 📝 开发指南

### 本地开发

```bash
# 1. 克隆项目
git clone <repo-url>
cd ReadLater

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动开发服务器
cd backend
python main.py
```

### 代码结构

- `backend/main.py` - 主要 API 逻辑
- `static/index.html` - 前端界面
- `extension/popup/popup.js` - 扩展逻辑

### 添加新功能

1. 后端：在 `main.py` 添加新的 API 路由
2. 前端：在 `index.html` 添加 UI 元素
3. 扩展：在 `popup.js` 添加新功能

## 🛠️ 技术栈

### 后端
- **Python 3.10+** - 编程语言
- **FastAPI** - Web 框架
- **SQLite** - 数据库
- **trafilatura** - 网页内容提取
- **httpx** - HTTP 客户端

### 前端
- **HTML5/CSS3** - 页面结构和样式
- **JavaScript (ES6+)** - 交互逻辑
- **Fetch API** - HTTP 请求

### 浏览器扩展
- **Manifest V3** - 扩展规范
- **Chrome Extensions API** - 浏览器接口

### 部署
- **Docker** - 容器化部署
- **Docker Compose** - 服务编排

## 📋 待办事项

- [ ] 添加用户认证
- [ ] 支持多用户
- [ ] 添加 RSS 订阅
- [ ] 移动端 App
- [ ] 文章分享功能
- [ ] 阅读统计图表
- [ ] 全文搜索优化
- [ ] 图片 OCR 识别

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 📞 联系方式

- 项目地址：GitHub
- 问题反馈：Issues

---

**ReadLater** - 让阅读更简单 📖