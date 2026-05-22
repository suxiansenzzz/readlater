"""
稍后阅读 - ReadLater
一个轻量级的网页内容抓取和阅读应用
"""
import os
import json
import sqlite3
from datetime import datetime
from typing import Optional, List

import trafilatura
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# 配置
DB_PATH = os.path.join(os.path.dirname(__file__), "readlater.db")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")

app = FastAPI(title="ReadLater", version="0.1.0")

# ==================== 数据模型 ====================

class ArticleCreate(BaseModel):
    url: str
    title: Optional[str] = None
    tags: Optional[List[str]] = []

class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    is_read: Optional[bool] = None
    is_favorite: Optional[bool] = None

class Article(BaseModel):
    id: int
    url: str
    title: str
    content: str
    excerpt: str
    tags: List[str]
    is_read: bool
    is_favorite: bool
    created_at: str
    word_count: int
    reading_time: int  # 分钟

# ==================== 数据库 ====================

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库"""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            excerpt TEXT,
            tags TEXT DEFAULT '[]',
            is_read INTEGER DEFAULT 0,
            is_favorite INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            word_count INTEGER DEFAULT 0,
            reading_time INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON articles(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_is_read ON articles(is_read)")
    conn.commit()
    conn.close()

# ==================== 抓取功能 ====================

def fetch_article(url: str, custom_title: str = None):
    """抓取网页内容"""
    try:
        # 下载网页
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            raise Exception("无法下载网页")
        
        # 提取正文
        content = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            no_fallback=False
        )
        
        if not content:
            raise Exception("无法提取正文内容")
        
        # 提取元数据
        metadata = trafilatura.extract_metadata(downloaded)
        
        # 获取标题
        title = custom_title or (metadata.title if metadata else None) or "无标题"
        
        # 生成摘要（取前200字）
        excerpt = content[:200].replace('\n', ' ').strip()
        if len(content) > 200:
            excerpt += "..."
        
        # 计算字数和阅读时间
        word_count = len(content)
        reading_time = max(1, word_count // 500)  # 假设每分钟500字
        
        return {
            "url": url,
            "title": title,
            "content": content,
            "excerpt": excerpt,
            "word_count": word_count,
            "reading_time": reading_time
        }
    except Exception as e:
        raise Exception(f"抓取失败: {str(e)}")

# ==================== API路由 ====================

@app.on_event("startup")
async def startup():
    """应用启动时初始化数据库"""
    init_db()

@app.get("/")
async def index():
    """返回前端页面"""
    index_path = os.path.join(STATIC_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.post("/api/save")
async def save_article(article: ArticleCreate):
    """保存文章"""
    conn = get_db()
    
    # 检查是否已存在
    existing = conn.execute(
        "SELECT id FROM articles WHERE url = ?", (article.url,)
    ).fetchone()
    
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="该链接已保存")
    
    try:
        # 抓取文章
        data = fetch_article(article.url, article.title)
        
        # 插入数据库
        now = datetime.now().isoformat()
        tags = json.dumps(article.tags or [], ensure_ascii=False)
        
        cursor = conn.execute("""
            INSERT INTO articles (url, title, content, excerpt, tags, created_at, word_count, reading_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["url"],
            data["title"],
            data["content"],
            data["excerpt"],
            tags,
            now,
            data["word_count"],
            data["reading_time"]
        ))
        
        article_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "message": "保存成功",
            "article_id": article_id
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/articles")
async def list_articles(
    page: int = 1,
    per_page: int = 20,
    is_read: Optional[bool] = None,
    is_favorite: Optional[bool] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None
):
    """获取文章列表"""
    conn = get_db()
    
    # 构建查询
    conditions = []
    params = []
    
    if is_read is not None:
        conditions.append("is_read = ?")
        params.append(1 if is_read else 0)
    
    if is_favorite is not None:
        conditions.append("is_favorite = ?")
        params.append(1 if is_favorite else 0)
    
    if tag:
        conditions.append("tags LIKE ?")
        params.append(f"%{tag}%")
    
    if search:
        conditions.append("(title LIKE ? OR content LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    
    # 获取总数
    total = conn.execute(
        f"SELECT COUNT(*) FROM articles {where}", params
    ).fetchone()[0]
    
    # 获取分页数据
    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT * FROM articles {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()
    
    conn.close()
    
    # 格式化结果
    articles = []
    for row in rows:
        articles.append({
            "id": row["id"],
            "url": row["url"],
            "title": row["title"],
            "excerpt": row["excerpt"],
            "tags": json.loads(row["tags"]),
            "is_read": bool(row["is_read"]),
            "is_favorite": bool(row["is_favorite"]),
            "created_at": row["created_at"],
            "word_count": row["word_count"],
            "reading_time": row["reading_time"]
        })
    
    return {
        "articles": articles,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page
    }

@app.get("/api/articles/{article_id}")
async def get_article(article_id: int):
    """获取文章详情"""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM articles WHERE id = ?", (article_id,)
    ).fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="文章不存在")
    
    return {
        "id": row["id"],
        "url": row["url"],
        "title": row["title"],
        "content": row["content"],
        "excerpt": row["excerpt"],
        "tags": json.loads(row["tags"]),
        "is_read": bool(row["is_read"]),
        "is_favorite": bool(row["is_favorite"]),
        "created_at": row["created_at"],
        "word_count": row["word_count"],
        "reading_time": row["reading_time"]
    }

@app.put("/api/articles/{article_id}")
async def update_article(article_id: int, update: ArticleUpdate):
    """更新文章"""
    conn = get_db()
    
    # 检查文章是否存在
    existing = conn.execute(
        "SELECT id FROM articles WHERE id = ?", (article_id,)
    ).fetchone()
    
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="文章不存在")
    
    # 构建更新语句
    updates = []
    params = []
    
    if update.title is not None:
        updates.append("title = ?")
        params.append(update.title)
    
    if update.tags is not None:
        updates.append("tags = ?")
        params.append(json.dumps(update.tags, ensure_ascii=False))
    
    if update.is_read is not None:
        updates.append("is_read = ?")
        params.append(1 if update.is_read else 0)
    
    if update.is_favorite is not None:
        updates.append("is_favorite = ?")
        params.append(1 if update.is_favorite else 0)
    
    if updates:
        params.append(article_id)
        conn.execute(
            f"UPDATE articles SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
    
    conn.close()
    return {"success": True}

@app.delete("/api/articles/{article_id}")
async def delete_article(article_id: int):
    """删除文章"""
    conn = get_db()
    
    result = conn.execute(
        "DELETE FROM articles WHERE id = ?", (article_id,)
    )
    conn.commit()
    conn.close()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="文章不存在")
    
    return {"success": True}

@app.get("/api/stats")
async def get_stats():
    """获取统计信息"""
    conn = get_db()
    
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    read = conn.execute("SELECT COUNT(*) FROM articles WHERE is_read = 1").fetchone()[0]
    unread = total - read
    favorites = conn.execute("SELECT COUNT(*) FROM articles WHERE is_favorite = 1").fetchone()[0]
    
    conn.close()
    
    return {
        "total": total,
        "read": read,
        "unread": unread,
        "favorites": favorites
    }

# ==================== 主程序 ====================

if __name__ == "__main__":
    import uvicorn
    print("🚀 ReadLater 启动中...")
    print("📖 访问 http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
