// ReadLater Popup 脚本 v0.3.0
// 支持页面内保存状态反馈

const DEFAULT_SERVER = 'http://192.168.31.5:8000';

// 初始化
document.addEventListener('DOMContentLoaded', async () => {
  // 获取当前标签页
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  
  // 显示当前页面标题
  document.getElementById('pageTitle').textContent = tab.title || '无标题';
  
  // 加载保存的服务器地址
  const result = await chrome.storage.sync.get(['serverUrl']);
  const serverUrl = result.serverUrl || DEFAULT_SERVER;
  document.getElementById('serverUrl').value = serverUrl;
  
  // 更新打开链接
  document.getElementById('openReadLater').href = serverUrl;
  
  // 监听服务器地址变化
  document.getElementById('serverUrl').addEventListener('change', async (e) => {
    await chrome.storage.sync.set({ serverUrl: e.target.value });
    document.getElementById('openReadLater').href = e.target.value;
  });
  
  // 加载上次使用的标签
  const tagsResult = await chrome.storage.local.get(['lastTags']);
  if (tagsResult.lastTags) {
    document.getElementById('tags').value = tagsResult.lastTags;
  }
});

// 保存页面
async function savePage() {
  const btn = document.getElementById('saveBtn');
  const status = document.getElementById('status');
  const tagsInput = document.getElementById('tags');
  
  // 禁用按钮
  btn.disabled = true;
  btn.textContent = '⏳ 保存中...';
  status.className = 'status';
  
  try {
    // 获取当前标签页
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    // 获取服务器地址
    const result = await chrome.storage.sync.get(['serverUrl']);
    const serverUrl = result.serverUrl || DEFAULT_SERVER;
    
    // 处理标签
    const tagsStr = tagsInput.value.trim();
    const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(t => t) : [];
    
    // 保存标签到本地
    if (tagsStr) {
      await chrome.storage.local.set({ lastTags: tagsStr });
    }
    
    // 先通知内容脚本显示保存中状态
    try {
      await chrome.tabs.sendMessage(tab.id, {
        type: 'READLATER_STATUS',
        status: 'saving',
        title: tab.title
      });
    } catch (e) {
      console.log('内容脚本未注入，跳过页面状态反馈');
    }
    
    // 发送保存请求
    const response = await fetch(`${serverUrl}/api/save`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        url: tab.url,
        title: tab.title,
        tags: tags
      })
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP ${response.status}`);
    }
    
    const data = await response.json();
    
    if (data.success) {
      status.className = 'status success';
      status.textContent = '✅ 保存成功！';
      btn.textContent = '✅ 已保存';
      
      // 通知内容脚本显示成功状态
      try {
        await chrome.tabs.sendMessage(tab.id, {
          type: 'READLATER_STATUS',
          status: 'success',
          title: tab.title,
          articleId: data.article_id
        });
      } catch (e) {
        console.log('内容脚本未注入，跳过页面状态反馈');
      }
      
      // 更新图标
      chrome.action.setBadgeText({ text: '✓' });
      chrome.action.setBadgeBackgroundColor({ color: '#10b981' });
      setTimeout(() => {
        chrome.action.setBadgeText({ text: '' });
      }, 2000);
      
      // 1.5秒后关闭弹窗
      setTimeout(() => {
        window.close();
      }, 1500);
    } else {
      throw new Error(data.detail || '保存失败');
    }
  } catch (error) {
    console.error('保存失败:', error);
    status.className = 'status error';
    status.textContent = '❌ ' + error.message;
    btn.disabled = false;
    btn.textContent = '💾 保存到稍后阅读';
    
    // 通知内容脚本显示错误状态
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      await chrome.tabs.sendMessage(tab.id, {
        type: 'READLATER_STATUS',
        status: 'error',
        detail: error.message
      });
    } catch (e) {
      console.log('内容脚本未注入，跳过页面状态反馈');
    }
    
    // 更新图标
    chrome.action.setBadgeText({ text: '✗' });
    chrome.action.setBadgeBackgroundColor({ color: '#ef4444' });
    setTimeout(() => {
      chrome.action.setBadgeText({ text: '' });
    }, 3000);
  }
}
