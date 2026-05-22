"""
ReadLater - 知乎API抓取器
使用知乎API获取文章内容
"""
import httpx
import json
import re
from typing import Optional

# 知乎API endpoints
ZHIHU_API_BASE = "https://www.zhihu.com/api/v4"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Referer': 'https://www.zhihu.com/',
    'Origin': 'https://www.zhihu.com',
}

def extract_zhihu_id(url: str) -> Optional[str]:
    """从知乎URL中提取文章ID"""
    # 匹配 zhuanlan.zhihu.com/p/123456 格式
    match = re.search(r'zhihu\.com/p/(\d+)', url)
    if match:
        return match.group(1)
    # 匹配 www.zhihu.com/question/123456/answer/789 格式
    match = re.search(r'zhihu\.com/question/\d+/answer/(\d+)', url)
    if match:
        return match.group(1)
    return None

def fetch_zhihu_via_api(url: str) -> dict:
    """通过知乎API抓取文章"""
    article_id = extract_zhihu_id(url)
    if not article_id:
        raise Exception("无法从URL中提取文章ID")
    
    print(f"文章ID: {article_id}")
    
    # 尝试获取文章详情
    api_url = f"{ZHIHU_API_BASE}/articles/{article_id}"
    
    params = {
        'include': 'content,voteup_count,thanked_count,comment_count,created,updated',
    }
    
    try:
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            response = client.get(api_url, headers=HEADERS, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                # 提取内容
                title = data.get('title', '无标题')
                content_html = data.get('content', '')
                
                # 清理HTML标签
                content = re.sub(r'<[^>]+>', '\n', content_html)
                content = re.sub(r'\n{3,}', '\n\n', content).strip()
                
                # 提取封面图
                cover_image = data.get('title_image')
                if not cover_image:
                    # 从content中提取第一张图
                    img_match = re.search(r'<img[^>]+src="([^"]+)"', content_html)
                    if img_match:
                        cover_image = img_match.group(1)
                
                # 提取所有图片
                images = re.findall(r'<img[^>]+src="([^"]+)"', content_html)
                images = [img for img in images if 'zhimg.com' in img]
                
                if cover_image and cover_image not in images:
                    images.insert(0, cover_image)
                
                return {
                    'title': title,
                    'content': content,
                    'cover_image': cover_image,
                    'images': images[:20],
                    'html': content_html
                }
            else:
                print(f"API返回状态码: {response.status_code}")
                print(f"响应内容: {response.text[:500]}")
                raise Exception(f"API请求失败: {response.status_code}")
                
    except Exception as e:
        print(f"API请求失败: {e}")
        raise

def fetch_zhihu_alternative(url: str) -> dict:
    """备用方法：使用移动端API"""
    article_id = extract_zhihu_id(url)
    if not article_id:
        raise Exception("无法从URL中提取文章ID")
    
    # 移动端API
    mobile_api = f"https://api.zhihu.com/articles/{article_id}"
    
    mobile_headers = {
        **HEADERS,
        'x-api-version': '3.0.91',
        'x-app-za': 'OS=iOS&Release=16.6&Version=8.39.0',
    }
    
    try:
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            response = client.get(mobile_api, headers=mobile_headers)
            
            if response.status_code == 200:
                data = response.json()
                
                title = data.get('title', '无标题')
                content_html = data.get('content', '')
                
                content = re.sub(r'<[^>]+>', '\n', content_html)
                content = re.sub(r'\n{3,}', '\n\n', content).strip()
                
                cover_image = data.get('title_image')
                images = re.findall(r'<img[^>]+src="([^"]+)"', content_html)
                
                return {
                    'title': title,
                    'content': content,
                    'cover_image': cover_image,
                    'images': images[:20],
                    'html': content_html
                }
            else:
                raise Exception(f"移动端API失败: {response.status_code}")
                
    except Exception as e:
        print(f"移动端API失败: {e}")
        raise

def test_zhihu():
    """测试知乎抓取"""
    url = "https://zhuanlan.zhihu.com/p/2014806418478355736"
    print(f"测试抓取: {url}\n")
    
    try:
        result = fetch_zhihu_via_api(url)
    except Exception as e:
        print(f"主API失败，尝试备用方法...")
        result = fetch_zhihu_alternative(url)
    
    print(f"\n✅ 抓取成功!")
    print(f"标题: {result['title']}")
    print(f"内容长度: {len(result['content'])} 字符")
    print(f"图片数量: {len(result['images'])}")
    if result['content']:
        print(f"\n内容预览:\n{result['content'][:300]}...")
    
    return result

if __name__ == "__main__":
    test_zhihu()
