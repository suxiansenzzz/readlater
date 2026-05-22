// ReadLater 后台脚本 v0.2.0

// 默认服务器地址
const DEFAULT_SERVER = 'http://192.168.31.5:8000';

// 初始化
chrome.runtime.onInstalled.addListener(() => {
  // 设置默认服务器地址
  chrome.storage.sync.get(['serverUrl'], (result) => {
    if (!result.serverUrl) {
      chrome.storage.sync.set({ serverUrl: DEFAULT_SERVER });
    }
  });
  
  // 创建右键菜单
  chrome.contextMenus.create({
    id: 'save-to-readlater',
    title: '📖 保存到 ReadLater',
    contexts: ['page', 'link', 'selection']
  });
  
  chrome.contextMenus.create({
    id: 'save-selection-to-readlater',
    title: '📝 保存选中内容到 ReadLater',
    contexts: ['selection']
  });
});

// 右键菜单点击处理
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === 'save-to-readlater') {
    const url = info.linkUrl || info.pageUrl || tab.url;
    const title = tab.title;
    savePage(url, title);
  } else if (info.menuItemId === 'save-selection-to-readlater') {
    const url = info.pageUrl || tab.url;
    const title = tab.title;
    const content = info.selectionText;
    savePage(url, title, content);
  }
});

// 快捷键保存
chrome.commands.onCommand.addListener(async (command) => {
  if (command === 'save-page') {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    savePage(tab.url, tab.title);
  }
});

// 保存页面函数
async function savePage(url, title, content = null) {
  try {
    const result = await chrome.storage.sync.get(['serverUrl']);
    const serverUrl = result.serverUrl || DEFAULT_SERVER;
    
    const body = { url, title };
    if (content) {
      body.content = content;
    }
    
    const response = await fetch(`${serverUrl}/api/save`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP ${response.status}`);
    }
    
    const data = await response.json();
    
    if (data.success) {
      // 更新图标为已保存状态
      chrome.action.setBadgeText({ text: '✓' });
      chrome.action.setBadgeBackgroundColor({ color: '#10b981' });
      setTimeout(() => {
        chrome.action.setBadgeText({ text: '' });
      }, 2000);
      
      // 发送成功通知
      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/icon128.png',
        title: 'ReadLater',
        message: '✅ 文章保存成功！'
      });
    } else {
      throw new Error(data.detail || '保存失败');
    }
  } catch (error) {
    console.error('保存失败:', error);
    
    // 更新图标为失败状态
    chrome.action.setBadgeText({ text: '✗' });
    chrome.action.setBadgeBackgroundColor({ color: '#ef4444' });
    setTimeout(() => {
      chrome.action.setBadgeText({ text: '' });
    }, 3000);
    
    chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon128.png',
      title: 'ReadLater',
      message: '❌ 保存失败：' + error.message
    });
  }
}

// 导出给popup使用
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'save') {
    savePage(request.url, request.title, request.content).then(() => {
      sendResponse({ success: true });
    }).catch((error) => {
      sendResponse({ success: false, error: error.message });
    });
    return true; // 保持消息通道打开
  }
});
