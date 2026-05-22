"""
稍后阅读 - ReadLater (带图片抓取版)
"""
import os
import json
import sqlite3
import hashlib
import re
from datetime import datetime
from typing import Optional, List
from urllib.parse import urljoin, urlparse

import trafilatura
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import httpx

# 配置
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "readlater.db")
IMAGES_DIR = os.path.join(BASE_DIR, "images")
STATIC_DIR = os.path.join(BASE_DIR, "..", "static")

# 确保目录存在
os.makedirs(IMAGES_DIR, exist_ok=True)

app = FastAPI(title="ReadLater", version="0.2.0")

# ==================== 数据模型 ====================

class ArticleCreate(BaseModel):
    url: str
    title: Optional[str] = None
    tags: Optional[List[str]] = []
    content: Optional[str] = None  # 手动传入的内容（用于知乎等反爬网站）

class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    is_read: Optional[bool] = None
    is_favorite: Optional[bool] = None

# ==================== 数据库 ====================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    
    # 文章表
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
            reading_time INTEGER DEFAULT 0,
            cover_image TEXT
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
    
    conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON articles(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_is_read ON articles(is_read)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_images_article ON images(article_id)")
    conn.commit()
    conn.close()

# ==================== 图片处理 ====================

def get_image_hash(url: str) -> str:
    """生成图片URL的哈希值作为文件名"""
    return hashlib.md5(url.encode()).hexdigest()

def get_image_extension(url: str, content_type: str = None) -> str:
    """获取图片扩展名"""
    # 从URL获取扩展名
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp']:
        if path.endswith(ext):
            return ext
    
    # 从content-type获取
    if content_type:
        if 'jpeg' in content_type or 'jpg' in content_type:
            return '.jpg'
        elif 'png' in content_type:
            return '.png'
        elif 'gif' in content_type:
            return '.gif'
        elif 'webp' in content_type:
            return '.webp'
    
    return '.jpg'  # 默认

async def download_image(client: httpx.AsyncClient, url: str, article_id: int) -> Optional[str]:
    """下载单张图片"""
    try:
        response = await client.get(url, timeout=10, follow_redirects=True)
        if response.status_code == 200:
            # 生成文件名
            url_hash = get_image_hash(url)
            ext = get_image_extension(url, response.headers.get('content-type'))
            filename = f"{url_hash}{ext}"
            filepath = os.path.join(IMAGES_DIR, filename)
            
            # 保存图片
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return filename
    except Exception as e:
        print(f"下载图片失败 {url}: {e}")
    return None

def extract_images_from_html(html: str, base_url: str) -> List[str]:
    """从HTML中提取图片URL"""
    # 匹配img标签的src属性
    img_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
    urls = re.findall(img_pattern, html, re.IGNORECASE)
    
    # 转换为绝对URL
    absolute_urls = []
    for url in urls:
        if url.startswith('data:'):  # 跳过base64图片
            continue
        if url.startswith('//'):
            url = 'https:' + url
        elif not url.startswith(('http://', 'https://')):
            url = urljoin(base_url, url)
        absolute_urls.append(url)
    
    return absolute_urls

def extract_images_from_content(content: str) -> List[str]:
    """从Markdown内容中提取图片URL"""
    # 匹配Markdown图片语法 ![alt](url)
    img_pattern = r'!\[[^\]]*\]\(([^)]+)\)'
    urls = re.findall(img_pattern, content)
    
    # 匹配HTML img标签
    html_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
    urls.extend(re.findall(html_pattern, content))
    
    return urls

async def download_article_images(html: str, content: str, base_url: str, article_id: int) -> List[dict]:
    """下载文章中的所有图片"""
    images = []
    
    # 提取所有图片URL
    img_urls = extract_images_from_html(html, base_url)
    img_urls.extend(extract_images_from_content(content))
    
    # 去重
    img_urls = list(set(img_urls))
    
    if not img_urls:
        return images
    
    # 下载图片
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
            no_fallback=False,
            include_images=True,  # 包含图片
            include_links=True
        )
        
        if not content:
            raise Exception("无法提取正文内容")
        
        # 提取元数据
        metadata = trafilatura.extract_metadata(downloaded)
        
        # 获取标题
        title = custom_title or (metadata.title if metadata else None) or "无标题"
        
        # 生成摘要
        excerpt = content[:200].replace('\n', ' ').strip()
        if len(content) > 200:
            excerpt += "..."
        
        # 计算字数和阅读时间
        word_count = len(content)
        reading_time = max(1, word_count // 500)
        
        # 提取封面图
        cover_image = None
        if metadata and metadata.image:
            cover_image = metadata.image
        
        return {
            "url": url,
            "title": title,
            "content": content,
            "excerpt": excerpt,
            "word_count": word_count,
            "reading_time": reading_time,
            "cover_image": cover_image,
            "html": downloaded  # 保留HTML用于提取图片
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
    """获取保存的图片"""
    filepath = os.path.join(IMAGES_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(filepath)

@app.post("/api/save")
async def save_article(article: ArticleCreate):
    """保存文章（含图片）"""
    conn = get_db()
    
    # 检查是否已存在
    existing = conn.execute(
        "SELECT id FROM articles WHERE url = ?", (article.url,)
    ).fetchone()
    
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="该链接已保存")
    
    try:
        # 如果有手动传入的内容，使用它；否则自动抓取
        if article.content:
            content = article.content
            title = article.title or "无标题"
            cover_image = None
            html = ""
            
            # 生成摘要
            excerpt = content[:200].replace('\n', ' ').strip()
            if len(content) > 200:
                excerpt += "..."
            
            # 计算字数和阅读时间
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
                "html": html
            }
        else:
            # 自动抓取文章
            data = fetch_article(article.url, article.title)
        
        # 插入文章
        now = datetime.now().isoformat()
        tags = json.dumps(article.tags or [], ensure_ascii=False)
        
        cursor = conn.execute("""
            INSERT INTO articles (url, title, content, excerpt, tags, created_at, word_count, reading_time, cover_image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["url"],
            data["title"],
            data["content"],
            data["excerpt"],
            tags,
            now,
            data["word_count"],
            data["reading_time"],
            data["cover_image"]
        ))
        
        article_id = cursor.lastrowid
        conn.commit()
        
        # 下载图片（异步）
        images = await download_article_images(
            data["html"], 
            data["content"], 
            data["url"], 
            article_id
        )
        
        # 保存图片记录
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
    tag: Optional[str] = None,
    search: Optional[str] = None
):
    """获取文章列表"""
    conn = get_db()
    
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
    
    total = conn.execute(f"SELECT COUNT(*) FROM articles {where}", params).fetchone()[0]
    
    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT * FROM articles {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()
    
    articles = []
    for row in rows:
        # 获取文章的图片数量
        img_count = conn.execute(
            "SELECT COUNT(*) FROM images WHERE article_id = ?", (row["id"],)
        ).fetchone()[0]
        
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
            "reading_time": row["reading_time"],
            "cover_image": row["cover_image"],
            "images_count": img_count
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
    """获取文章详情"""
    conn = get_db()
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="文章不存在")
    
    # 获取文章的图片
    images = conn.execute(
        "SELECT * FROM images WHERE article_id = ?", (article_id,)
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
        "created_at": row["created_at"],
        "word_count": row["word_count"],
        "reading_time": row["reading_time"],
        "cover_image": row["cover_image"],
        "images": [{
            "id": img["id"],
            "original_url": img["original_url"],
            "local_path": img["local_path"],
            "filename": img["filename"]
        } for img in images]
    }

@app.put("/api/articles/{article_id}")
async def update_article(article_id: int, update: ArticleUpdate):
    """更新文章"""
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
    
    if updates:
        params.append(article_id)
        conn.execute(f"UPDATE articles SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    
    conn.close()
    return {"success": True}

@app.delete("/api/articles/{article_id}")
async def delete_article(article_id: int):
    """删除文章及其图片"""
    conn = get_db()
    
    # 获取文章的图片
    images = conn.execute(
        "SELECT filename FROM images WHERE article_id = ?", (article_id,)
    ).fetchall()
    
    # 删除图片文件
    for img in images:
        filepath = os.path.join(IMAGES_DIR, img["filename"])
        if os.path.exists(filepath):
            os.remove(filepath)
    
    # 删除数据库记录
    conn.execute("DELETE FROM images WHERE article_id = ?", (article_id,))
    conn.execute("DELETE FROM articles WHERE id = ?", (article_id,))
    conn.commit()
    conn.close()
    
    return {"success": True}

@app.get("/api/stats")
async def get_stats():
    """获取统计信息"""
    conn = get_db()
    
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    read = conn.execute("SELECT COUNT(*) FROM articles WHERE is_read = 1").fetchone()[0]
    unread = total - read
    favorites = conn.execute("SELECT COUNT(*) FROM articles WHERE is_favorite = 1").fetchone()[0]
    images = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    
    conn.close()
    
    return {
        "total": total,
        "read": read,
        "unread": unread,
        "favorites": favorites,
        "images": images
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 ReadLater v0.2.0 启动中...")
    print("📖 访问 http://localhost:8000")
    print("📸 支持图片抓取")
    uvicorn.run(app, host="0.0.0.0", port=8000)
