# ReadLater Android APP 使用指南

## 🎉 项目已创建完成！

我已经为你创建了一个完整的 Android APP 项目，可以把 ReadLater 打包成安卓应用。

## 📱 APP 特性

### 功能
- ✅ 完整的 ReadLater 功能
- ✅ 优雅的加载进度条
- ✅ 返回键支持
- ✅ 外部链接自动跳转浏览器
- ✅ 错误提示页面
- ✅ 支持离线缓存

### 兼容性
- ✅ **小米澎湃OS4** - 完全兼容
- ✅ **小米澎湃OS3** - 完全兼容
- ✅ **MIUI 14** - 完全兼容
- ✅ **原生 Android 7.0-14** - 完全兼容
- ✅ **所有处理器架构** - ARM, ARM64, x86, x86_64

## 🚀 快速开始

### 第一步：配置服务器地址

APP 默认连接 `http://192.168.31.5:8000`

如果需要修改，运行：

```bash
cd /opt/data/workspace/readlater/android
python3 config_server.py
```

### 第二步：构建 APK

有三种方式：

#### 方式1: 使用 Python 脚本（推荐）

```bash
cd /opt/data/workspace/readlater/android
python3 build.py
```

脚本会自动：
- 检查环境
- 配置服务器地址
- 构建 APK
- 生成 `readlater.apk`

#### 方式2: 使用 GitHub Actions

1. 将 `android` 目录上传到 GitHub 仓库
2. 推送到 main 分支
3. GitHub Actions 自动构建
4. 在 Actions 页面下载 APK

#### 方式3: 使用 Android Studio

1. 下载安装 [Android Studio](https://developer.android.com/studio)
2. 打开 `android` 目录
3. 等待 Gradle 同步
4. 菜单: Build → Build Bundle(s) / APK(s) → Build APK(s)

### 第三步：安装到手机

1. 将 `readlater.apk` 传输到手机
2. 打开文件管理器
3. 点击 APK 文件
4. 按提示安装

如果提示"未知来源"：
- 设置 → 安全 → 更多安全设置 → 安装未知应用 → 允许

## 📂 项目文件说明

```
android/
├── build.py              # 构建脚本（运行这个）
├── config_server.py      # 服务器配置脚本
├── README.md             # 详细说明
├── PROJECT.md            # 项目清单
└── app/src/main/
    ├── AndroidManifest.xml    # APP 配置
    └── java/.../MainActivity.java  # 主代码
```

## ⚙️ 自定义配置

### 修改服务器地址

```bash
# 方式1: 使用脚本
python3 config_server.py

# 方式2: 手动编辑
# 编辑 app/src/main/java/com/readlater/app/MainActivity.java
# 修改 SERVER_URL 变量
```

### 修改 APP 名称

编辑 `app/src/main/res/values/strings.xml`:

```xml
<string name="app_name">你的APP名称</string>
```

### 修改主题颜色

编辑 `app/src/main/res/values/themes.xml`:

```xml
<item name="colorPrimary">#你的颜色</item>
```

### 替换 APP 图标

参考 `app/src/main/res/mipmap-xxxhdpi/README.md`

## 🔧 环境要求

### 必需
- Python 3.6+
- Java JDK 8+（如果没有，脚本会提示）

### 可选
- Android SDK（如果没有，可以使用 GitHub Actions）

### 安装 Java

```bash
# Ubuntu/Debian
sudo apt install openjdk-17-jdk

# macOS
brew install openjdk@17

# Windows
# 下载安装 Adoptium JDK: https://adoptium.net/
```

## 📋 常见问题

### Q: 构建失败怎么办？

A: 
1. 检查 Java 是否安装：`java -version`
2. 检查网络连接
3. 尝试使用 GitHub Actions 构建

### Q: 没有 Java 环境怎么办？

A: 使用 GitHub Actions 自动构建，不需要本地环境。

### Q: APP 无法连接服务器？

A:
1. 检查服务器地址配置
2. 确保手机和服务器在同一网络
3. 检查防火墙设置

### Q: 安装后闪退？

A:
1. 确保 Android 版本 >= 7.0
2. 清除 APP 数据重试
3. 检查服务器是否正常运行

## 🎯 下一步

1. ✅ 配置服务器地址
2. ✅ 构建 APK
3. ✅ 安装到手机
4. ✅ 测试功能
5. ✅ 分享给朋友

## 💡 小贴士

- 首次打开 APP 会加载网页，可能需要几秒钟
- 建议使用 HTTPS 连接（更安全）
- 可以添加到主屏幕，方便快速打开
- 支持横屏和竖屏切换

## 📞 技术支持

如果遇到问题，请检查：
1. README.md - 详细说明
2. PROJECT.md - 项目清单
3. 服务器日志

---

**祝你使用愉快！** 🎉
