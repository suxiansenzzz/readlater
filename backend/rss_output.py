"""
ReadLater v1.4.0 - RSS 输出模块
将保存的文章生成 RSS Feed，方便其他阅读器订阅
"""

import json
import sqlite3
from datetime import datetime
from typing import Optional, List
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString


def generate_rss_feed(
    conn: sqlite3.Connection,
    base_url: str = "http://localhost:8000",
    limit: int = 50,
    tag: Optional[str] = None,
    favorites_only: bool = False
) -> str:
    """
    生成 RSS 2.0 Feed

    Args:
        conn: 数据库连接
        base_url: 服务基础 URL（用于生成链接）
        limit: 最多返回文章数
        tag: 按标签筛选（可选）
        favorites_only: 只包含收藏文章

    Returns:
        RSS XML 字符串
    """
    # 构建查询
    conditions = []
    params = []

    if tag:
        conditions.append("tags LIKE ?")
        params.append(f"%{tag}%")

    if favorites_only:
        conditions.append("is_favorite = 1")
        params.append(1)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    rows = conn.execute(
        f"SELECT * FROM articles {where} ORDER BY created_at DESC LIMIT ?",
        params + [limit]
    ).fetchall()

    # 构建 RSS XML
    rss = Element("rss")
    rss.set("version", "2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")

    channel = SubElement(rss, "channel")

    # 频道信息
    SubElement(channel, "title").text = "ReadLater 稍后阅读"
    SubElement(channel, "link").text = base_url
    SubElement(channel, "description").text = "我的稍后阅读文章列表"
    SubElement(channel, "language").text = "zh-CN"
    SubElement(channel, "lastBuildDate").text = datetime.now().strftime(
        "%a, %d %b %Y %H:%M:%S +0000"
    )

    # 自引用链接
    atom_link = SubElement(channel, "atom:link")
    atom_link.set("href", f"{base_url}/api/rss")
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    # 文章条目
    for row in rows:
        item = SubElement(channel, "item")

        SubElement(item, "title").text = row["title"] or "无标题"
        SubElement(item, "link").text = row["url"]
        SubElement(item, "guid").text = row["url"]
        SubElement(item, "description").text = row["excerpt"] or ""

        # 发布时间
        try:
            dt = datetime.fromisoformat(row["created_at"])
            pub_date = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
        except (ValueError, TypeError):
            pub_date = ""
        SubElement(item, "pubDate").text = pub_date

        # 来源域名
        if row["domain"]:
            SubElement(item, "source", url=row["url"]).text = row["domain"]

        # 标签作为 category
        tags = json.loads(row["tags"])
        for tag_name in tags:
            SubElement(item, "category").text = tag_name

    # 格式化输出
    raw_xml = tostring(rss, encoding="unicode")
    return parseString(raw_xml).toprettyxml(indent="  ", encoding=None)
