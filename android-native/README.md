# 📱 ReadLater Android 原生 APP

> 稍后阅读的原生 Android 客户端，使用 Jetpack Compose + Material Design 3 构建。

## ✨ 功能

### 文章管理
- 📋 **文章列表** - 卡片式布局，显示封面图、阅读时长、字数
- 🔍 **智能筛选** - 全部 / 未读 / 收藏 / 归档
- 📖 **文章详情** - HTML 渲染，支持富文本显示
- ⭐ **快捷操作** - 收藏/已读/归档/删除
- ➕ **保存文章** - 输入 URL 即可保存
- 🔄 **下拉刷新** - 手势操作刷新列表
- 📄 **分页加载** - 自动加载更多

### 服务器配置
- ⚙️ **设置页面** - 可随时修改服务器地址
- 🔗 **地址格式** - 自动补全 `http://` 和 `/`
- ✅ **格式验证** - 检查 URL 格式是否正确
- 💾 **持久化** - 服务器地址保存在本地

### 界面设计
- 🎨 **Material 3** - 遵循 Material You 设计规范
- 🌙 **深色模式** - 跟随系统自动切换
- 🏷️ **标签显示** - 文章标签以 Chip 形式展示
- 🖼️ **图片加载** - Coil 异步加载封面图

## 🏗️ 技术架构

```
MVVM Architecture
├── UI Layer (Jetpack Compose)
│   ├── MainActivity.kt          # Compose 入口
│   ├── ArticleListScreen.kt     # 文章列表
│   ├── ArticleDetailScreen.kt   # 文章详情
│   ├── SettingsScreen.kt        # 设置页面
│   └── AddArticleDialog.kt      # 添加文章对话框
├── ViewModel Layer
│   └── MainViewModel.kt         # 状态管理
├── Data Layer
│   ├── api/
│   │   ├── ReadLaterApi.kt      # Retrofit API 接口
│   │   └── RetrofitClient.kt    # 网络客户端
│   └── model/
│       └── Article.kt           # 数据模型
└── Util Layer
    └── PrefsManager.kt          # SharedPreferences
```

## 🛠️ 技术栈

| 技术 | 用途 |
|------|------|
| Kotlin | 开发语言 |
| Jetpack Compose | UI 框架 |
| Material Design 3 | 设计系统 |
| Retrofit 2 | 网络请求 |
| Moshi | JSON 解析 |
| OkHttp | HTTP 客户端 |
| Coil | 图片加载 |
| SharedPreferences | 本地存储 |

## 🔧 开发环境

### 前置要求
- JDK 17
- Android SDK (compileSdk 34)
- Gradle 8.5+
- Android Studio Hedgehog 或更高版本（可选）

### 编译命令

```bash
# 设置环境变量
export JAVA_HOME=/path/to/jdk-17
export ANDROID_HOME=/path/to/android-sdk

# 编译 Debug 版本
cd android-native
./gradlew assembleDebug

# 编译 Release 版本
./gradlew assembleRelease
```

### 输出路径
```
# Debug APK
android-native/app/build/outputs/apk/debug/app-debug.apk

# Release APK
android-native/app/build/outputs/apk/release/app-release-unsigned.apk
```

## 📡 API 对接

APP 对接 ReadLater 后端的标准 REST API：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/articles` | GET | 获取文章列表 |
| `/api/articles/{id}` | GET | 获取单篇文章 |
| `/api/save` | POST | 保存新文章 |
| `/api/articles/{id}` | PUT | 更新文章状态 |
| `/api/articles/{id}` | DELETE | 删除文章 |
| `/api/stats` | GET | 获取统计数据 |

### 服务器地址配置

默认服务器地址：`http://192.168.31.5:8000`

用户可以在 **设置页面** 中修改服务器地址，修改后 APP 会自动重新连接。

## 📦 依赖说明

```gradle
// Compose BOM
implementation platform('androidx.compose:compose-bom:2023.10.01')

// Material 3
implementation 'androidx.compose.material3:material3'
implementation 'androidx.compose.material:material-icons-extended'

// Navigation
implementation 'androidx.navigation:navigation-compose:2.7.4'

// Retrofit + Moshi
implementation 'com.squareup.retrofit2:retrofit:2.9.0'
implementation 'com.squareup.retrofit2:converter-moshi:2.9.0'
implementation 'com.squareup.moshi:moshi-kotlin:1.15.0'

// Coil (图片加载)
implementation 'io.coil-kt:coil-compose:2.5.0'
```

## 📋 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| v2.0.0 | 2026-06-25 | 🎉 全面重写为原生 Compose UI，新增设置页面 |

## 📄 License

MIT
