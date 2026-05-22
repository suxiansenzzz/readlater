"""
ReadLater v1.5.0 - 公开分享模块
生成分享链接，让其他人可以查看你的文章
"""

import hashlib
import json
import sqlite3
from datetime import datetime
from typing import Optional


def init_share_table(conn: sqlite3.Connection):
    """初始化分享相关数据库表"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            share_token TEXT UNIQUE NOT NULL,
            is_active INTEGER DEFAULT 1,
            view_count INTEGER DEFAULT 0,
            expires_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_share_token ON shares(share_token)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_share_article ON shares(article_id)"
    )
    conn.commit()


def generate_share_token(article_id: int, secret: str = "readlater") -> str:
    """
    为文章生成唯一的分享令牌

    Args:
        article_id: 文章 ID
        secret: 加密盐

    Returns:
        8 位分享令牌
    """
    raw = f"{article_id}-{secret}-{datetime.now().isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def create_share(
    conn: sqlite3.Connection,
    article_id: int,
    expires_hours: Optional[int] = None
) -> dict:
    """
    创建文章分享链接

    Args:
        conn: 数据库连接
        article_id: 文章 ID
        expires_hours: 过期小时数（None 表示永不过期）

    Returns:
        分享信息字典
    """
    # 检查文章是否存在
    article = conn.execute(
        "SELECT id, title FROM articles WHERE id = ?", (article_id,)
    ).fetchone()

    if not article:
        raise ValueError("文章不存在")

    # 检查是否已有活跃的分享链接
    existing = conn.execute(
        "SELECT share_token FROM shares WHERE article_id = ? AND is_active = 1",
        (article_id,)
    ).fetchone()

    if existing:
        return {
            "share_token": existing["share_token"],
            "article_id": article_id,
            "article_title": article["title"],
            "already_exists": True
        }

    # 生成新的分享令牌
    token = generate_share_token(article_id)
    now = datetime.now().isoformat()

    expires_at = None
    if expires_hours:
        from datetime import timedelta
        expires_at = (datetime.now() + timedelta(hours=expires_hours)).isoformat()

    conn.execute("""
        INSERT INTO shares (article_id, share_token, expires_at, created_at)
        VALUES (?, ?, ?, ?)
    """, (article_id, token, expires_at, now))
    conn.commit()

    return {
        "share_token": token,
        "article_id": article_id,
        "article_title": article["title"],
        "expires_at": expires_at,
        "created_at": now
    }


def get_shared_article(conn: sqlite3.Connection, share_token: str) -> Optional[dict]:
    """
    通过分享令牌获取文章

    Args:
        conn: 数据库连接
        share_token: 分享令牌

    Returns:
        文章信息字典，过期或不存在返回 None
    """
    # 查找分享记录
    share = conn.execute("""
        SELECT s.*, a.title, a.content, a.url, a.domain,
               a.word_count, a.reading_time, a.created_at as article_created_at,
               a.tags
        FROM shares s
        JOIN articles a ON s.article_id = a.id
        WHERE s.share_token = ? AND s.is_active = 1
    """, (share_token,)).fetchone()

    if not share:
        return None

    # 检查是否过期
    if share["expires_at"]:
        try:
            expires = datetime.fromisoformat(share["expires_at"])
            if datetime.now() > expires:
                # 标记为过期
                conn.execute(
                    "UPDATE shares SET is_active = 0 WHERE id = ?",
                    (share["id"],)
                )
                conn.commit()
                return None
        except ValueError:
            pass

    # 增加查看计数
    conn.execute(
        "UPDATE shares SET view_count = view_count + 1 WHERE id = ?",
        (share["id"],)
    )
    conn.commit()

    return {
        "title": share["title"],
        "content": share["content"],
        "url": share["url"],
        "domain": share["domain"],
        "word_count": share["word_count"],
        "reading_time": share["reading_time"],
        "tags": json.loads(share["tags"]),
        "created_at": share["article_created_at"],
        "view_count": share["view_count"] + 1
    }


def revoke_share(conn: sqlite3.Connection, article_id: int) -> bool:
    """
    撤销文章的分享链接

    Args:
        conn: 数据库连接
        article_id: 文章 ID

    Returns:
        是否成功
    """
    conn.execute(
        "UPDATE shares SET is_active = 0 WHERE article_id = ?",
        (article_id,)
    )
    conn.commit()
    return True


def get_share_info(conn: sqlite3.Connection, article_id: int) -> Optional[dict]:
    """
    获取文章的分享信息

    Args:
        conn: 数据库连接
        article_id: 文章 ID

    Returns:
        分享信息，无分享返回 None
    """
    share = conn.execute(
        "SELECT * FROM shares WHERE article_id = ? AND is_active = 1",
        (article_id,)
    ).fetchone()

    if not share:
        return None

    return {
        "share_token": share["share_token"],
        "view_count": share["view_count"],
        "expires_at": share["expires_at"],
        "created_at": share["created_at"]
    }
