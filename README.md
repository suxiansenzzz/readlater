# 📖 ReadLater - 稍后阅读

自托管的稍后阅读应用，类似 Pocket/Wallabag。

## ✨ 功能特点

- 🔗 网页抓取 - 保存网页内容（trafilatura）
- 📱 阅读视图 - 清洁的阅读体验
- ⭐ 收藏管理 - 收藏/已读/搜索
- 📊 统计面板 - 阅读数据分析
- 🌐 浏览器扩展 - Chrome/Firefox 一键保存
- 📱 Android APP - 原生安卓客户端
- 🔍 全文搜索 - 搜索文章内容

## 🛠️ 技术栈

- **后端**: Python FastAPI + SQLite + Trafilatura
- **前端**: HTML/CSS/JavaScript
- **浏览器扩展**: Chrome Extension
- **安卓**: Kotlin Native (重构中)

## 🚀 快速开始

### 安装

```bash
git clone https://github.com/suxiansenzzz/readlater.git
cd readlater
pip install -r requirements.txt
```

### 启动

```bash
source venv/bin/activate
python backend/main.py
```

服务运行在 http://localhost:8000

### 安卓APP

[下载APK](https://github.com/suxiansenzzz/readlater/releases)

## 📡 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/articles | 添加文章 |
| GET | /api/articles | 获取文章列表 |
| GET | /api/articles/{id} | 获取单篇文章 |
| PUT | /api/articles/{id} | 更新文章 |
| DELETE | /api/articles/{id} | 删除文章 |
| POST | /api/articles/{id}/bookmark | 收藏/取消收藏 |
| GET | /api/stats | 获取统计 |
| GET | /api/search?q=xxx | 搜索文章 |

## 📄 License
MIT
