# ReadLater Android 项目文件清单

## 项目结构

```
android/
├── app/
│   ├── src/
│   │   └── main/
│   │       ├── java/com/readlater/app/
│   │       │   └── MainActivity.java         ✅ 主活动 - WebView实现
│   │       ├── res/
│   │       │   ├── layout/
│   │       │   │   └── activity_main.xml     ✅ 主布局
│   │       │   ├── values/
│   │       │   │   ├── strings.xml           ✅ 字符串资源
│   │       │   │   └── themes.xml            ✅ 主题样式
│   │       │   ├── drawable/
│   │       │   │   └── progress_bar.xml      ✅ 进度条样式
│   │       │   ├── xml/
│   │       │   │   ├── network_security_config.xml ✅ 网络安全配置
│   │       │   │   └── file_paths.xml        ✅ 文件路径配置
│   │       │   └── mipmap-xxxhdpi/
│   │       │       └── README.md             ✅ 图标说明
│   │       └── AndroidManifest.xml           ✅ 清单文件
│   ├── build.gradle                          ✅ 应用构建配置
│   └── proguard-rules.pro                    ✅ 代码混淆规则
├── build.gradle                              ✅ 项目构建配置
├── settings.gradle                           ✅ 项目设置
├── gradlew                                   ✅ Gradle 包装器脚本
├── gradle/wrapper/
│   └── gradle-wrapper.properties             ✅ Gradle 配置
├── build.py                                  ✅ Python 构建脚本
├── config_server.py                          ✅ 服务器配置脚本
├── README.md                                 ✅ 项目说明
└── .github/workflows/
    └── build.yml                             ✅ GitHub Actions 配置
```

## 功能特性

### APP 功能
- ✅ WebView 加载 ReadLater 网页版
- ✅ 支持 JavaScript
- ✅ 支持 Cookie
- ✅ 进度条显示
- ✅ 返回键处理
- ✅ 外部链接跳转
- ✅ 错误页面显示
- ✅ APP 信息注入

### 兼容性
- ✅ 最低支持 Android 7.0 (API 24)
- ✅ 目标版本 Android 14 (API 34)
- ✅ 支持所有处理器架构
- ✅ 小米澎湃OS4 完全兼容
- ✅ 支持 HTTP 和 HTTPS

### 构建方式
- ✅ 本地构建 (Python 脚本)
- ✅ GitHub Actions 自动构建
- ✅ Android Studio 构建

## 使用说明

### 快速配置服务器

```bash
cd android
python3 config_server.py
```

### 构建 APK

```bash
cd android
python3 build.py
```

### 使用 GitHub Actions

1. 将 android 目录上传到 GitHub
2. 推送代码到 main 分支
3. 在 Actions 页面下载 APK

## 服务器配置

默认服务器地址: `http://192.168.31.5:8000`

修改方式:
1. 运行 `python3 config_server.py`
2. 或直接编辑 `MainActivity.java`

## 注意事项

1. 首次构建需要下载 Gradle 和依赖，可能需要较长时间
2. 需要 Java JDK 8 或更高版本
3. 如果没有 Android SDK，可以使用 GitHub Actions 构建
4. APP 图标需要手动替换（见图标说明）
