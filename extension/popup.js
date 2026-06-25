// ReadLater 浏览器扩展 - Popup脚本

// DOM元素
const currentUrlEl = document.getElementById('currentUrl');
const saveBtn = document.getElementById('saveBtn');
const saveIcon = document.getElementById('saveIcon');
const saveText = document.getElementById('saveText');
const progressContainer = document.getElementById('progressContainer');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const statusEl = document.getElementById('status');
const openDashboardBtn = document.getElementById('openDashboard');
const serverSelect = document.getElementById('serverSelect');
const customServerInput = document.getElementById('customServer');
const checkUpdateBtn = document.getElementById('checkUpdate');

// 选项按钮
const optFullPage = document.getElementById('optFullPage');
const optSelection = document.getElementById('optSelection');
const optReadMode = document.getElementById('optReadMode');

let currentSaveMode = 'full'; // full, selection, read
let currentTabUrl = '';
let currentServer = 'http://localhost:8000'; // 默认本地服务器

// 配置
const SERVER_CONFIG = {
    local: 'http://localhost:8000',
    remote: 'https://your-readlater-server.com', // 用户可以修改为自己的远程服务器
    custom: ''
};

// 初始化
document.addEventListener('DOMContentLoaded', async () => {
    // 获取当前标签页信息
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tab) {
            currentTabUrl = tab.url;
            currentUrlEl.textContent = tab.title || tab.url;
            currentUrlEl.title = tab.url;
        }
    } catch (error) {
        currentUrlEl.textContent = '无法获取当前页面';
    }
    
    // 加载保存的服务器配置
    loadServerConfig();
    
    // 检查是否已保存
    checkIfSaved();
});

// 保存按钮点击
saveBtn.addEventListener('click', savePage);

// 打开控制台
openDashboardBtn.addEventListener('click', () => {
    chrome.tabs.create({ url: currentServer });
});

// 选项切换
optFullPage.addEventListener('click', () => setMode('full'));
optSelection.addEventListener('click', () => setMode('selection'));
optReadMode.addEventListener('click', () => setMode('read'));

// 服务器选择变化
serverSelect.addEventListener('change', () => {
    const value = serverSelect.value;
    if (value === 'custom') {
        customServerInput.style.display = 'block';
        customServerInput.focus();
    } else {
        customServerInput.style.display = 'none';
        currentServer = SERVER_CONFIG[value];
        saveServerConfig();
        // 更新按钮状态
        checkIfSaved();
    }
});

// 自定义服务器输入
customServerInput.addEventListener('change', () => {
    currentServer = customServerInput.value.trim();
    if (currentServer) {
        SERVER_CONFIG.custom = currentServer;
        saveServerConfig();
        // 更新按钮状态
        checkIfSaved();
    }
});

// 检查更新按钮
checkUpdateBtn.addEventListener('click', checkForUpdates);

// 检查更新
async function checkForUpdates() {
    checkUpdateBtn.disabled = true;
    checkUpdateBtn.textContent = '🔄 检查中...';
    
    try {
        // 获取当前版本
        const manifest = chrome.runtime.getManifest();
        const currentVersion = manifest.version;
        
        // 从服务器获取最新版本信息
        const response = await fetch(`${currentServer}/api/extension/version`);
        const data = await response.json();
        
        if (data.latest_version) {
            const latestVersion = data.latest_version;
            
            if (compareVersions(latestVersion, currentVersion) > 0) {
                // 有新版本
                const message = `发现新版本 ${latestVersion}（当前版本 ${currentVersion}）\n\n更新内容：\n${data.changelog || '暂无更新说明'}\n\n是否前往下载？`;
                
                if (confirm(message)) {
                    // 打开下载页面
                    chrome.tabs.create({ url: data.download_url || `${currentServer}/extension/update` });
                }
            } else {
                showStatus('当前已是最新版本', 'success');
            }
        } else {
            showStatus('无法获取版本信息', 'error');
        }
    } catch (error) {
        console.error('检查更新失败:', error);
        showStatus('检查更新失败: ' + error.message, 'error');
    } finally {
        checkUpdateBtn.disabled = false;
        checkUpdateBtn.textContent = '🔄 检查更新';
    }
}

// 版本比较函数
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

// 加载服务器配置
async function loadServerConfig() {
    try {
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
    } catch (error) {
        console.error('加载服务器配置失败:', error);
    }
}

// 保存服务器配置
async function saveServerConfig() {
    try {
        await chrome.storage.sync.set({
            serverType: serverSelect.value,
            customServer: serverSelect.value === 'custom' ? currentServer : ''
        });
    } catch (error) {
        console.error('保存服务器配置失败:', error);
    }
}

function setMode(mode) {
    currentSaveMode = mode;
    [optFullPage, optSelection, optReadMode].forEach(btn => btn.classList.remove('active'));
    
    switch(mode) {
        case 'full':
            optFullPage.classList.add('active');
            break;
        case 'selection':
            optSelection.classList.add('active');
            break;
        case 'read':
            optReadMode.classList.add('active');
            break;
    }
}

// 检查页面是否已保存
async function checkIfSaved() {
    if (!currentTabUrl) return;
    
    try {
        const response = await fetch(`${currentServer}/api/articles?url=${encodeURIComponent(currentTabUrl)}`);
        const data = await response.json();
        
        if (data.articles && data.articles.length > 0) {
            showStatus('此页面已保存', 'info');
            saveText.textContent = '已保存 ✓';
            saveBtn.disabled = true;
        } else {
            // 重置状态
            saveText.textContent = '保存到 ReadLater';
            saveBtn.disabled = false;
            hideStatus();
        }
    } catch (error) {
        console.error('检查保存状态失败:', error);
        // 服务器连接失败时不改变按钮状态
    }
}

// 保存页面
async function savePage() {
    if (!currentTabUrl) {
        showStatus('无法获取当前页面URL', 'error');
        return;
    }
    
    // 更新UI状态
    saveBtn.disabled = true;
    saveIcon.innerHTML = '<span class="spinner">⏳</span>';
    saveText.textContent = '保存中...';
    progressContainer.style.display = 'block';
    hideStatus();
    
    try {
        // 获取页面内容
        updateProgress(10, '正在获取页面内容...');
        
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        
        // 向content script发送消息获取页面内容
        let pageContent = '';
        let pageTitle = tab.title || '';
        
        try {
            const response = await chrome.tabs.sendMessage(tab.id, { 
                action: 'getPageContent',
                mode: currentSaveMode 
            });
            
            if (response && response.content) {
                pageContent = response.content;
                pageTitle = response.title || pageTitle;
            }
        } catch (e) {
            // 如果content script没有响应，使用URL直接保存
            console.log('Content script未响应，使用URL保存');
        }
        
        updateProgress(30, `正在保存到 ${serverSelect.options[serverSelect.selectedIndex].text}...`);
        
        // 发送到ReadLater API
        const saveResponse = await fetch(`${currentServer}/api/save`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                url: currentTabUrl,
                title: pageTitle,
                content: pageContent || undefined
            })
        });
        
        updateProgress(70, '正在处理...');
        
        const result = await saveResponse.json();
        
        if (result.success) {
            updateProgress(100, '保存成功！');
            
            setTimeout(() => {
                saveIcon.textContent = '✅';
                saveText.textContent = '保存成功';
                showStatus('文章已成功保存到 ReadLater', 'success');
                
                // 提供反向操作选项
                setTimeout(() => {
                    if (confirm('保存成功！是否打开 ReadLater 查看？')) {
                        chrome.tabs.create({ url: currentServer });
                    }
                }, 500);
            }, 300);
        } else {
            throw new Error(result.detail || '保存失败');
        }
        
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
        
        // 重置按钮
        setTimeout(() => {
            saveBtn.disabled = false;
            saveIcon.textContent = '💾';
            saveText.textContent = '重试保存';
            progressContainer.style.display = 'none';
        }, 3000);
    }
}

// 更新进度条
function updateProgress(percent, text) {
    progressFill.style.width = percent + '%';
    progressText.textContent = text;
}

// 显示状态消息
function showStatus(message, type = 'info') {
    statusEl.textContent = message;
    statusEl.className = 'status ' + type;
}

// 隐藏状态消息
function hideStatus() {
    statusEl.className = 'status';
}
