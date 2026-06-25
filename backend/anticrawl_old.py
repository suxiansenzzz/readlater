"""
ReadLater 反爬虫模块 v2.0
功能：
1. Playwright 无头浏览器 - 绕过 JS 反爬
2. ddddocr 验证码识别 - 自动识别图形验证码
3. 滑块验证码处理框架
4. 智能重试机制
"""

import asyncio
import base64
import hashlib
import io
import os
import random
import re
import time
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

import httpx
from PIL import Image


class CaptchaType(Enum):
    """验证码类型"""
    NONE = "none"
    IMAGE = "image"  # 图形验证码
    SLIDER = "slider"  # 滑块验证码
    CLICK = "click"  # 点选验证码
    GEETEST = "geetest"  # 极验
    RECAPTCHA = "recaptcha"  # Google reCAPTCHA
    UNKNOWN = "unknown"


@dataclass
class FetchResult:
    """抓取结果"""
    success: bool
    html: Optional[str] = None
    error: Optional[str] = None
    captcha_type: CaptchaType = CaptchaType.NONE
    captcha_image: Optional[bytes] = None
    status_code: int = 200


class UserAgentPool:
    """User-Agent 池"""
    
    DESKTOP_AGENTS = [
        # Chrome
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        # Firefox
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
        # Safari
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
        # Edge
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    ]
    
    MOBILE_AGENTS = [
        # iPhone
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Mobile/15E148 Safari/604.1",
        # Android
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    ]
    
    @classmethod
    def get_random(cls, mobile: bool = False) -> str:
        agents = cls.MOBILE_AGENTS if mobile else cls.DESKTOP_AGENTS
        return random.choice(agents)


class CaptchaSolver:
    """验证码识别器"""
    
    def __init__(self):
        self._ocr = None
    
    @property
    def ocr(self):
        if self._ocr is None:
            try:
                import ddddocr
                self._ocr = ddddocr.DdddOcr()
            except ImportError:
                print("警告: ddddocr 未安装，验证码识别功能不可用")
                return None
        return self._ocr
    
    def recognize_image_captcha(self, image_data: bytes) -> Optional[str]:
        """识别图形验证码"""
        if not self.ocr:
            return None
        try:
            result = self.ocr.classification(image_data)
            return result
        except Exception as e:
            print(f"验证码识别失败: {e}")
            return None
    
    def detect_captcha_type(self, html: str) -> CaptchaType:
        """检测页面中的验证码类型"""
        html_lower = html.lower()
        
        # 极验
        if any(x in html_lower for x in ['geetest', 'gt-init', 'geetest_challenge']):
            return CaptchaType.GEETEST
        
        # reCAPTCHA
        if any(x in html_lower for x in ['recaptcha', 'g-recaptcha', 'grecaptcha']):
            return CaptchaType.RECAPTCHA
        
        # 滑块验证码
        slider_patterns = [
            'slider', 'slide-verify', 'slideBlock',
            'captcha-slider', 'drag-verify',
            '滑动验证', '拖动滑块'
        ]
        if any(x in html_lower for x in slider_patterns):
            return CaptchaType.SLIDER
        
        # 点选验证码
        click_patterns = [
            'click-verify', 'click-captcha',
            '点选验证', '点击验证', '文字点选'
        ]
        if any(x in html_lower for x in click_patterns):
            return CaptchaType.CLICK
        
        # 图形验证码
        image_patterns = [
            'captcha', 'verify-code', 'verifycode',
            '验证码', '安全验证', 'safety check'
        ]
        if any(x in html_lower for x in image_patterns):
            return CaptchaType.IMAGE
        
        return CaptchaType.NONE
    
    def extract_captcha_image(self, html: str, base_url: str) -> Optional[bytes]:
        """从 HTML 中提取验证码图片"""
        # 查找验证码图片 URL
        patterns = [
            r'<img[^>]+src=["\']([^"\']*(?:captcha|verify)[^"\']*)["\']',
            r'<img[^>]+src=["\']([^"\']*\.(?:png|jpg|gif))["\'][^>]*(?:captcha|verify)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                img_url = match.group(1)
                if not img_url.startswith('http'):
                    from urllib.parse import urljoin
                    img_url = urljoin(base_url, img_url)
                
                # 下载图片
                try:
                    response = httpx.get(img_url, timeout=10)
                    if response.status_code == 200:
                        return response.content
                except Exception as e:
                    print(f"下载验证码图片失败: {e}")
        
        return None


class BrowserFetcher:
    """基于 Playwright 的浏览器抓取器"""
    
    def __init__(self):
        self._playwright = None
        self._browser = None
        self.captcha_solver = CaptchaSolver()
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
    
    async def start(self):
        """启动浏览器"""
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu',
                    '--window-size=1920,1080',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                ]
            )
        except Exception as e:
            print(f"启动浏览器失败: {e}")
            raise
    
    async def stop(self):
        """关闭浏览器"""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
    
    async def create_context(self):
        """创建浏览器上下文"""
        ua = UserAgentPool.get_random()
        context = await self._browser.new_context(
            user_agent=ua,
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
        )
        
        # 注入反检测脚本
        await context.add_init_script("""
            // 隐藏 webdriver 特征
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // 修改 chrome 特征
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            // 修改 permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // 修改 plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // 修改 languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en']
            });
        """)
        
        return context
    
    async def fetch_page(
        self, 
        url: str, 
        wait_for: str = 'networkidle',
        timeout: int = 30000,
        wait_selector: Optional[str] = None
    ) -> FetchResult:
        """使用浏览器抓取页面"""
        try:
            context = await self.create_context()
            page = await context.new_page()
            
            # 设置额外 headers
            await page.set_extra_http_headers({
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Referer': self._get_referer(url),
            })
            
            # 随机延迟
            await asyncio.sleep(random.uniform(0.5, 2))
            
            # 导航到页面
            response = await page.goto(url, wait_until=wait_for, timeout=timeout)
            status_code = response.status if response else 0
            
            # 等待特定元素
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=10000)
                except:
                    pass
            
            # 检测验证码
            html = await page.content()
            captcha_type = self.captcha_solver.detect_captcha_type(html)
            
            if captcha_type != CaptchaType.NONE:
                print(f"检测到验证码类型: {captcha_type.value}")
                
                if captcha_type == CaptchaType.IMAGE:
                    # 尝试识别图形验证码
                    captcha_result = await self._handle_image_captcha(page, url)
                    if captcha_result:
                        # 验证码识别成功，重新获取页面
                        html = await page.content()
                        captcha_type = CaptchaType.NONE
                    else:
                        # 截图验证码供用户处理
                        captcha_image = await self._screenshot_captcha(page)
                        await context.close()
                        return FetchResult(
                            success=False,
                            error="需要验证码",
                            captcha_type=captcha_type,
                            captcha_image=captcha_image
                        )
                elif captcha_type == CaptchaType.SLIDER:
                    # 尝试处理滑块验证码
                    captcha_result = await self._handle_slider_captcha(page)
                    if captcha_result:
                        # 滑块处理成功，等待页面加载
                        await asyncio.sleep(3)
                        html = await page.content()
                        # 再次检查是否还有验证码
                        captcha_type = self.captcha_solver.detect_captcha_type(html)
                        if captcha_type != CaptchaType.NONE:
                            captcha_image = await self._screenshot_captcha(page)
                            await context.close()
                            return FetchResult(
                                success=False,
                                error=f"滑块验证后仍需验证: {captcha_type.value}",
                                captcha_type=captcha_type,
                                captcha_image=captcha_image
                            )
                    else:
                        captcha_image = await self._screenshot_captcha(page)
                        await context.close()
                        return FetchResult(
                            success=False,
                            error="滑块验证码处理失败",
                            captcha_type=captcha_type,
                            captcha_image=captcha_image
                        )
                else:
                    # 其他类型验证码，截图返回
                    captcha_image = await self._screenshot_captcha(page)
                    await context.close()
                    return FetchResult(
                        success=False,
                        error=f"不支持的验证码类型: {captcha_type.value}",
                        captcha_type=captcha_type,
                        captcha_image=captcha_image
                    )
            
            # 模拟人类行为
            await self._human_behavior(page)
            
            # 获取最终页面内容
            html = await page.content()
            await context.close()
            
            return FetchResult(
                success=True,
                html=html,
                status_code=status_code
            )
            
        except Exception as e:
            return FetchResult(
                success=False,
                error=str(e)
            )
    
    async def _handle_image_captcha(self, page, url: str) -> bool:
        """处理图形验证码"""
        try:
            # 查找验证码图片
            captcha_selectors = [
                'img[src*="captcha"]',
                'img[src*="verify"]',
                'img[src*="Captcha"]',
                'img[src*="code"]',
                '.captcha-img img',
                '.verify-img img',
                '#captcha-img',
                '.geetest_item_img',
            ]
            
            captcha_img = None
            for selector in captcha_selectors:
                captcha_img = await page.query_selector(selector)
                if captcha_img:
                    break
            
            if not captcha_img:
                print("未找到验证码图片")
                return False
            
            # 截图验证码
            img_buffer = await captcha_img.screenshot()
            
            # 识别验证码
            code = self.captcha_solver.recognize_image_captcha(img_buffer)
            if not code:
                print("验证码识别失败")
                return False
            
            print(f"识别到验证码: {code}")
            
            # 查找输入框并输入
            input_selectors = [
                'input[name*="captcha"]',
                'input[name*="verify"]',
                'input[name*="code"]',
                'input[placeholder*="验证码"]',
                'input[placeholder*="请输入"]',
                '.captcha-input input',
                '.verify-input input',
                'input[type="text"]',
            ]
            
            for selector in input_selectors:
                input_elem = await page.query_selector(selector)
                if input_elem:
                    # 清空输入框
                    await input_elem.fill('')
                    # 输入验证码
                    await input_elem.type(code, delay=100)  # 模拟人工输入
                    
                    # 随机延迟
                    import random
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    
                    # 查找提交按钮
                    submit_selectors = [
                        'button[type="submit"]',
                        'input[type="submit"]',
                        'button:has-text("验证")',
                        'button:has-text("提交")',
                        'button:has-text("确认")',
                        '.captcha-btn',
                        '.verify-btn',
                    ]
                    
                    for btn_selector in submit_selectors:
                        submit_btn = await page.query_selector(btn_selector)
                        if submit_btn:
                            await submit_btn.click()
                            await asyncio.sleep(2)
                            return True
            
            # 尝试直接按 Enter
            await page.keyboard.press('Enter')
            await asyncio.sleep(2)
            return True
            
        except Exception as e:
            print(f"处理验证码失败: {e}")
            return False
    
    async def _handle_slider_captcha(self, page) -> bool:
        """处理滑块验证码（基础实现）"""
        try:
            # 查找滑块 - 更广泛的选择器
            slider_selectors = [
                # 极验
                '.geetest_slider_button',
                '.geetest_btn',
                '.geetest_slider',
                # 百度
                '#pass-slide-button',
                '.pass-slide-btn',
                # 通用
                '.slider-btn',
                '.slide-btn',
                '.slide-button',
                '[class*="slider"]',
                '[class*="slide-"] button',
                '[class*="drag"]',
                # 更通用的选择器
                'div[style*="cursor: move"]',
                'div[style*="cursor:grab"]',
                '[role="slider"]',
            ]
            
            slider = None
            for selector in slider_selectors:
                try:
                    slider = await page.query_selector(selector)
                    if slider:
                        print(f"找到滑块: {selector}")
                        break
                except:
                    continue
            
            if not slider:
                # 尝试查找所有可拖动元素
                print("未找到滑块，尝试查找可拖动元素...")
                draggable = await page.query_selector_all('[draggable="true"]')
                if draggable:
                    slider = draggable[0]
                    print("找到可拖动元素")
            
            if not slider:
                print("未找到滑块元素")
                return False
            
            # 获取滑块位置和尺寸
            box = await slider.bounding_box()
            if not box:
                print("无法获取滑块位置")
                return False
            
            print(f"滑块位置: x={box['x']}, y={box['y']}, width={box['width']}, height={box['height']}")
            
            # 模拟拖动（简单实现：从左到右拖动）
            import random
            start_x = box['x'] + box['width'] / 2
            start_y = box['y'] + box['height'] / 2
            
            # 随机拖动距离
            distance = random.randint(200, 350)
            
            # 模拟人类拖动行为
            await page.mouse.move(start_x, start_y)
            await asyncio.sleep(random.uniform(0.1, 0.3))
            await page.mouse.down()
            
            # 分段移动，模拟人类拖动
            steps = random.randint(20, 30)
            for i in range(steps):
                progress = (i + 1) / steps
                # 添加随机偏移
                offset_x = random.uniform(-2, 2)
                offset_y = random.uniform(-1, 1)
                current_x = start_x + distance * progress + offset_x
                current_y = start_y + offset_y
                await page.mouse.move(current_x, current_y)
                await asyncio.sleep(random.uniform(0.01, 0.03))
            
            await page.mouse.up()
            await asyncio.sleep(2)
            
            return True
        except Exception as e:
            print(f"处理滑块验证码失败: {e}")
            return False
    
    async def _screenshot_captcha(self, page) -> bytes:
        """截图验证码区域"""
        try:
            # 尝试截取验证码区域
            captcha_area = await page.query_selector(
                '.captcha-container, .verify-container, [class*="captcha"], [class*="verify"]'
            )
            if captcha_area:
                return await captcha_area.screenshot()
            return await page.screenshot()
        except:
            return b''
    
    async def _human_behavior(self, page):
        """模拟人类行为"""
        # 随机滚动
        for _ in range(random.randint(1, 3)):
            await page.mouse.wheel(0, random.randint(100, 500))
            await asyncio.sleep(random.uniform(0.3, 0.8))
        
        # 随机移动鼠标
        for _ in range(random.randint(2, 5)):
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.1, 0.3))
    
    def _get_referer(self, url: str) -> str:
        """生成合理的 Referer"""
        parsed = urlparse(url)
        domain = parsed.netloc
        
        referers = [
            f"https://www.google.com/search?q={parsed.path}",
            f"https://www.baidu.com/s?wd={parsed.path}",
            f"https://{domain}/",
            "",
        ]
        return random.choice(referers)


class AntiCrawlFetcher:
    """反爬虫抓取器主类 - 整合多种策略"""
    
    def __init__(self):
        self.captcha_solver = CaptchaSolver()
        self._browser_fetcher = None
    
    async def fetch(
        self,
        url: str,
        use_browser: bool = False,
        max_retries: int = 3,
        timeout: int = 30
    ) -> FetchResult:
        """
        抓取网页内容
        
        Args:
            url: 目标 URL
            use_browser: 是否强制使用浏览器
            max_retries: 最大重试次数
            timeout: 超时时间(秒)
        
        Returns:
            FetchResult 包含抓取结果
        """
        # 先尝试普通 HTTP 请求
        if not use_browser:
            for attempt in range(max_retries):
                result = await self._fetch_with_httpx(url, timeout)
                if result.success:
                    # 检查是否被反爬拦截
                    if self._is_blocked(result.html or ""):
                        print(f"HTTP 请求被拦截，切换到浏览器模式 (尝试 {attempt + 1}/{max_retries})")
                        break
                    return result
                
                # 随机延迟后重试
                await asyncio.sleep(random.uniform(1, 3) * (attempt + 1))
        
        # 使用浏览器模式
        return await self._fetch_with_browser(url, timeout)
    
    async def _fetch_with_httpx(self, url: str, timeout: int) -> FetchResult:
        """使用 httpx 抓取"""
        try:
            headers = {
                'User-Agent': UserAgentPool.get_random(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Referer': self._get_search_referer(url),
            }
            
            async with httpx.AsyncClient(
                follow_redirects=True,
                verify=False,
                timeout=timeout,
                headers=headers
            ) as client:
                response = await client.get(url)
                
                return FetchResult(
                    success=response.status_code == 200,
                    html=response.text if response.status_code == 200 else None,
                    status_code=response.status_code,
                    error=None if response.status_code == 200 else f"HTTP {response.status_code}"
                )
        except Exception as e:
            return FetchResult(success=False, error=str(e))
    
    async def _fetch_with_browser(self, url: str, timeout: int) -> FetchResult:
        """使用浏览器抓取"""
        try:
            async with BrowserFetcher() as browser:
                return await browser.fetch_page(url, timeout=timeout * 1000)
        except Exception as e:
            return FetchResult(success=False, error=str(e))
    
    def _is_blocked(self, html: str) -> bool:
        """检测是否被反爬拦截"""
        # 更精确的拦截模式
        block_patterns = [
            '安全验证', 'Safety Check', 'safety check',
            '访问被拒绝', 'Access Denied', 'access denied',
            '请完成验证', 'Please verify your',
            '验证码', 
            '403 Forbidden', 
            'temporarily restricted',
            '您的请求已被拦截',
            'anti-bot',
        ]
        html_lower = html.lower()
        
        # 检查页面标题是否包含验证相关词汇
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).lower()
            if any(x in title for x in ['验证', 'verify', 'captcha', '安全', 'security']):
                return True
        
        # 检查特定模式（排除正常内容中可能包含的词）
        for pattern in block_patterns:
            if pattern.lower() in html_lower:
                # 排除在正常内容中出现的情况
                if pattern.lower() in ['captcha', 'robot', 'bot']:
                    # 检查是否在表单或验证码相关上下文中
                    if re.search(r'<(form|input|button)[^>]*' + pattern, html_lower):
                        return True
                    continue
                return True
        
        return False
    
    def _get_search_referer(self, url: str) -> str:
        """生成搜索引擎 Referer"""
        parsed = urlparse(url)
        referers = [
            f"https://www.google.com/",
            f"https://www.baidu.com/",
            f"https://www.bing.com/",
            f"https://{parsed.netloc}/",
            "",
        ]
        return random.choice(referers)


# 便捷函数
async def fetch_with_anticrawl(
    url: str,
    force_browser: bool = False,
    timeout: int = 30
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    反爬虫抓取（简化接口）
    
    Returns:
        (success, html, error)
    """
    fetcher = AntiCrawlFetcher()
    result = await fetcher.fetch(url, use_browser=force_browser, timeout=timeout)
    return result.success, result.html, result.error


# 同步包装器
def fetch_sync(
    url: str,
    force_browser: bool = False,
    timeout: int = 30
) -> Tuple[bool, Optional[str], Optional[str]]:
    """同步版本的反爬虫抓取"""
    return asyncio.run(fetch_with_anticrawl(url, force_browser, timeout))


if __name__ == "__main__":
    # 测试
    import sys
    
    test_urls = [
        "https://httpbin.org/get",
        "https://www.smzdm.com/",
        "https://www.zhihu.com/",
    ]
    
    async def test():
        for url in test_urls:
            print(f"\n测试: {url}")
            success, html, error = await fetch_with_anticrawl(url)
            if success:
                print(f"  ✅ 成功，HTML 长度: {len(html)}")
            else:
                print(f"  ❌ 失败: {error}")
    
    asyncio.run(test())
