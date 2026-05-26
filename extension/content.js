// ReadLater 内容脚本 v0.3.0
// 在页面上显示保存状态反馈

(function() {
  'use strict';

  // 防止重复注入
  if (window.readlaterContentLoaded) {
    return;
  }
  window.readlaterContentLoaded = true;

  // Toast 容器
  let toastContainer = null;
  let toastCounter = 0;

  // 初始化容器
  function initContainer() {
    if (!toastContainer) {
      toastContainer = document.createElement('div');
      toastContainer.className = 'readlater-toast-container';
      toastContainer.id = 'readlater-toast-container';
      document.body.appendChild(toastContainer);
    }
    return toastContainer;
  }

  // 创建 Toast
  function createToast(options) {
    const container = initContainer();
    const id = `readlater-toast-${++toastCounter}`;
    
    const {
      type = 'info',        // saving, success, error, warning, info
      title = '',
      message = '',
      duration = 4000,      // 自动关闭时间，0 表示不自动关闭
      showProgress = true,
      closable = true
    } = options;

    // 图标映射
    const icons = {
      saving: '⏳',
      success: '✅',
      error: '❌',
      warning: '⚠️',
      info: 'ℹ️'
    };

    // 创建 toast 元素
    const toast = document.createElement('div');
    toast.className = `readlater-toast ${type}`;
    toast.id = id;

    // 内容 HTML
    let html = `
      <div class="readlater-toast-icon">${icons[type] || icons.info}</div>
      <div class="readlater-toast-content">
        ${title ? `<div class="readlater-toast-title">${escapeHtml(title)}</div>` : ''}
        ${message ? `<div class="readlater-toast-message">${escapeHtml(message)}</div>` : ''}
      </div>
    `;

    // 关闭按钮
    if (closable) {
      html += `<button class="readlater-toast-close" onclick="window.readlaterRemoveToast('${id}')">✕</button>`;
    }

    // 进度条
    if (showProgress && duration > 0) {
      html += `<div class="readlater-toast-progress" style="width: 100%;"></div>`;
    }

    toast.innerHTML = html;
    container.appendChild(toast);

    // 触发动画
    requestAnimationFrame(() => {
      toast.classList.add('show');
      
      // 进度条动画
      if (showProgress && duration > 0) {
        const progress = toast.querySelector('.readlater-toast-progress');
        if (progress) {
          progress.style.transition = `width ${duration}ms linear`;
          requestAnimationFrame(() => {
            progress.style.width = '0%';
          });
        }
      }
    });

    // 自动关闭
    if (duration > 0) {
      setTimeout(() => {
        removeToast(id);
      }, duration);
    }

    return id;
  }

  // 移除 Toast
  function removeToast(id) {
    const toast = document.getElementById(id);
    if (toast) {
      toast.classList.remove('show');
      toast.classList.add('hide');
      setTimeout(() => {
        toast.remove();
      }, 400);
    }
  }

  // HTML 转义
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // 全局移除函数
  window.readlaterRemoveToast = removeToast;

  // 保存中状态
  let savingToastId = null;

  // 显示保存中
  function showSaving(title) {
    if (savingToastId) {
      removeToast(savingToastId);
    }
    savingToastId = createToast({
      type: 'saving',
      title: '正在保存...',
      message: title || '请稍候',
      duration: 0,
      showProgress: false,
      closable: false
    });
    return savingToastId;
  }

  // 显示成功
  function showSuccess(title, message) {
    if (savingToastId) {
      removeToast(savingToastId);
      savingToastId = null;
    }
    return createToast({
      type: 'success',
      title: title || '保存成功！',
      message: message || '',
      duration: 3000
    });
  }

  // 显示错误
  function showError(title, message) {
    if (savingToastId) {
      removeToast(savingToastId);
      savingToastId = null;
    }
    return createToast({
      type: 'error',
      title: title || '保存失败',
      message: message || '请检查网络连接或服务器设置',
      duration: 5000
    });
  }

  // 显示信息
  function showInfo(title, message) {
    return createToast({
      type: 'info',
      title: title,
      message: message,
      duration: 3000
    });
  }

  // 显示警告
  function showWarning(title, message) {
    return createToast({
      type: 'warning',
      title: title,
      message: message,
      duration: 4000
    });
  }

  // 更新现有 toast
  function updateToast(id, options) {
    const toast = document.getElementById(id);
    if (!toast) return;

    const { title, message, type } = options;
    
    if (type) {
      toast.className = `readlater-toast ${type} show`;
      const icon = toast.querySelector('.readlater-toast-icon');
      if (icon) {
        const icons = {
          saving: '⏳',
          success: '✅',
          error: '❌',
          warning: '⚠️',
          info: 'ℹ️'
        };
        icon.textContent = icons[type] || icons.info;
      }
    }

    if (title) {
      const titleEl = toast.querySelector('.readlater-toast-title');
      if (titleEl) titleEl.textContent = title;
    }

    if (message) {
      const msgEl = toast.querySelector('.readlater-toast-message');
      if (msgEl) msgEl.textContent = message;
    }
  }

  // 监听来自 background 的消息
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'READLATER_STATUS') {
      const { status, title, detail, articleId } = message;
      
      switch (status) {
        case 'saving':
          showSaving(title);
          break;
        case 'success':
          showSuccess(
            '保存成功！',
            title ? `"${truncate(title, 30)}" 已保存` : '文章已保存到稍后阅读'
          );
          break;
        case 'error':
          showError('保存失败', detail || '请检查网络连接或服务器设置');
          break;
        case 'warning':
          showWarning('注意', detail);
          break;
        case 'info':
          showInfo('提示', detail);
          break;
        case 'duplicate':
          showWarning('已存在', title ? `"${truncate(title, 30)}" 已经保存过了` : '该文章已保存');
          break;
      }
      
      sendResponse({ received: true });
    }
    
    return true;
  });

  // 字符串截断
  function truncate(str, len) {
    if (!str) return '';
    return str.length > len ? str.substring(0, len) + '...' : str;
  }

  // 导出 API（供其他脚本使用）
  window.ReadLaterToast = {
    show: createToast,
    remove: removeToast,
    saving: showSaving,
    success: showSuccess,
    error: showError,
    info: showInfo,
    warning: showWarning,
    update: updateToast
  };

  console.log('[ReadLater] 内容脚本已加载');
})();
