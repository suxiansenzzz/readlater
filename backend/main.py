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
import asyncio
import time
from datetime import datetime
from typing import Optional, List
from urllib.parse import urljoin, urlparse

import trafilatura
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Request, Depends, Response, BackgroundTasks
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

# 导入批注模块
try:
    from backend.annotations import (
        init_annotations_table, create_annotation, get_annotations,
        get_annotation, update_annotation, delete_annotation,
        get_all_annotations, get_annotations_stats
    )
except ImportError:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from backend.annotations import (
        init_annotations_table, create_annotation, get_annotations,
        get_annotation, update_annotation, delete_annotation,
        get_all_annotations, get_annotations_stats
    )

# 导入抓取错误管理模块
try:
    from backend.fetch_errors import (
        init_fetch_errors_table, record_fetch_error, get_fetch_errors,
        get_fetch_error, get_fetch_error_by_url, resolve_fetch_error,
        delete_fetch_error, clear_resolved_errors, get_fetch_errors_stats
    )
except ImportError:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from backend.fetch_errors import (
        init_fetch_errors_table, record_fetch_error, get_fetch_errors,
        get_fetch_error, get_fetch_error_by_url, resolve_fetch_error,
        delete_fetch_error, clear_resolved_errors, get_fetch_errors_stats
    )

# 导入自动标签规则模块
try:
    from backend.rules import (
        init_rules_table, apply_rules_to_article, create_rule,
        get_all_rules, get_rule, update_rule, delete_rule, apply_rules_to_all, get_rules_stats
    )
except ImportError:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from backend.rules import (
        init_rules_table, apply_rules_to_article, create_rule,
        get_all_rules, get_rule, update_rule, delete_rule, apply_rules_to_all, get_rules_stats
    )

# 导入认证模块
try:
    from backend.auth import (
        init_users_table, create_user, get_user_by_username, update_last_login,
        update_password, has_any_user, hash_password, verify_password,
        create_token, decode_token, get_current_user, require_auth, require_admin,
        set_auth_cookie, clear_auth_cookie, check_login_allowed, record_login_failure,
        clear_login_attempts, load_config, COOKIE_NAME,
    )
except ImportError:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from backend.auth import (
        init_users_table, create_user, get_user_by_username, update_last_login,
        update_password, has_any_user, hash_password, verify_password,
        create_token, decode_token, get_current_user, require_auth, require_admin,
        set_auth_cookie, clear_auth_cookie, check_login_allowed, record_login_failure,
        clear_login_attempts, load_config, COOKIE_NAME,
    )

# 配置 - 支持环境变量覆盖（Docker部署用）
DB_PATH = os.environ.get("DB_PATH") or os.path.join(os.path.dirname(__file__), "readlater.db")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
IMAGES_DIR = os.environ.get("IMAGES_DIR") or os.path.join(os.path.dirname(__file__), "images")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    init_db()
    print("🚀 ReadLater 启动完成!")
    print("📖 访问 http://localhost:8000")
    yield
    print("👋 ReadLater 关闭")

app = FastAPI(title="ReadLater", version="2.6.0", lifespan=lifespan)

# 添加CORS中间件，允许浏览器扩展跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境应限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 认证中间件 ====================

# 不需要认证的路径前缀
_AUTH_SKIP_PATHS=(
    "/static/",
    "/images/",
    "/login",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/status",
    "/api/auth/setup",
    "/extension/",
    "/favicon",
    "/api/news/fetch",   # 新闻抓取（手动触发）
)

# 游客可访问的 GET 路径（白名单）
_GUEST_ALLOWED_GET = (
    "/api/articles",      # 列表 + 详情
    "/api/stats",         # 统计
    "/api/auth/status",   # 认证状态
    "/api/news",          # 新闻列表
    "/api/news/sources",  # 新闻来源
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """认证中间件：检查 JWT，设置 request.state.user"""
    path = request.url.path

    # 跳过不需要认证的路径
    if any(path.startswith(p) for p in _AUTH_SKIP_PATHS) or path == "/":
        response = await call_next(request)
        return response

    # 解析用户（可能为 None）
    user = get_current_user(request)
    config = load_config()
    request.state.user = user
    request.state.is_guest = user is None

    # 非 GET 请求必须认证（浏览器扩展的 POST 通过 Bearer token）
    if request.method != "GET" and not user:
        return JSONResponse(
            status_code=401,
            content={"error": "未认证，请先登录"},
        )

    # GET 请求：检查游客模式
    if request.method == "GET" and not user:
        # 游客模式关闭 → 必须登录
        if not config.get("guest_enabled", True):
            return JSONResponse(
                status_code=401,
                content={"error": "游客模式已关闭，请先登录"},
            )
        # 游客模式开启 → 只允许白名单路径
        if not any(path.startswith(p) for p in _GUEST_ALLOWED_GET):
            return JSONResponse(
                status_code=401,
                content={"error": "游客无权访问此接口，请登录"},
            )

    response = await call_next(request)
    return response


# 简单的内存缓存
class SimpleCache:
    def __init__(self, ttl=300):  # 默认5分钟过期
        self.cache = {}
        self.ttl = ttl
    
    def get(self, key):
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            else:
                del self.cache[key]
        return None
    
    def set(self, key, value):
        self.cache[key] = (value, time.time())
    
    def delete(self, key):
        if key in self.cache:
            del self.cache[key]
    
    def clear(self):
        self.cache.clear()

# 初始化缓存
article_cache = SimpleCache(ttl=60)  # 文章缓存1分钟
stats_cache = SimpleCache(ttl=30)    # 统计缓存30秒

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
    # WAL模式：写入更安全，崩溃恢复更好
    conn.execute("PRAGMA journal_mode=WAL")
    # FULL同步：确保数据完全写入磁盘
    conn.execute("PRAGMA synchronous=FULL")
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
            reading_time INTEGER DEFAULT 0,
            lead_image_url TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON articles(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_is_read ON articles(is_read)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_is_archived ON articles(is_archived)")
    
    # 检查是否需要添加 lead_image_url 字段（兼容旧数据库）
    cursor = conn.execute("PRAGMA table_info(articles)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'lead_image_url' not in columns:
        conn.execute("ALTER TABLE articles ADD COLUMN lead_image_url TEXT")
        print("已添加 lead_image_url 字段")
    
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
    
    # 初始化批注表
    init_annotations_table(conn)
    
    # 初始化抓取错误表
    init_fetch_errors_table(conn)
    
    # 初始化自动标签规则表
    init_rules_table(conn)

    # 初始化用户表
    init_users_table(conn)

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
            
            # 检查是否有验证码需要处理
            if result.get('captcha_required'):
                user_msg = result.get('user_message') or result.get('error') or '需要验证码'
                raise Exception(f"CAPTCHA_REQUIRED:{user_msg}")
            
            if result.get('error'):
                user_msg = result.get('user_message') or result.get('error')
                raise Exception(user_msg)
            
            if not result.get('content'):
                raise Exception("无法提取正文内容")
            
            content = result['content']
            title = custom_title or result.get('title') or "无标题"
            
            # 生成摘要（取前200字，去除HTML标签）
            import re as _re
            plain = _re.sub(r'<[^>]+>', '', content)
            plain = _re.sub(r'&[a-z]+;', ' ', plain)
            plain = _re.sub(r'\s+', ' ', plain).strip()
            excerpt = plain[:200]
            if len(plain) > 200:
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
            error_msg = str(e)
            print(f"新反爬模块失败，降级到旧模块: {e}")
            
            # 如果是验证码错误，直接抛出
            if error_msg.startswith("CAPTCHA_REQUIRED:"):
                raise Exception(error_msg)
    
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
        
        # 生成摘要（取前200字，去除HTML标签）
        import re as _re2
        plain2 = _re2.sub(r'<[^>]+>', '', content)
        plain2 = _re2.sub(r'&[a-z]+;', ' ', plain2)
        plain2 = _re2.sub(r'\s+', ' ', plain2).strip()
        excerpt = plain2[:200]
        if len(plain2) > 200:
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

async def download_image(client: httpx.AsyncClient, url: str, article_id: int, base_url: str = None, max_retries: int = 2) -> Optional[str]:
    """下载单张图片，支持防盗链、重试"""
    import random
    import asyncio
    import time
    
    for attempt in range(max_retries + 1):
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
            elif response.status_code in (403, 429) and attempt < max_retries:
                wait = random.uniform(1, 3) * (attempt + 1)
                print(f"图片下载 {response.status_code}，{wait:.1f}s后重试 ({attempt+1}/{max_retries}): {url[:80]}")
                await asyncio.sleep(wait)
                continue
            else:
                print(f"图片下载失败 HTTP {response.status_code}: {url[:80]}")
                return None
        except Exception as e:
            if attempt < max_retries:
                wait = random.uniform(1, 2) * (attempt + 1)
                print(f"图片下载异常，{wait:.1f}s后重试 ({attempt+1}/{max_retries}): {e}")
                await asyncio.sleep(wait)
            else:
                print(f"下载图片失败 {url[:80]}: {e}")
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
    """下载文章中的所有图片，支持智能过滤、并行下载和去重"""
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
    
    # 并行下载图片
    downloaded_hashes = set()  # 用于内容去重
    successful_downloads = []
    
    # 控制并发数量，避免对目标网站造成过大压力
    max_concurrent = 5  # 最多同时下载5张图片
    
    async def download_single_image(client, url, index):
        """下载单张图片的包装函数"""
        try:
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
                        return None
                    
                    downloaded_hashes.add(content_hash)
                    
                    local_path = f'/images/{filename}'
                    print(f"[图片下载] 下载成功 [{index+1}/{len(filtered_urls)}]: {url[:50]}... -> {local_path}")
                    return {
                        'original_url': url,
                        'local_path': local_path,
                        'filename': filename,
                        'content_hash': content_hash
                    }
                except Exception as e:
                    print(f"[图片下载] 处理图片失败 {url}: {e}")
                    return None
        except Exception as e:
            print(f"[图片下载] 下载图片失败 {url}: {e}")
            return None
    
    # 使用信号量控制并发
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def download_with_semaphore(client, url, index):
        async with semaphore:
            return await download_single_image(client, url, index)
    
    # 并行下载
    async with httpx.AsyncClient() as client:
        tasks = [download_with_semaphore(client, url, i) for i, url in enumerate(filtered_urls)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        for result in results:
            if isinstance(result, dict) and result:
                successful_downloads.append(result)
                url_mapping[result['original_url']] = result['local_path']
    
    images = successful_downloads
    
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

# 添加静态文件服务
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 添加图片静态文件服务
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

@app.get("/")
async def index():
    """返回前端页面"""
    index_path = os.path.join(STATIC_DIR, "index_v3.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/extension/update")
async def extension_update_page():
    """返回扩展更新页面"""
    update_path = os.path.join(STATIC_DIR, "extension-update.html")
    with open(update_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


# ==================== 认证 API ====================

@app.get("/login")
async def login_page():
    """返回登录页面"""
    login_path = os.path.join(STATIC_DIR, "login.html")
    if os.path.exists(login_path):
        with open(login_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>login.html 不存在</h1>", status_code=500)


class LoginRequest(BaseModel):
    password: str


@app.post("/api/auth/login")
async def api_login(req: LoginRequest, request: Request, response: Response):
    """登录"""
    client_ip = request.client.host if request.client else "unknown"

    # 检查是否被锁定
    allowed, remaining = check_login_allowed(client_ip)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"success": False, "error": f"登录尝试过多，请 {remaining} 秒后再试"},
        )

    conn = get_db()
    try:
        config = load_config()
        username = config.get("username", "admin")
        user = get_user_by_username(conn, username)

        # 首次使用：还没有用户
        if user is None:
            return JSONResponse(
                status_code=200,
                content={"success": False, "need_setup": True, "error": "请先设置管理员密码"},
            )

        # 验证密码
        if not verify_password(req.password, user["password_hash"]):
            record_login_failure(client_ip)
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "密码错误"},
            )

        # 登录成功
        clear_login_attempts(client_ip)
        update_last_login(conn, user["id"])

        token = create_token(user["id"], user["username"], user["role"])
        resp = JSONResponse(content={
            "success": True,
            "user": {"username": user["username"], "role": user["role"]},
        })
        set_auth_cookie(resp, token)
        return resp
    finally:
        conn.close()


@app.post("/api/auth/logout")
async def api_logout():
    """登出"""
    resp = JSONResponse(content={"success": True})
    clear_auth_cookie(resp)
    return resp


@app.get("/api/auth/status")
async def api_auth_status(request: Request):
    """检查认证状态（无需登录）"""
    user = get_current_user(request)
    config = load_config()
    conn = get_db()
    try:
        need_setup = not has_any_user(conn)
        return {
            "authenticated": user is not None,
            "user": user if user else None,
            "guest_enabled": config.get("guest_enabled", True),
            "need_setup": need_setup,
        }
    finally:
        conn.close()


@app.get("/api/auth/me")
async def api_auth_me(request: Request):
    """获取当前用户信息"""
    user = require_auth(request)
    return {"user": user}


class SetupRequest(BaseModel):
    password: str
    username: Optional[str] = "admin"


@app.post("/api/auth/setup")
async def api_setup(req: SetupRequest, request: Request, response: Response):
    """首次使用：设置管理员密码"""
    conn = get_db()
    try:
        if has_any_user(conn):
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "管理员已存在，请直接登录"},
            )

        # 密码强度校验
        if len(req.password) < 6:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "密码至少6个字符"},
            )

        username = req.username or "admin"
        user_id = create_user(conn, username, req.password, "admin")

        token = create_token(user_id, username, "admin")
        resp = JSONResponse(content={
            "success": True,
            "user": {"username": username, "role": "admin"},
        })
        set_auth_cookie(resp, token)
        return resp
    finally:
        conn.close()


class PasswordRequest(BaseModel):
    old_password: str
    new_password: str


@app.put("/api/auth/password")
async def api_change_password(req: PasswordRequest, request: Request):
    """修改密码"""
    user = require_auth(request)
    conn = get_db()
    try:
        db_user = get_user_by_username(conn, user["username"])
        if not db_user or not verify_password(req.old_password, db_user["password_hash"]):
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "旧密码错误"},
            )
        if len(req.new_password) < 6:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "新密码至少6个字符"},
            )
        update_password(conn, db_user["id"], req.new_password)
        return {"success": True, "message": "密码已更新"}
    finally:
        conn.close()

def _background_download_images(html: str, content: str, url: str, article_id: int):
    """后台下载文章图片（同步包装）"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        images, updated_content = loop.run_until_complete(
            download_article_images(html, content, url, article_id)
        )
        loop.close()
        
        # 保存图片记录和更新内容
        conn = get_db()
        try:
            now = datetime.now().isoformat()
            for img in images:
                conn.execute("""
                    INSERT INTO images (article_id, original_url, local_path, filename, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (article_id, img['original_url'], img['local_path'], img['filename'], now))
            
            if updated_content != content:
                conn.execute(
                    "UPDATE articles SET content = ? WHERE id = ?",
                    (updated_content, article_id)
                )
            conn.commit()
            print(f"[后台] 文章 {article_id} 图片下载完成: {len(images)} 张")
        finally:
            conn.close()
    except Exception as e:
        print(f"[后台] 文章 {article_id} 图片下载失败: {e}")

@app.post("/api/save")
async def save_article(article: ArticleCreate, background_tasks: BackgroundTasks):
    """保存文章（立即返回，图片后台下载）"""
    conn = get_db()
    
    try:
        # 检查是否已存在
        existing = conn.execute(
            "SELECT id FROM articles WHERE url = ?", (article.url,)
        ).fetchone()
        
        if existing:
            raise HTTPException(status_code=400, detail="该链接已保存")
        
        # 抓取文章（线程池执行，不阻塞事件循环）
        data = await asyncio.to_thread(fetch_article, article.url)
        
        # 如果提供了标题，使用提供的标题
        if article.title:
            data['title'] = article.title
        
        # 插入数据库
        now = datetime.now().isoformat()
        tags = json.dumps(article.tags or [], ensure_ascii=False)
        
        # 获取封面图 URL
        lead_image_url = data.get('lead_image_url', '')
        
        cursor = conn.execute("""
            INSERT INTO articles (url, title, content, excerpt, tags, created_at, word_count, reading_time, lead_image_url)
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
            lead_image_url
        ))
        
        article_id = cursor.lastrowid
        conn.commit()
        
        # 图片后台下载，不阻塞返回
        if data.get("html"):
            background_tasks.add_task(
                _background_download_images,
                data["html"],
                data["content"],
                data["url"],
                article_id
            )
        
        return {
            "success": True,
            "message": "保存成功",
            "article_id": article_id,
            "images_pending": bool(data.get("html"))
        }
    except HTTPException:
        raise
    except Exception as e:
        # 记录抓取失败
        error_type = "unknown"
        error_msg = str(e)
        
        # 根据错误信息判断错误类型
        if "timeout" in error_msg.lower():
            error_type = "timeout"
        elif "403" in error_msg or "forbidden" in error_msg.lower():
            error_type = "http_error"
        elif "404" in error_msg or "not found" in error_msg.lower():
            error_type = "http_error"
        elif "connection" in error_msg.lower():
            error_type = "network"
        elif "captcha" in error_msg.lower() or "验证" in error_msg or "CAPTCHA_REQUIRED" in error_msg:
            error_type = "captcha"
            # 提取用户友好的消息
            if "CAPTCHA_REQUIRED:" in error_msg:
                error_msg = error_msg.replace("CAPTCHA_REQUIRED:", "")
        elif "parse" in error_msg.lower() or "提取" in error_msg:
            error_type = "parse"
        
        record_fetch_error(
            conn,
            url=article.url,
            error_type=error_type,
            error_message=error_msg,
            title=article.title or '',
            metadata={"source": "save_article"}
        )
        
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/articles/{article_id}/refetch")
async def refetch_article(article_id: int):
    """重新抓取文章（重新获取内容和图片）"""
    conn = get_db()
    
    try:
        # 获取现有文章
        article = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
        if not article:
            raise HTTPException(status_code=404, detail="文章不存在")
        
        url = article['url']
        
        # 删除旧图片文件和记录
        old_images = conn.execute("SELECT filename FROM images WHERE article_id = ?", (article_id,)).fetchall()
        for img in old_images:
            filepath = os.path.join(IMAGES_DIR, img['filename'])
            if os.path.exists(filepath):
                os.remove(filepath)
        conn.execute("DELETE FROM images WHERE article_id = ?", (article_id,))
        conn.commit()
        
        # 重新抓取文章（线程池执行）
        data = await asyncio.to_thread(fetch_article, url)
        
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
        
        return {
            "success": True,
            "message": "重新抓取成功",
            "article_id": article_id,
            "title": data["title"],
            "images_count": len(images)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/articles/{article_id}/images")
async def get_article_images(article_id: int):
    """获取文章的图片列表"""
    conn = get_db()
    
    try:
        # 检查文章是否存在
        article = conn.execute(
            "SELECT id FROM articles WHERE id = ?", (article_id,)
        ).fetchone()
        
        if not article:
            raise HTTPException(status_code=404, detail="文章不存在")
        
        # 获取图片列表
        rows = conn.execute(
            "SELECT * FROM images WHERE article_id = ? ORDER BY id",
            (article_id,)
        ).fetchall()
        
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
    except HTTPException:
        raise
    finally:
        conn.close()

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
    order: str = "desc",
    time_filter: Optional[str] = None,
    reading_time_min: Optional[int] = None,
    reading_time_max: Optional[int] = None
):
    """获取文章列表"""
    # 尝试从缓存获取
    cache_key = f"articles_{page}_{per_page}_{is_read}_{is_favorite}_{is_archived}_{tag}_{search}_{sort}_{order}_{time_filter}_{reading_time_min}_{reading_time_max}"
    cached = article_cache.get(cache_key)
    if cached:
        return cached
    
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
    
    # 智能时间筛选
    if time_filter:
        from datetime import date, timedelta
        today = date.today()
        if time_filter == "today":
            conditions.append("created_at >= ?")
            params.append(today.isoformat())
        elif time_filter == "this_week":
            # 本周一
            monday = today - timedelta(days=today.weekday())
            conditions.append("created_at >= ?")
            params.append(monday.isoformat())
        elif time_filter == "this_month":
            first_day = today.replace(day=1)
            conditions.append("created_at >= ?")
            params.append(first_day.isoformat())
        elif time_filter == "this_year":
            first_day = today.replace(month=1, day=1)
            conditions.append("created_at >= ?")
            params.append(first_day.isoformat())
    
    # 阅读时间筛选
    if reading_time_min is not None:
        conditions.append("reading_time >= ?")
        params.append(reading_time_min)
    
    if reading_time_max is not None:
        conditions.append("reading_time <= ?")
        params.append(reading_time_max)
    
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
            "reading_time": row["reading_time"],
            "lead_image_url": row["lead_image_url"] if "lead_image_url" in row.keys() else ""
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
        "reading_time": row["reading_time"],
        "lead_image_url": row["lead_image_url"] if "lead_image_url" in row.keys() else ""
    }

@app.put("/api/articles/{article_id}")
async def update_article(article_id: int, update: ArticleUpdate):
    """更新文章"""
    conn = get_db()
    
    try:
        # 检查文章是否存在
        existing = conn.execute(
            "SELECT id FROM articles WHERE id = ?", (article_id,)
        ).fetchone()
        
        if not existing:
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
        
        return {"success": True}
    except HTTPException:
        raise
    finally:
        conn.close()

@app.patch("/api/articles/{article_id}")
async def patch_article(article_id: int, update: ArticleUpdate):
    """更新文章（PATCH方法）"""
    # 复用PUT端点的逻辑
    return await update_article(article_id, update)

@app.delete("/api/articles/{article_id}")
async def delete_article(article_id: int):
    """删除文章"""
    conn = get_db()
    
    try:
        result = conn.execute(
            "DELETE FROM articles WHERE id = ?", (article_id,)
        )
        conn.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="文章不存在")
        
        return {"success": True}
    except HTTPException:
        raise
    finally:
        conn.close()

@app.get("/api/stats")
async def get_stats():
    """获取统计信息"""
    # 尝试从缓存获取
    cached = stats_cache.get("stats")
    if cached:
        return cached
    
    conn = get_db()
    
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    read = conn.execute("SELECT COUNT(*) FROM articles WHERE is_read = 1").fetchone()[0]
    unread = total - read
    favorites = conn.execute("SELECT COUNT(*) FROM articles WHERE is_favorite = 1").fetchone()[0]
    archived = conn.execute("SELECT COUNT(*) FROM articles WHERE is_archived = 1").fetchone()[0]
    
    # 本周新增
    from datetime import datetime, timedelta, timezone
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    this_week = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE created_at >= ?", (week_ago,)
    ).fetchone()[0]
    
    conn.close()
    
    result = {
        "total": total,
        "read": read,
        "unread": unread,
        "favorites": favorites,
        "archived": archived,
        "this_week": this_week
    }
    stats_cache.set("stats", result)
    return result

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
    
    try:
        # 解析文章ID
        ids = None
        if article_ids:
            try:
                ids = [int(id.strip()) for id in article_ids.split(',') if id.strip()]
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的文章ID格式")
        
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
            raise HTTPException(status_code=400, detail=f"不支持的导出格式: {format}")
        
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
    
    except HTTPException:
        raise
    except ImportError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")
    finally:
        conn.close()

# ==================== 批注功能 API ====================

class AnnotationCreate(BaseModel):
    article_id: int
    highlight_text: str
    start_offset: int
    end_offset: int
    note: Optional[str] = ''
    color: Optional[str] = '#ffeb3b'

class AnnotationUpdate(BaseModel):
    note: Optional[str] = None
    color: Optional[str] = None

@app.get("/api/annotations/stats")
async def api_get_annotations_stats():
    """获取批注统计信息"""
    conn = get_db()
    try:
        stats = get_annotations_stats(conn)
        return stats
    finally:
        conn.close()

@app.get("/api/annotations/all")
async def api_get_all_annotations(limit: int = 50, offset: int = 0):
    """获取所有批注（带分页）"""
    conn = get_db()
    try:
        annotations = get_all_annotations(conn, limit=limit, offset=offset)
        return {"annotations": annotations, "count": len(annotations)}
    finally:
        conn.close()

@app.get("/api/articles/{article_id}/annotations")
async def api_get_article_annotations(article_id: int):
    """获取文章的所有批注"""
    conn = get_db()
    try:
        # 验证文章存在
        article = conn.execute("SELECT id FROM articles WHERE id = ?", (article_id,)).fetchone()
        if not article:
            raise HTTPException(status_code=404, detail="文章不存在")
        
        annotations = get_annotations(conn, article_id)
        return {"annotations": annotations, "count": len(annotations)}
    finally:
        conn.close()

@app.post("/api/annotations")
async def api_create_annotation(annotation: AnnotationCreate):
    """创建批注"""
    conn = get_db()
    try:
        result = create_annotation(
            conn,
            article_id=annotation.article_id,
            highlight_text=annotation.highlight_text,
            start_offset=annotation.start_offset,
            end_offset=annotation.end_offset,
            note=annotation.note or '',
            color=annotation.color or '#ffeb3b'
        )
        return {"success": True, "annotation": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建批注失败: {str(e)}")
    finally:
        conn.close()

@app.get("/api/annotations/{annotation_id}")
async def api_get_annotation(annotation_id: int):
    """获取单个批注详情"""
    conn = get_db()
    try:
        annotation = get_annotation(conn, annotation_id)
        if not annotation:
            raise HTTPException(status_code=404, detail="批注不存在")
        return annotation
    finally:
        conn.close()

@app.put("/api/annotations/{annotation_id}")
async def api_update_annotation(annotation_id: int, update: AnnotationUpdate):
    """更新批注"""
    conn = get_db()
    try:
        result = update_annotation(
            conn,
            annotation_id=annotation_id,
            note=update.note,
            color=update.color
        )
        if not result:
            raise HTTPException(status_code=404, detail="批注不存在")
        return {"success": True, "annotation": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@app.delete("/api/annotations/{annotation_id}")
async def api_delete_annotation(annotation_id: int):
    """删除批注"""
    conn = get_db()
    try:
        success = delete_annotation(conn, annotation_id)
        if not success:
            raise HTTPException(status_code=404, detail="批注不存在")
        return {"success": True}
    finally:
        conn.close()

# ==================== 抓取错误管理 API ====================

@app.get("/api/fetch-errors/stats")
async def api_get_fetch_errors_stats():
    """获取抓取错误统计"""
    conn = get_db()
    try:
        stats = get_fetch_errors_stats(conn)
        return stats
    finally:
        conn.close()

@app.get("/api/fetch-errors")
async def api_get_fetch_errors(unresolved_only: bool = True, limit: int = 50, offset: int = 0):
    """获取抓取错误列表"""
    conn = get_db()
    try:
        errors = get_fetch_errors(conn, unresolved_only=unresolved_only, limit=limit, offset=offset)
        return {"errors": errors, "count": len(errors)}
    finally:
        conn.close()

@app.get("/api/fetch-errors/{error_id}")
async def api_get_fetch_error(error_id: int):
    """获取单个抓取错误详情"""
    conn = get_db()
    try:
        error = get_fetch_error(conn, error_id)
        if not error:
            raise HTTPException(status_code=404, detail="错误记录不存在")
        return error
    finally:
        conn.close()

@app.post("/api/fetch-errors/{error_id}/resolve")
async def api_resolve_fetch_error(error_id: int):
    """标记抓取错误为已解决"""
    conn = get_db()
    try:
        success = resolve_fetch_error(conn, error_id)
        if not success:
            raise HTTPException(status_code=404, detail="错误记录不存在")
        return {"success": True}
    finally:
        conn.close()

@app.post("/api/fetch-errors/{error_id}/retry")
async def api_retry_fetch_error(error_id: int):
    """重试抓取失败的URL"""
    conn = get_db()
    try:
        error = get_fetch_error(conn, error_id)
        if not error:
            raise HTTPException(status_code=404, detail="错误记录不存在")
        
        url = error["url"]
        title = error.get("title", "")
        
        # 尝试重新抓取
        try:
            data = await asyncio.to_thread(fetch_article, url, title if title else None)
            
            # 抓取成功，保存文章
            now = datetime.now().isoformat()
            tags = json.dumps([], ensure_ascii=False)
            
            # 获取封面图 URL
            lead_image_url = data.get('lead_image_url', '')
            
            cursor = conn.execute("""
                INSERT INTO articles (url, title, content, excerpt, tags, created_at, word_count, reading_time, lead_image_url)
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
                lead_image_url
            ))
            
            article_id = cursor.lastrowid
            
            # 应用自动标签规则
            matched_tags = apply_rules_to_article(conn, article_id, data["url"], data["title"], data["content"])
            if matched_tags:
                conn.execute(
                    "UPDATE articles SET tags = ? WHERE id = ?",
                    (json.dumps(matched_tags, ensure_ascii=False), article_id)
                )
            
            conn.commit()
            
            # 标记错误为已解决
            resolve_fetch_error(conn, error_id)
            
            return {
                "success": True,
                "message": "抓取成功",
                "article_id": article_id,
                "title": data["title"]
            }
        except Exception as e:
            # 抓取仍然失败，更新错误记录
            record_fetch_error(
                conn,
                url=url,
                error_type="retry_failed",
                error_message=str(e),
                title=title
            )
            return {
                "success": False,
                "message": f"重试失败: {str(e)}"
            }
    finally:
        conn.close()

@app.delete("/api/fetch-errors/{error_id}")
async def api_delete_fetch_error(error_id: int):
    """删除抓取错误记录"""
    conn = get_db()
    try:
        success = delete_fetch_error(conn, error_id)
        if not success:
            raise HTTPException(status_code=404, detail="错误记录不存在")
        return {"success": True}
    finally:
        conn.close()

@app.delete("/api/fetch-errors/clear-resolved")
async def api_clear_resolved_errors():
    """清除所有已解决的错误记录"""
    conn = get_db()
    try:
        count = clear_resolved_errors(conn)
        return {"success": True, "deleted_count": count}
    finally:
        conn.close()

# ==================== 自动标签规则 API ====================

class TagRuleCreate(BaseModel):
    name: str
    rule_type: str
    pattern: str
    tags: List[str]
    priority: Optional[int] = 0

class TagRuleUpdate(BaseModel):
    name: Optional[str] = None
    rule_type: Optional[str] = None
    pattern: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None

@app.get("/api/rules/stats")
async def api_get_rules_stats():
    """获取规则统计信息"""
    conn = get_db()
    try:
        stats = get_rules_stats(conn)
        return stats
    finally:
        conn.close()

@app.get("/api/rules")
async def api_get_rules():
    """获取所有标签规则"""
    conn = get_db()
    try:
        rules = get_all_rules(conn)
        return {"rules": rules}
    finally:
        conn.close()

@app.post("/api/rules")
async def api_create_rule(rule: TagRuleCreate):
    """创建标签规则"""
    conn = get_db()
    try:
        result = create_rule(
            conn,
            name=rule.name,
            rule_type=rule.rule_type,
            pattern=rule.pattern,
            tags=rule.tags,
            priority=rule.priority or 0
        )
        return {"success": True, "rule": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@app.get("/api/rules/{rule_id}")
async def api_get_rule(rule_id: int):
    """获取单个规则详情"""
    conn = get_db()
    try:
        rule = get_rule(conn, rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="规则不存在")
        return rule
    finally:
        conn.close()

@app.put("/api/rules/{rule_id}")
async def api_update_rule(rule_id: int, update: TagRuleUpdate):
    """更新标签规则"""
    conn = get_db()
    try:
        success = update_rule(
            conn,
            rule_id=rule_id,
            name=update.name,
            rule_type=update.rule_type,
            pattern=update.pattern,
            tags=update.tags,
            is_active=update.is_active,
            priority=update.priority
        )
        if not success:
            raise HTTPException(status_code=404, detail="规则不存在")
        
        # 获取更新后的规则
        rule = get_rule(conn, rule_id)
        return {"success": True, "rule": rule}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@app.delete("/api/rules/{rule_id}")
async def api_delete_rule(rule_id: int):
    """删除标签规则"""
    conn = get_db()
    try:
        success = delete_rule(conn, rule_id)
        if not success:
            raise HTTPException(status_code=404, detail="规则不存在")
        return {"success": True}
    finally:
        conn.close()

@app.post("/api/rules/apply-all")
async def api_apply_rules_to_all():
    """将所有规则应用到所有文章"""
    conn = get_db()
    try:
        result = apply_rules_to_all(conn)
        return {"success": True, "result": result}
    finally:
        conn.close()

# ==================== RSS ====================

@app.get("/api/rss")
async def rss_feed(request: Request):
    """生成 RSS 2.0 订阅源"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM articles WHERE is_archived = 0 ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    conn.close()

    base_url = str(request.base_url).rstrip('/')
    
    items = []
    for row in rows:
        title = (row["title"] or "无标题").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        link = row["url"] or ""
        excerpt = (row["excerpt"] or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        content = (row["content"] or "")[:2000]
        content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        pub_date = row["created_at"] or ""
        # 格式化为 RFC 822 日期
        try:
            dt = datetime.fromisoformat(pub_date)
            pub_date_rfc = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
        except Exception as e:
            pub_date_rfc = pub_date
        
        items.append(f"""    <item>
      <title>{title}</title>
      <link>{link}</link>
      <description>{excerpt}</description>
      <content:encoded><![CDATA[{row["content"] or ""}]]></content:encoded>
      <pubDate>{pub_date_rfc}</pubDate>
      <guid isPermaLink="false">readlater-{row["id"]}</guid>
    </item>""")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>ReadLater - 我的文章收藏</title>
    <link>{base_url}</link>
    <description>ReadLater 稍后阅读应用的文章订阅源</description>
    <language>zh-cn</language>
    <lastBuildDate>{datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>
{chr(10).join(items)}
  </channel>
</rss>"""

    from fastapi.responses import Response
    return Response(content=xml, media_type="application/rss+xml; charset=utf-8")

# ==================== RSS 订阅管理 ====================

from backend.rss import get_rss_manager

@app.post("/api/rss/subscribe")
async def add_rss_subscription(feed: ArticleCreate):
    """添加 RSS 订阅"""
    rss = get_rss_manager(DB_PATH)
    
    try:
        feed_id = await rss.add_subscription(
            url=feed.url,
            title=feed.title,
            tags=feed.tags or []
        )
        return {"success": True, "feed_id": feed_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/rss/subscriptions")
async def get_rss_subscriptions():
    """获取所有 RSS 订阅"""
    rss = get_rss_manager(DB_PATH)
    return {"subscriptions": rss.get_subscriptions()}

@app.put("/api/rss/subscriptions/{feed_id}")
async def update_rss_subscription(feed_id: int, update: ArticleUpdate):
    """更新 RSS 订阅"""
    rss = get_rss_manager(DB_PATH)
    
    update_data = {}
    if update.title is not None:
        update_data['title'] = update.title
    if update.tags is not None:
        update_data['tags'] = update.tags
    
    rss.update_subscription(feed_id, **update_data)
    return {"success": True}

@app.delete("/api/rss/subscriptions/{feed_id}")
async def delete_rss_subscription(feed_id: int):
    """删除 RSS 订阅"""
    rss = get_rss_manager(DB_PATH)
    rss.delete_subscription(feed_id)
    return {"success": True}

@app.post("/api/rss/fetch/{feed_id}")
async def fetch_rss_feed(feed_id: int):
    """抓取 RSS 订阅的最新文章"""
    rss = get_rss_manager(DB_PATH)
    conn = get_db()
    
    # 获取订阅信息
    subs = rss.get_subscriptions(active_only=False)
    feed = next((s for s in subs if s['id'] == feed_id), None)
    
    if not feed:
        raise HTTPException(status_code=404, detail="订阅不存在")
    
    try:
        # 解析 feed
        feed_data = await rss.parse_feed(feed['url'])
        saved_count = 0
        
        for item in feed_data['items']:
            # 检查是否已保存
            if rss.is_item_saved(feed_id, item.url):
                continue
            
            # 检查文章库是否已有
            existing = conn.execute(
                "SELECT id FROM articles WHERE url = ?", (item.url,)
            ).fetchone()
            
            if existing:
                rss.mark_item_saved(feed_id, item.url, item.title)
                continue
            
            # 抓取并保存文章
            try:
                data = await asyncio.to_thread(fetch_article, item.url)
                tags = list(set(feed['tags'] + item.tags))
                now = datetime.now().isoformat()
                
                # 获取封面图 URL
                lead_image_url = data.get('lead_image_url', '')
                
                cursor = conn.execute("""
                    INSERT INTO articles (url, title, content, excerpt, tags, created_at, word_count, reading_time, domain, lead_image_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data["url"], data["title"], data["content"], data["excerpt"],
                    json.dumps(tags, ensure_ascii=False), now,
                    data["word_count"], data["reading_time"], data.get("domain", ""),
                    lead_image_url
                ))
                
                article_id = cursor.lastrowid
                conn.commit()
                
                # 下载图片
                images, updated_content = await download_article_images(
                    data["html"], data["content"], data["url"], article_id
                )
                
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
                rss.mark_item_saved(feed_id, item.url, item.title)
                saved_count += 1
                
            except Exception as e:
                print(f"保存文章失败 {item.url}: {e}")
                continue
        
        # 更新最后抓取时间
        rss.update_subscription(feed_id, last_fetched=datetime.now().isoformat())
        
        conn.close()
        return {"success": True, "saved_count": saved_count, "total_items": len(feed_data['items'])}
        
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/rss/fetch-all")
async def fetch_all_rss_feeds():
    """抓取所有活跃订阅"""
    rss = get_rss_manager(DB_PATH)
    subscriptions = rss.get_subscriptions(active_only=True)
    
    results = []
    for sub in subscriptions:
        try:
            result = await fetch_rss_feed(sub['id'])
            results.append({
                "feed_id": sub['id'],
                "title": sub['title'],
                **result
            })
        except Exception as e:
            results.append({
                "feed_id": sub['id'],
                "title": sub['title'],
                "success": False,
                "error": str(e)
            })
    
    return {"results": results}

@app.get("/api/rss/stats")
async def get_rss_stats():
    """获取 RSS 统计"""
    rss = get_rss_manager(DB_PATH)
    return rss.get_stats()

@app.get("/api/extension/version")
async def get_extension_version():
    """获取浏览器扩展最新版本信息"""
    # 这里可以从数据库或配置文件中读取，现在先硬编码
    return {
        "latest_version": "1.1.0",
        "changelog": "1. 添加服务器选择功能\n2. 添加检查更新功能\n3. 修复错误提示问题",
        "download_url": "http://localhost:8000/extension/update"
    }

# ==================== 每日新闻头条 ====================

# 导入新闻模块
try:
    from backend.daily_news import fetch_all_news, init_news_table, save_news_to_db, get_today_news, ALL_FETCHERS
except ImportError:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from backend.daily_news import fetch_all_news, init_news_table, save_news_to_db, get_today_news, ALL_FETCHERS

# 初始化新闻表
init_news_table(DB_PATH)

@app.post("/api/news/fetch")
async def api_fetch_news(request: Request):
    """手动抓取新闻头条"""
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    sources = body.get("sources", None)  # None=全部, 或指定来源列表
    
    all_items = fetch_all_news(sources)
    
    stats = {}
    total = 0
    for source_name, items in all_items.items():
        count = save_news_to_db(items, DB_PATH)
        stats[source_name] = count
        total += count
    
    return {"success": True, "total": total, "stats": stats}

@app.get("/api/news")
async def api_get_news(source: str = None, date: str = None):
    """获取新闻列表"""
    conn = get_db()
    try:
        target_date = date or datetime.now().strftime("%Y-%m-%d")
        
        if source:
            rows = conn.execute(
                "SELECT * FROM daily_news WHERE fetch_date = ? AND source = ? ORDER BY rank",
                (target_date, source)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM daily_news WHERE fetch_date = ? ORDER BY source, rank",
                (target_date,)
            ).fetchall()
        
        items = []
        for row in rows:
            r = dict(row)
            items.append(r)
        
        # 按来源分组
        grouped = {}
        for item in items:
            src = item.get("source", "未知")
            if src not in grouped:
                grouped[src] = {
                    "source": src,
                    "icon": item.get("source_icon", "📰"),
                    "items": []
                }
            grouped[src]["items"].append(item)
        
        return {
            "date": target_date,
            "sources": list(grouped.values()),
            "total": len(items)
        }
    finally:
        conn.close()

@app.get("/api/news/sources")
async def api_get_news_sources():
    """获取可用新闻来源列表"""
    sources = []
    for name, _ in ALL_FETCHERS:
        sources.append({"name": name, "enabled": True})
    return {"sources": sources}

@app.delete("/api/news")
async def api_clear_news(date: str = None):
    """清除指定日期的新闻（默认清除今天）"""
    conn = get_db()
    try:
        target_date = date or datetime.now().strftime("%Y-%m-%d")
        conn.execute("DELETE FROM daily_news WHERE fetch_date = ?", (target_date,))
        conn.commit()
        return {"success": True, "cleared_date": target_date}
    finally:
        conn.close()

# ==================== 主程序 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
