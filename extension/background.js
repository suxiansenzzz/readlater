// ReadLater 后台脚本 v0.3.0
// 支持页面内保存状态反馈

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
    await savePage(url, title, null, tab.id);
  } else if (info.menuItemId === 'save-selection-to-readlater') {
    const url = info.pageUrl || tab.url;
    const title = tab.title;
    const content = info.selectionText;
    await savePage(url, title, content, tab.id);
  }
});

// 快捷键保存
chrome.commands.onCommand.addListener(async (command) => {
  if (command === 'save-page') {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    await savePage(tab.url, tab.title, null, tab.id);
  }
});

// 监听来自 popup 的消息
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'SAVE_FROM_POPUP') {
    // Popup 请求保存，需要发送状态到当前标签页
    const { url, title, tags, tabId } = message;
    
    // 先发送保存中状态
    sendStatusToTab(tabId, {
      type: 'READLATER_STATUS',
      status: 'saving',
      title: title
    });
    
    // 执行保存
    savePage(url, title, null, tabId, tags).then(result => {
      sendResponse(result);
    });
    
    return true; // 异步响应
  }
});

// 向标签页发送状态消息
async function sendStatusToTab(tabId, message) {
  try {
    // 先检查标签页是否还存在
    const tab = await chrome.tabs.get(tabId).catch(() => null);
    if (!tab) {
      console.log('标签页不存在，跳过状态发送');
      return;
    }
    
    // 尝试发送消息
    await chrome.tabs.sendMessage(tabId, message).catch((err) => {
      console.log('发送状态消息失败（内容脚本可能未注入）:', err.message);
    });
  } catch (error) {
    console.log('发送状态消息失败:', error);
  }
}

// 保存页面函数
async function savePage(url, title, content = null, tabId = null, tags = []) {
  try {
    const result = await chrome.storage.sync.get(['serverUrl']);
    const serverUrl = result.url || DEFAULT_SERVER;
    
    console.log('保存页面:', { url, title, serverUrl, tabId });
    
    // 发送保存中状态
    if (tabId) {
      sendStatusToTab(tabId, {
        type: 'READLATER_STATUS',
        status: 'saving',
        title: title
      });
    }
    
    const body = { url, title };
    if (content) {
      body.content = content;
    }
    if (tags && tags.length > 0) {
      body.tags = tags;
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
    console.log('保存响应:', data);
    
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
        message: `✅ "${truncate(title, 30)}" 保存成功！`
      });
      
      // 发送成功状态到页面
      if (tabId) {
        sendStatusToTab(tabId, {
          type: 'READLATER_STATUS',
          status: 'success',
          title: title,
          articleId: data.article_id
        });
      }
      
      return { success: true, data };
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
    
    // 发送失败通知
    chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon128.png',
      title: 'ReadLater',
      message: `❌ 保存失败: ${error.message}`
    });
    
    // 发送错误状态到页面
    if (tabId) {
      sendStatusToTab(tabId, {
        type: 'READLATER_STATUS',
        status: 'error',
        title: title,
        detail: error.message
      });
    }
    
    return { success: false, error: error.message };
  }
}

// 字符串截断
function truncate(str, len) {
  if (!str) return '';
  return str.length > len ? str.substring(0, len) + '...' : str;
}
