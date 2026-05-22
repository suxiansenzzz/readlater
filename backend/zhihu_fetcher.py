"""
ReadLater - 增强版网页抓取器
使用cloudscraper绕过反爬
"""
import cloudscraper
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

# 创建scraper实例
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'darwin',
        'desktop': True
    }
)

def fetch_zhihu(url: str) -> dict:
    """抓取知乎文章"""
    try:
        # 添加额外的headers
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        }
        
        response = scraper.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        html = response.text
        soup = BeautifulSoup(html, 'lxml')
        
        # 提取标题
        title = soup.find('title')
        title_text = title.text.replace(' - 知乎', '').strip() if title else '无标题'
        
        # 尝试从meta标签获取标题
        og_title = soup.find('meta', property='og:title')
        if og_title:
            title_text = og_title.get('content', title_text)
        
        # 提取文章内容
        content = ''
        
        # 方法1: 从script标签的JSON数据中提取
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'window.__INITIAL_DATA__' in script.string:
                # 提取JSON数据
                match = re.search(r'window\.__INITIAL_DATA__\s*=\s*({.*?});?\s*$', script.string, re.DOTALL)
                if match:
                    try:
                        import json
                        data = json.loads(match.group(1))
                        # 从data中提取content
                        if 'initialData' in data:
                            content_html = data['initialData'].get('content', '')
                            if content_html:
                                content_soup = BeautifulSoup(content_html, 'lxml')
                                content = content_soup.get_text(separator='\n', strip=True)
                    except:
                        pass
        
        # 方法2: 直接从页面提取
        if not content:
            article = soup.find('article') or soup.find('div', class_='RichText')
            if article:
                content = article.get_text(separator='\n', strip=True)
        
        # 方法3: 提取所有段落
        if not content:
            paragraphs = soup.find_all('p')
            content = '\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        
        # 提取封面图
        cover_image = None
        og_image = soup.find('meta', property='og:image')
        if og_image:
            cover_image = og_image.get('content')
        
        # 提取所有图片
        images = []
        img_tags = soup.find_all('img')
        for img in img_tags:
            src = img.get('src') or img.get('data-src') or img.get('data-original')
            if src and ('zhimg.com' in src or 'zhihu.com' in src):
                # 转换为高清图
                src = re.sub(r'_\d+x\d+\.', '.', src)
                if src not in images:
                    images.append(src)
        
        if cover_image and cover_image not in images:
            images.insert(0, cover_image)
        
        return {
            'title': title_text,
            'content': content,
            'cover_image': cover_image,
            'images': images[:20],
            'html': html
        }
        
    except Exception as e:
        print(f"抓取失败: {e}")
        raise

def test_zhihu():
    """测试知乎抓取"""
    url = "https://zhuanlan.zhihu.com/p/2014806418478355736"
    print(f"测试抓取: {url}")
    
    result = fetch_zhihu(url)
    print(f"\n✅ 抓取成功!")
    print(f"标题: {result['title']}")
    print(f"内容长度: {len(result['content'])} 字符")
    print(f"图片数量: {len(result['images'])}")
    if result['content']:
        print(f"\n内容预览:\n{result['content'][:300]}...")
    
    return result

if __name__ == "__main__":
    test_zhihu()
