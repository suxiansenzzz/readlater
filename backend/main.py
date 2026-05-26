"""
稍后阅读 - ReadLater
一个轻量级的网页内容抓取和阅读应用
"""
import os
import io
import json
import sqlite3
import re
import hashlib
from datetime import datetime
from typing import Optional, List
from urllib.parse import urljoin, urlparse

import trafilatura
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

# BeautifulSoup用于保留HTML格式和图片
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("警告: BeautifulSoup未安装，将使用trafilatura提取内容（可能丢失图片）")

# 导入导出模块
try:
    from backend.exporters import (
        export_to_pdf, export_to_txt, export_to_xml, export_to_epub,
        export_to_csv, export_to_html, export_to_json
    )
except ImportError:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from backend.exporters import (
        export_to_pdf, export_to_txt, export_to_xml, export_to_epub,
        export_to_csv, export_to_html, export_to_json
    )

# 配置
DB_PATH = os.path.join(os.path.dirname(__file__), "readlater.db")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
IMAGES_DIR = os.path.join(os.path.dirname(__file__), "images")

app = FastAPI(title="ReadLater", version="0.1.0")

# 添加CORS中间件，允许浏览器扩展跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境应限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    is_archived: Optional[bool] = None

class Article(BaseModel):
    id: int
    url: str
    title: str
    content: str
    excerpt: str
    tags: List[str]
    is_read: bool
    is_favorite: bool
    is_archived: bool
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
            is_archived INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            word_count INTEGER DEFAULT 0,
            reading_time INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON articles(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_is_read ON articles(is_read)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_is_archived ON articles(is_archived)")
    
    # 图片表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            original_url TEXT NOT NULL,
            local_path TEXT NOT NULL,
            filename TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (article_id) REFERENCES articles (id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_images_article_id ON images(article_id)")
    
    conn.commit()
    conn.close()
    
    # 创建图片目录
    os.makedirs(IMAGES_DIR, exist_ok=True)

# ==================== 抓取功能 ====================

# 导入反爬虫模块
try:
    from backend.anti_crawler import fetch_with_trafilatura, get_headers
except ImportError:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from backend.anti_crawler import fetch_with_trafilatura, get_headers

# 导入新的反爬模块
try:
    from fetcher import fetch_article as fetch_article_new, ANTICRAWL_AVAILABLE
except ImportError:
    ANTICRAWL_AVAILABLE = False

def extract_content_with_images(html: str, url: str) -> dict:
    """使用BeautifulSoup提取内容，保留图片和HTML格式"""
    if not BS4_AVAILABLE:
        # 如果没有BeautifulSoup，使用trafilatura
        content = trafilatura.extract(html, include_comments=False, include_tables=True, output_format='html')
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else "无标题"
        return {'title': title, 'content': content or ''}
    
    soup = BeautifulSoup(html, 'lxml')
    
    # 提取标题
    title_tag = soup.find('title')
    title = title_tag.get_text().strip() if title_tag else "无标题"
    
    # 尝试找到文章正文区域（针对不同网站）
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    article_content = None
    
    # 36kr
    if '36kr.com' in domain:
        article_content = soup.find('div', class_=re.compile(r'article|content|kr-article', re.I))
    # 知乎
    elif 'zhihu.com' in domain:
        article_content = soup.find('div', class_=re.compile(r'RichText|Post-RichText', re.I))
    # CSDN
    elif 'csdn.net' in domain:
        article_content = soup.find('div', id='article_content') or soup.find('div', class_='article-content')
    # 通用方法
    if not article_content:
        # 尝试找常见的文章容器
        for selector in ['article', '.article', '.post', '.content', '.entry-content', '[role="article"]']:
            article_content = soup.select_one(selector)
            if article_content:
                break
    
    # 如果还是找不到，提取所有p标签
    if not article_content:
        paragraphs = soup.find_all('p')
        if paragraphs:
            # 创建一个临时容器
            article_content = soup.new_tag('div')
            for p in paragraphs:
                article_content.append(p)
    
    if article_content:
        # 清理不必要的属性，但保留图片
        for tag in article_content.find_all(True):
            # 保留img标签的src和alt属性
            if tag.name == 'img':
                attrs_to_keep = ['src', 'alt', 'width', 'height']
                attrs = dict(tag.attrs)
                for attr in attrs:
                    if attr not in attrs_to_keep:
                        del tag[attr]
            else:
                # 对于其他标签，只保留class和style
                attrs = dict(tag.attrs)
                for attr in attrs:
                    if attr not in ['class', 'style']:
                        del tag[attr]
        
        content_html = str(article_content)
    else:
        content_html = ''
    
    return {'title': title, 'content': content_html}

def fetch_article(url: str, custom_title: str = None):
    """抓取网页内容（带反爬虫优化）"""
    # 优先使用新的反爬模块
    if ANTICRAWL_AVAILABLE:
        try:
            result = fetch_article_new(url, download_images=False, use_anticrawl=True)
            if result.get('error'):
                raise Exception(result['error'])
            if not result.get('content'):
                raise Exception("无法提取正文内容")
            
            content = result['content']
            title = custom_title or result.get('title') or "无标题"
            
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
                "reading_time": reading_time,
                "html": result.get('html', '')
            }
        except Exception as e:
            print(f"新反爬模块失败，降级到旧模块: {e}")
    
    # 降级到旧的抓取方法
    try:
        # 使用反爬虫优化的方法下载网页
        downloaded = fetch_with_trafilatura(url)
        if not downloaded:
            raise Exception("无法下载网页")
        
        # 使用BeautifulSoup提取正文（保留图片和HTML格式）
        extracted = extract_content_with_images(downloaded, url)
        content = extracted['content']
        
        if not content:
            raise Exception("无法提取正文内容")
        
        # 获取标题
        title = custom_title or extracted.get('title') or "无标题"
        
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
            "reading_time": reading_time,
            "html": downloaded  # 保留HTML用于提取图片
        }
    except Exception as e:
        raise Exception(f"抓取失败: {str(e)}")

# ==================== 图片处理 ====================

def get_image_hash(url: str) -> str:
    """生成图片URL的哈希值作为文件名"""
    return hashlib.md5(url.encode()).hexdigest()

def get_image_extension(url: str, content_type: str = None) -> str:
    """获取图片扩展名"""
    # 从URL获取扩展名
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    if path.endswith('.jpg') or path.endswith('.jpeg'):
        return '.jpg'
    elif path.endswith('.png'):
        return '.png'
    elif path.endswith('.gif'):
        return '.gif'
    elif path.endswith('.webp'):
        return '.webp'
    elif path.endswith('.svg'):
        return '.svg'
    
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
    
    # 默认jpg
    return '.jpg'

def is_article_image(url: str, base_url: str = None) -> bool:
    """判断是否是文章内容图片（而不是装饰性图片）"""
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    # 过滤掉SVG图标
    if path.endswith('.svg'):
        return False
    
    # 过滤掉明显的装饰性图片
    skip_patterns = [
        '/avatar/', '/head/', '/user/', '/profile/',  # 头像
        '/logo/', '/icon/', '/brand/',                 # Logo/图标
        '/qr', '/qrcode',                             # 二维码
        '/banner/', '/ad/', '/ads/',                   # 广告/横幅
        '/favicon',                                   # 网站图标
        '/emoji/', '/emoticon/',                       # 表情
        '/badge/', '/medal/',                          # 徽章
        '/button/', '/btn/',                           # 按钮
        '/loading/', '/spinner/',                      # 加载动画
        '/placeholder/',                               # 占位图
        '/thumb/', '/thumbnail/',                      # 缩略图
        'avatar_placeholder',                          # 头像占位图
        'otter_avatar',                                # 少数派头像占位图
        '/icons/',                                     # 图标目录
        'logo.gif',                                    # 网站logo
        'ghs.png',                                     # 备案图标
    ]
    
    for pattern in skip_patterns:
        if pattern in path:
            return False
    
    # 检查完整URL中的域名
    url_lower = url.lower()
    skip_domains = [
        'staticx.36krcdn.com/36kr-web/static/',       # 36kr静态资源
        'static.36krcdn.com',                          # 36kr静态资源
    ]
    
    for pattern in skip_domains:
        if pattern in url_lower:
            return False
    
    # 过滤掉太小的图片（通过URL判断）
    if any(size in path for size in ['_16.', '_24.', '_32.', '_48.', '_64.', '_80.', '_96.']):
        return False
    
    # 过滤掉明显的追踪像素
    if '1x1' in path or 'pixel' in path:
        return False
    
    return True

async def download_image(client: httpx.AsyncClient, url: str, article_id: int, base_url: str = None) -> Optional[str]:
    """下载单张图片，支持防盗链和反爬虫"""
    try:
        # 使用反爬虫模块获取请求头
        headers = get_headers(url)
        
        # 添加图片相关的Accept头
        headers['Accept'] = 'image/webp,image/apng,image/*,*/*;q=0.8'
        
        # 添加Referer头（防盗链关键）
        if base_url:
            parsed_base = urlparse(base_url)
            headers['Referer'] = f"{parsed_base.scheme}://{parsed_base.netloc}/"
        
        # 随机延迟（避免被检测为爬虫）
        import random
        import asyncio
        await asyncio.sleep(random.uniform(0.1, 0.5))
        
        response = await client.get(url, timeout=15, follow_redirects=True, headers=headers)
        if response.status_code == 200:
            # 检查图片大小（过滤太小的图片）
            content = response.content
            if len(content) < 1024:  # 小于1KB的图片可能是追踪像素或图标
                print(f"图片太小，跳过: {url} ({len(content)} bytes)")
                return None
            
            url_hash = get_image_hash(url)
            ext = get_image_extension(url, response.headers.get('content-type'))
            filename = f"{url_hash}{ext}"
            filepath = os.path.join(IMAGES_DIR, filename)
            
            with open(filepath, 'wb') as f:
                f.write(content)
            
            return filename
    except Exception as e:
        print(f"下载图片失败 {url}: {e}")
    return None

def extract_images_from_html(html: str, base_url: str) -> List[str]:
    """从HTML中提取图片URL"""
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
    """从内容中提取图片URL（支持HTML和Markdown）"""
    urls = []
    
    # 从HTML img标签中提取完整的src URL（包括查询参数）
    html_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
    for match in re.finditer(html_pattern, content):
        url = match.group(1)
        if url and url.startswith('http'):
            urls.append(url)
    
    # 从Markdown图片中提取
    md_pattern = r'!\[[^\]]*\]\(([^)]+)\)'
    for match in re.finditer(md_pattern, content):
        url = match.group(1)
        if url and url.startswith('http'):
            urls.append(url)
    
    return urls

async def download_article_images(html: str, content: str, base_url: str, article_id: int) -> List[dict]:
    """下载文章中的所有图片，支持智能过滤和去重"""
    images = []
    url_mapping = {}  # 原始URL -> 本地路径的映射
    
    # 提取所有图片URL
    img_urls = extract_images_from_html(html, base_url)
    img_urls.extend(extract_images_from_content(content))
    
    # 去重
    img_urls = list(set(img_urls))
    
    print(f"[图片下载] 文章 {article_id}: 提取到 {len(img_urls)} 个图片URL")
    
    # 智能过滤：只保留文章内容图片
    filtered_urls = []
    for url in img_urls:
        if is_article_image(url, base_url):
            filtered_urls.append(url)
        else:
            print(f"[图片下载] 过滤装饰性图片: {url[:80]}...")
    
    print(f"[图片下载] 过滤后: {len(filtered_urls)} 个图片")
    
    if not filtered_urls:
        print(f"[图片下载] 没有需要下载的图片")
        return images, content
    
    # 限制最多下载20张图片
    if len(filtered_urls) > 20:
        print(f"[图片下载] 图片数量过多，只下载前20张 (总共 {len(filtered_urls)} 张)")
        filtered_urls = filtered_urls[:20]
    
    # 下载图片
    downloaded_hashes = set()  # 用于内容去重
    async with httpx.AsyncClient() as client:
        for url in filtered_urls:
            filename = await download_image(client, url, article_id, base_url)
            if filename:
                # 检查内容去重（基于文件哈希）
                filepath = os.path.join(IMAGES_DIR, filename)
                try:
                    with open(filepath, 'rb') as f:
                        content_hash = hashlib.md5(f.read()).hexdigest()
                    
                    if content_hash in downloaded_hashes:
                        # 重复图片，删除文件
                        os.remove(filepath)
                        print(f"[图片下载] 重复图片，跳过: {url[:80]}...")
                        continue
                    
                    downloaded_hashes.add(content_hash)
                    
                    local_path = f'/images/{filename}'
                    images.append({
                        'original_url': url,
                        'local_path': local_path,
                        'filename': filename,
                        'content_hash': content_hash
                    })
                    url_mapping[url] = local_path
                    print(f"[图片下载] 下载成功: {url[:50]}... -> {local_path}")
                except Exception as e:
                    print(f"[图片下载] 处理图片失败 {url}: {e}")
    
    # 替换内容中的图片URL为本地路径
    updated_content = content
    for original_url, local_path in url_mapping.items():
        # 替换HTML格式: <img src="url">
        html_pattern = r'(<img[^>]+src=["\'])' + re.escape(original_url) + r'(["\'])'
        updated_content = re.sub(html_pattern, r'\1' + local_path + r'\2', updated_content)
        
        # 替换其他可能的格式（data-src等）
        data_src_pattern = r'(data-src=["\'])' + re.escape(original_url) + r'(["\'])'
        updated_content = re.sub(data_src_pattern, r'\1' + local_path + r'\2', updated_content)
    
    print(f"[图片下载] 完成: 成功 {len(images)}/{len(filtered_urls)}，内容已更新: {updated_content != content}")
    return images, updated_content

# ==================== API路由 ====================

# 添加图片静态文件服务
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

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
        
        # 下载图片（异步）
        images, updated_content = await download_article_images(
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
        
        # 更新文章内容（如果图片URL被替换）
        if updated_content != data["content"]:
            conn.execute(
                "UPDATE articles SET content = ? WHERE id = ?",
                (updated_content, article_id)
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

@app.post("/api/articles/{article_id}/refetch")
async def refetch_article(article_id: int):
    """重新抓取文章（重新获取内容和图片）"""
    conn = get_db()
    
    # 获取现有文章
    article = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    if not article:
        conn.close()
        raise HTTPException(status_code=404, detail="文章不存在")
    
    url = article['url']
    
    try:
        # 删除旧图片文件和记录
        old_images = conn.execute("SELECT filename FROM images WHERE article_id = ?", (article_id,)).fetchall()
        for img in old_images:
            filepath = os.path.join(IMAGES_DIR, img['filename'])
            if os.path.exists(filepath):
                os.remove(filepath)
        conn.execute("DELETE FROM images WHERE article_id = ?", (article_id,))
        conn.commit()
        
        # 重新抓取文章
        data = fetch_article(url)
        
        # 更新文章内容
        now = datetime.now().isoformat()
        conn.execute("""
            UPDATE articles SET title = ?, content = ?, excerpt = ?, word_count = ?, reading_time = ?, created_at = ?
            WHERE id = ?
        """, (
            data["title"],
            data["content"],
            data["excerpt"],
            data["word_count"],
            data["reading_time"],
            now,
            article_id
        ))
        conn.commit()
        
        # 重新下载图片
        images, updated_content = await download_article_images(
            data["html"],
            data["content"],
            url,
            article_id
        )
        
        # 保存新图片记录
        for img in images:
            conn.execute("""
                INSERT INTO images (article_id, original_url, local_path, filename, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (article_id, img['original_url'], img['local_path'], img['filename'], now))
        
        # 更新内容（如果图片URL被替换）
        if updated_content != data["content"]:
            conn.execute(
                "UPDATE articles SET content = ? WHERE id = ?",
                (updated_content, article_id)
            )
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "message": "重新抓取成功",
            "article_id": article_id,
            "title": data["title"],
            "images_count": len(images)
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/articles/{article_id}/images")
async def get_article_images(article_id: int):
    """获取文章的图片列表"""
    conn = get_db()
    
    # 检查文章是否存在
    article = conn.execute(
        "SELECT id FROM articles WHERE id = ?", (article_id,)
    ).fetchone()
    
    if not article:
        conn.close()
        raise HTTPException(status_code=404, detail="文章不存在")
    
    # 获取图片列表
    rows = conn.execute(
        "SELECT * FROM images WHERE article_id = ? ORDER BY id",
        (article_id,)
    ).fetchall()
    
    conn.close()
    
    images = []
    for row in rows:
        images.append({
            "id": row["id"],
            "original_url": row["original_url"],
            "local_path": row["local_path"],
            "filename": row["filename"],
            "created_at": row["created_at"]
        })
    
    return {"images": images}

@app.get("/api/articles")
async def list_articles(
    page: int = 1,
    per_page: int = 20,
    is_read: Optional[bool] = None,
    is_favorite: Optional[bool] = None,
    is_archived: Optional[bool] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    sort: str = "created_at",
    order: str = "desc"
):
    """获取文章列表"""
    # 调试信息
    print(f"[DEBUG] sort={sort}, order={order}, page={page}, per_page={per_page}")
    
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
    
    if is_archived is not None:
        conditions.append("is_archived = ?")
        params.append(1 if is_archived else 0)
    
    if tag:
        conditions.append("tags LIKE ?")
        params.append(f"%{tag}%")
    
    if search:
        conditions.append("(title LIKE ? OR content LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    
    # 排序（白名单校验防止SQL注入）
    allowed_sorts = {"created_at", "title", "word_count", "reading_time"}
    allowed_orders = {"asc", "desc"}
    if sort not in allowed_sorts:
        sort = "created_at"
    if order not in allowed_orders:
        order = "desc"
    
    order_clause = f"ORDER BY {sort} {order}"
    
    # 获取总数
    total = conn.execute(
        f"SELECT COUNT(*) FROM articles {where}", params
    ).fetchone()[0]
    
    # 获取分页数据
    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT * FROM articles {where} {order_clause} LIMIT ? OFFSET ?",
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
            "is_archived": bool(row["is_archived"]),
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
        "is_archived": bool(row["is_archived"]),
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
    
    if update.is_archived is not None:
        updates.append("is_archived = ?")
        params.append(1 if update.is_archived else 0)
    
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
    archived = conn.execute("SELECT COUNT(*) FROM articles WHERE is_archived = 1").fetchone()[0]
    
    conn.close()
    
    return {
        "total": total,
        "read": read,
        "unread": unread,
        "favorites": favorites,
        "archived": archived
    }

# ==================== 导出功能 ====================

@app.get("/api/export/formats")
async def get_export_formats():
    """获取支持的导出格式"""
    return {
        "formats": [
            {
                "id": "pdf",
                "name": "PDF",
                "description": "便携式文档格式，适合打印和分享",
                "mime_type": "application/pdf",
                "extension": ".pdf"
            },
            {
                "id": "epub",
                "name": "EPUB",
                "description": "电子书格式，适合在阅读器上阅读",
                "mime_type": "application/epub+zip",
                "extension": ".epub"
            },
            {
                "id": "txt",
                "name": "TXT",
                "description": "纯文本格式，通用兼容",
                "mime_type": "text/plain",
                "extension": ".txt"
            },
            {
                "id": "html",
                "name": "HTML",
                "description": "网页格式，可在浏览器中查看",
                "mime_type": "text/html",
                "extension": ".html"
            },
            {
                "id": "json",
                "name": "JSON",
                "description": "数据交换格式，适合备份和迁移",
                "mime_type": "application/json",
                "extension": ".json"
            },
            {
                "id": "csv",
                "name": "CSV",
                "description": "表格格式，适合在Excel中查看",
                "mime_type": "text/csv",
                "extension": ".csv"
            },
            {
                "id": "xml",
                "name": "XML",
                "description": "结构化数据格式，适合程序处理",
                "mime_type": "application/xml",
                "extension": ".xml"
            }
        ]
    }

@app.get("/api/export/{format}")
async def export_articles(format: str, article_ids: Optional[str] = None):
    """
    导出文章
    
    Args:
        format: 导出格式 (pdf, epub, txt, html, json, csv, xml)
        article_ids: 文章ID列表，逗号分隔，空表示全部
    """
    conn = get_db()
    
    # 解析文章ID
    ids = None
    if article_ids:
        try:
            ids = [int(id.strip()) for id in article_ids.split(',') if id.strip()]
        except ValueError:
            conn.close()
            raise HTTPException(status_code=400, detail="无效的文章ID格式")
    
    try:
        if format == "pdf":
            data = export_to_pdf(conn, ids)
            media_type = "application/pdf"
            filename = f"readlater_export_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        elif format == "epub":
            data = export_to_epub(conn, ids)
            media_type = "application/epub+zip"
            filename = f"readlater_export_{datetime.now().strftime('%Y%m%d_%H%M')}.epub"
        elif format == "txt":
            data = export_to_txt(conn, ids)
            media_type = "text/plain"
            filename = f"readlater_export_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        elif format == "html":
            data = export_to_html(conn, ids)
            media_type = "text/html"
            filename = f"readlater_export_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
        elif format == "json":
            data = export_to_json(conn, ids)
            media_type = "application/json"
            filename = f"readlater_export_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        elif format == "csv":
            data = export_to_csv(conn, ids)
            media_type = "text/csv"
            filename = f"readlater_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        elif format == "xml":
            data = export_to_xml(conn, ids)
            media_type = "application/xml"
            filename = f"readlater_export_{datetime.now().strftime('%Y%m%d_%H%M')}.xml"
        else:
            conn.close()
            raise HTTPException(status_code=400, detail=f"不支持的导出格式: {format}")
        
        conn.close()
        
        # 返回文件流
        if isinstance(data, bytes):
            return StreamingResponse(
                io.BytesIO(data),
                media_type=media_type,
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        else:
            return StreamingResponse(
                io.BytesIO(data.encode('utf-8')),
                media_type=media_type,
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
    
    except ImportError as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")

# ==================== 主程序 ====================

if __name__ == "__main__":
    import uvicorn
    print("🚀 ReadLater 启动中...")
    print("📖 访问 http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
