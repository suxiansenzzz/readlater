# 2026-05-29 批注加载失败修复

## 问题概述

用户反馈批注加载失败，点击批注按钮后显示"加载批注失败"错误。

## 根因分析

**现象：** 批注侧边栏无法加载批注数据，控制台显示API调用失败。

**根因：** 前端API路径与后端端点不匹配，以及数据格式不匹配。

### 具体问题

1. **API路径不匹配**
   - 前端调用：`/api/annotations/${articleId}`
   - 后端端点：`/api/articles/${article_id}/annotations`
   - 结果：404错误

2. **响应格式不匹配**
   - 前端期望：直接返回数组 `[{...}, {...}]`
   - 后端返回：对象格式 `{"annotations": [...], "count": N}`
   - 结果：`annotations.length` 报错

3. **字段名不匹配**
   - 前端使用：`a.text`
   - 后端返回：`highlight_text`
   - 结果：显示undefined

## 修复方案

### 1. 修复 `loadAnnotations` 函数

**修改前：**
```javascript
async function loadAnnotations(articleId) {
    try {
        const res = await fetch(`/api/annotations/${articleId}`);
        if (!res.ok) throw new Error('Failed');
        const annotations = await res.json();
        const content = document.getElementById('annotationsContent');
        if (annotations.length === 0) {
            // ...
        } else {
            content.innerHTML = annotations.map(a => `
                <div class="annotation-item">
                    <div class="annotation-color" style="background: ${a.color}"></div>
                    <div class="annotation-content">
                        <div class="annotation-text">${a.text}</div>
                        ${a.note ? `<div class="annotation-note">${a.note}</div>` : ''}
                        <div class="annotation-time">${formatDate(a.created_at)}</div>
                    </div>
                    <button class="btn btn-ghost btn-sm" onclick="deleteAnnotation(${a.id})" title="删除批注">🗑️</button>
                </div>
            `).join('');
        }
    } catch (err) {
        showToast('加载批注失败', 'error');
    }
}
```

**修改后：**
```javascript
async function loadAnnotations(articleId) {
    try {
        const res = await fetch(`/api/articles/${articleId}/annotations`);
        if (!res.ok) throw new Error('Failed');
        const data = await res.json();
        const annotations = data.annotations || [];
        const content = document.getElementById('annotationsContent');
        if (annotations.length === 0) {
            // ...
        } else {
            content.innerHTML = annotations.map(a => `
                <div class="annotation-item">
                    <div class="annotation-color" style="background: ${a.color}"></div>
                    <div class="annotation-content">
                        <div class="annotation-text">${a.highlight_text}</div>
                        ${a.note ? `<div class="annotation-note">${a.note}</div>` : ''}
                        <div class="annotation-time">${formatDate(a.created_at)}</div>
                    </div>
                    <button class="btn btn-ghost btn-sm" onclick="deleteAnnotation(${a.id})" title="删除批注">🗑️</button>
                </div>
            `).join('');
        }
    } catch (err) {
        showToast('加载批注失败', 'error');
    }
}
```

**关键修改：**
- 修改API路径为 `/api/articles/${articleId}/annotations`
- 从响应对象中提取 `data.annotations`
- 修改字段名从 `a.text` 改为 `a.highlight_text`

### 2. 修复 `applyAnnotations` 函数

**修改前：**
```javascript
function applyAnnotations(annotations) {
    const body = document.querySelector('.reading-body');
    if (!body) return;
    annotations.forEach(ann => {
        const regex = new RegExp(escapeRegex(ann.text), 'gi');
        // ...
    });
}
```

**修改后：**
```javascript
function applyAnnotations(annotations) {
    const body = document.querySelector('.reading-body');
    if (!body) return;
    annotations.forEach(ann => {
        const text = ann.highlight_text || ann.text;
        const regex = new RegExp(escapeRegex(text), 'gi');
        // ...
    });
}
```

**关键修改：**
- 兼容处理 `ann.highlight_text` 和 `ann.text` 两种字段名

## 测试结果

| 测试项 | 修复前 | 修复后 |
|--------|--------|--------|
| 批注侧边栏加载 | ❌ 显示"加载批注失败" | ✅ 正常加载批注列表 |
| 批注数据格式 | ❌ undefined | ✅ 正确显示高亮文本 |
| API调用 | ❌ 404错误 | ✅ 200成功 |
| 批注高亮显示 | ❌ 不显示 | ✅ 正常显示 |

## 相关文件

- 前端：`/opt/data/workspace/readlater/static/index_v3.html`
- 后端：`/opt/data/workspace/readlater/backend/main.py`
- 批注模块：`/opt/data/workspace/readlater/backend/annotations.py`

## 经验教训

1. **API路径一致性** - 前端调用路径必须与后端端点定义完全匹配
2. **数据格式约定** - 前后端需要约定统一的数据格式（数组 vs 包装对象）
3. **字段名映射** - 后端数据库字段名与前端显示字段名需要明确映射
4. **向后兼容** - 修改字段名时要考虑兼容性，使用 `||` 操作符处理两种情况

## 更新时间

2026-05-29 20:45