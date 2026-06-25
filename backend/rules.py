"""
ReadLater v1.7.0 - 自动标签规则引擎
根据域名、关键词等条件自动为文章打标签
"""

import json
import re
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional


def init_rules_table(conn: sqlite3.Connection):
    """初始化标签规则数据库表"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tag_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            rule_type TEXT NOT NULL,
            pattern TEXT NOT NULL,
            tags TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            priority INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_rules_active ON tag_rules(is_active)"
    )
    conn.commit()


def apply_rules_to_article(
    conn: sqlite3.Connection,
    article_id: int,
    url: str,
    title: str,
    content: str
) -> List[str]:
    """
    将所有活跃规则应用到文章，返回匹配到的标签

    Args:
        conn: 数据库连接
        article_id: 文章 ID
        url: 文章 URL
        title: 文章标题
        content: 文章内容

    Returns:
        匹配到的标签列表
    """
    # 获取所有活跃规则，按优先级排序
    rules = conn.execute(
        "SELECT * FROM tag_rules WHERE is_active = 1 ORDER BY priority DESC"
    ).fetchall()

    matched_tags = []

    for rule in rules:
        pattern = rule["pattern"]
        rule_type = rule["rule_type"]
        tags = json.loads(rule["tags"])

        matched = False

        if rule_type == "domain":
            # 域名匹配
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            # 支持通配符：*.example.com 匹配 sub.example.com
            if pattern.startswith("*."):
                base_domain = pattern[2:]
                matched = domain.endswith(base_domain)
            else:
                matched = domain == pattern or domain.endswith(f".{pattern}")

        elif rule_type == "url_contains":
            # URL 包含指定字符串
            matched = pattern.lower() in url.lower()

        elif rule_type == "title_contains":
            # 标题包含指定关键词
            matched = pattern.lower() in title.lower()

        elif rule_type == "title_regex":
            # 标题匹配正则表达式
            try:
                matched = bool(re.search(pattern, title, re.IGNORECASE))
            except re.error:
                continue

        elif rule_type == "content_contains":
            # 正文包含指定关键词
            matched = pattern.lower() in content.lower()

        elif rule_type == "content_regex":
            # 正文匹配正则表达式
            try:
                matched = bool(re.search(pattern, content[:5000], re.IGNORECASE))
            except re.error:
                continue

        if matched:
            matched_tags.extend(tags)

    # 去重
    matched_tags = list(set(matched_tags))

    # 如果有匹配的标签，更新文章
    if matched_tags:
        current_row = conn.execute(
            "SELECT tags FROM articles WHERE id = ?", (article_id,)
        ).fetchone()

        if current_row:
            current_tags = json.loads(current_row["tags"])
            # 合并标签（不覆盖已有标签）
            merged_tags = list(set(current_tags + matched_tags))
            conn.execute(
                "UPDATE articles SET tags = ?, updated_at = ? WHERE id = ?",
                (
                    json.dumps(merged_tags, ensure_ascii=False),
                    datetime.now().isoformat(),
                    article_id
                )
            )
            conn.commit()

    return matched_tags


def create_rule(
    conn: sqlite3.Connection,
    name: str,
    rule_type: str,
    pattern: str,
    tags: List[str],
    priority: int = 0
) -> int:
    """
    创建新的标签规则

    Args:
        conn: 数据库连接
        name: 规则名称（便于识别）
        rule_type: 规则类型（domain/url_contains/title_contains/title_regex/content_contains/content_regex）
        pattern: 匹配模式
        tags: 匹配后自动添加的标签
        priority: 优先级（数字越大优先级越高）

    Returns:
        规则 ID
    """
    valid_types = {
        "domain", "url_contains", "title_contains",
        "title_regex", "content_contains", "content_regex"
    }
    if rule_type not in valid_types:
        raise ValueError(f"无效的规则类型: {rule_type}，支持: {', '.join(valid_types)}")

    now = datetime.now().isoformat()
    cursor = conn.execute("""
        INSERT INTO tag_rules (name, rule_type, pattern, tags, priority, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, rule_type, pattern, json.dumps(tags, ensure_ascii=False), priority, now))

    rule_id = cursor.lastrowid
    conn.commit()
    return rule_id


def get_all_rules(conn: sqlite3.Connection) -> List[Dict]:
    """获取所有标签规则"""
    rows = conn.execute(
        "SELECT * FROM tag_rules ORDER BY priority DESC, created_at DESC"
    ).fetchall()

    return [{
        "id": row["id"],
        "name": row["name"],
        "rule_type": row["rule_type"],
        "pattern": row["pattern"],
        "tags": json.loads(row["tags"]),
        "is_active": bool(row["is_active"]),
        "priority": row["priority"],
        "created_at": row["created_at"]
    } for row in rows]


def get_rule(conn: sqlite3.Connection, rule_id: int) -> Optional[Dict]:
    """获取单个标签规则"""
    row = conn.execute(
        "SELECT * FROM tag_rules WHERE id = ?", (rule_id,)
    ).fetchone()
    
    if not row:
        return None
    
    return {
        "id": row["id"],
        "name": row["name"],
        "rule_type": row["rule_type"],
        "pattern": row["pattern"],
        "tags": json.loads(row["tags"]),
        "is_active": bool(row["is_active"]),
        "priority": row["priority"],
        "created_at": row["created_at"]
    }


def update_rule(conn: sqlite3.Connection, rule_id: int, **kwargs) -> bool:
    """更新标签规则"""
    # 检查规则是否存在
    existing = get_rule(conn, rule_id)
    if not existing:
        return False
    
    updates = []
    params = []

    for key, value in kwargs.items():
        if value is None:
            continue  # 跳过None值
            
        if key == "tags":
            updates.append("tags = ?")
            params.append(json.dumps(value, ensure_ascii=False))
        elif key in ("name", "rule_type", "pattern"):
            updates.append(f"{key} = ?")
            params.append(value)
        elif key == "is_active":
            updates.append("is_active = ?")
            params.append(1 if value else 0)
        elif key == "priority":
            updates.append("priority = ?")
            params.append(value)

    if updates:
        params.append(rule_id)
        conn.execute(
            f"UPDATE tag_rules SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
        return True

    return False


def delete_rule(conn: sqlite3.Connection, rule_id: int) -> bool:
    """删除标签规则"""
    conn.execute("DELETE FROM tag_rules WHERE id = ?", (rule_id,))
    conn.commit()
    return True


def apply_rules_to_all(conn: sqlite3.Connection) -> Dict:
    """
    将所有规则应用到所有文章（批量操作）

    Returns:
        处理结果统计
    """
    rows = conn.execute("SELECT id, url, title, content FROM articles").fetchall()

    updated = 0
    total_tags_added = 0

    for row in rows:
        matched = apply_rules_to_article(
            conn, row["id"], row["url"], row["title"], row["content"]
        )
        if matched:
            updated += 1
            total_tags_added += len(matched)

    return {
        "total_articles": len(rows),
        "updated": updated,
        "total_tags_added": total_tags_added
    }


def get_rules_stats(conn: sqlite3.Connection) -> Dict:
    """获取规则统计信息"""
    # 总规则数
    total = conn.execute("SELECT COUNT(*) as count FROM tag_rules").fetchone()["count"]
    
    # 活跃规则数
    active = conn.execute("SELECT COUNT(*) as count FROM tag_rules WHERE is_active = 1").fetchone()["count"]
    
    # 按类型统计
    type_stats = conn.execute("""
        SELECT rule_type, COUNT(*) as count 
        FROM tag_rules 
        GROUP BY rule_type 
        ORDER BY count DESC
    """).fetchall()
    
    # 最近创建的规则
    recent = conn.execute("""
        SELECT id, name, rule_type, created_at 
        FROM tag_rules 
        ORDER BY created_at DESC 
        LIMIT 5
    """).fetchall()
    
    return {
        "total": total,
        "active": active,
        "inactive": total - active,
        "by_type": {row["rule_type"]: row["count"] for row in type_stats},
        "recent_rules": [{
            "id": row["id"],
            "name": row["name"],
            "rule_type": row["rule_type"],
            "created_at": row["created_at"]
        } for row in recent]
    }
