# 📋 更新日志 (Changelog)

## v2.0.1 (2026-06-25)

### 🐛 Bug Fixes
- 修复白屏问题：ComponentActivity 改为 AppCompatActivity 兼容 AppCompat 主题

## v2.0.0 (2026-06-25)

### 🎉 重大更新
- **全面重写为原生 Android UI**，彻底抛弃 WebView
- 使用 Jetpack Compose + Material Design 3

### ✨ 新增功能
- 原生文章列表（卡片式布局，封面图/阅读时长/字数）
- 文章详情页（HTML 渲染 + 收藏/已读/删除操作）
- 智能筛选（全部/未读/收藏/归档）
- 保存文章对话框
- ⚙️ 设置页面 — 可配置服务器地址
- 深色模式支持
- 下拉刷新
- 分页加载

### 🔧 技术改进
- MVVM 架构（ViewModel + StateFlow）
- Retrofit + Moshi 网络层
- Coil 图片加载
- SharedPreferences 本地存储
- 默认服务器地址：http://192.168.31.5:8000

## v1.0.3 (2026-05-30)

### 🐛 Bug Fixes
- 修复闪屏问题

## v1.0.2 (2026-05-28)

### ✨ 新增功能
- 批注功能（高亮/笔记）

## v1.0.0 (2026-05-23)

### 🎉 首次发布
- 基于 WebView 的 Android 客户端
- 文章列表和阅读视图
- 收藏/已读管理
- 服务器地址配置
