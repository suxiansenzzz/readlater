# 📖 ReadLater - 稍后阅读

自托管的稍后阅读应用，类似 Pocket / Wallabag，支持网页端、浏览器扩展和原生 Android 客户端。

## ✨ 功能特点

### 🖥️ 服务端
- 🔗 **网页抓取** - 基于 Trafilatura 的智能内容提取
- 📱 **阅读视图** - 清洁舒适的阅读体验
- ⭐ **收藏管理** - 收藏/已读/归档/标签
- 📊 **统计面板** - 阅读数据分析
- 🔍 **全文搜索** - 搜索文章标题和内容
- 📤 **批量导入** - 支持批量操作
- 🖼️ **图片提取** - 自动提取文章配图

### 🌐 浏览器扩展
- 一键保存当前网页
- 自动提取标题和 URL
- Toast 通知反馈（保存中/成功/失败）

### 📱 Android 原生 APP (v2.0.0)
- **全新原生 UI** - Jetpack Compose + Material Design 3
- **文章列表** - 卡片式布局，显示封面图/阅读时长/字数
- **智能筛选** - 全部/未读/收藏/归档
- **文章详情** - HTML 渲染 + 收藏/已读/删除操作
- **服务器配置** - 设置页面可随时修改服务器地址
- **深色模式** - 跟随系统自动切换
- **下拉刷新** - 手势操作刷新文章列表

## 🛠️ 技术栈

| 组件 | 技术 |
|------|------|
| **后端** | Python FastAPI + SQLite + Trafilatura |
| **前端** | HTML / CSS / JavaScript |
| **浏览器扩展** | Chrome Extension (Manifest V3) |
| **Android APP** | Kotlin + Jetpack Compose + Material 3 |
| **网络层** | Retrofit + Moshi + OkHttp |
| **本地存储** | SharedPreferences |

## 📁 项目结构

```
readlater/
├── backend/                # 后端服务
│   ├── main.py            # 主程序入口
│   └── ...
├── frontend/              # 前端页面
├── extension/             # 浏览器扩展
├── android/               # 旧版 Android APP (WebView)
├── android-native/        # 原生 Android APP (Compose) ✨ 新版
│   ├── app/
│   │   └── src/main/java/com/readlater/app/
│   │       ├── MainActivity.kt          # 主入口
│   │       ├── ReadLaterApp.kt          # Application 类
│   │       ├── data/
│   │       │   ├── api/                 # Retrofit API
│   │       │   └── model/               # 数据模型
│   │       ├── viewmodel/               # ViewModel
│   │       ├── ui/
│   │       │   ├── theme/               # 主题/颜色
│   │       │   └── screens/             # 页面组件
│   │       └── util/                    # 工具类
│   └── build.gradle
├── ugapp/                 # 绿联 NAS 应用
└── README.md
```

## 🚀 快速开始

### 服务端安装

```bash
git clone https://github.com/suxiansenzzz/readlater.git
cd readlater

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动服务
python backend/main.py
```

服务运行在 `http://localhost:8000`

### Android APP

1. 从 [Releases](https://github.com/suxiansenzzz/readlater/releases) 下载 APK
2. 安装到手机
3. 打开 APP → 点击右上角 ⚙️ 设置
4. 输入服务器地址（如 `http://192.168.31.5:8000`）
5. 保存后即可使用

### 浏览器扩展

1. 打开 Chrome → `chrome://extensions/`
2. 开启「开发者模式」
3. 点击「加载已解压的扩展程序」
4. 选择 `extension/` 目录

## 📡 API 接口

### 文章管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/save` | 保存文章（传入 URL） |
| `GET` | `/api/articles` | 获取文章列表（支持分页、筛选） |
| `GET` | `/api/articles/{id}` | 获取单篇文章详情 |
| `PUT` | `/api/articles/{id}` | 更新文章（已读/收藏/归档） |
| `DELETE` | `/api/articles/{id}` | 删除文章 |
| `POST` | `/api/articles/batch` | 批量操作 |

### 统计和搜索

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/stats` | 获取统计数据 |
| `GET` | `/api/search?q=xxx` | 全文搜索 |
| `GET` | `/api/tags` | 获取所有标签 |

### 请求示例

```bash
# 保存文章
curl -X POST http://localhost:8000/api/save \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article"}'

# 获取文章列表
curl http://localhost:8000/api/articles?page=1&per_page=20&is_read=false

# 标记为已读
curl -X PUT http://localhost:8000/api/articles/1 \
  -H "Content-Type: application/json" \
  -d '{"is_read": true}'
```

## 🔧 开发指南

### Android 原生 APP 开发环境

```bash
# 前置要求
# - JDK 17
# - Android SDK (API 34)
# - Gradle 8.5+

# 设置环境
export JAVA_HOME=/opt/jdk-17.0.2
export ANDROID_HOME=/opt/android-sdk

# 编译
cd android-native
./gradlew assembleDebug

# APK 输出位置
# android-native/app/build/outputs/apk/debug/app-debug.apk
```

### 架构说明

Android APP 采用 MVVM 架构：

- **MainActivity** - Compose 入口，管理导航状态
- **MainViewModel** - 状态管理，API 调用
- **RetrofitClient** - 网络层，可动态切换服务器地址
- **PrefsManager** - SharedPreferences 封装

## 📦 部署

### Docker 部署

```bash
docker build -t readlater .
docker run -p 8000:8000 -v ./data:/app/data readlater
```

### 绿联 NAS 部署

详见 [ugapp/README.md](ugapp/README.md)

## 📋 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| **v2.0.0** | 2026-06-25 | 🎉 Android 原生重写（Compose + Material 3） |
| v1.0.3 | 2026-05-30 | 闪屏修复 |
| v1.0.2 | 2026-05-28 | 批注功能 |
| v1.0.0 | 2026-05-23 | 初始版本 |

## 📄 License

MIT

## 🙏 致谢

- [Trafilatura](https://github.com/adbar/trafilatura) - 网页内容提取
- [FastAPI](https://fastapi.tiangolo.com/) - Web 框架
- [Jetpack Compose](https://developer.android.com/jetpack/compose) - Android UI 框架
- [Material Design 3](https://m3.material.io/) - 设计系统
