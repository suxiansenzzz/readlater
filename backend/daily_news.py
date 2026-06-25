"""
ReadLater 每日新闻头条抓取模块 v1.0
支持来源：今日头条热榜、百度热搜、36氪、新浪、网易、澎湃、IT之家、虎嗅
"""

import httpx
import json
import re
import time
import sqlite3
import os
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup

# ============================================================
# 数据模型
# ============================================================

@dataclass
class NewsItem:
    """单条新闻"""
    title: str
    url: str
    source: str           # 来源名称
    source_icon: str      # 来源图标emoji
    rank: int = 0         # 排名（热榜类）
    hot_score: str = ""   # 热度值
    summary: str = ""     # 摘要
    fetch_time: str = ""  # 抓取时间

# ============================================================
# HTTP客户端
# ============================================================

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

def get_client() -> httpx.Client:
    return httpx.Client(timeout=15, follow_redirects=True, headers=HEADERS)

# ============================================================
# 各来源抓取器
# ============================================================

def fetch_toutiao_hot() -> List[NewsItem]:
    """今日头条热榜 — API方式"""
    items = []
    try:
        client = get_client()
        resp = client.get("https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc")
        data = resp.json()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        for i, entry in enumerate(data.get('data', [])[:50], 1):
            title = entry.get('Title', '') or entry.get('title', '')
            url = entry.get('Url', '') or entry.get('url', '')
            hot = entry.get('HotValue', '') or entry.get('hot_value', '')
            if title:
                items.append(NewsItem(
                    title=title,
                    url=url,
                    source="今日头条",
                    source_icon="🔥",
                    rank=i,
                    hot_score=str(hot),
                    fetch_time=now,
                ))
        client.close()
    except Exception as e:
        print(f"[今日头条] 错误: {e}")
    return items


def fetch_baidu_hot() -> List[NewsItem]:
    """百度热搜 — HTML解析"""
    items = []
    try:
        client = get_client()
        resp = client.get("https://top.baidu.com/board?tab=realtime")
        soup = BeautifulSoup(resp.text, 'html.parser')
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 百度热搜的标题在 .c-single-text-ellipsis 中
        title_tags = soup.select('.c-single-text-ellipsis')
        if not title_tags:
            # 备用选择器
            title_tags = soup.select('[class*="title_"]')
        
        for i, tag in enumerate(title_tags[:30], 1):
            text = tag.get_text(strip=True)
            if text and len(text) > 2:
                items.append(NewsItem(
                    title=text,
                    url=f"https://www.baidu.com/s?wd={text}",
                    source="百度热搜",
                    source_icon="🔍",
                    rank=i,
                    fetch_time=now,
                ))
        client.close()
    except Exception as e:
        print(f"[百度热搜] 错误: {e}")
    return items


def fetch_36kr() -> List[NewsItem]:
    """36氪快讯 — API方式"""
    items = []
    try:
        client = get_client()
        resp = client.get("https://36kr.com/api/newsflash?b_id=&per_page=30")
        data = resp.json()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        for i, entry in enumerate(data.get('data', {}).get('items', [])[:30], 1):
            title = entry.get('title', '')
            nid = entry.get('id', '')
            summary = entry.get('description', '') or entry.get('summary', '')
            if title:
                items.append(NewsItem(
                    title=title,
                    url=f"https://36kr.com/newsflashes/{nid}" if nid else "https://36kr.com/newsflashes",
                    source="36氪",
                    source_icon="💼",
                    rank=i,
                    summary=summary[:200] if summary else "",
                    fetch_time=now,
                ))
        client.close()
    except Exception as e:
        print(f"[36氪] 错误: {e}")
    return items


def fetch_sina_news() -> List[NewsItem]:
    """新浪新闻 — HTML解析"""
    items = []
    try:
        client = get_client()
        resp = client.get("https://news.sina.com.cn/")
        soup = BeautifulSoup(resp.text, 'html.parser')
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        links = soup.select('a[href*="news.sina.com.cn"]')
        seen = set()
        for a in links:
            text = a.get_text(strip=True)
            href = a.get('href', '')
            if (text and len(text) > 10 and len(text) < 80 
                and text not in seen 
                and not any(kw in text for kw in ['视频', '图片', '专题', '更多', '首页', '导航'])):
                seen.add(text)
                items.append(NewsItem(
                    title=text,
                    url=href,
                    source="新浪新闻",
                    source_icon="📰",
                    rank=len(items) + 1,
                    fetch_time=now,
                ))
                if len(items) >= 30:
                    break
        client.close()
    except Exception as e:
        print(f"[新浪新闻] 错误: {e}")
    return items


def fetch_163_news() -> List[NewsItem]:
    """网易新闻 — HTML解析"""
    items = []
    try:
        client = get_client()
        resp = client.get("https://news.163.com/")
        soup = BeautifulSoup(resp.text, 'html.parser')
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        links = soup.select('a[href*="163.com"]')
        seen = set()
        for a in links:
            text = a.get_text(strip=True)
            href = a.get('href', '')
            if (text and len(text) > 10 and len(text) < 80 
                and text not in seen
                and any(kw in href for kw in ['/article/', '/25/', '/26/'])):
                seen.add(text)
                items.append(NewsItem(
                    title=text,
                    url=href,
                    source="网易新闻",
                    source_icon="📋",
                    rank=len(items) + 1,
                    fetch_time=now,
                ))
                if len(items) >= 30:
                    break
        client.close()
    except Exception as e:
        print(f"[网易新闻] 错误: {e}")
    return items


def fetch_thepaper() -> List[NewsItem]:
    """澎湃新闻 — HTML解析"""
    items = []
    try:
        client = get_client()
        resp = client.get("https://www.thepaper.cn/")
        soup = BeautifulSoup(resp.text, 'html.parser')
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        links = soup.select('a[href*="newsDetail"]')
        seen = set()
        for a in links:
            text = a.get_text(strip=True)
            href = a.get('href', '')
            if text and len(text) > 10 and len(text) < 80 and text not in seen:
                seen.add(text)
                if not href.startswith('http'):
                    href = f"https://www.thepaper.cn{href}"
                items.append(NewsItem(
                    title=text,
                    url=href,
                    source="澎湃新闻",
                    source_icon="🗞️",
                    rank=len(items) + 1,
                    fetch_time=now,
                ))
                if len(items) >= 30:
                    break
        client.close()
    except Exception as e:
        print(f"[澎湃新闻] 错误: {e}")
    return items


def fetch_ithome() -> List[NewsItem]:
    """IT之家 — HTML解析"""
    items = []
    try:
        client = get_client()
        resp = client.get("https://www.ithome.com/")
        soup = BeautifulSoup(resp.text, 'html.parser')
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        links = soup.select('a[href*="ithome.com/0/"]')
        seen = set()
        for a in links:
            text = a.get_text(strip=True)
            href = a.get('href', '')
            if (text and len(text) > 10 and len(text) < 80 
                and text not in seen
                and '下载' not in text and '描述文件' not in text):
                seen.add(text)
                items.append(NewsItem(
                    title=text,
                    url=href,
                    source="IT之家",
                    source_icon="💻",
                    rank=len(items) + 1,
                    fetch_time=now,
                ))
                if len(items) >= 30:
                    break
        client.close()
    except Exception as e:
        print(f"[IT之家] 错误: {e}")
    return items


def fetch_huxiu() -> List[NewsItem]:
    """虎嗅 — HTML解析"""
    items = []
    try:
        client = get_client()
        resp = client.get("https://www.huxiu.com/")
        soup = BeautifulSoup(resp.text, 'html.parser')
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        links = soup.select('a[href*="huxiu.com/article"]')
        seen = set()
        for a in links:
            text = a.get_text(strip=True)
            href = a.get('href', '')
            if text and len(text) > 10 and len(text) < 80 and text not in seen:
                seen.add(text)
                if not href.startswith('http'):
                    href = f"https://www.huxiu.com{href}"
                items.append(NewsItem(
                    title=text,
                    url=href,
                    source="虎嗅",
                    source_icon="🐯",
                    rank=len(items) + 1,
                    fetch_time=now,
                ))
                if len(items) >= 30:
                    break
        client.close()
    except Exception as e:
        print(f"[虎嗅] 错误: {e}")
    return items

# ============================================================
# 聚合抓取
# ============================================================

ALL_FETCHERS = [
    ("今日头条热榜", fetch_toutiao_hot),
    ("百度热搜", fetch_baidu_hot),
    ("36氪快讯", fetch_36kr),
    ("新浪新闻", fetch_sina_news),
    ("网易新闻", fetch_163_news),
    ("澎湃新闻", fetch_thepaper),
    ("IT之家", fetch_ithome),
    ("虎嗅", fetch_huxiu),
]


def fetch_all_news(sources: List[str] = None) -> Dict[str, List[NewsItem]]:
    """
    抓取所有（或指定来源）的新闻头条
    
    Args:
        sources: 指定来源名称列表，None则全部抓取
    
    Returns:
        {source_name: [NewsItem, ...]}
    """
    results = {}
    fetchers = ALL_FETCHERS if sources is None else [
        (name, fn) for name, fn in ALL_FETCHERS if name in sources
    ]
    
    for name, fetcher_fn in fetchers:
        try:
            items = fetcher_fn()
            results[name] = items
            print(f"✅ {name}: {len(items)} 条")
        except Exception as e:
            results[name] = []
            print(f"❌ {name}: {e}")
    
    return results


# ============================================================
# SQLite 持久化
# ============================================================

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", "readlater.db")


def init_news_table(db_path: str = None):
    """初始化新闻相关表"""
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT,
            source TEXT NOT NULL,
            source_icon TEXT DEFAULT '',
            rank INTEGER DEFAULT 0,
            hot_score TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            fetch_date TEXT NOT NULL,
            fetch_time TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            UNIQUE(title, source, fetch_date)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_daily_news_date ON daily_news(fetch_date)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_daily_news_source ON daily_news(source)
    """)
    conn.commit()
    conn.close()


def save_news_to_db(items: List[NewsItem], db_path: str = None):
    """保存新闻到数据库"""
    conn = sqlite3.connect(db_path or DB_PATH)
    today = datetime.now().strftime("%Y-%m-%d")
    
    saved = 0
    for item in items:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO daily_news 
                (title, url, source, source_icon, rank, hot_score, summary, fetch_date, fetch_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (item.title, item.url, item.source, item.source_icon,
                  item.rank, item.hot_score, item.summary, today, item.fetch_time))
            saved += 1
        except Exception:
            pass
    
    conn.commit()
    conn.close()
    return saved


def get_today_news(db_path: str = None, source: str = None) -> List[Dict]:
    """获取今日新闻"""
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    today = datetime.now().strftime("%Y-%m-%d")
    
    if source:
        rows = conn.execute(
            "SELECT * FROM daily_news WHERE fetch_date = ? AND source = ? ORDER BY rank",
            (today, source)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM daily_news WHERE fetch_date = ? ORDER BY source, rank",
            (today,)
        ).fetchall()
    
    conn.close()
    return [dict(row) for row in rows]


# ============================================================
# 快捷函数
# ============================================================

def run_daily_fetch(db_path: str = None) -> Dict[str, int]:
    """
    执行每日抓取并保存到数据库
    
    Returns:
        {source: count} 各来源保存条数
    """
    init_news_table(db_path)
    
    all_items = fetch_all_news()
    
    stats = {}
    for source_name, items in all_items.items():
        count = save_news_to_db(items, db_path)
        stats[source_name] = count
    
    total = sum(stats.values())
    print(f"\n📊 总计抓取: {total} 条新闻")
    return stats


if __name__ == "__main__":
    print("=" * 60)
    print("📰 ReadLater 每日新闻头条抓取 v1.0")
    print("=" * 60)
    
    stats = run_daily_fetch()
    
    print("\n" + "=" * 60)
    print("📋 抓取统计:")
    for source, count in stats.items():
        print(f"  {source}: {count} 条")
