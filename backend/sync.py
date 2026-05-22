"""
ReadLater v1.9.0 - 跨设备同步模块
多用户支持 + 设备同步 API
"""

import hashlib
import json
import sqlite3
import secrets
from datetime import datetime
from typing import Optional, Dict, List


def init_users_table(conn: sqlite3.Connection):
    """初始化用户和同步相关数据库表"""
    # 用户表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            api_token TEXT UNIQUE,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            last_login TEXT
        )
    """)

    # 同步日志表：记录设备间同步状态
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            device_id TEXT NOT NULL,
            article_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            sync_data TEXT,
            synced_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
        )
    """)

    # 给 articles 表添加 user_id 列（多用户支持）
    try:
        conn.execute("ALTER TABLE articles ADD COLUMN user_id INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass  # 列已存在

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_token ON users(api_token)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sync_user ON sync_log(user_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sync_device ON sync_log(device_id)"
    )
    conn.commit()


def hash_password(password: str, salt: str = "readlater") -> str:
    """密码哈希"""
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


def create_user(
    conn: sqlite3.Connection,
    username: str,
    password: str,
    display_name: str = None
) -> Dict:
    """
    创建新用户

    Args:
        conn: 数据库连接
        username: 用户名
        password: 密码
        display_name: 显示名称

    Returns:
        用户信息
    """
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()

    if existing:
        raise ValueError("用户名已存在")

    password_hash = hash_password(password)
    api_token = secrets.token_hex(32)
    now = datetime.now().isoformat()

    cursor = conn.execute("""
        INSERT INTO users (username, password_hash, display_name, api_token, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (username, password_hash, display_name or username, api_token, now))

    user_id = cursor.lastrowid
    conn.commit()

    return {
        "id": user_id,
        "username": username,
        "display_name": display_name or username,
        "api_token": api_token,
        "created_at": now
    }


def authenticate_user(
    conn: sqlite3.Connection,
    username: str,
    password: str
) -> Optional[Dict]:
    """
    用户认证

    Args:
        conn: 数据库连接
        username: 用户名
        password: 密码

    Returns:
        用户信息，认证失败返回 None
    """
    password_hash = hash_password(password)

    user = conn.execute("""
        SELECT * FROM users
        WHERE username = ? AND password_hash = ? AND is_active = 1
    """, (username, password_hash)).fetchone()

    if not user:
        return None

    # 更新最后登录时间
    now = datetime.now().isoformat()
    conn.execute(
        "UPDATE users SET last_login = ? WHERE id = ?",
        (now, user["id"])
    )
    conn.commit()

    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "api_token": user["api_token"],
        "last_login": now
    }


def verify_token(conn: sqlite3.Connection, token: str) -> Optional[Dict]:
    """
    验证 API 令牌

    Args:
        conn: 数据库连接
        token: API 令牌

    Returns:
        用户信息，验证失败返回 None
    """
    user = conn.execute(
        "SELECT * FROM users WHERE api_token = ? AND is_active = 1",
        (token,)
    ).fetchone()

    if not user:
        return None

    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"]
    }


def record_sync_action(
    conn: sqlite3.Connection,
    user_id: int,
    device_id: str,
    article_id: int,
    action: str,
    sync_data: Dict = None
):
    """
    记录同步操作

    Args:
        conn: 数据库连接
        user_id: 用户 ID
        device_id: 设备标识
        article_id: 文章 ID
        action: 操作类型（save/read/favorite/archive/delete/tag）
        sync_data: 同步附加数据
    """
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO sync_log (user_id, device_id, article_id, action, sync_data, synced_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_id, device_id, article_id, action,
        json.dumps(sync_data or {}, ensure_ascii=False),
        now
    ))
    conn.commit()


def get_sync_changes(
    conn: sqlite3.Connection,
    user_id: int,
    device_id: str,
    since: str = None
) -> List[Dict]:
    """
    获取自上次同步以来的变更

    Args:
        conn: 数据库连接
        user_id: 用户 ID
        device_id: 设备标识（获取其他设备的变更）
        since: 起始时间（ISO 格式），None 表示获取所有

    Returns:
        变更列表
    """
    if since:
        rows = conn.execute("""
            SELECT * FROM sync_log
            WHERE user_id = ? AND device_id != ? AND synced_at > ?
            ORDER BY synced_at ASC
        """, (user_id, device_id, since)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM sync_log
            WHERE user_id = ? AND device_id != ?
            ORDER BY synced_at ASC
        """, (user_id, device_id)).fetchall()

    return [{
        "article_id": row["article_id"],
        "action": row["action"],
        "sync_data": json.loads(row["sync_data"]),
        "synced_at": row["synced_at"]
    } for row in rows]


def get_default_user(conn: sqlite3.Connection) -> Dict:
    """
    获取或创建默认用户（兼容单用户模式）

    在没有多用户需求时，自动创建一个默认用户
    """
    user = conn.execute(
        "SELECT * FROM users WHERE username = 'default'"
    ).fetchone()

    if user:
        return {
            "id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "api_token": user["api_token"]
        }

    # 创建默认用户
    return create_user(conn, "default", "default", "默认用户")
