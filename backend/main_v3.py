"""
ReadLater v1.9.0 - 稍后阅读（全功能版）
Pocket & Wallabag 风格的自托管稍后阅读应用

功能概览：
- 文章保存/正文提取/图片本地化
- 阅读视图（暗色/亮色主题）
- 收藏/已读/存档/标签管理
- 全文搜索/排序/筛选/批量操作
- 高亮笔记
- 多格式导出（JSON/CSV/HTML/PDF/TXT/XML/MOBI/EPUB）
- 数据导入（Pocket/Instapaper/书签/Wallabag）
- RSS 订阅抓取 + RSS 输出 Feed
- 公开分享链接
- 智能筛选（时间/阅读时长）
- 自动标签规则引擎
- 阅读体验增强（TTS/字体/编辑标题）
- 跨设备同步（多用户+同步API）
- 数据持久化（WAL 模式+备份+自动迁移）
"""
import os
import json
import csv
import sqlite3
import hashlib
import re
import io
import tempfile
from datetime import datetime, timedelta
from typing import Optional, List
from urllib.parse import urljoin, urlparse

import trafilatura
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import (
    HTMLResponse, FileResponse, StreamingResponse, Response, JSONResponse
)
from pydantic import BaseModel
import httpx

# 导入功能模块
from backend.exporters import export_to_pdf, export_to_txt, export_to_xml, export_to_mobi
from backend.importers import (
    import_from_pocket_csv, import_from_wallabag_json,
    import_from_bookmarks_html, import_from_instapaper_csv
)
from backend.rss_output import generate_rss_feed
from backend.sharing import (
    init_share_table, create_share, get_shared_article,
    revoke_share, get_share_info
)
from backend.rules import (
    init_rules_table, apply_rules_to_article, create_rule,
    get_all_rules, update_rule, delete_rule, apply_rules_to_all
)
from backend.sync import (
    init_users_table, create_user, authenticate_user,
    verify_token, record_sync_action, get_sync_changes, get_default_user
)

# 配置
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "readlater.db")
IMAGES_DIR = os.path.join(BASE_DIR, "images")
STATIC_DIR = os.path.join(BASE_DIR, "..", "static")

# 确保目录存在
os.makedirs(IMAGES_DIR, exist_ok=True)

app = FastAPI(title="ReadLater", version="1.9.0")

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
    """
    获取数据库连接
    启用 WAL 模式以提高并发性能和数据持久性
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # 启用 WAL 模式：写入更安全，崩溃恢复更好
    conn.execute("PRAGMA journal_mode=WAL")
    # 同步模式 FULL：确保数据完全写入磁盘
    conn.execute("PRAGMA synchronous=FULL")
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
    
    # 索引
    conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON articles(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_is_read ON articles(is_read)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_is_archived ON articles(is_archived)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_is_favorite ON articles(is_favorite)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_domain ON articles(domain)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_images_article ON images(article_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_highlights_article ON highlights(article_id)")
    
    # 迁移旧数据库（添加新列）
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

async def download_article_images(html: str, content: str, base_url: str, article_id: int) -> List[dict]:
    images = []
    
    img_urls = extract_images_from_html(html, base_url)
    img_urls.extend(extract_images_from_content(content))
    
    img_urls = list(set(img_urls))
    
    if not img_urls:
        return images
    
    async with httpx.AsyncClient() as client:
        for url in img_urls:
            filename = await download_image(client, url, article_id)
            if filename:
                images.append({
                    'original_url': url,
                    'local_path': f'/images/{filename}',
                    'filename': filename
                })
    
    return images

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
    """应用启动时初始化数据库和所有功能模块"""
    conn = get_db()
    init_db()

    # 初始化新功能模块的数据库表
    init_share_table(conn)
    init_rules_table(conn)
    init_users_table(conn)

    # 创建默认用户（兼容单用户模式）
    try:
        get_default_user(conn)
    except Exception:
        pass

    conn.close()

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
        
        images = await download_article_images(
            data["html"], 
            data["content"], 
            data["url"], 
            article_id
        )
        
        for img in images:
            conn.execute("""
                INSERT INTO images (article_id, original_url, local_path, filename, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (article_id, img['original_url'], img['local_path'], img['filename'], now))
        
        # 应用自动标签规则
        matched_tags = apply_rules_to_article(
            conn, article_id, data["url"], data["title"], data["content"]
        )
        
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
    sort: Optional[str] = "created_at",  # created_at, title, word_count, reading_time, updated_at
    order: Optional[str] = "desc",  # asc, desc
    # 智能筛选参数
    time_filter: Optional[str] = None,  # today, this_week, this_month, this_year
    reading_time_min: Optional[int] = None,  # 最短阅读时间（分钟）
    reading_time_max: Optional[int] = None,  # 最长阅读时间（分钟）
    date_from: Optional[str] = None,  # 自定义日期范围起始
    date_to: Optional[str] = None  # 自定义日期范围结束
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
    
    # 智能时间筛选
    now = datetime.now()
    if time_filter == "today":
        today_start = now.strftime("%Y-%m-%d") + "T00:00:00"
        conditions.append("created_at >= ?")
        params.append(today_start)
    elif time_filter == "this_week":
        week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d") + "T00:00:00"
        conditions.append("created_at >= ?")
        params.append(week_start)
    elif time_filter == "this_month":
        month_start = now.strftime("%Y-%m") + "-01T00:00:00"
        conditions.append("created_at >= ?")
        params.append(month_start)
    elif time_filter == "this_year":
        year_start = now.strftime("%Y") + "-01-01T00:00:00"
        conditions.append("created_at >= ?")
        params.append(year_start)
    
    # 自定义日期范围
    if date_from:
        conditions.append("created_at >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("created_at <= ?")
        params.append(date_to)
    
    # 阅读时长筛选
    if reading_time_min is not None:
        conditions.append("reading_time >= ?")
        params.append(reading_time_min)
    if reading_time_max is not None:
        conditions.append("reading_time <= ?")
        params.append(reading_time_max)
    
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

# ==================== v1.2.0 多格式导出 ====================

@app.get("/api/export/pdf")
async def export_pdf():
    """导出所有文章为 PDF 格式"""
    conn = get_db()
    try:
        pdf_bytes = export_to_pdf(conn)
        conn.close()
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=readlater_export.pdf"}
        )
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"PDF 导出失败: {str(e)}")


@app.get("/api/export/txt")
async def export_txt():
    """导出所有文章为纯文本格式"""
    conn = get_db()
    try:
        txt_content = export_to_txt(conn)
        conn.close()
        return StreamingResponse(
            iter([txt_content.encode("utf-8")]),
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=readlater_export.txt"}
        )
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"TXT 导出失败: {str(e)}")


@app.get("/api/export/xml")
async def export_xml():
    """导出所有文章为 XML 格式"""
    conn = get_db()
    try:
        xml_content = export_to_xml(conn)
        conn.close()
        return StreamingResponse(
            iter([xml_content.encode("utf-8")]),
            media_type="application/xml",
            headers={"Content-Disposition": "attachment; filename=readlater_export.xml"}
        )
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"XML 导出失败: {str(e)}")


@app.get("/api/export/mobi")
async def export_mobi():
    """导出所有文章为 MOBI/EPUB 格式"""
    conn = get_db()
    try:
        epub_bytes = export_to_mobi(conn)
        conn.close()
        return StreamingResponse(
            iter([epub_bytes]),
            media_type="application/epub+zip",
            headers={"Content-Disposition": "attachment; filename=readlater_export.epub"}
        )
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"MOBI 导出失败: {str(e)}")


# ==================== v1.3.0 数据导入 ====================

@app.post("/api/import/pocket")
async def import_pocket(file: UploadFile = File(...)):
    """
    从 Pocket 导出的 CSV 文件导入文章
    Pocket 导出路径：Settings → Export → CSV
    """
    conn = get_db()
    try:
        content = await file.read()
        csv_content = content.decode("utf-8")
        result = import_from_pocket_csv(conn, csv_content, fetch_article)
        conn.close()
        return {
            "success": True,
            "imported": result["imported"],
            "skipped": result["skipped"],
            "errors": result["errors"],
            "source": "pocket"
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Pocket 导入失败: {str(e)}")


@app.post("/api/import/wallabag")
async def import_wallabag(file: UploadFile = File(...)):
    """
    从 Wallabag 导出的 JSON 文件导入文章
    Wallabag 导出路径：Export → JSON
    """
    conn = get_db()
    try:
        content = await file.read()
        json_content = content.decode("utf-8")
        result = import_from_wallabag_json(conn, json_content, fetch_article)
        conn.close()
        return {
            "success": True,
            "imported": result["imported"],
            "skipped": result["skipped"],
            "errors": result["errors"],
            "source": "wallabag"
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Wallabag 导入失败: {str(e)}")


@app.post("/api/import/bookmarks")
async def import_bookmarks(file: UploadFile = File(...)):
    """
    从浏览器导出的书签 HTML 文件导入文章
    支持 Chrome、Firefox、Safari 等标准书签格式
    """
    conn = get_db()
    try:
        content = await file.read()
        html_content = content.decode("utf-8")
        result = import_from_bookmarks_html(conn, html_content, fetch_article)
        conn.close()
        return {
            "success": True,
            "imported": result["imported"],
            "skipped": result["skipped"],
            "errors": result["errors"],
            "source": "bookmarks"
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"书签导入失败: {str(e)}")


@app.post("/api/import/instapaper")
async def import_instapaper(file: UploadFile = File(...)):
    """
    从 Instapaper 导出的 CSV 文件导入文章
    Instapaper 导出路径：Settings → Export → CSV
    """
    conn = get_db()
    try:
        content = await file.read()
        csv_content = content.decode("utf-8")
        result = import_from_instapaper_csv(conn, csv_content, fetch_article)
        conn.close()
        return {
            "success": True,
            "imported": result["imported"],
            "skipped": result["skipped"],
            "errors": result["errors"],
            "source": "instapaper"
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Instapaper 导入失败: {str(e)}")


# ==================== v1.4.0 RSS 输出 ====================

@app.get("/api/rss")
async def rss_feed(
    limit: int = Query(50, ge=1, le=200),
    tag: Optional[str] = None,
    favorites: bool = False
):
    """
    生成 RSS 2.0 Feed
    可以用任何 RSS 阅读器订阅此地址
    """
    conn = get_db()
    try:
        base_url = "http://localhost:8000"
        rss_xml = generate_rss_feed(
            conn, base_url=base_url,
            limit=limit, tag=tag, favorites_only=favorites
        )
        conn.close()
        return Response(
            content=rss_xml,
            media_type="application/rss+xml",
            headers={"Content-Disposition": "inline"}
        )
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"RSS 生成失败: {str(e)}")


# ==================== v1.5.0 公开分享 ====================

class ShareRequest(BaseModel):
    """创建分享请求"""
    article_id: int
    expires_hours: Optional[int] = None  # 过期小时数，None 表示永不过期


@app.post("/api/share")
async def create_share_link(request: ShareRequest):
    """
    为文章创建公开分享链接
    其他人可以通过分享链接查看文章内容
    """
    conn = get_db()
    try:
        result = create_share(conn, request.article_id, request.expires_hours)
        conn.close()
        return {
            "success": True,
            "share_token": result["share_token"],
            "article_title": result["article_title"],
            "share_url": f"/s/{result['share_token']}",
            "expires_at": result.get("expires_at")
        }
    except ValueError as e:
        conn.close()
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"创建分享失败: {str(e)}")


@app.get("/api/share/{article_id}")
async def get_share_status(article_id: int):
    """获取文章的分享状态"""
    conn = get_db()
    info = get_share_info(conn, article_id)
    conn.close()

    if info:
        return {
            "shared": True,
            "share_token": info["share_token"],
            "share_url": f"/s/{info['share_token']}",
            "view_count": info["view_count"],
            "expires_at": info["expires_at"]
        }
    return {"shared": False}


@app.delete("/api/share/{article_id}")
async def revoke_share_link(article_id: int):
    """撤销文章的分享链接"""
    conn = get_db()
    revoke_share(conn, article_id)
    conn.close()
    return {"success": True, "message": "分享已撤销"}


@app.get("/s/{share_token}")
async def view_shared_article(share_token: str):
    """
    通过分享令牌查看文章（公开页面）
    这个页面不需要登录即可访问
    """
    conn = get_db()
    article = get_shared_article(conn, share_token)
    conn.close()

    if not article:
        raise HTTPException(status_code=404, detail="分享链接不存在或已过期")

    # 生成简化的阅读页面
    tags_html = " ".join([
        f'<span style="background:#f0f0f0;padding:2px 8px;border-radius:10px;font-size:0.8em;">{t}</span>'
        for t in article["tags"]
    ])

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{article['title']} - ReadLater 分享</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px; margin: 0 auto; padding: 2rem;
            line-height: 1.8; color: #1e293b;
        }}
        h1 {{ font-size: 1.8rem; margin-bottom: 1rem; }}
        .meta {{ color: #64748b; margin-bottom: 2rem; padding-bottom: 1rem; border-bottom: 1px solid #e2e8f0; }}
        .content p {{ margin-bottom: 1rem; }}
        .footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e2e8f0; color: #94a3b8; font-size: 0.85rem; }}
    </style>
</head>
<body>
    <h1>{article['title']}</h1>
    <div class="meta">
        <span>{article.get('domain', '')}</span> ·
        <span>{article['word_count']}字</span> ·
        <span>{article['reading_time']}分钟</span> ·
        <span>浏览 {article['view_count']} 次</span>
        <br>{tags_html}
    </div>
    <div class="content">
        {''.join(f'<p>{p}</p>' for p in article['content'].split(chr(10)) if p.strip())}
    </div>
    <div class="footer">
        通过 <strong>ReadLater</strong> 分享 · 原文：<a href="{article['url']}">{article['url']}</a>
    </div>
</body>
</html>"""

    return HTMLResponse(content=html)


# ==================== v1.6.0 智能筛选（已集成到 list_articles） ====================

# v1.6.0 的智能筛选功能已集成到 /api/articles 接口中
# 新增参数：time_filter, reading_time_min, reading_time_max, date_from, date_to


# ==================== v1.7.0 自动标签规则 ====================

class TagRuleCreate(BaseModel):
    """创建标签规则请求"""
    name: str
    rule_type: str  # domain/url_contains/title_contains/title_regex/content_contains/content_regex
    pattern: str
    tags: List[str]
    priority: int = 0


class TagRuleUpdate(BaseModel):
    """更新标签规则请求"""
    name: Optional[str] = None
    rule_type: Optional[str] = None
    pattern: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None


@app.get("/api/rules")
async def list_tag_rules():
    """获取所有标签规则"""
    conn = get_db()
    rules = get_all_rules(conn)
    conn.close()
    return {"rules": rules}


@app.post("/api/rules")
async def create_tag_rule(rule: TagRuleCreate):
    """创建新的标签规则"""
    conn = get_db()
    try:
        rule_id = create_rule(
            conn, rule.name, rule.rule_type,
            rule.pattern, rule.tags, rule.priority
        )
        conn.close()
        return {"success": True, "rule_id": rule_id}
    except ValueError as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/rules/{rule_id}")
async def update_tag_rule(rule_id: int, update: TagRuleUpdate):
    """更新标签规则"""
    conn = get_db()
    update_data = {k: v for k, v in update.dict().items() if v is not None}
    success = update_rule(conn, rule_id, **update_data)
    conn.close()
    return {"success": success}


@app.delete("/api/rules/{rule_id}")
async def delete_tag_rule(rule_id: int):
    """删除标签规则"""
    conn = get_db()
    delete_rule(conn, rule_id)
    conn.close()
    return {"success": True}


@app.post("/api/rules/apply-all")
async def apply_all_rules():
    """
    将所有规则应用到所有文章
    用于首次设置规则后批量应用
    """
    conn = get_db()
    try:
        result = apply_rules_to_all(conn)
        conn.close()
        return {
            "success": True,
            "total_articles": result["total_articles"],
            "updated": result["updated"],
            "total_tags_added": result["total_tags_added"]
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"批量应用失败: {str(e)}")


# ==================== v1.8.0 阅读体验增强 ====================

@app.get("/api/tts/{article_id}")
async def text_to_speech(article_id: int):
    """
    将文章转换为纯文本（供 TTS 使用）
    返回清理后的纯文本内容
    """
    conn = get_db()
    row = conn.execute(
        "SELECT title, content FROM articles WHERE id = ?",
        (article_id,)
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="文章不存在")

    # 清理内容为纯文本（去除 HTML 标签等）
    text = row["title"] + "\n\n" + (row["content"] or "")
    text = re.sub(r'<[^>]+>', '', text)  # 去除 HTML 标签
    text = re.sub(r'!\[[^\]]*\]\([^)]+\)', '[图片]', text)  # 替换 Markdown 图片
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # 保留链接文本
    text = re.sub(r'\n{3,}', '\n\n', text)  # 合并多余空行

    return {"text": text, "length": len(text)}


class ArticleTitleUpdate(BaseModel):
    """更新文章标题请求"""
    title: str


@app.put("/api/articles/{article_id}/title")
async def update_article_title(article_id: int, update: ArticleTitleUpdate):
    """
    编辑文章标题
    """
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM articles WHERE id = ?", (article_id,)
    ).fetchone()

    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="文章不存在")

    conn.execute(
        "UPDATE articles SET title = ?, updated_at = ? WHERE id = ?",
        (update.title, datetime.now().isoformat(), article_id)
    )
    conn.commit()
    conn.close()

    return {"success": True, "title": update.title}


# ==================== v1.9.0 跨设备同步 ====================

class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


class RegisterRequest(BaseModel):
    """注册请求"""
    username: str
    password: str
    display_name: Optional[str] = None


class SyncRequest(BaseModel):
    """同步请求"""
    device_id: str
    since: Optional[str] = None


@app.post("/api/auth/register")
async def register(request: RegisterRequest):
    """注册新用户"""
    conn = get_db()
    try:
        user = create_user(
            conn, request.username,
            request.password, request.display_name
        )
        conn.close()
        return {
            "success": True,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "display_name": user["display_name"]
            },
            "api_token": user["api_token"]
        }
    except ValueError as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """用户登录"""
    conn = get_db()
    user = authenticate_user(conn, request.username, request.password)
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    return {
        "success": True,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"]
        },
        "api_token": user["api_token"]
    }


@app.get("/api/sync/changes")
async def get_device_changes(
    device_id: str,
    since: Optional[str] = None,
    token: Optional[str] = None
):
    """
    获取其他设备的变更
    用于跨设备同步
    """
    conn = get_db()

    if token:
        user = verify_token(conn, token)
        if not user:
            conn.close()
            raise HTTPException(status_code=401, detail="无效的令牌")
        user_id = user["id"]
    else:
        # 兼容模式：使用默认用户
        default_user = get_default_user(conn)
        user_id = default_user["id"]

    changes = get_sync_changes(conn, user_id, device_id, since)
    conn.close()

    return {
        "changes": changes,
        "count": len(changes)
    }


# ==================== 数据备份 ====================

@app.get("/api/backup")
async def backup_database():
    """
    下载数据库备份文件
    定期备份以防止数据丢失
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="数据库不存在")

    return FileResponse(
        DB_PATH,
        media_type="application/octet-stream",
        filename=f"readlater_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )


@app.post("/api/backup/restore")
async def restore_database(file: UploadFile = File(...)):
    """
    从备份文件恢复数据库
    ⚠️ 警告：这会覆盖当前所有数据！
    """
    try:
        content = await file.read()

        # 先备份当前数据库
        backup_path = DB_PATH + f".bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
        if os.path.exists(DB_PATH):
            import shutil
            shutil.copy2(DB_PATH, backup_path)

        # 写入新数据库
        with open(DB_PATH, "wb") as f:
            f.write(content)

        return {
            "success": True,
            "message": "数据库恢复成功",
            "previous_backup": backup_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"恢复失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    print("🚀 ReadLater v1.9.0 启动中...")
    print("📖 访问 http://localhost:8000")
    print("✨ 全功能版：导出/导入/RSS/分享/筛选/规则/同步/备份")
    uvicorn.run(app, host="0.0.0.0", port=8000)
