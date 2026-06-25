# ReadLater 浏览器扩展

## 功能特性

- 🚀 一键保存网页到 ReadLater
- 📊 实时保存进度显示
- 🔔 保存成功/失败通知
- ⌨️ 快捷键支持 (Ctrl+Shift+S)
- 📱 响应式设计，支持移动端

## 安装方法

### Chrome/Edge 浏览器

1. 打开浏览器，进入扩展管理页面：
   - Chrome: `chrome://extensions/`
   - Edge: `edge://extensions/`

2. 开启「开发者模式」

3. 点击「加载已解压的扩展程序」

4. 选择本扩展的 `extension` 文件夹

5. 扩展安装完成！

## 使用方法

### 方法一：点击扩展图标

1. 点击浏览器工具栏中的 ReadLater 图标
2. 选择保存模式（完整页面/仅选中/阅读模式）
3. 点击「保存到 ReadLater」按钮
4. 等待保存完成，查看进度条

### 方法二：快捷键

- `Ctrl+Shift+S` - 快速保存当前页面

## 保存模式说明

- **📄 完整页面**：保存整个网页内容
- **✂️ 仅选中**：只保存当前选中的文本
- **📖 阅读模式**：只保存主要文章内容

## 文件结构

```
extension/
├── manifest.json      # 扩展配置文件
├── popup.html        # 弹出窗口界面
├── popup.js          # 弹出窗口逻辑
├── content.js        # 内容脚本
├── content.css       # 内容样式
├── background.js     # 后台脚本
└── icons/            # 图标文件
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
```

## 配置说明

默认连接本地 ReadLater 服务：`http://localhost:8000`

如需修改，请编辑以下文件中的 `API_BASE` 变量：
- `popup.js`
- `background.js`

## 常见问题

### 1. 扩展无法保存

- 确保 ReadLater 服务已启动
- 检查网络连接
- 查看浏览器控制台错误信息

### 2. 保存进度卡住

- 刷新页面重试
- 检查服务器状态

### 3. 快捷键不工作

- 检查快捷键是否与其他扩展冲突
- 在扩展管理页面重新加载扩展

## 技术栈

- Manifest V3
- Chrome Extensions API
- Fetch API
- CSS3 动画

## 更新日志

### v1.0.0 (2026-05-28)
- 初始版本发布
- 支持一键保存网页
- 实时进度显示
- 快捷键支持