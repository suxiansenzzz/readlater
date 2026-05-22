"""
ReadLater RSS 订阅模块
支持 RSS/Atom feed 抓取和自动保存
"""
import asyncio
import json
import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

import httpx
import feedparser
from pydantic import BaseModel


@dataclass
class FeedItem:
    """RSS 文章项"""
    title: str
    url: str
    content: str
    published: Optional[datetime] = None
    author: Optional[str] = None
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class FeedSubscription(BaseModel):
    """RSS 订阅"""
    id: Optional[int] = None
    url: str
    title: Optional[str] = None
    tags: List[str] = []
    is_active: bool = True
    last_fetched: Optional[str] = None
    created_at: Optional[str] = None


class RSSManager:
    """RSS 订阅管理器"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()

    def get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """初始化 RSS 相关表"""
        conn = self.get_db()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rss_feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                tags TEXT DEFAULT '[]',
                is_active INTEGER DEFAULT 1,
                last_fetched TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rss_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feed_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                published TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (feed_id) REFERENCES rss_feeds(id) ON DELETE CASCADE,
                UNIQUE(feed_id, url)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rss_feed ON rss_items(feed_id)")
        conn.commit()
        conn.close()

    async def parse_feed(self, url: str) -> Dict[str, Any]:
        """解析 RSS/Atom feed"""
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30)
            response.raise_for_status()
            
        feed = feedparser.parse(response.text)
        
        return {
            'title': feed.feed.get('title', 'Unknown Feed'),
            'items': [
                FeedItem(
                    title=entry.get('title', '无标题'),
                    url=entry.get('link', ''),
                    content=entry.get('summary', entry.get('description', '')),
                    published=self._parse_date(entry),
                    author=entry.get('author'),
                    tags=[tag.get('term', '') for tag in entry.get('tags', [])]
                )
                for entry in feed.entries
            ]
        }

    def _parse_date(self, entry) -> Optional[datetime]:
        """解析发布日期"""
        for field in ['published_parsed', 'updated_parsed']:
            if hasattr(entry, field):
                parsed = getattr(entry, field)
                if parsed:
                    try:
                        return datetime(*parsed[:6])
                    except:
                        pass
        return None

    async def add_subscription(self, url: str, title: str = None, tags: List[str] = None) -> int:
        """添加订阅"""
        # 先解析 feed 获取标题
        if not title:
            try:
                feed_data = await self.parse_feed(url)
                title = feed_data['title']
            except:
                title = url

        conn = self.get_db()
        now = datetime.now().isoformat()
        
        cursor = conn.execute("""
            INSERT INTO rss_feeds (url, title, tags, created_at)
            VALUES (?, ?, ?, ?)
        """, (url, title, json.dumps(tags or [], ensure_ascii=False), now))
        
        feed_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return feed_id

    def get_subscriptions(self, active_only: bool = True) -> List[Dict]:
        """获取所有订阅"""
        conn = self.get_db()
        
        query = "SELECT * FROM rss_feeds"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY created_at DESC"
        
        rows = conn.execute(query).fetchall()
        conn.close()
        
        return [
            {
                'id': row['id'],
                'url': row['url'],
                'title': row['title'],
                'tags': json.loads(row['tags']),
                'is_active': bool(row['is_active']),
                'last_fetched': row['last_fetched'],
                'created_at': row['created_at']
            }
            for row in rows
        ]

    def update_subscription(self, feed_id: int, **kwargs) -> bool:
        """更新订阅"""
        conn = self.get_db()
        
        updates = []
        params = []
        
        for key, value in kwargs.items():
            if key == 'tags':
                updates.append("tags = ?")
                params.append(json.dumps(value, ensure_ascii=False))
            elif key in ['title', 'is_active', 'last_fetched']:
                updates.append(f"{key} = ?")
                params.append(value)
        
        if updates:
            params.append(feed_id)
            conn.execute(
                f"UPDATE rss_feeds SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()
        
        conn.close()
        return True

    def delete_subscription(self, feed_id: int) -> bool:
        """删除订阅"""
        conn = self.get_db()
        conn.execute("DELETE FROM rss_feeds WHERE id = ?", (feed_id,))
        conn.commit()
        conn.close()
        return True

    def is_item_saved(self, feed_id: int, url: str) -> bool:
        """检查文章是否已保存"""
        conn = self.get_db()
        result = conn.execute(
            "SELECT id FROM rss_items WHERE feed_id = ? AND url = ?",
            (feed_id, url)
        ).fetchone()
        conn.close()
        return result is not None

    def mark_item_saved(self, feed_id: int, url: str, title: str):
        """标记文章已保存"""
        conn = self.get_db()
        now = datetime.now().isoformat()
        try:
            conn.execute("""
                INSERT INTO rss_items (feed_id, url, title, created_at)
                VALUES (?, ?, ?, ?)
            """, (feed_id, url, title, now))
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # 已存在
        conn.close()

    def get_stats(self) -> Dict:
        """获取 RSS 统计"""
        conn = self.get_db()
        
        total_feeds = conn.execute("SELECT COUNT(*) FROM rss_feeds").fetchone()[0]
        active_feeds = conn.execute("SELECT COUNT(*) FROM rss_feeds WHERE is_active = 1").fetchone()[0]
        total_items = conn.execute("SELECT COUNT(*) FROM rss_items").fetchone()[0]
        
        conn.close()
        
        return {
            'total_feeds': total_feeds,
            'active_feeds': active_feeds,
            'total_items': total_items
        }


# 全局实例
_rss_manager = None

def get_rss_manager(db_path: str) -> RSSManager:
    global _rss_manager
    if _rss_manager is None:
        _rss_manager = RSSManager(db_path)
    return _rss_manager