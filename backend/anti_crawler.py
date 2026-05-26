"""
反爬虫绕过模块
提供更好的网页抓取能力
"""
import httpx
import random
import time
from typing import Optional, Dict, Any
from urllib.parse import urlparse

# 尝试导入fake_useragent
try:
    from fake_useragent import UserAgent
    ua = UserAgent()
    USE_FAKE_UA = True
    print("[反爬] 使用fake_useragent生成随机User-Agent")
except ImportError:
    USE_FAKE_UA = False
    # 常用User-Agent列表（备用）
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    ]
    print("[反爬] 使用内置User-Agent列表")

def get_random_user_agent() -> str:
    """获取随机User-Agent"""
    if USE_FAKE_UA:
        return ua.random
    else:
        return random.choice(USER_AGENTS)

def get_headers(url: str) -> Dict[str, str]:
    """获取完整的请求头"""
    parsed = urlparse(url)
    
    headers = {
        'User-Agent': get_random_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
    }
    
    # 添加Referer（模拟从搜索引擎跳转）
    referers = [
        f'https://www.google.com/',
        f'https://www.baidu.com/',
        f'https://www.bing.com/',
        f'{parsed.scheme}://{parsed.netloc}/',
    ]
    headers['Referer'] = random.choice(referers)
    
    return headers

def fetch_url_with_retry(url: str, max_retries: int = 3, timeout: int = 30) -> Optional[str]:
    """
    带重试机制的网页抓取
    
    Args:
        url: 要抓取的URL
        max_retries: 最大重试次数
        timeout: 超时时间（秒）
    
    Returns:
        网页内容，失败返回None
    """
    for attempt in range(max_retries):
        try:
            # 随机延迟（模拟人类行为）
            if attempt > 0:
                delay = random.uniform(1, 3)
                print(f"[反爬] 重试 {attempt}/{max_retries}，等待 {delay:.1f} 秒...")
                time.sleep(delay)
            
            # 获取请求头
            headers = get_headers(url)
            
            # 发送请求
            with httpx.Client(
                follow_redirects=True,
                timeout=timeout,
                headers=headers,
                verify=False  # 忽略SSL证书验证
            ) as client:
                response = client.get(url)
                
                # 检查状态码
                if response.status_code == 200:
                    print(f"[反爬] 成功抓取 {url}")
                    return response.text
                elif response.status_code == 403:
                    print(f"[反爬] 403 禁止访问，尝试更换User-Agent...")
                    continue
                elif response.status_code == 429:
                    print(f"[反爬] 429 请求过多，等待更长时间...")
                    time.sleep(random.uniform(5, 10))
                    continue
                elif response.status_code == 503:
                    print(f"[反爬] 503 服务不可用，等待后重试...")
                    time.sleep(random.uniform(3, 6))
                    continue
                else:
                    print(f"[反爬] 状态码 {response.status_code}，重试...")
                    continue
                    
        except httpx.TimeoutException:
            print(f"[反爬] 超时，重试...")
            continue
        except httpx.NetworkError as e:
            print(f"[反爬] 网络错误: {e}，重试...")
            continue
        except Exception as e:
            print(f"[反爬] 未知错误: {e}，重试...")
            continue
    
    print(f"[反爬] 抓取失败 {url}，已重试 {max_retries} 次")
    return None

def fetch_with_trafilatura(url: str) -> Optional[str]:
    """
    使用trafilatura抓取网页（带反爬优化）
    
    Args:
        url: 要抓取的URL
    
    Returns:
        网页内容，失败返回None
    """
    try:
        import trafilatura
        
        # 先用我们的方法抓取
        html = fetch_url_with_retry(url)
        if not html:
            # 如果失败，尝试直接用trafilatura
            print(f"[反爬] 使用trafilatura直接抓取...")
            html = trafilatura.fetch_url(url)
        
        return html
    except Exception as e:
        print(f"[反爬] trafilatura抓取失败: {e}")
        return None

def test_fetch(url: str) -> Dict[str, Any]:
    """
    测试抓取功能
    
    Args:
        url: 要测试的URL
    
    Returns:
        测试结果
    """
    print(f"\n{'='*60}")
    print(f"测试抓取: {url}")
    print(f"{'='*60}")
    
    start_time = time.time()
    html = fetch_url_with_retry(url)
    elapsed = time.time() - start_time
    
    if html:
        # 提取图片URL
        import re
        img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
        img_urls = re.findall(img_pattern, html)
        
        # 过滤掉小图标和base64
        filtered_imgs = [url for url in img_urls if not url.startswith('data:') and len(url) > 20]
        
        result = {
            'success': True,
            'url': url,
            'content_length': len(html),
            'image_count': len(filtered_imgs),
            'images': filtered_imgs[:5],
            'elapsed': elapsed,
        }
    else:
        result = {
            'success': False,
            'url': url,
            'error': '抓取失败',
            'elapsed': elapsed,
        }
    
    print(f"\n结果:")
    print(f"  成功: {result['success']}")
    if result['success']:
        print(f"  内容长度: {result['content_length']}")
        print(f"  图片数量: {result['image_count']}")
        print(f"  耗时: {result['elapsed']:.2f}秒")
    else:
        print(f"  错误: {result.get('error', '未知')}")
    
    return result