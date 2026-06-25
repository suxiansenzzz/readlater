// ReadLater 浏览器扩展 - Background Script

// 默认服务器地址
let API_BASE = 'http://localhost:8000';

// 从存储中加载服务器配置
async function loadServerConfig() {
    try {
        const result = await chrome.storage.sync.get(['serverType', 'customServer']);
        if (result.serverType) {
            const SERVER_CONFIG = {
                local: 'http://localhost:8000',
                remote: 'https://your-readlater-server.com',
                custom: result.customServer || 'http://localhost:8000'
            };
            API_BASE = SERVER_CONFIG[result.serverType] || API_BASE;
        }
    } catch (error) {
        console.error('加载服务器配置失败:', error);
    }
}

// 初始化时加载配置
loadServerConfig();

// 监听存储变化
chrome.storage.onChanged.addListener((changes, namespace) => {
    if (namespace === 'sync' && (changes.serverType || changes.customServer)) {
        loadServerConfig();
    }
});

// 监听来自content script的消息
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'savePage') {
        savePage(request.url, request.title)
            .then(result => sendResponse(result))
            .catch(error => sendResponse({ success: false, error: error.message }));
        return true; // 保持消息通道开放
    }
});

// 保存页面到ReadLater
async function savePage(url, title) {
    try {
        const response = await fetch(`${API_BASE}/api/save`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                url: url,
                title: title
            })
        });
        
        const result = await response.json();
        return result;
    } catch (error) {
        throw error;
    }
}

// 监听快捷键命令
chrome.commands?.onCommand?.addListener((command) => {
    if (command === 'save-to-readlater') {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0]) {
                savePage(tabs[0].url, tabs[0].title)
                    .then(result => {
                        console.log('保存成功:', result);
                    })
                    .catch(error => {
                        console.error('保存失败:', error);
                    });
            }
        });
    }
});

console.log('ReadLater 后台脚本已加载');
