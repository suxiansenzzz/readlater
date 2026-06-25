# 2026-05-30 Bug修复合集

## 修复的问题

### 1. 搜索功能不工作
**原因**：`tags`是数组，但代码调用`toLowerCase()`方法
**修复**：使用`Array.isArray()`检查并用`some()`遍历
```javascript
// 错误
(a.tags && a.tags.toLowerCase().includes(q))

// 正确
(a.tags && Array.isArray(a.tags) && a.tags.some(tag => tag.toLowerCase().includes(q)))
```

### 2. 少数派文章抓取失败
**原因**：
- `fetch_article`调用参数顺序错误
- 返回数据缺少`word_count`、`reading_time`、`excerpt`字段

**修复**：
- 修改main.py调用方式：`fetch_article(url)` 而非 `fetch_article(url, title)`
- 在fetcher.py中添加字段计算

### 3. 打开文章显示"更新失败"
**原因**：前端使用PATCH方法，后端只有PUT端点
**修复**：添加PATCH端点
```python
@app.patch("/api/articles/{article_id}")
async def patch_article(article_id: int, update: ArticleUpdate):
    return await update_article(article_id, update)
```

### 4. 浏览器扩展显示"[object Object]"
**原因**：错误对象直接拼接字符串
**修复**：使用`typeof`检查并`JSON.stringify`转换

### 5. 浏览器扩展功能增强
- 添加服务器选择（本地/远程/自定义）
- 添加检查更新功能
- 使用`chrome.storage.sync`持久化配置

## 测试结果

| 功能 | 修复前 | 修复后 |
|------|--------|--------|
| 搜索"少数派" | ❌ 报错 | ✅ 正常 |
| 抓取sspai文章 | ❌ KeyError | ✅ 成功 |
| 打开文章 | ❌ 更新失败 | ✅ 正常 |
| PATCH API | ❌ 405错误 | ✅ 200成功 |

## 更新时间
2026-05-30 01:00