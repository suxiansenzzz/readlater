"""
ReadLater v0.3.0 - 稍后阅读（增强版）
新增功能：存档、标签管理、导出、批量操作、排序、高亮笔记
"""
import os
import json
import csv
import sqlite3
import hashlib
import re
import io
from datetime import datetime
from typing import Optional, List
from urllib.parse import urljoin, urlparse

import trafilatura
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

# 配置
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "readlater.db")
IMAGES_DIR = os.path.join(BASE_DIR, "images")
STATIC_DIR = os.path.join(BASE_DIR, "..", "static")

# 确保目录存在
os.makedirs(IMAGES_DIR, exist_ok=True)

app = FastAPI(title="ReadLater", version="0.3.0")

# 添加CORS中间件，允许浏览器扩展跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境应该限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 数据模型 ====================

class ArticleCreate(BaseModel):
    url: str
    title: Optional[str] = None
    tags: Optional[List[str]] = []
    content: Optional[str] = None

class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    is_read: Optional[bool] = None
    is_favorite: Optional[bool] = None
    is_archived: Optional[bool] = None
    reading_progress: Optional[float] = None

class HighlightCreate(BaseModel):
    article_id: int
    text: str
    note: Optional[str] = None
    position: Optional[int] = None

class HighlightUpdate(BaseModel):
    note: Optional[str] = None

class BatchOperation(BaseModel):
    article_ids: List[int]
    action: str  # mark_read, mark_unread, archive, unarchive, favorite, unfavorite, delete
    tags: Optional[List[str]] = None  # for add_tags, remove_tags

# ==================== 数据库 ====================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    
    # 文章表（增加 archived, reading_progress 字段）
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
            is_archived INTEGER DEFAULT 0,
            reading_progress REAL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            word_count INTEGER DEFAULT 0,
            reading_time INTEGER DEFAULT 0,
            cover_image TEXT,
            domain TEXT
        )
    """)
    
    # 图片表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            original_url TEXT NOT NULL,
            local_path TEXT NOT NULL,
            filename TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
        )
    """)
    
    # 高亮/笔记表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS highlights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            note TEXT,
            position INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
        )
    """)
    
    # 迁移旧数据库（添加新列）- 必须在创建索引之前
    try:
        conn.execute("ALTER TABLE articles ADD COLUMN is_archived INTEGER DEFAULT 0")
    except:
        pass
    try:
        conn.execute("ALTER TABLE articles ADD COLUMN reading_progress REAL DEFAULT 0")
    except:
        pass
    try:
        conn.execute("ALTER TABLE articles ADD COLUMN updated_at TEXT")
    except:
        pass
    try:
        conn.execute("ALTER TABLE articles ADD COLUMN domain TEXT")
    except:
        pass
    
    # 索引（在迁移之后创建）
    conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON articles(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_is_read ON articles(is_read)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_is_archived ON articles(is_archived)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_is_favorite ON articles(is_favorite)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_domain ON articles(domain)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_images_article ON images(article_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_highlights_article ON highlights(article_id)")
    
    conn.commit()
    conn.close()

# ==================== 图片处理 ====================

def get_image_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()

def get_image_extension(url: str, content_type: str = None) -> str:
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp']:
        if path.endswith(ext):
            return ext
    
    if content_type:
        if 'jpeg' in content_type or 'jpg' in content_type:
            return '.jpg'
        elif 'png' in content_type:
            return '.png'
        elif 'gif' in content_type:
            return '.gif'
        elif 'webp' in content_type:
            return '.webp'
    
    return '.jpg'

async def download_image(client: httpx.AsyncClient, url: str, article_id: int) -> Optional[str]:
    try:
        response = await client.get(url, timeout=10, follow_redirects=True)
        if response.status_code == 200:
            url_hash = get_image_hash(url)
            ext = get_image_extension(url, response.headers.get('content-type'))
            filename = f"{url_hash}{ext}"
            filepath = os.path.join(IMAGES_DIR, filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return filename
    except Exception as e:
        print(f"下载图片失败 {url}: {e}")
    return None

def extract_images_from_html(html: str, base_url: str) -> List[str]:
    img_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
    urls = re.findall(img_pattern, html, re.IGNORECASE)
    
    absolute_urls = []
    for url in urls:
        if url.startswith('data:'):
            continue
        if url.startswith('//'):
            url = 'https:' + url
        elif not url.startswith(('http://', 'https://')):
            url = urljoin(base_url, url)
        absolute_urls.append(url)
    
    return absolute_urls

def extract_images_from_content(content: str) -> List[str]:
    img_pattern = r'!\[[^\]]*\]\(([^)]+)\)'
    urls = re.findall(img_pattern, content)
    
    html_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
    urls.extend(re.findall(html_pattern, content))
    
    return urls

def replace_image_urls_in_content(content: str, url_mapping: dict) -> str:
    """替换内容中的图片URL为本地路径"""
    result = content
    
    # 替换Markdown格式的图片
    for original_url, local_path in url_mapping.items():
        # 替换 ![](url) 格式
        markdown_pattern = r'!\[([^\]]*)\]\(' + re.escape(original_url) + r'\)'
        result = re.sub(markdown_pattern, r'![\1](' + local_path + r')', result)
        
        # 替换 <img src="url"> 格式
        html_pattern = r'(<img[^>]+src=["\'])' + re.escape(original_url) + r'(["\'])'
        result = re.sub(html_pattern, r'\1' + local_path + r'\2', result)
    
    return result

async def download_article_images(html: str, content: str, base_url: str, article_id: int) -> List[dict]:
    images = []
    url_mapping = {}  # 原始URL -> 本地路径的映射
    
    img_urls = extract_images_from_html(html, base_url)
    img_urls.extend(extract_images_from_content(content))
    
    img_urls = list(set(img_urls))
    
    if not img_urls:
        return images, content
    
    async with httpx.AsyncClient() as client:
        for url in img_urls:
            filename = await download_image(client, url, article_id)
            if filename:
                local_path = f'/images/{filename}'
                images.append({
                    'original_url': url,
                    'local_path': local_path,
                    'filename': filename
                })
                url_mapping[url] = local_path
    
    # 替换内容中的图片URL为本地路径
    updated_content = replace_image_urls_in_content(content, url_mapping)
    
    return images, updated_content

# ==================== 抓取功能 ====================

def fetch_article(url: str, custom_title: str = None):
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            raise Exception("无法下载网页")
        
        content = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            include_images=True,
            include_links=True
        )
        
        if not content:
            raise Exception("无法提取正文内容")
        
        metadata = trafilatura.extract_metadata(downloaded)
        
        title = custom_title or (metadata.title if metadata else None) or "无标题"
        
        excerpt = content[:200].replace('\n', ' ').strip()
        if len(content) > 200:
            excerpt += "..."
        
        word_count = len(content)
        reading_time = max(1, word_count // 500)
        
        cover_image = None
        if metadata and metadata.image:
            cover_image = metadata.image
        
        # 提取域名
        parsed = urlparse(url)
        domain = parsed.netloc
        
        return {
            "url": url,
            "title": title,
            "content": content,
            "excerpt": excerpt,
            "word_count": word_count,
            "reading_time": reading_time,
            "cover_image": cover_image,
            "html": downloaded,
            "domain": domain
        }
    except Exception as e:
        raise Exception(f"抓取失败: {str(e)}")

# ==================== API路由 ====================

@app.on_event("startup")
async def startup():
    init_db()

@app.get("/")
async def index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/images/{filename}")
async def get_image(filename: str):
    filepath = os.path.join(IMAGES_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(filepath)

@app.post("/api/save")
async def save_article(article: ArticleCreate):
    conn = get_db()
    
    existing = conn.execute(
        "SELECT id FROM articles WHERE url = ?", (article.url,)
    ).fetchone()
    
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="该链接已保存")
    
    try:
        if article.content:
            content = article.content
            title = article.title or "无标题"
            cover_image = None
            html = ""
            parsed = urlparse(article.url)
            domain = parsed.netloc
            
            excerpt = content[:200].replace('\n', ' ').strip()
            if len(content) > 200:
                excerpt += "..."
            
            word_count = len(content)
            reading_time = max(1, word_count // 500)
            
            data = {
                "url": article.url,
                "title": title,
                "content": content,
                "excerpt": excerpt,
                "word_count": word_count,
                "reading_time": reading_time,
                "cover_image": cover_image,
                "html": html,
                "domain": domain
            }
        else:
            data = fetch_article(article.url, article.title)
        
        now = datetime.now().isoformat()
        tags = json.dumps(article.tags or [], ensure_ascii=False)
        
        cursor = conn.execute("""
            INSERT INTO articles (url, title, content, excerpt, tags, created_at, word_count, reading_time, cover_image, domain)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["url"],
            data["title"],
            data["content"],
            data["excerpt"],
            tags,
            now,
            data["word_count"],
            data["reading_time"],
            data["cover_image"],
            data.get("domain", "")
        ))
        
        article_id = cursor.lastrowid
        conn.commit()
        
        # 下载图片并更新内容中的图片URL
        images, updated_content = await download_article_images(
            data["html"], 
            data["content"], 
            data["url"], 
            article_id
        )
        
        # 如果内容被更新了，更新数据库中的内容
        if updated_content != data["content"]:
            conn.execute(
                "UPDATE articles SET content = ? WHERE id = ?",
                (updated_content, article_id)
            )
            conn.commit()
        
        for img in images:
            conn.execute("""
                INSERT INTO images (article_id, original_url, local_path, filename, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (article_id, img['original_url'], img['local_path'], img['filename'], now))
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "message": "保存成功",
            "article_id": article_id,
            "images_count": len(images)
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
    is_archived: Optional[bool] = None,
    tag: Optional[str] = None,
    domain: Optional[str] = None,
    search: Optional[str] = None,
    sort: Optional[str] = "created_at",  # created_at, title, word_count, reading_time
    order: Optional[str] = "desc"  # asc, desc
):
    conn = get_db()
    
    conditions = []
    params = []
    
    if is_read is not None:
        conditions.append("is_read = ?")
        params.append(1 if is_read else 0)
    
    if is_favorite is not None:
        conditions.append("is_favorite = ?")
        params.append(1 if is_favorite else 0)
    
    if is_archived is not None:
        conditions.append("is_archived = ?")
        params.append(1 if is_archived else 0)
    
    if tag:
        conditions.append("tags LIKE ?")
        params.append(f"%{tag}%")
    
    if domain:
        conditions.append("domain = ?")
        params.append(domain)
    
    if search:
        conditions.append("(title LIKE ? OR content LIKE ? OR excerpt LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    
    # 排序
    valid_sorts = {"created_at", "title", "word_count", "reading_time", "updated_at"}
    if sort not in valid_sorts:
        sort = "created_at"
    order_sql = "DESC" if order.lower() == "desc" else "ASC"
    
    total = conn.execute(f"SELECT COUNT(*) FROM articles {where}", params).fetchone()[0]
    
    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT * FROM articles {where} ORDER BY {sort} {order_sql} LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()
    
    articles = []
    for row in rows:
        img_count = conn.execute(
            "SELECT COUNT(*) FROM images WHERE article_id = ?", (row["id"],)
        ).fetchone()[0]
        
        highlight_count = conn.execute(
            "SELECT COUNT(*) FROM highlights WHERE article_id = ?", (row["id"],)
        ).fetchone()[0]
        
        articles.append({
            "id": row["id"],
            "url": row["url"],
            "title": row["title"],
            "excerpt": row["excerpt"],
            "tags": json.loads(row["tags"]),
            "is_read": bool(row["is_read"]),
            "is_favorite": bool(row["is_favorite"]),
            "is_archived": bool(row["is_archived"]),
            "reading_progress": row["reading_progress"],
            "created_at": row["created_at"],
            "word_count": row["word_count"],
            "reading_time": row["reading_time"],
            "cover_image": row["cover_image"],
            "domain": row["domain"],
            "images_count": img_count,
            "highlights_count": highlight_count
        })
    
    conn.close()
    
    return {
        "articles": articles,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page
    }

@app.get("/api/articles/{article_id}")
async def get_article(article_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="文章不存在")
    
    images = conn.execute(
        "SELECT * FROM images WHERE article_id = ?", (article_id,)
    ).fetchall()
    
    highlights = conn.execute(
        "SELECT * FROM highlights WHERE article_id = ? ORDER BY position", (article_id,)
    ).fetchall()
    
    conn.close()
    
    return {
        "id": row["id"],
        "url": row["url"],
        "title": row["title"],
        "content": row["content"],
        "excerpt": row["excerpt"],
        "tags": json.loads(row["tags"]),
        "is_read": bool(row["is_read"]),
        "is_favorite": bool(row["is_favorite"]),
        "is_archived": bool(row["is_archived"]),
        "reading_progress": row["reading_progress"],
        "created_at": row["created_at"],
        "word_count": row["word_count"],
        "reading_time": row["reading_time"],
        "cover_image": row["cover_image"],
        "domain": row["domain"],
        "images": [{
            "id": img["id"],
            "original_url": img["original_url"],
            "local_path": img["local_path"],
            "filename": img["filename"]
        } for img in images],
        "highlights": [{
            "id": h["id"],
            "text": h["text"],
            "note": h["note"],
            "position": h["position"],
            "created_at": h["created_at"]
        } for h in highlights]
    }

@app.put("/api/articles/{article_id}")
async def update_article(article_id: int, update: ArticleUpdate):
    conn = get_db()
    
    existing = conn.execute("SELECT id FROM articles WHERE id = ?", (article_id,)).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="文章不存在")
    
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
    
    if update.is_archived is not None:
        updates.append("is_archived = ?")
        params.append(1 if update.is_archived else 0)
    
    if update.reading_progress is not None:
        updates.append("reading_progress = ?")
        params.append(update.reading_progress)
    
    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(article_id)
        conn.execute(f"UPDATE articles SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    
    conn.close()
    return {"success": True}

@app.delete("/api/articles/{article_id}")
async def delete_article(article_id: int):
    conn = get_db()
    
    images = conn.execute(
        "SELECT filename FROM images WHERE article_id = ?", (article_id,)
    ).fetchall()
    
    for img in images:
        filepath = os.path.join(IMAGES_DIR, img["filename"])
        if os.path.exists(filepath):
            os.remove(filepath)
    
    conn.execute("DELETE FROM images WHERE article_id = ?", (article_id,))
    conn.execute("DELETE FROM highlights WHERE article_id = ?", (article_id,))
    conn.execute("DELETE FROM articles WHERE id = ?", (article_id,))
    conn.commit()
    conn.close()
    
    return {"success": True}

# ==================== 批量操作 ====================

@app.post("/api/articles/batch")
async def batch_operation(operation: BatchOperation):
    conn = get_db()
    
    ids_placeholder = ",".join("?" * len(operation.article_ids))
    
    if operation.action == "mark_read":
        conn.execute(f"UPDATE articles SET is_read = 1, updated_at = ? WHERE id IN ({ids_placeholder})", 
                     [datetime.now().isoformat()] + operation.article_ids)
    elif operation.action == "mark_unread":
        conn.execute(f"UPDATE articles SET is_read = 0, updated_at = ? WHERE id IN ({ids_placeholder})", 
                     [datetime.now().isoformat()] + operation.article_ids)
    elif operation.action == "archive":
        conn.execute(f"UPDATE articles SET is_archived = 1, updated_at = ? WHERE id IN ({ids_placeholder})", 
                     [datetime.now().isoformat()] + operation.article_ids)
    elif operation.action == "unarchive":
        conn.execute(f"UPDATE articles SET is_archived = 0, updated_at = ? WHERE id IN ({ids_placeholder})", 
                     [datetime.now().isoformat()] + operation.article_ids)
    elif operation.action == "favorite":
        conn.execute(f"UPDATE articles SET is_favorite = 1, updated_at = ? WHERE id IN ({ids_placeholder})", 
                     [datetime.now().isoformat()] + operation.article_ids)
    elif operation.action == "unfavorite":
        conn.execute(f"UPDATE articles SET is_favorite = 0, updated_at = ? WHERE id IN ({ids_placeholder})", 
                     [datetime.now().isoformat()] + operation.article_ids)
    elif operation.action == "delete":
        # 删除图片文件
        for article_id in operation.article_ids:
            images = conn.execute("SELECT filename FROM images WHERE article_id = ?", (article_id,)).fetchall()
            for img in images:
                filepath = os.path.join(IMAGES_DIR, img["filename"])
                if os.path.exists(filepath):
                    os.remove(filepath)
        
        conn.execute(f"DELETE FROM images WHERE article_id IN ({ids_placeholder})", operation.article_ids)
        conn.execute(f"DELETE FROM highlights WHERE article_id IN ({ids_placeholder})", operation.article_ids)
        conn.execute(f"DELETE FROM articles WHERE id IN ({ids_placeholder})", operation.article_ids)
    elif operation.action == "add_tags" and operation.tags:
        for article_id in operation.article_ids:
            row = conn.execute("SELECT tags FROM articles WHERE id = ?", (article_id,)).fetchone()
            if row:
                current_tags = json.loads(row["tags"])
                new_tags = list(set(current_tags + operation.tags))
                conn.execute("UPDATE articles SET tags = ?, updated_at = ? WHERE id = ?", 
                           (json.dumps(new_tags, ensure_ascii=False), datetime.now().isoformat(), article_id))
    elif operation.action == "remove_tags" and operation.tags:
        for article_id in operation.article_ids:
            row = conn.execute("SELECT tags FROM articles WHERE id = ?", (article_id,)).fetchone()
            if row:
                current_tags = json.loads(row["tags"])
                new_tags = [t for t in current_tags if t not in operation.tags]
                conn.execute("UPDATE articles SET tags = ?, updated_at = ? WHERE id = ?", 
                           (json.dumps(new_tags, ensure_ascii=False), datetime.now().isoformat(), article_id))
    else:
        conn.close()
        raise HTTPException(status_code=400, detail="无效的操作")
    
    conn.commit()
    conn.close()
    
    return {"success": True, "affected": len(operation.article_ids)}

# ==================== 标签管理 ====================

@app.get("/api/tags")
async def get_tags():
    conn = get_db()
    
    rows = conn.execute("SELECT tags FROM articles").fetchall()
    
    tag_counts = {}
    for row in rows:
        tags = json.loads(row["tags"])
        for tag in tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    conn.close()
    
    # 按使用次数排序
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    
    return {
        "tags": [{"name": name, "count": count} for name, count in sorted_tags]
    }

# ==================== 高亮/笔记 ====================

@app.post("/api/highlights")
async def create_highlight(highlight: HighlightCreate):
    conn = get_db()
    
    now = datetime.now().isoformat()
    cursor = conn.execute("""
        INSERT INTO highlights (article_id, text, note, position, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (highlight.article_id, highlight.text, highlight.note, highlight.position, now))
    
    highlight_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "highlight_id": highlight_id
    }

@app.get("/api/highlights/{article_id}")
async def get_highlights(article_id: int):
    conn = get_db()
    
    rows = conn.execute(
        "SELECT * FROM highlights WHERE article_id = ? ORDER BY position", (article_id,)
    ).fetchall()
    
    conn.close()
    
    return {
        "highlights": [{
            "id": row["id"],
            "article_id": row["article_id"],
            "text": row["text"],
            "note": row["note"],
            "position": row["position"],
            "created_at": row["created_at"]
        } for row in rows]
    }

@app.put("/api/highlights/{highlight_id}")
async def update_highlight(highlight_id: int, update: HighlightUpdate):
    conn = get_db()
    
    existing = conn.execute("SELECT id FROM highlights WHERE id = ?", (highlight_id,)).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="高亮不存在")
    
    if update.note is not None:
        conn.execute("UPDATE highlights SET note = ? WHERE id = ?", (update.note, highlight_id))
    
    conn.commit()
    conn.close()
    
    return {"success": True}

@app.delete("/api/highlights/{highlight_id}")
async def delete_highlight(highlight_id: int):
    conn = get_db()
    
    conn.execute("DELETE FROM highlights WHERE id = ?", (highlight_id,))
    conn.commit()
    conn.close()
    
    return {"success": True}

# ==================== 导出功能 ====================

@app.get("/api/export/json")
async def export_json():
    conn = get_db()
    
    rows = conn.execute("SELECT * FROM articles ORDER BY created_at DESC").fetchall()
    
    articles = []
    for row in rows:
        articles.append({
            "url": row["url"],
            "title": row["title"],
            "content": row["content"],
            "tags": json.loads(row["tags"]),
            "is_read": bool(row["is_read"]),
            "is_favorite": bool(row["is_favorite"]),
            "is_archived": bool(row["is_archived"]),
            "created_at": row["created_at"],
            "word_count": row["word_count"]
        })
    
    conn.close()
    
    return StreamingResponse(
        iter([json.dumps(articles, ensure_ascii=False, indent=2)]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=readlater_export.json"}
    )

@app.get("/api/export/csv")
async def export_csv():
    conn = get_db()
    
    rows = conn.execute("SELECT * FROM articles ORDER BY created_at DESC").fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 写入表头
    writer.writerow(["URL", "Title", "Tags", "Is Read", "Is Favorite", "Is Archived", "Created At", "Word Count"])
    
    for row in rows:
        writer.writerow([
            row["url"],
            row["title"],
            ", ".join(json.loads(row["tags"])),
            "Yes" if row["is_read"] else "No",
            "Yes" if row["is_favorite"] else "No",
            "Yes" if row["is_archived"] else "No",
            row["created_at"],
            row["word_count"]
        ])
    
    conn.close()
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=readlater_export.csv"}
    )

@app.get("/api/export/html")
async def export_html():
    conn = get_db()
    
    rows = conn.execute("SELECT * FROM articles ORDER BY created_at DESC").fetchall()
    
    html_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>ReadLater 导出</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        article { margin-bottom: 30px; padding-bottom: 20px; border-bottom: 1px solid #eee; }
        h1 { color: #4f46e5; }
        h2 { margin-bottom: 5px; }
        .meta { color: #666; font-size: 14px; margin-bottom: 10px; }
        .tags { display: inline-block; background: #f0f0f0; padding: 2px 8px; border-radius: 12px; font-size: 12px; margin-right: 5px; }
        .content { line-height: 1.6; }
    </style>
</head>
<body>
    <h1>📖 ReadLater 导出</h1>
    <p>导出时间: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
    <hr>
"""
    
    for row in rows:
        tags_html = "".join([f'<span class="tags">{tag}</span>' for tag in json.loads(row["tags"])])
        html_content += f"""
    <article>
        <h2><a href="{row['url']}">{row['title']}</a></h2>
        <div class="meta">
            {row['created_at']} · {row['word_count']}字
            {' · ✅已读' if row['is_read'] else ''}
            {' · ⭐收藏' if row['is_favorite'] else ''}
            {' · 📦已存档' if row['is_archived'] else ''}
        </div>
        <div class="tags-container">{tags_html}</div>
        <div class="content">{row['content'][:500]}{'...' if len(row['content']) > 500 else ''}</div>
    </article>
"""
    
    html_content += """
</body>
</html>"""
    
    conn.close()
    
    return StreamingResponse(
        iter([html_content]),
        media_type="text/html",
        headers={"Content-Disposition": "attachment; filename=readlater_export.html"}
    )

# ==================== 统计 ====================

@app.get("/api/stats")
async def get_stats():
    conn = get_db()
    
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    read = conn.execute("SELECT COUNT(*) FROM articles WHERE is_read = 1").fetchone()[0]
    unread = total - read
    favorites = conn.execute("SELECT COUNT(*) FROM articles WHERE is_favorite = 1").fetchone()[0]
    archived = conn.execute("SELECT COUNT(*) FROM articles WHERE is_archived = 1").fetchone()[0]
    images = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    highlights = conn.execute("SELECT COUNT(*) FROM highlights").fetchone()[0]
    
    # 获取域名统计
    domain_rows = conn.execute("""
        SELECT domain, COUNT(*) as count 
        FROM articles 
        WHERE domain IS NOT NULL AND domain != ''
        GROUP BY domain 
        ORDER BY count DESC 
        LIMIT 10
    """).fetchall()
    
    # 获取总字数
    total_words = conn.execute("SELECT SUM(word_count) FROM articles").fetchone()[0] or 0
    
    conn.close()
    
    return {
        "total": total,
        "read": read,
        "unread": unread,
        "favorites": favorites,
        "archived": archived,
        "images": images,
        "highlights": highlights,
        "total_words": total_words,
        "top_domains": [{"domain": row["domain"], "count": row["count"]} for row in domain_rows]
    }

# ==================== 域名列表 ====================

@app.get("/api/domains")
async def get_domains():
    conn = get_db()
    
    rows = conn.execute("""
        SELECT domain, COUNT(*) as count 
        FROM articles 
        WHERE domain IS NOT NULL AND domain != ''
        GROUP BY domain 
        ORDER BY count DESC
    """).fetchall()
    
    conn.close()
    
    return {
        "domains": [{"domain": row["domain"], "count": row["count"]} for row in rows]
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 ReadLater v0.3.0 启动中...")
    print("📖 访问 http://localhost:8000")
    print("✨ 新功能: 存档、标签管理、导出、批量操作、高亮笔记")
    uvicorn.run(app, host="0.0.0.0", port=8000)
