# ReadLater - 稍后阅读

一个轻量级的网页内容抓取和阅读应用，支持全文抓取、离线阅读、标签管理和浏览器扩展一键保存。

## 技术栈

- 后端：Python FastAPI
- 前端：原生 HTML/CSS/JavaScript
- 数据库：SQLite
- 浏览器扩展：Manifest V3

## 快速开始

### Docker 部署（推荐）

```bash
./start.sh
```

### 手动部署

```bash
pip install -r requirements.txt
cd backend
python main.py
```

### 安装浏览器扩展

1. 打开 `chrome://extensions/`
2. 开启「开发者模式」
3. 拖拽 `extension` 目录到页面
4. 配置服务器地址

## 版本历史

- v1.0.0 (2026-05-23): 初始版本
  - 文章抓取和保存
  - 标签管理
  - 已读/收藏/存档
  - 浏览器扩展
  - Docker 部署支持

## 许可证

MIT