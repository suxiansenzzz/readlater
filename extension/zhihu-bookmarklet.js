/*
 * ReadLater - 知乎专用Bookmarklet
 * 用于保存知乎文章（手动选择内容模式）
 */

javascript:(function() {
    // 获取当前页面信息
    var url = window.location.href;
    var title = document.title.replace(' - 知乎', '').trim();
    
    // 尝试获取文章内容
    var content = '';
    var images = [];
    
    // 方法1: 从页面提取
    var article = document.querySelector('.RichText') || 
                  document.querySelector('article') ||
                  document.querySelector('.Post-RichTextContainer');
    
    if (article) {
        content = article.innerText;
        
        // 提取图片
        var imgs = article.querySelectorAll('img');
        imgs.forEach(function(img) {
            var src = img.src || img.getAttribute('data-src');
            if (src && src.indexOf('zhimg.com') > -1) {
                images.push(src);
            }
        });
    }
    
    // 如果无法自动提取，提示用户手动复制
    if (!content || content.length < 100) {
        // 创建一个浮动窗口让用户复制内容
        var modal = document.createElement('div');
        modal.id = 'readlater-modal';
        modal.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.8);z-index:99999;display:flex;align-items:center;justify-content:center;';
        
        modal.innerHTML = `
            <div style="background:white;border-radius:16px;padding:24px;max-width:600px;width:90%;max-height:80vh;overflow:auto;">
                <h2 style="margin:0 0 16px 0;color:#4f46e5;">📖 保存到ReadLater</h2>
                <p style="margin:0 0 8px 0;color:#666;">知乎有反爬保护，请手动复制文章内容：</p>
                <p style="margin:0 0 16px 0;font-size:14px;color:#999;">1. 在页面上选择(Ctrl+A)并复制文章内容<br>2. 粘贴到下面的文本框<br>3. 点击保存按钮</p>
                
                <div style="margin-bottom:16px;">
                    <label style="display:block;margin-bottom:4px;font-weight:bold;">文章标题：</label>
                    <input type="text" id="rl-title" value="${title}" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:8px;font-size:14px;">
                </div>
                
                <div style="margin-bottom:16px;">
                    <label style="display:block;margin-bottom:4px;font-weight:bold;">文章内容：</label>
                    <textarea id="rl-content" rows="10" placeholder="请粘贴文章内容..." style="width:100%;padding:8px;border:1px solid #ddd;border-radius:8px;font-size:14px;resize:vertical;"></textarea>
                </div>
                
                <div style="display:flex;gap:12px;justify-content:flex-end;">
                    <button onclick="document.getElementById('readlater-modal').remove();" style="padding:10px 20px;border:1px solid #ddd;border-radius:8px;background:white;cursor:pointer;">取消</button>
                    <button onclick="saveToReadLater()" style="padding:10px 20px;border:none;border-radius:8px;background:#4f46e5;color:white;cursor:pointer;">保存</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // 保存函数
        window.saveToReadLater = function() {
            var title = document.getElementById('rl-title').value;
            var content = document.getElementById('rl-content').value;
            
            if (!content) {
                alert('请输入文章内容');
                return;
            }
            
            // 发送到ReadLater服务器
            fetch('http://192.168.31.5:8000/api/save', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    url: url,
                    title: title,
                    content: content  // 需要后端支持手动内容
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('✅ 保存成功！');
                    document.getElementById('readlater-modal').remove();
                } else {
                    alert('❌ 保存失败：' + (data.detail || '未知错误'));
                }
            })
            .catch(e => alert('❌ 错误：' + e));
        };
        
        return;
    }
    
    // 如果能自动提取，直接保存
    fetch('http://192.168.31.5:8000/api/save', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            url: url,
            title: title
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            alert('✅ 保存成功！');
        } else {
            alert('❌ 保存失败：' + (data.detail || '未知错误'));
        }
    })
    .catch(e => alert('❌ 错误：' + e));
})();
