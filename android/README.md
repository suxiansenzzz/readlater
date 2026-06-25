# ReadLater Android APP

一个轻量级的稍后阅读应用，支持小米澎湃OS4和所有安卓版本。

## 功能特点

- 📖 网页内容抓取和保存
- 🎨 优雅的阅读界面
- ⭐ 收藏和归档功能
- 🏷️ 标签管理
- 🔍 全文搜索
- 📱 完美适配移动端
- 🎤 语音朗读
- 📝 批注功能

## 系统要求

- Android 7.0 (API 24) 或更高版本
- 支持所有处理器架构 (ARM, ARM64, x86, x86_64)

## 兼容性

| 系统 | 兼容性 |
|------|--------|
| 小米澎湃OS4 | ✅ 完全兼容 |
| 小米澎湃OS3 | ✅ 完全兼容 |
| MIUI 14 | ✅ 完全兼容 |
| 原生 Android 14 | ✅ 完全兼容 |
| 原生 Android 13 | ✅ 完全兼容 |
| 原生 Android 12 | ✅ 完全兼容 |
| 原生 Android 11 | ✅ 完全兼容 |
| 原生 Android 10 | ✅ 完全兼容 |
| 原生 Android 9 | ✅ 完全兼容 |
| 原生 Android 8 | ✅ 完全兼容 |
| 原生 Android 7 | ✅ 完全兼容 |

## 快速开始

### 方法1: 使用预编译 APK

1. 从 [Releases](../../releases) 页面下载最新 APK
2. 传输到手机
3. 打开文件管理器，点击 APK 安装
4. 如果提示"未知来源"，在设置中允许

### 方法2: 自己构建

#### 前提条件

- Java JDK 8 或更高版本
- Android SDK (可选，也可以使用 GitHub Actions)

#### 构建步骤

```bash
# 1. 进入 android 目录
cd android

# 2. 运行构建脚本
python3 build.py

# 3. 按照提示配置服务器地址

# 4. 等待构建完成
# 构建好的 APK 在当前目录: readlater.apk
```

### 方法3: 使用 GitHub Actions

1. Fork 这个仓库
2. 推送代码到 main 分支
3. GitHub Actions 会自动构建 APK
4. 在 Actions 页面下载构建产物

## 配置服务器

### 默认配置

APP 默认连接: `http://192.168.31.5:8000`

### 修改服务器地址

编辑文件 `app/src/main/java/com/readlater/app/MainActivity.java`:

```java
// 修改这一行
private static final String SERVER_URL = "http://你的服务器地址:端口";
```

### 局域网部署

如果 ReadLater 部署在局域网:

```java
private static final String SERVER_URL = "http://192.168.1.100:8000";
```

### 公网部署

如果 ReadLater 部署在公网:

```java
private static final String SERVER_URL = "https://your-domain.com";
```

## 项目结构

```
android/
├── app/
│   ├── src/
│   │   └── main/
│   │       ├── java/com/readlater/app/
│   │       │   └── MainActivity.java    # 主活动
│   │       ├── res/
│   │       │   ├── layout/
│   │       │   │   └── activity_main.xml # 布局
│   │       │   ├── values/
│   │       │   │   ├── strings.xml      # 字符串
│   │       │   │   └── themes.xml       # 主题
│   │       │   ├── drawable/
│   │       │   │   └── progress_bar.xml # 进度条
│   │       │   ├── xml/
│   │       │   │   ├── network_security_config.xml # 网络配置
│   │       │   │   └── file_paths.xml   # 文件路径
│   │       │   └── mipmap-*/            # 图标
│   │       └── AndroidManifest.xml      # 清单文件
│   └── build.gradle                     # 应用构建配置
├── build.gradle                         # 项目构建配置
├── settings.gradle                      # 项目设置
├── gradle/                              # Gradle 包装器
├── build.py                             # 构建脚本
└── .github/workflows/build.yml          # GitHub Actions
```

## 技术栈

- **语言**: Java
- **UI框架**: Android WebView
- **构建工具**: Gradle 8.0
- **最低SDK**: API 24 (Android 7.0)
- **目标SDK**: API 34 (Android 14)

## 常见问题

### Q: 无法连接到服务器

A: 检查以下几点:
1. 手机和服务器是否在同一网络
2. 服务器地址是否正确
3. 服务器是否正常运行
4. 防火墙是否阻止了连接

### Q: 安装时提示"未知来源"

A: 在手机设置中:
1. 打开"设置" -> "安全" -> "更多安全设置"
2. 找到"安装未知应用"
3. 允许文件管理器或浏览器安装应用

### Q: APP 闪退

A: 尝试以下方法:
1. 清除 APP 数据
2. 卸载重装
3. 检查 Android 版本是否 >= 7.0

### Q: 页面加载很慢

A: 
1. 检查网络连接
2. 确保服务器性能足够
3. 尝试使用 HTTPS 连接

## 开发说明

### 添加新功能

1. 修改 `MainActivity.java` 添加功能
2. 在 `res/layout/activity_main.xml` 修改布局
3. 在 `AndroidManifest.xml` 添加权限

### 自定义主题

编辑 `res/values/themes.xml`:

```xml
<style name="Theme.ReadLater" parent="Theme.MaterialComponents.DayNight.NoActionBar">
    <item name="colorPrimary">#你的颜色</item>
    <!-- 更多颜色配置 -->
</style>
```

### 自定义图标

替换 `res/mipmap-*/` 目录下的图标文件:
- `ic_launcher.png` - 普通图标
- `ic_launcher_round.png` - 圆形图标
- `ic_launcher_foreground.png` - 自适应图标前景
- `ic_launcher_background.png` - 自适应图标背景

## 许可证

MIT License

## 作者

ReadLater Team

## 致谢

感谢所有贡献者和用户的支持！
