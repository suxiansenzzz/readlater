"""
ReadLater - 网页抓取增强版
支持知乎、CSDN等需要特殊处理的网站
"""
import os
import re
import json
import hashlib
from urllib.parse import urljoin, urlparse
from typing import Optional, List
import httpx

# 请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

def fetch_with_httpx(url: str, timeout: int = 30) -> Optional[str]:
    """使用httpx下载网页"""
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            response = client.get(url, headers=HEADERS)
            response.raise_for_status()
            return response.text
    except Exception as e:
        print(f"httpx下载失败: {e}")
        return None

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
            if 'initialData' in data:
                content_html = data['initialData'].get('content', '')
                content = re.sub(r'<[^>]+>', '\n', content_html)
                content = re.sub(r'\n{3,}', '\n\n', content).strip()
        except:
            pass
    
    # 方法2: 从HTML中提取
    if not content:
        content_match = re.search(r'<div[^>]*class="RichText[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
        if content_match:
            content = re.sub(r'<[^>]+>', '\n', content_match.group(1))
            content = re.sub(r'\n{3,}', '\n\n', content).strip()
    
    # 提取图片
    images = []
    img_matches = re.findall(r'<img[^>]+src="([^"]+)"[^>]*>', html)
    for img_url in img_matches:
        if 'zhimg.com' in img_url or 'zhihu.com' in img_url:
            # 转换为高清图
            img_url = re.sub(r'_\d+x\d+\.', '.', img_url)
            images.append(img_url)
    
    return {
        'title': title,
        'content': content,
        'images': list(set(images))  # 去重
    }

def fetch_article_enhanced(url: str, custom_title: str = None) -> dict:
    """增强版网页抓取"""
    print(f"正在抓取: {url}")
    
    # 下载网页
    html = fetch_with_httpx(url)
    if not html:
        raise Exception("无法下载网页")
    
    # 根据网站选择提取方法
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()
    
    if 'zhihu.com' in domain:
        # 知乎特殊处理
        data = extract_zhihu_content(html)
        content = data['content']
        title = custom_title or data['title']
        images = data['images']
    else:
        # 通用提取
        import trafilatura
        content = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            include_images=True
        )
        
        metadata = trafilatura.extract_metadata(html)
        title = custom_title or (metadata.title if metadata else None) or "无标题"
        
        # 提取图片
        images = []
        img_matches = re.findall(r'<img[^>]+src="([^"]+)"[^>]*>', html)
        for img_url in img_matches:
            if img_url.startswith('//'):
                img_url = 'https:' + img_url
            elif not img_url.startswith(('http://', 'https://')):
                img_url = urljoin(url, img_url)
            if not img_url.startswith('data:'):
                images.append(img_url)
    
    if not content:
        raise Exception("无法提取正文内容")
    
    # 生成摘要
    excerpt = content[:200].replace('\n', ' ').strip()
    if len(content) > 200:
        excerpt += "..."
    
    # 计算字数和阅读时间
    word_count = len(content)
    reading_time = max(1, word_count // 500)
    
    return {
        'url': url,
        'title': title,
        'content': content,
        'excerpt': excerpt,
        'word_count': word_count,
        'reading_time': reading_time,
        'images': images[:20],  # 最多20张图
        'html': html
    }

if __name__ == "__main__":
    # 测试
    url = "https://zhuanlan.zhihu.com/p/2014806418478355736"
    result = fetch_article_enhanced(url)
    print(f"标题: {result['title']}")
    print(f"字数: {result['word_count']}")
    print(f"图片数: {len(result['images'])}")
    print(f"摘要: {result['excerpt'][:100]}...")
