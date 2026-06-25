"""
ReadLater v2.6.0 - 文章批注与高亮模块
支持用户在文章中添加高亮和文字批注
"""

import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional


def init_annotations_table(conn: sqlite3.Connection):
    """初始化批注数据库表"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            highlight_text TEXT NOT NULL,
            note TEXT DEFAULT '',
            color TEXT DEFAULT '#ffeb3b',
            start_offset INTEGER NOT NULL,
            end_offset INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_annotations_article_id ON annotations(article_id)"
    )
    conn.commit()


def create_annotation(
    conn: sqlite3.Connection,
    article_id: int,
    highlight_text: str,
    start_offset: int,
    end_offset: int,
    note: str = '',
    color: str = '#ffeb3b'
) -> Dict:
    """
    创建新批注
    
    Args:
        conn: 数据库连接
        article_id: 文章ID
        highlight_text: 高亮的文本内容
        start_offset: 高亮起始偏移量
        end_offset: 高亮结束偏移量
        note: 批注内容（可选）
        color: 高亮颜色（默认黄色）
    
    Returns:
        创建的批注信息
    """
    # 验证文章存在
    article = conn.execute(
        "SELECT id FROM articles WHERE id = ?", (article_id,)
    ).fetchone()
    
    if not article:
        raise ValueError(f"文章不存在: {article_id}")
    
    # 验证偏移量
    if start_offset < 0 or end_offset < 0:
        raise ValueError("偏移量不能为负数")
    
    if start_offset >= end_offset:
        raise ValueError("起始偏移量必须小于结束偏移量")
    
    # 验证颜色格式
    if not color.startswith('#') or len(color) not in (4, 7):
        raise ValueError("颜色格式无效，应为 #rgb 或 #rrggbb")
    
    # 验证高亮文本长度
    if not highlight_text or len(highlight_text.strip()) == 0:
        raise ValueError("高亮文本不能为空")
    
    if len(highlight_text) > 5000:
        raise ValueError("高亮文本长度不能超过5000字符")
    
    # 验证批注长度
    if len(note) > 10000:
        raise ValueError("批注内容长度不能超过10000字符")
    
    now = datetime.now().isoformat()
    
    cursor = conn.execute("""
        INSERT INTO annotations (article_id, highlight_text, note, color, start_offset, end_offset, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (article_id, highlight_text.strip(), note.strip(), color, start_offset, end_offset, now, now))
    
    annotation_id = cursor.lastrowid
    conn.commit()
    
    return {
        "id": annotation_id,
        "article_id": article_id,
        "highlight_text": highlight_text.strip(),
        "note": note.strip(),
        "color": color,
        "start_offset": start_offset,
        "end_offset": end_offset,
        "created_at": now,
        "updated_at": now
    }


def get_annotations(conn: sqlite3.Connection, article_id: int) -> List[Dict]:
    """
    获取文章的所有批注
    
    Args:
        conn: 数据库连接
        article_id: 文章ID
    
    Returns:
        批注列表，按start_offset排序
    """
    rows = conn.execute("""
        SELECT * FROM annotations 
        WHERE article_id = ? 
        ORDER BY start_offset ASC
    """, (article_id,)).fetchall()
    
    return [
        {
            "id": row["id"],
            "article_id": row["article_id"],
            "highlight_text": row["highlight_text"],
            "note": row["note"],
            "color": row["color"],
            "start_offset": row["start_offset"],
            "end_offset": row["end_offset"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
        for row in rows
    ]


def get_annotation(conn: sqlite3.Connection, annotation_id: int) -> Optional[Dict]:
    """
    获取单个批注详情
    
    Args:
        conn: 数据库连接
        annotation_id: 批注ID
    
    Returns:
        批注信息，不存在返回None
    """
    row = conn.execute(
        "SELECT * FROM annotations WHERE id = ?", (annotation_id,)
    ).fetchone()
    
    if not row:
        return None
    
    return {
        "id": row["id"],
        "article_id": row["article_id"],
        "highlight_text": row["highlight_text"],
        "note": row["note"],
        "color": row["color"],
        "start_offset": row["start_offset"],
        "end_offset": row["end_offset"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }


def update_annotation(
    conn: sqlite3.Connection,
    annotation_id: int,
    note: Optional[str] = None,
    color: Optional[str] = None
) -> Optional[Dict]:
    """
    更新批注
    
    Args:
        conn: 数据库连接
        annotation_id: 批注ID
        note: 新批注内容（可选）
        color: 新颜色（可选）
    
    Returns:
        更新后的批注信息，不存在返回None
    """
    # 检查批注是否存在
    existing = get_annotation(conn, annotation_id)
    if not existing:
        return None
    
    updates = []
    params = []
    
    if note is not None:
        if len(note) > 10000:
            raise ValueError("批注内容长度不能超过10000字符")
        updates.append("note = ?")
        params.append(note.strip())
    
    if color is not None:
        if not color.startswith('#') or len(color) not in (4, 7):
            raise ValueError("颜色格式无效，应为 #rgb 或 #rrggbb")
        updates.append("color = ?")
        params.append(color)
    
    if not updates:
        return existing
    
    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(annotation_id)
    
    conn.execute(
        f"UPDATE annotations SET {', '.join(updates)} WHERE id = ?",
        params
    )
    conn.commit()
    
    return get_annotation(conn, annotation_id)


def delete_annotation(conn: sqlite3.Connection, annotation_id: int) -> bool:
    """
    删除批注
    
    Args:
        conn: 数据库连接
        annotation_id: 批注ID
    
    Returns:
        是否删除成功
    """
    result = conn.execute(
        "DELETE FROM annotations WHERE id = ?", (annotation_id,)
    )
    conn.commit()
    return result.rowcount > 0


def get_all_annotations(conn: sqlite3.Connection, limit: int = 100, offset: int = 0) -> List[Dict]:
    """
    获取所有批注（带分页）
    
    Args:
        conn: 数据库连接
        limit: 每页数量
        offset: 偏移量
    
    Returns:
        批注列表（含文章标题）
    """
    rows = conn.execute("""
        SELECT a.*, ar.title as article_title, ar.url as article_url
        FROM annotations a
        JOIN articles ar ON a.article_id = ar.id
        ORDER BY a.updated_at DESC
        LIMIT ? OFFSET ?
    """, (limit, offset)).fetchall()
    
    return [
        {
            "id": row["id"],
            "article_id": row["article_id"],
            "article_title": row["article_title"],
            "article_url": row["article_url"],
            "highlight_text": row["highlight_text"],
            "note": row["note"],
            "color": row["color"],
            "start_offset": row["start_offset"],
            "end_offset": row["end_offset"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
        for row in rows
    ]


def get_annotations_stats(conn: sqlite3.Connection) -> Dict:
    """
    获取批注统计信息
    
    Returns:
        统计信息字典
    """
    total = conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0]
    articles_with_annotations = conn.execute(
        "SELECT COUNT(DISTINCT article_id) FROM annotations"
    ).fetchone()[0]
    annotations_with_notes = conn.execute(
        "SELECT COUNT(*) FROM annotations WHERE note != ''"
    ).fetchone()[0]
    
    return {
        "total_annotations": total,
        "articles_with_annotations": articles_with_annotations,
        "highlights_only": total - annotations_with_notes,
        "with_notes": annotations_with_notes
    }
