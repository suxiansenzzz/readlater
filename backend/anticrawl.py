"""
ReadLater 反爬虫模块 v3.0
功能：
1. Playwright 无头浏览器 - 绕过 JS 反爬
2. ddddocr 验证码识别 - 自动识别图形验证码
3. 智能滑块验证码处理 - 图像分析+模拟拖动
4. 2captcha 第三方服务集成
5. 用户友好的错误提示
"""

import asyncio
import base64
import hashlib
import io
import os
import random
import re
import time
from typing import Optional, Tuple, Dict, Any, List
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
    ALIYUN = "aliyun"  # 阿里云验证码
    TENCENT = "tencent"  # 腾讯验证码 (TencentCaptcha)
    UNKNOWN = "unknown"


@dataclass
class FetchResult:
    """抓取结果"""
    success: bool
    html: Optional[str] = None
    error: Optional[str] = None
    captcha_type: CaptchaType = CaptchaType.NONE
    captcha_image: Optional[bytes] = None
    captcha_site_key: Optional[str] = None  # 用于2captcha
    status_code: int = 200
    user_message: Optional[str] = None  # 用户友好的错误消息


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


class TwoCaptchaSolver:
    """2captcha 第三方验证码解决服务"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('TWOCAPTCHA_API_KEY')
        self.base_url = "https://2captcha.com"
    
    def is_available(self) -> bool:
        """检查2captcha服务是否可用"""
        return bool(self.api_key)
    
    async def solve_slider(self, page_screenshot: bytes, target_url: str) -> Optional[int]:
        """
        使用2captcha解决滑块验证码
        
        Returns:
            滑块需要移动的距离（像素），失败返回None
        """
        if not self.is_available():
            return None
        
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                # 上传图片
                files = {'file': ('captcha.png', page_screenshot, 'image/png')}
                data = {
                    'key': self.api_key,
                    'method': 'post',
                    'numeric': 4,  # 返回数字距离
                    'min_len': 100,
                    'max_len': 400,
                }
                
                response = await client.post(
                    f"{self.base_url}/in.php",
                    data=data,
                    files=files
                )
                
                if not response.text.startswith('OK|'):
                    print(f"2captcha上传失败: {response.text}")
                    return None
                
                captcha_id = response.text.split('|')[1]
                print(f"2captcha任务ID: {captcha_id}")
                
                # 等待结果
                for _ in range(30):  # 最多等待60秒
                    await asyncio.sleep(2)
                    
                    result_response = await client.get(
                        f"{self.base_url}/res.php",
                        params={'key': self.api_key, 'action': 'get', 'id': captcha_id}
                    )
                    
                    if result_response.text == 'CAPCHA_NOT_READY':
                        continue
                    
                    if result_response.text.startswith('OK|'):
                        distance = int(result_response.text.split('|')[1])
                        print(f"2captcha解决成功，距离: {distance}px")
                        return distance
                    
                    print(f"2captcha错误: {result_response.text}")
                    return None
                
                print("2captcha超时")
                return None
                
        except Exception as e:
            print(f"2captcha调用失败: {e}")
            return None
    
    async def solve_image_captcha(self, image_data: bytes) -> Optional[str]:
        """
        使用2captcha解决图形验证码
        
        Returns:
            验证码文本，失败返回None
        """
        if not self.is_available():
            return None
        
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                # 上传图片
                files = {'file': ('captcha.png', image_data, 'image/png')}
                data = {
                    'key': self.api_key,
                    'method': 'post',
                }
                
                response = await client.post(
                    f"{self.base_url}/in.php",
                    data=data,
                    files=files
                )
                
                if not response.text.startswith('OK|'):
                    return None
                
                captcha_id = response.text.split('|')[1]
                
                # 等待结果
                for _ in range(30):
                    await asyncio.sleep(2)
                    
                    result_response = await client.get(
                        f"{self.base_url}/res.php",
                        params={'key': self.api_key, 'action': 'get', 'id': captcha_id}
                    )
                    
                    if result_response.text == 'CAPCHA_NOT_READY':
                        continue
                    
                    if result_response.text.startswith('OK|'):
                        return result_response.text.split('|')[1]
                    
                    return None
                
                return None
                
        except Exception as e:
            print(f"2captcha图片验证码失败: {e}")
            return None


class CaptchaSolver:
    """验证码识别器"""
    
    def __init__(self):
        self._ocr = None
        self.two_captcha = TwoCaptchaSolver()
    
    @property
    def ocr(self):
        if self._ocr is None:
            try:
                import ddddocr
                self._ocr = ddddocr.DdddOcr()
            except ImportError:
                print("警告: ddddocr 未安装，图形验证码识别不可用")
        return self._ocr
    
    def recognize(self, image_data: bytes) -> Optional[str]:
        """识别验证码"""
        if not self.ocr:
            return None
        
        try:
            result = self.ocr.classification(image_data)
            return result
        except Exception as e:
            print(f"验证码识别失败: {e}")
            return None
    
    def detect_captcha_type(self, html: str) -> Tuple[CaptchaType, Optional[str]]:
        """
        检测页面中的验证码类型
        
        Returns:
            (验证码类型, site_key或其他标识)
        """
        html_lower = html.lower()
        
        # 腾讯验证码 (TencentCaptcha) - 什么值得买等
        if 'tencentcaptcha' in html_lower or 'tcaptcha.js' in html_lower or 'ssl.captcha.qq.com' in html_lower:
            # 提取 appId
            appid_match = re.search(r"TencentCaptcha\(['\"](\d+)['\"]", html)
            site_key = appid_match.group(1) if appid_match else None
            return CaptchaType.TENCENT, site_key
        
        # 阿里云验证码
        if 'aliyuncaptcha' in html_lower or 'aliyun-captcha' in html_lower:
            # 提取appkey
            appkey_match = re.search(r'appid["\s:=]+([a-zA-Z0-9]+)', html)
            appkey = appkey_match.group(1) if appkey_match else None
            return CaptchaType.ALIYUN, appkey
        
        # 极验
        if any(x in html_lower for x in ['geetest', 'gt-init', 'geetest_challenge']):
            return CaptchaType.GEETEST, None
        
        # reCAPTCHA
        if any(x in html_lower for x in ['recaptcha', 'g-recaptcha', 'grecaptcha']):
            site_key_match = re.search(r'data-sitekey["\s=]+["\']([^"\']+)["\']', html)
            site_key = site_key_match.group(1) if site_key_match else None
            return CaptchaType.RECAPTCHA, site_key
        
        # 滑块验证码
        slider_patterns = [
            'slider', 'slide-verify', 'slideBlock',
            'captcha-slider', 'drag-verify',
            '滑动验证', '拖动滑块'
        ]
        if any(x in html_lower for x in slider_patterns):
            return CaptchaType.SLIDER, None
        
        # 点选验证码
        click_patterns = [
            'click-verify', 'click-captcha',
            '点选验证', '点击验证', '文字点选'
        ]
        if any(x in html_lower for x in click_patterns):
            return CaptchaType.CLICK, None
        
        # 图形验证码
        image_patterns = [
            'captcha', 'verify-code', 'verifycode',
            '验证码', '安全验证', 'safety check'
        ]
        if any(x in html_lower for x in image_patterns):
            return CaptchaType.IMAGE, None
        
        return CaptchaType.NONE, None
    
    def extract_captcha_image(self, html: str, base_url: str) -> Optional[bytes]:
        """从 HTML 中提取验证码图片"""
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
                
                try:
                    response = httpx.get(img_url, timeout=10)
                    if response.status_code == 200:
                        return response.content
                except Exception as e:
                    print(f"下载验证码图片失败: {e}")
        
        return None


class SmartSliderSolver:
    """智能滑块验证码解决器"""
    
    @staticmethod
    def find_gap_position(background_image: bytes, slider_image: Optional[bytes] = None) -> Optional[int]:
        """
        通过图像分析找到滑块缺口位置
        
        Args:
            background_image: 背景图（包含缺口）
            slider_image: 滑块图片（可选）
        
        Returns:
            缺口的x坐标（相对于图片左侧的像素距离）
        """
        try:
            img = Image.open(io.BytesIO(background_image))
            img = img.convert('RGB')
            width, height = img.size
            
            # 方法1: 检测颜色差异（缺口通常颜色不同）
            pixels = img.load()
            
            # 计算每一列的平均颜色差异
            col_diffs = []
            for x in range(width):
                col_diff = 0
                count = 0
                for y in range(height // 4, height * 3 // 4):  # 只检查中间部分
                    r, g, b = pixels[x, y]
                    # 检查与周围像素的差异
                    if x > 0 and x < width - 1:
                        r_left, g_left, b_left = pixels[x-1, y]
                        r_right, g_right, b_right = pixels[x+1, y]
                        diff = abs(r - r_left) + abs(g - g_left) + abs(b - b_left)
                        diff += abs(r - r_right) + abs(g - g_right) + abs(b - b_right)
                        col_diff += diff
                        count += 1
                col_diffs.append(col_diff / max(count, 1))
            
            # 平滑处理
            window = 10
            smoothed = []
            for i in range(len(col_diffs)):
                start = max(0, i - window)
                end = min(len(col_diffs), i + window + 1)
                smoothed.append(sum(col_diffs[start:end]) / (end - start))
            
            # 找到差异最大的区域（缺口位置）
            # 排除最左边（滑块起始位置）
            min_x = width // 5
            max_diff = 0
            gap_x = None
            
            for x in range(min_x, len(smoothed)):
                if smoothed[x] > max_diff:
                    max_diff = smoothed[x]
                    gap_x = x
            
            if gap_x and max_diff > 10:  # 差异阈值
                print(f"检测到缺口位置: x={gap_x}, 差异值={max_diff:.2f}")
                return gap_x
            
            # 方法2: 检测边缘（缺口边缘通常比较锐利）
            edges = []
            for x in range(min_x, width - 10):
                edge_strength = 0
                for y in range(height // 4, height * 3 // 4):
                    r1, g1, b1 = pixels[x, y]
                    r2, g2, b2 = pixels[x + 5, y]
                    edge_strength += abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2)
                edges.append((x, edge_strength))
            
            if edges:
                edges.sort(key=lambda x: x[1], reverse=True)
                if edges[0][1] > 500:
                    print(f"边缘检测找到缺口: x={edges[0][0]}, 强度={edges[0][1]}")
                    return edges[0][0]
            
            print("未能检测到缺口位置")
            return None
            
        except Exception as e:
            print(f"图像分析失败: {e}")
            return None
    
    @staticmethod
    def generate_human_drag_path(distance: int, total_steps: int = None) -> List[Tuple[float, float]]:
        """
        生成模拟人类拖动的路径
        
        Args:
            distance: 总拖动距离
            total_steps: 总步数（默认根据距离自动计算）
        
        Returns:
            [(offset_x, offset_y), ...] 每步的偏移量
        """
        if total_steps is None:
            # 根据距离计算合适的步数
            total_steps = max(20, min(50, distance // 5))
        
        path = []
        
        # 人类拖动的特点：
        # 1. 开始时加速
        # 2. 中间匀速
        # 3. 结束时减速
        # 4. 有轻微的上下抖动
        
        for i in range(total_steps):
            progress = (i + 1) / total_steps
            
            # 使用缓动函数模拟真实拖动
            if progress < 0.3:
                # 开始加速
                ease = progress * progress / 0.3 * 0.4
            elif progress < 0.7:
                # 中间匀速
                ease = 0.4 + (progress - 0.3) * 0.4
            else:
                # 结束减速
                remaining = 1 - progress
                ease = 0.8 + (1 - remaining * remaining) * 0.2
            
            offset_x = distance * ease
            
            # 添加轻微的上下抖动
            offset_y = random.uniform(-2, 2)
            
            # 添加微小的水平抖动（模拟手抖）
            if random.random() < 0.1:  # 10%概率
                offset_x += random.uniform(-3, 3)
            
            path.append((offset_x, offset_y))
        
        return path


class BrowserFetcher:
    """基于 Playwright 的浏览器抓取器"""
    
    def __init__(self):
        self._playwright = None
        self._browser = None
        self.captcha_solver = CaptchaSolver()
        self.slider_solver = SmartSliderSolver()
    
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
        
        # 使用 playwright-stealth 进行全面反检测
        try:
            from playwright_stealth import stealth_async
            await stealth_async(context)
        except ImportError:
            # 回退到手动反检测脚本
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
        wait_for: str = 'domcontentloaded',
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
            
            # 等待页面稳定
            try:
                await page.wait_for_load_state('networkidle', timeout=10000)
            except:
                pass

            # 检测验证码
            try:
                html = await page.content()
            except Exception as e:
                # 页面可能还在跳转，等待后重试
                await asyncio.sleep(3)
                try:
                    html = await page.content()
                except Exception as e2:
                    await context.close()
                    return FetchResult(success=False, error=str(e2), user_message='抓取失败: 页面内容获取超时，该网站可能有较强的反爬机制')
            captcha_type, site_key = self.captcha_solver.detect_captcha_type(html)
            
            if captcha_type != CaptchaType.NONE:
                print(f"检测到验证码类型: {captcha_type.value}")
                
                # 截图验证码区域
                captcha_image = await self._screenshot_captcha(page)
                
                if captcha_type == CaptchaType.IMAGE:
                    # 尝试识别图形验证码
                    captcha_result = await self._handle_image_captcha(page, url)
                    if captcha_result:
                        html = await page.content()
                        captcha_type = CaptchaType.NONE
                    else:
                        await context.close()
                        return FetchResult(
                            success=False,
                            error="需要图形验证码",
                            captcha_type=captcha_type,
                            captcha_image=captcha_image,
                            user_message="该网站需要输入验证码，请在浏览器中手动完成验证后重试"
                        )
                
                elif captcha_type == CaptchaType.SLIDER:
                    # 尝试处理滑块验证码
                    captcha_result = await self._handle_slider_captcha(page, captcha_image)
                    if captcha_result:
                        await asyncio.sleep(3)
                        html = await page.content()
                        captcha_type, _ = self.captcha_solver.detect_captcha_type(html)
                        if captcha_type != CaptchaType.NONE:
                            captcha_image = await self._screenshot_captcha(page)
                            await context.close()
                            return FetchResult(
                                success=False,
                                error=f"滑块验证后仍需验证: {captcha_type.value}",
                                captcha_type=captcha_type,
                                captcha_image=captcha_image,
                                user_message="滑块验证码处理失败，该网站的验证机制较为复杂。建议：\n1. 在浏览器中手动访问该网站\n2. 配置2captcha API密钥以自动解决验证码"
                            )
                    else:
                        await context.close()
                        return FetchResult(
                            success=False,
                            error="滑块验证码处理失败",
                            captcha_type=captcha_type,
                            captcha_image=captcha_image,
                            user_message="无法自动解决滑块验证码。建议：\n1. 在浏览器中手动访问该网站完成验证\n2. 配置2captcha API密钥（https://2captcha.com）以自动解决"
                        )
                
                elif captcha_type == CaptchaType.ALIYUN:
                    # 阿里云验证码，暂时无法自动处理
                    await context.close()
                    return FetchResult(
                        success=False,
                        error="阿里云验证码",
                        captcha_type=captcha_type,
                        captcha_image=captcha_image,
                        captcha_site_key=site_key,
                        user_message="该网站使用阿里云验证码保护，暂时无法自动解决。建议在浏览器中手动访问该网站。"
                    )
                
                elif captcha_type == CaptchaType.GEETEST:
                    # 极验验证码
                    await context.close()
                    return FetchResult(
                        success=False,
                        error="极验验证码",
                        captcha_type=captcha_type,
                        captcha_image=captcha_image,
                        user_message="该网站使用极验验证码保护，暂时无法自动解决。建议在浏览器中手动访问该网站。"
                    )
                
                elif captcha_type == CaptchaType.TENCENT:
                    # 腾讯验证码 (什么值得买等)
                    await context.close()
                    return FetchResult(
                        success=False,
                        error="腾讯验证码",
                        captcha_type=captcha_type,
                        captcha_site_key=site_key,
                        user_message="该网站使用腾讯验证码(WAF)保护，暂时无法自动解决。建议：\n1. 使用浏览器扩展保存（扩展会在真实浏览器中打开页面）\n2. 在浏览器中手动访问该网站完成验证后重试"
                    )
                
                else:
                    await context.close()
                    return FetchResult(
                        success=False,
                        error=f"不支持的验证码类型: {captcha_type.value}",
                        captcha_type=captcha_type,
                        captcha_image=captcha_image,
                        user_message=f"检测到{captcha_type.value}类型的验证码，暂时无法自动解决。建议在浏览器中手动访问该网站。"
                    )
            
            # 模拟人类行为
            await self._human_behavior(page)
            
            # 获取最终页面内容
            try:
                html = await page.content()
            except Exception as e:
                # 页面可能还在跳转，等待后重试
                await asyncio.sleep(3)
                try:
                    html = await page.content()
                except Exception as e2:
                    await context.close()
                    return FetchResult(success=False, error=str(e2), user_message='抓取失败: 页面内容获取超时，该网站可能有较强的反爬机制')
            await context.close()
            
            return FetchResult(
                success=True,
                html=html,
                status_code=status_code
            )
            
        except Exception as e:
            return FetchResult(
                success=False,
                error=str(e),
                user_message=f"抓取失败: {str(e)}"
            )
    
    async def _handle_image_captcha(self, page, url: str) -> bool:
        """处理图形验证码"""
        try:
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
            
            img_buffer = await captcha_img.screenshot()
            
            # 先尝试本地OCR
            captcha_text = self.captcha_solver.recognize(img_buffer)
            
            # 如果本地OCR失败，尝试2captcha
            if not captcha_text and self.captcha_solver.two_captcha.is_available():
                captcha_text = await self.captcha_solver.two_captcha.solve_image_captcha(img_buffer)
            
            if not captcha_text:
                print("验证码识别失败")
                return False
            
            print(f"识别到验证码: {captcha_text}")
            
            # 输入验证码
            input_selectors = [
                'input[name*="captcha"]',
                'input[name*="verify"]',
                'input[name*="code"]',
                'input[type="text"]',
                '.captcha-input input',
                '.verify-input input',
            ]
            
            for selector in input_selectors:
                input_el = await page.query_selector(selector)
                if input_el:
                    await input_el.fill(captcha_text)
                    
                    submit_selectors = [
                        'button[type="submit"]',
                        '.captcha-submit',
                        '.verify-submit',
                        'button:has-text("确认")',
                        'button:has-text("验证")',
                        'button:has-text("提交")',
                    ]
                    
                    for btn_selector in submit_selectors:
                        submit_btn = await page.query_selector(btn_selector)
                        if submit_btn:
                            await submit_btn.click()
                            await asyncio.sleep(2)
                            return True
            
            await page.keyboard.press('Enter')
            await asyncio.sleep(2)
            return True
            
        except Exception as e:
            print(f"处理验证码失败: {e}")
            return False
    
    async def _handle_slider_captcha(self, page, captcha_image: bytes = None) -> bool:
        """处理滑块验证码（智能版本）"""
        try:
            # 查找滑块
            slider_selectors = [
                '.geetest_slider_button',
                '.geetest_btn',
                '.geetest_slider',
                '#pass-slide-button',
                '.pass-slide-btn',
                '.slider-btn',
                '.slide-btn',
                '.slide-button',
                '[class*="slider"]',
                '[class*="slide-"] button',
                '[class*="drag"]',
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
                draggable = await page.query_selector_all('[draggable="true"]')
                if draggable:
                    slider = draggable[0]
                    print("找到可拖动元素")
            
            if not slider:
                print("未找到滑块元素")
                return False
            
            # 获取滑块位置
            box = await slider.bounding_box()
            if not box:
                print("无法获取滑块位置")
                return False
            
            print(f"滑块位置: x={box['x']}, y={box['y']}, width={box['width']}, height={box['height']}")
            
            start_x = box['x'] + box['width'] / 2
            start_y = box['y'] + box['height'] / 2
            
            # 尝试获取背景图进行分析
            distance = None
            
            # 方法1: 尝试使用2captcha
            if self.captcha_solver.two_captcha.is_available() and captcha_image:
                print("尝试使用2captcha解决滑块验证码...")
                distance = await self.captcha_solver.two_captcha.solve_slider(captcha_image, "")
            
            # 方法2: 尝试图像分析
            if not distance:
                try:
                    # 截取整个验证码区域
                    captcha_area = await page.query_selector(
                        '.geetest_canvas_bg, .captcha-bg, [class*="captcha"] canvas, [class*="slider"] canvas'
                    )
                    if captcha_area:
                        bg_screenshot = await captcha_area.screenshot()
                        gap_x = self.slider_solver.find_gap_position(bg_screenshot)
                        if gap_x:
                            # 计算需要移动的距离
                            # 滑块起始位置通常在最左边
                            slider_start_x = box['x']
                            distance = gap_x - slider_start_x
                            print(f"图像分析计算距离: {distance}px")
                except Exception as e:
                    print(f"图像分析失败: {e}")
            
            # 方法3: 使用默认距离（随机）
            if not distance:
                distance = random.randint(150, 300)
                print(f"使用随机距离: {distance}px")
            
            # 生成拖动路径
            drag_path = self.slider_solver.generate_human_drag_path(distance)
            
            # 执行拖动
            await page.mouse.move(start_x, start_y)
            await asyncio.sleep(random.uniform(0.1, 0.3))
            await page.mouse.down()
            
            for offset_x, offset_y in drag_path:
                current_x = start_x + offset_x
                current_y = start_y + offset_y
                await page.mouse.move(current_x, current_y)
                await asyncio.sleep(random.uniform(0.01, 0.03))
            
            # 松开鼠标
            await page.mouse.up()
            await asyncio.sleep(2)
            
            return True
            
        except Exception as e:
            print(f"处理滑块验证码失败: {e}")
            return False
    
    async def _screenshot_captcha(self, page) -> bytes:
        """截图验证码区域"""
        try:
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
        for _ in range(random.randint(1, 3)):
            await page.mouse.wheel(0, random.randint(100, 500))
            await asyncio.sleep(random.uniform(0.3, 0.8))
        
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
    
    def __init__(self, twocaptcha_api_key: Optional[str] = None):
        self.captcha_solver = CaptchaSolver()
        if twocaptcha_api_key:
            self.captcha_solver.two_captcha.api_key = twocaptcha_api_key
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
        
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).lower()
            if any(x in title for x in ['验证', 'verify', 'captcha', '安全', 'security']):
                return True
        
        for pattern in block_patterns:
            if pattern.lower() in html_lower:
                if pattern.lower() in ['captcha', 'robot', 'bot']:
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
    timeout: int = 30,
    twocaptcha_api_key: Optional[str] = None
) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    反爬虫抓取（简化接口）
    
    Returns:
        (success, html, error, user_message)
    """
    fetcher = AntiCrawlFetcher(twocaptcha_api_key=twocaptcha_api_key)
    result = await fetcher.fetch(url, use_browser=force_browser, timeout=timeout)
    return result.success, result.html, result.error, result.user_message


# 同步包装器
def fetch_sync(
    url: str,
    force_browser: bool = False,
    timeout: int = 30,
    twocaptcha_api_key: Optional[str] = None
) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """同步版本的反爬虫抓取"""
    return asyncio.run(fetch_with_anticrawl(url, force_browser, timeout, twocaptcha_api_key))


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
            success, html, error, user_msg = await fetch_with_anticrawl(url)
            if success:
                print(f"  ✅ 成功，HTML 长度: {len(html)}")
            else:
                print(f"  ❌ 失败: {error}")
                if user_msg:
                    print(f"  💡 用户提示: {user_msg}")
    
    asyncio.run(test())
