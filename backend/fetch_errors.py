"""
ReadLater v2.6.0 - 抓取失败管理模块
记录和管理抓取失败的文章URL，支持重试
"""

import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Tuple


def init_fetch_errors_table(conn: sqlite3.Connection):
    """初始化抓取错误数据库表"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fetch_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT DEFAULT '',
            error_type TEXT NOT NULL,
            error_message TEXT NOT NULL,
            attempts INTEGER DEFAULT 1,
            first_attempt_at TEXT NOT NULL,
            last_attempt_at TEXT NOT NULL,
            is_resolved INTEGER DEFAULT 0,
            resolved_at TEXT,
            metadata TEXT DEFAULT '{}'
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_fetch_errors_url ON fetch_errors(url)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_fetch_errors_resolved ON fetch_errors(is_resolved)"
    )
    conn.commit()


def record_fetch_error(
    conn: sqlite3.Connection,
    url: str,
    error_type: str,
    error_message: str,
    title: str = '',
    metadata: Dict = None
) -> Dict:
    """
    记录抓取失败
    
    Args:
        conn: 数据库连接
        url: 抓取失败的URL
        error_type: 错误类型（network, timeout, parse, captcha, http_error等）
        error_message: 错误详细信息
        title: 文章标题（如果能获取到）
        metadata: 额外元数据（HTTP状态码等）
    
    Returns:
        记录的错误信息
    """
    # 输入验证
    if not url or len(url.strip()) == 0:
        raise ValueError("URL不能为空")
    
    if len(url) > 2048:
        raise ValueError("URL长度不能超过2048字符")
    
    if not error_type or len(error_type.strip()) == 0:
        raise ValueError("错误类型不能为空")
    
    if len(error_type) > 50:
        raise ValueError("错误类型长度不能超过50字符")
    
    if not error_message or len(error_message.strip()) == 0:
        raise ValueError("错误信息不能为空")
    
    if len(error_message) > 5000:
        raise ValueError("错误信息长度不能超过5000字符")
    
    if len(title) > 500:
        raise ValueError("标题长度不能超过500字符")
    
    now = datetime.now().isoformat()
    meta_json = json.dumps(metadata or {}, ensure_ascii=False)
    
    # 检查是否已有记录
    existing = conn.execute(
        "SELECT * FROM fetch_errors WHERE url = ? AND is_resolved = 0", (url,)
    ).fetchone()
    
    if existing:
        # 更新已有记录
        attempts = existing["attempts"] + 1
        conn.execute("""
            UPDATE fetch_errors 
            SET attempts = ?, last_attempt_at = ?, error_type = ?, error_message = ?, metadata = ?
            WHERE id = ?
        """, (attempts, now, error_type, error_message, meta_json, existing["id"]))
        conn.commit()
        
        return {
            "id": existing["id"],
            "url": url,
            "title": title or existing["title"],
            "error_type": error_type,
            "error_message": error_message,
            "attempts": attempts,
            "first_attempt_at": existing["first_attempt_at"],
            "last_attempt_at": now,
            "is_resolved": False,
            "metadata": metadata or {}
        }
    else:
        # 创建新记录
        cursor = conn.execute("""
            INSERT INTO fetch_errors (url, title, error_type, error_message, attempts, first_attempt_at, last_attempt_at, metadata)
            VALUES (?, ?, ?, ?, 1, ?, ?, ?)
        """, (url, title, error_type, error_message, now, now, meta_json))
        
        error_id = cursor.lastrowid
        conn.commit()
        
        return {
            "id": error_id,
            "url": url,
            "title": title,
            "error_type": error_type,
            "error_message": error_message,
            "attempts": 1,
            "first_attempt_at": now,
            "last_attempt_at": now,
            "is_resolved": False,
            "metadata": metadata or {}
        }


def get_fetch_errors(
    conn: sqlite3.Connection,
    unresolved_only: bool = True,
    limit: int = 50,
    offset: int = 0
) -> List[Dict]:
    """
    获取抓取失败记录列表
    
    Args:
        conn: 数据库连接
        unresolved_only: 是否只返回未解决的
        limit: 每页数量
        offset: 偏移量
    
    Returns:
        错误记录列表
    """
    query = "SELECT * FROM fetch_errors"
    params = []
    
    if unresolved_only:
        query += " WHERE is_resolved = 0"
    
    query += " ORDER BY last_attempt_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    rows = conn.execute(query, params).fetchall()
    
    return [_row_to_dict(row) for row in rows]


def get_fetch_error(conn: sqlite3.Connection, error_id: int) -> Optional[Dict]:
    """
    获取单个抓取错误详情
    
    Args:
        conn: 数据库连接
        error_id: 错误ID
    
    Returns:
        错误信息，不存在返回None
    """
    row = conn.execute(
        "SELECT * FROM fetch_errors WHERE id = ?", (error_id,)
    ).fetchone()
    
    if not row:
        return None
    
    return _row_to_dict(row)


def get_fetch_error_by_url(conn: sqlite3.Connection, url: str) -> Optional[Dict]:
    """
    根据URL获取抓取错误
    
    Args:
        conn: 数据库连接
        url: 文章URL
    
    Returns:
        错误信息，不存在返回None
    """
    row = conn.execute(
        "SELECT * FROM fetch_errors WHERE url = ? AND is_resolved = 0", (url,)
    ).fetchone()
    
    if not row:
        return None
    
    return _row_to_dict(row)


def resolve_fetch_error(conn: sqlite3.Connection, error_id: int) -> bool:
    """
    标记抓取错误为已解决
    
    Args:
        conn: 数据库连接
        error_id: 错误ID
    
    Returns:
        是否操作成功
    """
    now = datetime.now().isoformat()
    result = conn.execute(
        "UPDATE fetch_errors SET is_resolved = 1, resolved_at = ? WHERE id = ?",
        (now, error_id)
    )
    conn.commit()
    return result.rowcount > 0


def delete_fetch_error(conn: sqlite3.Connection, error_id: int) -> bool:
    """
    删除抓取错误记录
    
    Args:
        conn: 数据库连接
        error_id: 错误ID
    
    Returns:
        是否删除成功
    """
    result = conn.execute(
        "DELETE FROM fetch_errors WHERE id = ?", (error_id,)
    )
    conn.commit()
    return result.rowcount > 0


def clear_resolved_errors(conn: sqlite3.Connection) -> int:
    """
    清除所有已解决的错误记录
    
    Returns:
        删除的记录数
    """
    result = conn.execute("DELETE FROM fetch_errors WHERE is_resolved = 1")
    conn.commit()
    return result.rowcount


def get_fetch_errors_stats(conn: sqlite3.Connection) -> Dict:
    """
    获取抓取错误统计信息
    
    Returns:
        统计信息字典
    """
    total = conn.execute("SELECT COUNT(*) FROM fetch_errors").fetchone()[0]
    unresolved = conn.execute(
        "SELECT COUNT(*) FROM fetch_errors WHERE is_resolved = 0"
    ).fetchone()[0]
    resolved = total - unresolved
    
    # 按错误类型统计
    error_types = conn.execute("""
        SELECT error_type, COUNT(*) as count 
        FROM fetch_errors 
        WHERE is_resolved = 0 
        GROUP BY error_type 
        ORDER BY count DESC
    """).fetchall()
    
    # 按尝试次数排序的Top失败URL
    top_failures = conn.execute("""
        SELECT url, title, attempts, error_type
        FROM fetch_errors 
        WHERE is_resolved = 0 
        ORDER BY attempts DESC
        LIMIT 5
    """).fetchall()
    
    return {
        "total": total,
        "unresolved": unresolved,
        "resolved": resolved,
        "error_types": [
            {"type": row["error_type"], "count": row["count"]}
            for row in error_types
        ],
        "top_failures": [
            {
                "url": row["url"],
                "title": row["title"] or "(无标题)",
                "attempts": row["attempts"],
                "error_type": row["error_type"]
            }
            for row in top_failures
        ]
    }


def _row_to_dict(row: sqlite3.Row) -> Dict:
    """将数据库行转换为字典"""
    metadata = {}
    try:
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}
    except (json.JSONDecodeError, TypeError):
        pass
    
    return {
        "id": row["id"],
        "url": row["url"],
        "title": row["title"],
        "error_type": row["error_type"],
        "error_message": row["error_message"],
        "attempts": row["attempts"],
        "first_attempt_at": row["first_attempt_at"],
        "last_attempt_at": row["last_attempt_at"],
        "is_resolved": bool(row["is_resolved"]),
        "resolved_at": row["resolved_at"],
        "metadata": metadata
    }
