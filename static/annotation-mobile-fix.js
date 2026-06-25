/**
 * ReadLater 批注功能手机端触摸支持
 * 为主代码的批注功能添加触摸事件支持
 */

// 等待DOM加载完成
document.addEventListener('DOMContentLoaded', function() {
    console.log('批注触摸支持脚本已加载');
    addTouchSupport();
});

/**
 * 添加触摸事件支持
 * 配合主代码的selectionchange事件使用
 */
function addTouchSupport() {
    let isTouching = false;
    
    // 监听触摸开始
    document.addEventListener('touchstart', function(e) {
        isTouching = true;
    }, { passive: true });
    
    // 监听触摸结束
    document.addEventListener('touchend', function(e) {
        isTouching = false;
        // 触摸结束后，触发文本选择检查
        // 延迟一下，让浏览器完成选择
        setTimeout(function() {
            // 触发selectionchange事件的处理
            if (typeof checkTextSelection === 'function') {
                checkTextSelection();
            }
        }, 500);
    }, { passive: true });
    
    console.log('触摸事件支持已添加');
}