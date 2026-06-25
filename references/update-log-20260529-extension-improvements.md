# 2026-05-29 浏览器扩展更新：服务器选择、更新检查、错误修复

## 问题概述

用户反馈浏览器扩展三个问题：
1. 保存失败时显示"[object Object]"错误
2. 没有"保存到何处"的选项（服务器选择）
3. 需要自动更新功能

## 根因分析

### 1. "[object Object]"错误显示
**现象：** 保存失败时，Toast通知显示"[object Object]"而不是具体错误信息

**根因：** JavaScript中当error对象直接拼接字符串时，会调用toString()方法返回"[object Object]"

**错误代码：**
```javascript
// content.js
showToast('保存失败：' + (response?.error || '未知错误'), 'error');
// 如果response.error是对象，会显示"[object Object]"

// popup.js
showStatus(error.message || '保存失败，请重试', 'error');
// 如果error.message是对象，同样会出问题
```

**修复：** 添加类型检查，对象转JSON字符串
```javascript
// 确保message是字符串
if (typeof message === 'object') {
    message = JSON.stringify(message);
}
```

### 2. 服务器选择功能缺失
**现象：** 用户无法选择保存到哪个服务器

**根因：** 扩展硬编码了localhost:8000作为唯一服务器

**解决方案：** 
- 添加服务器选择下拉框（本地/远程/自定义）
- 使用`chrome.storage.sync`持久化配置
- background.js监听配置变化并更新API_BASE

### 3. 更新检查功能
**现象：** 用户希望扩展能检查是否有新版本

**解决方案：**
- 添加`/api/extension/version`端点返回版本信息
- 前端调用该端点比较版本号
- 使用语义化版本比较函数

## 修复方案

### 1. 错误处理修复

**content.js修改：**
```javascript
function showToast(message, type = 'info') {
    injectToastStyles();
    
    // 确保message是字符串
    if (typeof message === 'object') {
        message = JSON.stringify(message);
    }
    
    const toast = document.createElement('div');
    toast.className = `readlater-toast ${type}`;
    toast.textContent = message;
    // ...
}
```

**popup.js修改：**
```javascript
} catch (error) {
    console.error('保存失败:', error);
    updateProgress(0, '保存失败');
    saveIcon.textContent = '❌';
    saveText.textContent = '保存失败';
    // 确保错误信息是字符串
    let errorMsg = error.message || error;
    if (typeof errorMsg === 'object') {
        errorMsg = JSON.stringify(errorMsg);
    }
    showStatus(errorMsg || '保存失败，请重试', 'error');
}
```

### 2. 服务器选择功能

**popup.html新增UI：**
```html
<div class="card">
    <div class="current-page">保存到</div>
    <select id="serverSelect" class="server-select">
        <option value="local">🏠 本地服务器</option>
        <option value="remote">☁️ 远程服务器</option>
        <option value="custom">⚙️ 自定义...</option>
    </select>
    <input type="text" id="customServer" class="custom-server-input" 
           placeholder="输入服务器地址" style="display: none;">
</div>
```

**popup.js配置管理：**
```javascript
const SERVER_CONFIG = {
    local: 'http://localhost:8000',
    remote: 'https://your-readlater-server.com',
    custom: ''
};

// 加载服务器配置
async function loadServerConfig() {
    const result = await chrome.storage.sync.get(['serverType', 'customServer']);
    if (result.serverType) {
        serverSelect.value = result.serverType;
        if (result.serverType === 'custom' && result.customServer) {
            customServerInput.value = result.customServer;
            customServerInput.style.display = 'block';
            currentServer = result.customServer;
        } else {
            currentServer = SERVER_CONFIG[result.serverType];
        }
    }
}

// 保存服务器配置
async function saveServerConfig() {
    await chrome.storage.sync.set({
        serverType: serverSelect.value,
        customServer: serverSelect.value === 'custom' ? currentServer : ''
    });
}
```

**background.js动态配置：**
```javascript
let API_BASE = 'http://localhost:8000';

async function loadServerConfig() {
    const result = await chrome.storage.sync.get(['serverType', 'customServer']);
    if (result.serverType) {
        const SERVER_CONFIG = {
            local: 'http://localhost:8000',
            remote: 'https://your-readlater-server.com',
            custom: result.customServer || 'http://localhost:8000'
        };
        API_BASE = SERVER_CONFIG[result.serverType] || API_BASE;
    }
}

// 监听存储变化
chrome.storage.onChanged.addListener((changes, namespace) => {
    if (namespace === 'sync' && (changes.serverType || changes.customServer)) {
        loadServerConfig();
    }
});
```

### 3. 更新检查功能

**后端API端点：**
```python
@app.get("/api/extension/version")
async def get_extension_version():
    """获取浏览器扩展最新版本信息"""
    return {
        "latest_version": "1.1.0",
        "changelog": "1. 添加服务器选择功能\n2. 添加检查更新功能\n3. 修复错误提示问题",
        "download_url": "http://localhost:8000/extension/update"
    }
}
```

**前端版本比较：**
```javascript
async function checkForUpdates() {
    const manifest = chrome.runtime.getManifest();
    const currentVersion = manifest.version;
    
    const response = await fetch(`${currentServer}/api/extension/version`);
    const data = await response.json();
    
    if (data.latest_version) {
        if (compareVersions(data.latest_version, currentVersion) > 0) {
            // 有新版本，提示用户
            if (confirm(`发现新版本 ${data.latest_version}`)) {
                chrome.tabs.create({ url: data.download_url });
            }
        } else {
            showStatus('当前已是最新版本', 'success');
        }
    }
}

function compareVersions(v1, v2) {
    const parts1 = v1.split('.').map(Number);
    const parts2 = v2.split('.').map(Number);
    
    for (let i = 0; i < Math.max(parts1.length, parts2.length); i++) {
        const part1 = parts1[i] || 0;
        const part2 = parts2[i] || 0;
        
        if (part1 > part2) return 1;
        if (part1 < part2) return -1;
    }
    
    return 0;
}
```

### 4. manifest.json更新

```json
{
  "version": "1.1.0",
  "permissions": ["activeTab", "storage"],
  "host_permissions": [
    "http://localhost:8000/*",
    "http://192.168.31.5:8000/*",
    "https://your-readlater-server.com/*"
  ]
}
```

## 测试结果

| 功能 | 修复前 | 修复后 |
|------|--------|--------|
| 错误提示 | ❌ 显示"[object Object]" | ✅ 显示具体错误信息 |
| 服务器选择 | ❌ 硬编码localhost | ✅ 支持本地/远程/自定义 |
| 配置持久化 | ❌ 每次重置 | ✅ 自动保存恢复 |
| 更新检查 | ❌ 无此功能 | ✅ 一键检查更新 |

## 相关文件

- 扩展文件：`/opt/data/workspace/readlater/extension/`
- 扩展包：`/opt/data/workspace/readlater/dist/readlater-extension-v1.1.0.tar.gz`
- 更新页面：`/opt/data/workspace/readlater/static/extension-update.html`
- 版本API：`/opt/data/workspace/readlater/backend/main.py` (get_extension_version)

## 经验教训

1. **JavaScript对象转字符串** - 直接拼接对象会得到"[object Object]"，需要用JSON.stringify
2. **Chrome扩展配置持久化** - 使用`chrome.storage.sync`可以跨设备同步配置
3. **Background script配置更新** - 需要监听`chrome.storage.onChanged`事件
4. **语义化版本比较** - 拆分为数组逐位比较，处理不同长度的版本号
5. **扩展更新机制** - 通过API返回版本信息，前端比较后提示用户

## 更新时间

2026-05-29 23:50