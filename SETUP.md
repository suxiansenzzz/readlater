# ReadLater 完整部署指南

## 📋 准备工作

### 1. 服务器端（Docker 部署）

```bash
# 进入项目目录
cd /opt/data/workspace/readlater

# 一键部署
./start.sh
```

部署完成后，服务运行在 `http://你的服务器IP:8000`

### 2. 浏览器扩展安装

#### 打包扩展

```bash
# 打包扩展
./package-extension.sh
```

会在 `dist/` 目录生成 `readlater-extension.zip`

#### Chrome / Edge 安装

1. 打开扩展管理页面
   - Chrome: `chrome://extensions/`
   - Edge: `edge://extensions/`

2. 开启「开发者模式」（右上角开关）

3. 安装扩展（二选一）：
   - **方法A**: 直接拖拽 `readlater-extension.zip` 到页面
   - **方法B**: 解压 zip，点击「加载已解压的扩展程序」选择 `extension` 目录

4. 安装成功后，工具栏会出现 📖 图标

#### Firefox 安装

1. 打开 `about:debugging#/runtime/this-firefox`

2. 点击「临时加载附加组件」

3. 选择 `extension/manifest.json`

4. 注意：Firefox 重启后需要重新加载

## ⚙️ 配置扩展

1. 点击工具栏的 ReadLater 图标

2. 在底部「服务器地址」输入框填写你的服务器地址：
   ```
   http://你的服务器IP:8000
   ```

3. 点击「打开 ReadLater →」验证连接

## 🚀 使用方法

### 保存网页

**方法一：点击扩展图标**
- 点击工具栏 📖 图标
- 可选填标签
- 点击「保存到稍后阅读」

**方法二：右键菜单**
- 在页面上右键
- 选择「📖 保存到 ReadLater」
- 或选中文字后选择「📝 保存选中内容到 ReadLater」

**方法三：快捷键**
- 按 `Alt + S` 快速保存当前页面

### 阅读文章

1. 访问 `http://你的服务器IP:8000`
2. 点击文章卡片进入阅读模式
3. 支持：标记已读、收藏、存档、删除

## 🔧 常见问题

### 1. 扩展保存失败

检查：
- 服务器地址是否正确
- 服务器是否正常运行：`curl http://localhost:8000/api/stats`
- 是否开启了 CORS（已默认开启）

### 2. 无法连接服务器

确保：
- 服务器防火墙开放 8000 端口
- 服务器和客户端在同一网络，或服务器有公网IP

### 3. 扩展在某些网站不工作

某些网站（如 Chrome Web Store）禁止扩展运行，这是浏览器限制。

## 📦 绿联NAS部署

1. 在电脑上构建镜像：
   ```bash
   ./build.sh
   ```

2. 导出镜像：
   ```bash
   docker save readlater:latest | gzip > readlater.tar.gz
   ```

3. 上传到 NAS，导入并运行

4. 浏览器扩展服务器地址填写：
   ```
   http://NAS的IP:8000
   ```

## 🎉 完成！

现在你可以在任何浏览器上一键保存网页了！