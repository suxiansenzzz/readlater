"""
ReadLater - 网页抓取增强版 v2.0
支持知乎、CSDN等需要特殊处理的网站
集成反爬虫模块：Playwright浏览器 + ddddocr验证码识别
"""
import os
import re
import json
import hashlib
import asyncio
from urllib.parse import urljoin, urlparse
from typing import Optional, List, Tuple, Dict, Any
import httpx

# 导入反爬模块
try:
    from anticrawl import AntiCrawlFetcher, fetch_sync, CaptchaType
    ANTICRAWL_AVAILABLE = True
except ImportError as e:
    ANTICRAWL_AVAILABLE = False
    print(f"警告: 反爬模块不可用 ({e})，将使用基础抓取")

# 请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# 需要浏览器模式的网站列表
BROWSER_REQUIRED_SITES = [
    'smzdm.com',      # 什么值得买
    'zhihu.com',      # 知乎
    'csdn.net',       # CSDN
    'juejin.cn',      # 掘金
    'jianshu.com',    # 简书
    'weixin.qq.com',  # 微信公众号
    'mp.weixin.qq.com',
    '36kr.com',       # 36氪
    'infoq.cn',       # InfoQ
    'bilibili.com',   # B站专栏
    'tieba.baidu.com',# 百度贴吧
    'douban.com',     # 豆瓣
    'xiaohongshu.com',# 小红书
    'weibo.com',      # 微博
]


def is_article_image(url: str, base_url: str) -> bool:
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
        '/thumb/', '/thumbnail/',                      # 缩略图（通常是小图）
        'avatar_placeholder',                          # 头像占位图
        'otter_avatar',                                # 少数派头像占位图
        '/icons/',                                     # 图标目录
        'logo.gif',                                    # 网站logo
        'ghs.png',                                     # 备案图标
    ]
    
    for pattern in skip_patterns:
        if pattern in path:
            return False
    
    # 过滤掉太小的图片（通过URL判断）
    if any(size in path for size in ['_16.', '_24.', '_32.', '_48.', '_64.', '_80.', '_96.']):
        return False
    
    # 过滤掉明显的追踪像素
    if '1x1' in path or 'pixel' in path:
        return False
    
    return True


def needs_browser_mode(url: str) -> bool:
    """判断是否需要使用浏览器模式 - 默认不使用，除非明确需要"""
    # 只有在明确需要 JS 渲染的情况下才使用浏览器
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    # 这些网站明确需要浏览器
    browser_required = [
        'mp.weixin.qq.com',  # 微信公众号需要 JS
    ]
    
    for site in browser_required:
        if site in domain:
            return True
    return False


def fetch_with_httpx(url: str, timeout: int = 30) -> Optional[str]:
    """使用httpx下载网页 - 优化版"""
    try:
        # 随机化 User-Agent
        import random
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15',
        ]
        
        headers = {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }
        
        # 添加 Referer
        parsed = urlparse(url)
        referers = [
            f"https://www.baidu.com/",
            f"https://www.google.com/",
            f"https://{parsed.netloc}/",
            "",
        ]
        headers['Referer'] = random.choice(referers)
        
        with httpx.Client(
            follow_redirects=True, 
            timeout=timeout,
            headers=headers,
            verify=False
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text
    except Exception as e:
        print(f"httpx下载失败: {e}")
        return None


def fetch_with_anticrawl(url: str, timeout: int = 30) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    使用反爬模块抓取网页
    
    Returns:
        (success, html, error)
    """
    if not ANTICRAWL_AVAILABLE:
        # 降级到普通 httpx
        html = fetch_with_httpx(url, timeout)
        if html:
            return True, html, None
        return False, None, "反爬模块不可用，httpx抓取失败"
    
    # 判断是否需要浏览器模式
    force_browser = needs_browser_mode(url)
    
    # 检查是否已经在事件循环中
    try:
        loop = asyncio.get_running_loop()
        # 如果已经在事件循环中，使用同步方式调用
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, fetch_with_anticrawl_async(url, force_browser=force_browser, timeout=timeout))
            return future.result()
    except RuntimeError:
        # 没有运行的事件循环，可以直接使用 asyncio.run
        return asyncio.run(fetch_with_anticrawl_async(url, force_browser=force_browser, timeout=timeout))


async def fetch_with_anticrawl_async(
    url: str,
    force_browser: bool = False,
    timeout: int = 30
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    反爬虫抓取（异步版本）
    
    Returns:
        (success, html, error)
    """
    fetcher = AntiCrawlFetcher()
    result = await fetcher.fetch(url, use_browser=force_browser, timeout=timeout)
    return result.success, result.html, result.error


def extract_zhihu_content(html: str) -> dict:
    """从知乎页面提取内容"""
    # 提取标题
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE)
    title = title_match.group(1) if title_match else "无标题"
    title = title.replace(' - 知乎', '').strip()
    
    # 提取文章内容
    content = ""
    
    # 方法1: 从JSON数据中提取
    json_match = re.search(r'<script[^>]*>window\.__INITIAL_DATA__\s*=\s*({.*?})</script>', html, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            # 尝试从不同路径获取内容
            if 'initialData' in data:
                initial = data['initialData']
                if 'content' in initial:
                    content = initial['content']
                elif 'detail' in initial:
                    content = initial['detail'].get('content', '')
        except json.JSONDecodeError:
            pass
    
    # 方法2: 直接从 HTML 提取
    if not content:
        # 查找文章主体
        content_match = re.search(r'<div[^>]*class="[^"]*RichText[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
        if content_match:
            content = content_match.group(1)
    
    # 方法3: 查找所有段落
    if not content:
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
        content = '\n'.join(paragraphs)
    
    return {
        'title': title,
        'content': content,
        'html': html
    }


def extract_csdn_content(html: str) -> dict:
    """从CSDN页面提取内容"""
    # 提取标题
    title_match = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h1>', html, re.DOTALL)
    if not title_match:
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else "无标题"
    title = re.sub(r'<[^>]+>', '', title)  # 移除HTML标签
    title = title.replace('_CSDN博客', '').replace('-CSDN博客', '').strip()
    
    # 提取文章内容
    content = ""
    
    # 方法1: 从JSON数据提取
    json_match = re.search(r'article_content.*?<script[^>]*>.*?({.*?})\s*</script>', html, re.DOTALL)
    if json_match:
        try:
            # CSDN 的内容可能在不同位置
            content_match = re.search(r'<div[^>]*id="content_views"[^>]*>(.*?)</div>', html, re.DOTALL)
            if content_match:
                content = content_match.group(1)
        except:
            pass
    
    # 方法2: 直接从 HTML 提取
    if not content:
        content_match = re.search(r'<div[^>]*id="content_views"[^>]*>(.*?)</div>\s*</article>', html, re.DOTALL)
        if content_match:
            content = content_match.group(1)
    
    # 方法3: 查找文章主体
    if not content:
        content_match = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
        if content_match:
            content = content_match.group(1)
    
    return {
        'title': title,
        'content': content,
        'html': html
    }


def extract_weixin_content(html: str) -> dict:
    """从微信公众号页面提取内容"""
    # 提取标题
    title_match = re.search(r'var\s+msg_title\s*=\s*["\'](.+?)["\'];', html)
    if not title_match:
        title_match = re.search(r'<h1[^>]*id="activity-name"[^>]*>(.*?)</h1>', html, re.DOTALL)
    if not title_match:
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else "无标题"
    title = re.sub(r'<[^>]+>', '', title)
    
    # 提取文章内容
    content = ""
    content_match = re.search(r'<div[^>]*id="js_content"[^>]*>(.*?)</div>\s*<script', html, re.DOTALL)
    if content_match:
        content = content_match.group(1)
    
    return {
        'title': title,
        'content': content,
        'html': html
    }


def extract_juejin_content(html: str) -> dict:
    """从掘金页面提取内容"""
    # 提取标题
    title_match = re.search(r'<h1[^>]*class="[^"]*article-title[^"]*"[^>]*>(.*?)</h1>', html, re.DOTALL)
    if not title_match:
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else "无标题"
    title = re.sub(r'<[^>]+>', '', title)
    title = title.replace(' - 掘金', '').strip()
    
    # 提取文章内容
    content = ""
    content_match = re.search(r'<div[^>]*class="[^"]*article-content[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
    if content_match:
        content = content_match.group(1)
    
    # 方法2: 从JSON提取
    if not content:
        json_match = re.search(r'"article_info":\s*{[^}]*"mark_content":\s*"(.*?)"', html)
        if json_match:
            content = json_match.group(1).replace('\\n', '\n').replace('\\"', '"')
    
    return {
        'title': title,
        'content': content,
        'html': html
    }


def extract_generic_content(html: str) -> dict:
    """通用内容提取（使用BeautifulSoup保留图片，trafilatura作为备选）"""
    # 提取标题
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else "无标题"
    title = re.sub(r'<[^>]+>', '', title)
    
    # 优先使用BeautifulSoup提取（保留图片）
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')
        
        # 尝试找到文章正文区域
        article_content = None
        for selector in ['article', '.article', '.post', '.content', '.entry-content', '[role="article"]', '.article-content']:
            article_content = soup.select_one(selector)
            if article_content:
                break
        
        if not article_content:
            # 尝试找包含最多<p>标签的div
            divs = soup.find_all('div')
            best_div = None
            best_count = 0
            for div in divs:
                p_count = len(div.find_all('p'))
                if p_count > best_count:
                    best_count = p_count
                    best_div = div
            if best_div and best_count >= 3:
                article_content = best_div
        
        if article_content:
            # 清理不必要的属性，但保留img标签
            for tag in article_content.find_all(True):
                if tag.name == 'img':
                    # 保留img的关键属性
                    attrs_to_keep = ['src', 'alt', 'width', 'height', 'data-src']
                    attrs = dict(tag.attrs)
                    for attr in attrs:
                        if attr not in attrs_to_keep:
                            del tag[attr]
                elif tag.name not in ['a', 'br', 'hr']:
                    # 其他标签只保留class和style
                    attrs = dict(tag.attrs)
                    for attr in attrs:
                        if attr not in ['class', 'style', 'href']:
                            del tag[attr]
            
            content = str(article_content)
            return {'title': title, 'content': content, 'html': html}
    except ImportError:
        pass
    
    # 备选：使用trafilatura（会丢失图片）
    try:
        import trafilatura
        content = trafilatura.extract(html, include_comments=False, include_tables=True, output_format='html')
        return {'title': title, 'content': content or '', 'html': html}
    except ImportError:
        pass
    
    # 最后的备选：简单正则提取
    html_clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    html_clean = re.sub(r'<style[^>]*>.*?</style>', '', html_clean, flags=re.DOTALL)
    paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html_clean, re.DOTALL)
    if paragraphs:
        content = '\n'.join(f'<p>{p.strip()}</p>' for p in paragraphs if p.strip())
    else:
        content = re.sub(r'<[^>]+>', ' ', html_clean)
        content = re.sub(r'\s+', ' ', content).strip()
    
    return {'title': title, 'content': content, 'html': html}


def extract_content_by_site(html: str, url: str) -> dict:
    """根据网站类型选择合适的提取方法"""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    if 'zhihu.com' in domain:
        return extract_zhihu_content(html)
    elif 'csdn.net' in domain:
        return extract_csdn_content(html)
    elif 'weixin.qq.com' in domain or 'mp.weixin.qq.com' in domain:
        return extract_weixin_content(html)
    elif 'juejin.cn' in domain:
        return extract_juejin_content(html)
    else:
        return extract_generic_content(html)


def download_image(url: str, base_url: str, save_dir: str = "images") -> Optional[str]:
    """
    下载图片并保存到本地
    
    Returns:
        保存后的本地路径，如果下载失败返回 None
    """
    # 创建保存目录
    os.makedirs(save_dir, exist_ok=True)
    
    # 处理相对路径
    if not url.startswith(('http://', 'https://')):
        url = urljoin(base_url, url)
    
    # 判断是否是文章图片
    if not is_article_image(url, base_url):
        print(f"跳过装饰性图片: {url}")
        return None
    
    try:
        # 下载图片
        headers = {
            'User-Agent': HEADERS['User-Agent'],
            'Referer': base_url,  # 重要：添加 Referer 防盗链
        }
        
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            
            # 检查内容类型
            content_type = response.headers.get('content-type', '')
            if 'image' not in content_type and len(response.content) > 100:
                print(f"非图片内容: {url}")
                return None
            
            # 过滤太小的图片（可能是追踪像素）
            if len(response.content) < 1024:  # 小于1KB
                print(f"图片太小，跳过: {url} ({len(response.content)} bytes)")
                return None
            
            # 生成文件名（使用内容哈希避免重复）
            content_hash = hashlib.md5(response.content).hexdigest()
            
            # 确定文件扩展名
            ext = '.jpg'  # 默认
            if 'png' in content_type:
                ext = '.png'
            elif 'gif' in content_type:
                ext = '.gif'
            elif 'webp' in content_type:
                ext = '.webp'
            elif 'svg' in content_type:
                ext = '.svg'
            else:
                # 从URL推断
                url_lower = url.lower()
                if '.png' in url_lower:
                    ext = '.png'
                elif '.gif' in url_lower:
                    ext = '.gif'
                elif '.webp' in url_lower:
                    ext = '.webp'
                elif '.svg' in url_lower:
                    ext = '.svg'
            
            filename = f"{content_hash}{ext}"
            filepath = os.path.join(save_dir, filename)
            
            # 保存图片
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            print(f"图片已保存: {filename} ({len(response.content)} bytes)")
            return f"/images/{filename}"
            
    except Exception as e:
        print(f"下载图片失败 {url}: {e}")
        return None


def replace_image_urls(content: str, base_url: str, save_dir: str = "images") -> str:
    """
    替换内容中的图片URL为本地路径
    """
    # 匹配 markdown 格式的图片
    img_pattern = r'!\[(.*?)\]\((.*?)\)'
    
    def replace_img(match):
        alt_text = match.group(1)
        img_url = match.group(2)
        
        # 下载图片
        local_path = download_image(img_url, base_url, save_dir)
        if local_path:
            return f'![{alt_text}]({local_path})'
        else:
            return match.group(0)  # 保持原样
    
    content = re.sub(img_pattern, replace_img, content)
    
    # 匹配 HTML 格式的图片
    html_img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
    
    def replace_html_img(match):
        img_url = match.group(1)
        local_path = download_image(img_url, base_url, save_dir)
        if local_path:
            return f'<img src="{local_path}">'
        else:
            return match.group(0)
    
    content = re.sub(html_img_pattern, replace_html_img, content)
    
    return content


def fetch_article(url: str, download_images: bool = True, use_anticrawl: bool = True) -> dict:
    """
    抓取文章的主函数
    
    Args:
        url: 文章URL
        download_images: 是否下载图片
        use_anticrawl: 是否使用反爬模块
    
    Returns:
        dict: 包含 title, content, images, error 等字段
    """
    result = {
        'url': url,
        'title': '',
        'content': '',
        'html': '',  # 添加 html 字段
        'images': [],
        'error': None,
        'captcha_required': False,
        'captcha_image': None,
    }
    
    try:
        # 获取页面内容
        if use_anticrawl and ANTICRAWL_AVAILABLE:
            print(f"使用反爬模块抓取: {url}")
            success, html, error = fetch_with_anticrawl(url, timeout=30)
            
            if not success:
                result['error'] = error
                # 检查是否需要验证码
                if '验证码' in str(error) or 'captcha' in str(error).lower():
                    result['captcha_required'] = True
                return result
        else:
            print(f"使用 httpx 抓取: {url}")
            html = fetch_with_httpx(url)
            if not html:
                result['error'] = "无法获取页面内容"
                return result
        
        # 提取内容
        extracted = extract_content_by_site(html, url)
        result['title'] = extracted.get('title', '无标题')
        content = extracted.get('content', '')
        
        if not content:
            result['error'] = "无法提取文章内容"
            return result
        
        # 下载并替换图片
        if download_images:
            save_dir = os.path.join(os.path.dirname(__file__), '..', 'images')
            save_dir = os.path.abspath(save_dir)
            content = replace_image_urls(content, url, save_dir)
            
            # 收集图片信息
            img_pattern = r'!\[(.*?)\]\((/images/[^)]+)\)'
            images = re.findall(img_pattern, content)
            result['images'] = [path for _, path in images]
        
        result['content'] = content
        result['html'] = html  # 保存 HTML 用于图片提取
        
    except Exception as e:
        result['error'] = str(e)
        print(f"抓取文章失败: {e}")
    
    return result


# 测试代码
if __name__ == "__main__":
    test_urls = [
        "https://httpbin.org/get",
        "https://www.smzdm.com/p/29810861/",
        "https://www.zhihu.com/question/19550389",
    ]
    
    for url in test_urls:
        print(f"\n{'='*50}")
        print(f"测试: {url}")
        print('='*50)
        
        result = fetch_article(url, download_images=False, use_anticrawl=True)
        
        if result['error']:
            print(f"❌ 错误: {result['error']}")
            if result['captcha_required']:
                print("⚠️ 需要验证码")
        else:
            print(f"✅ 成功!")
            print(f"   标题: {result['title'][:50]}...")
            print(f"   内容长度: {len(result['content'])} 字符")
