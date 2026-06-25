// ReadLater 浏览器扩展 - Content Script

// 监听来自popup的消息
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'getPageContent') {
        const content = getPageContent(request.mode);
        sendResponse(content);
    }
    return true;
});

// 获取页面内容
function getPageContent(mode = 'full') {
    let content = '';
    let title = document.title || '';
    
    switch(mode) {
        case 'full':
            // 获取完整页面内容
            content = getFullPageContent();
            break;
            
        case 'selection':
            // 获取选中的内容
            const selection = window.getSelection();
            if (selection && selection.toString().trim()) {
                content = selection.toString().trim();
                // 尝试获取包含选中内容的HTML
                if (selection.rangeCount > 0) {
                    const range = selection.getRangeAt(0);
                    const container = document.createElement('div');
                    container.appendChild(range.cloneContents());
                    content = container.innerHTML;
                }
            } else {
                content = getFullPageContent();
            }
            break;
            
        case 'read':
            // 获取阅读模式内容（主要文本）
            content = getReadModeContent();
            break;
    }
    
    return {
        title: title,
        content: content,
        url: window.location.href
    };
}

// 获取完整页面内容
function getFullPageContent() {
    // 优先获取文章内容
    const articleSelectors = [
        'article',
        '[role="article"]',
        '.post-content',
        '.article-content',
        '.entry-content',
        '.content',
        'main'
    ];
    
    for (const selector of articleSelectors) {
        const element = document.querySelector(selector);
        if (element && element.innerHTML.length > 200) {
            return element.innerHTML;
        }
    }
    
    // 如果没找到文章内容，获取body内容
    // 移除脚本和样式
    const body = document.body.cloneNode(true);
    const scripts = body.querySelectorAll('script, style, noscript, iframe');
    scripts.forEach(el => el.remove());
    
    return body.innerHTML;
}

// 获取阅读模式内容
function getReadModeContent() {
    // 获取主要文本内容
    const paragraphs = document.querySelectorAll('p, h1, h2, h3, h4, h5, h6, li, blockquote');
    let content = '';
    
    paragraphs.forEach(p => {
        const text = p.textContent.trim();
        if (text.length > 20) {
            content += `<${p.tagName.toLowerCase()}>${text}</${p.tagName.toLowerCase()}>`;
        }
    });
    
    return content || getFullPageContent();
}

// 注入Toast通知样式
function injectToastStyles() {
    const style = document.createElement('style');
    style.textContent = `
        .readlater-toast {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 8px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 14px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
            z-index: 999999;
            animation: readlater-slideIn 0.3s ease;
        }
        
        @keyframes readlater-slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        .readlater-toast.success {
            background: linear-gradient(135deg, #4caf50 0%, #45a049 100%);
        }
        
        .readlater-toast.error {
            background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);
        }
    `;
    document.head.appendChild(style);
}

// 显示Toast通知
function showToast(message, type = 'info') {
    injectToastStyles();
    
    // 确保message是字符串
    if (typeof message === 'object') {
        message = JSON.stringify(message);
    }
    
    const toast = document.createElement('div');
    toast.className = `readlater-toast ${type}`;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'readlater-slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// 监听快捷键保存
document.addEventListener('keydown', (e) => {
    // Ctrl+Shift+S 保存到ReadLater
    if (e.ctrlKey && e.shiftKey && e.key === 'S') {
        e.preventDefault();
        showToast('正在保存到 ReadLater...', 'info');
        
        chrome.runtime.sendMessage({
            action: 'savePage',
            url: window.location.href,
            title: document.title
        }, (response) => {
            if (response && response.success) {
                showToast('保存成功！', 'success');
            } else {
                showToast('保存失败：' + (response?.error || '未知错误'), 'error');
            }
        });
    }
});

console.log('ReadLater 扩展已加载');