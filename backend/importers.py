"""
ReadLater v1.3.0 - 数据导入模块
支持从 Pocket、Instapaper、浏览器书签、Wallabag 导入文章
"""

import csv
import json
import sqlite3
from datetime import datetime
from io import StringIO
from typing import List, Dict, Tuple, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup


def import_from_pocket_csv(
    conn: sqlite3.Connection,
    csv_content: str,
    fetcher_func=None
) -> Dict:
    """
    从 Pocket 导出的 CSV 文件导入文章

    Pocket CSV 栗式:
    title,url,time,tags
    "文章标题","https://example.com","2024-01-01","tag1,tag2"

    Args:
        conn: 数据库连接
        csv_content: CSV 文件内容
        fetcher_func: 文章抓取函数（可选，不提供则只保存基本信息）

    Returns:
        导入结果统计
    """
    reader = csv.DictReader(StringIO(csv_content))
    imported = 0
    skipped = 0
    errors = []

    for row in reader:
        try:
            url = row.get("url", "").strip()
            if not url:
                continue

            # 检查是否已存在
            existing = conn.execute(
                "SELECT id FROM articles WHERE url = ?", (url,)
            ).fetchone()
            if existing:
                skipped += 1
                continue

            title = row.get("title", "").strip() or "无标题"
            tags_str = row.get("tags", "").strip()
            tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

            # 解析时间
            time_str = row.get("time", "").strip()
            created_at = _parse_timestamp(time_str)

            # 如果有抓取函数，尝试抓取完整内容
            content = ""
            word_count = 0
            reading_time = 0
            domain = urlparse(url).netloc

            if fetcher_func:
                try:
                    data = fetcher_func(url)
                    content = data.get("content", "")
                    title = data.get("title", title)
                    word_count = data.get("word_count", len(content))
                    reading_time = data.get("reading_time", max(1, word_count // 500))
                except Exception:
                    # 抓取失败，保存基本信息
                    pass

            if not content:
                content = f"[待抓取] {title}"
                word_count = len(content)
                reading_time = 1

            excerpt = content[:200].replace("\n", " ").strip()
            if len(content) > 200:
                excerpt += "..."

            now = datetime.now().isoformat()
            conn.execute("""
                INSERT INTO articles
                (url, title, content, excerpt, tags, is_read, created_at,
                 word_count, reading_time, domain)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                url, title, content, excerpt,
                json.dumps(tags, ensure_ascii=False),
                1,  # Pocket 导出的标记为已读
                created_at or now,
                word_count, reading_time, domain
            ))
            imported += 1

        except Exception as e:
            errors.append(f"行导入失败: {str(e)}")

    conn.commit()
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "source": "pocket"
    }


def import_from_wallabag_json(
    conn: sqlite3.Connection,
    json_content: str,
    fetcher_func=None
) -> Dict:
    """
    从 Wallabag 导出的 JSON 文件导入文章

    Wallabag JSON 栗式:
    {
        "export": [
            {
                "title": "...",
                "url": "...",
                "content": "...",
                "tags": ["tag1", "tag2"],
                "is_archived": 0,
                "is_starred": 0,
                "created_at": "2024-01-01T00:00:00+0000"
            }
        ]
    }

    Args:
        conn: 数据库连接
        json_content: JSON 文件内容
        fetcher_func: 文章抓取函数（可选）

    Returns:
        导入结果统计
    """
    try:
        data = json.loads(json_content)
    except json.JSONDecodeError:
        return {"imported": 0, "skipped": 0, "errors": ["JSON 格式无效"], "source": "wallabag"}

    # Wallabag 导出格式可能是数组或 {export: [...]}
    if isinstance(data, list):
        articles = data
    elif isinstance(data, dict):
        articles = data.get("export", data.get("entries", []))
    else:
        return {"imported": 0, "skipped": 0, "errors": ["无法识别的格式"], "source": "wallabag"}

    imported = 0
    skipped = 0
    errors = []

    for item in articles:
        try:
            url = item.get("url", "").strip()
            if not url:
                continue

            existing = conn.execute(
                "SELECT id FROM articles WHERE url = ?", (url,)
            ).fetchone()
            if existing:
                skipped += 1
                continue

            title = item.get("title", "").strip() or "无标题"
            content = item.get("content", "").strip()
            tags = item.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]

            is_read = bool(item.get("is_archived", 0))
            is_favorite = bool(item.get("is_starred", 0))
            created_at = _parse_iso_time(item.get("created_at"))

            domain = urlparse(url).netloc
            word_count = len(content) if content else 0
            reading_time = max(1, word_count // 500)

            # 如果没有内容且有抓取函数，尝试抓取
            if not content and fetcher_func:
                try:
                    data = fetcher_func(url)
                    content = data.get("content", "")
                    title = data.get("title", title)
                    word_count = data.get("word_count", len(content))
                    reading_time = data.get("reading_time", max(1, word_count // 500))
                except Exception:
                    pass

            if not content:
                content = f"[待抓取] {title}"
                word_count = len(content)

            excerpt = content[:200].replace("\n", " ").strip()
            if len(content) > 200:
                excerpt += "..."

            now = datetime.now().isoformat()
            conn.execute("""
                INSERT INTO articles
                (url, title, content, excerpt, tags, is_read, is_favorite,
                 created_at, word_count, reading_time, domain)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                url, title, content, excerpt,
                json.dumps(tags, ensure_ascii=False),
                1 if is_read else 0,
                1 if is_favorite else 0,
                created_at or now,
                word_count, reading_time, domain
            ))
            imported += 1

        except Exception as e:
            errors.append(f"文章导入失败: {str(e)}")

    conn.commit()
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "source": "wallabag"
    }


def import_from_bookmarks_html(
    conn: sqlite3.Connection,
    html_content: str,
    fetcher_func=None
) -> Dict:
    """
    从浏览器导出的书签 HTML 文件导入文章

    支持 Chrome、Firefox、Safari 等标准书签 HTML 格式

    Args:
        conn: 数据库连接
        html_content: 书签 HTML 内容
        fetcher_func: 文章抓取函数（可选）

    Returns:
        导入结果统计
    """
    soup = BeautifulSoup(html_content, "html.parser")
    links = soup.find_all("a")

    imported = 0
    skipped = 0
    errors = []

    for link in links:
        try:
            url = link.get("href", "").strip()
            if not url or not url.startswith(("http://", "https://")):
                continue

            existing = conn.execute(
                "SELECT id FROM articles WHERE url = ?", (url,)
            ).fetchone()
            if existing:
                skipped += 1
                continue

            title = link.get_text(strip=True) or "无标题"

            # 解析添加日期（Netscape 书签格式）
            add_date = link.get("add_date", "")
            created_at = _parse_timestamp(add_date)

            domain = urlparse(url).netloc

            # 尝试从父级 <DT><H3> 获取文件夹名作为标签
            tags = []
            parent_h3 = link.find_previous("h3")
            if parent_h3:
                folder_name = parent_h3.get_text(strip=True)
                if folder_name:
                    tags.append(folder_name)

            content = ""
            word_count = 0
            reading_time = 0

            if fetcher_func:
                try:
                    data = fetcher_func(url)
                    content = data.get("content", "")
                    title = data.get("title", title)
                    word_count = data.get("word_count", len(content))
                    reading_time = data.get("reading_time", max(1, word_count // 500))
                except Exception:
                    pass

            if not content:
                content = f"[待抓取] {title}"
                word_count = len(content)
                reading_time = 1

            excerpt = content[:200].replace("\n", " ").strip()
            if len(content) > 200:
                excerpt += "..."

            now = datetime.now().isoformat()
            conn.execute("""
                INSERT INTO articles
                (url, title, content, excerpt, tags, created_at,
                 word_count, reading_time, domain)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                url, title, content, excerpt,
                json.dumps(tags, ensure_ascii=False),
                created_at or now,
                word_count, reading_time, domain
            ))
            imported += 1

        except Exception as e:
            errors.append(f"书签导入失败: {str(e)}")

    conn.commit()
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "source": "bookmarks"
    }


def import_from_instapaper_csv(
    conn: sqlite3.Connection,
    csv_content: str,
    fetcher_func=None
) -> Dict:
    """
    从 Instapaper 导出的 CSV 文件导入文章

    Instapaper CSV 栗式:
    URL,Title,Selection,Folder,Time
    "https://example.com","文章标题","","Unread","1704067200"

    Args:
        conn: 数据库连接
        csv_content: CSV 文件内容
        fetcher_func: 文章抓取函数（可选）

    Returns:
        导入结果统计
    """
    reader = csv.DictReader(StringIO(csv_content))
    imported = 0
    skipped = 0
    errors = []

    for row in reader:
        try:
            url = row.get("URL", row.get("url", "")).strip()
            if not url:
                continue

            existing = conn.execute(
                "SELECT id FROM articles WHERE url = ?", (url,)
            ).fetchone()
            if existing:
                skipped += 1
                continue

            title = row.get("Title", row.get("title", "")).strip() or "无标题"
            folder = row.get("Folder", row.get("folder", "")).strip()
            tags = [folder] if folder and folder != "Unread" else []

            time_str = row.get("Time", row.get("time", "")).strip()
            created_at = _parse_timestamp(time_str)

            domain = urlparse(url).netloc

            content = ""
            word_count = 0
            reading_time = 0

            if fetcher_func:
                try:
                    data = fetcher_func(url)
                    content = data.get("content", "")
                    title = data.get("title", title)
                    word_count = data.get("word_count", len(content))
                    reading_time = data.get("reading_time", max(1, word_count // 500))
                except Exception:
                    pass

            if not content:
                content = f"[待抓取] {title}"
                word_count = len(content)
                reading_time = 1

            excerpt = content[:200].replace("\n", " ").strip()
            if len(content) > 200:
                excerpt += "..."

            is_read = 1 if folder == "Archive" else 0

            now = datetime.now().isoformat()
            conn.execute("""
                INSERT INTO articles
                (url, title, content, excerpt, tags, is_read, created_at,
                 word_count, reading_time, domain)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                url, title, content, excerpt,
                json.dumps(tags, ensure_ascii=False),
                is_read,
                created_at or now,
                word_count, reading_time, domain
            ))
            imported += 1

        except Exception as e:
            errors.append(f"Instapaper 导入失败: {str(e)}")

    conn.commit()
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "source": "instapaper"
    }


# ==================== 辅助函数 ====================

def _parse_timestamp(time_str: str) -> Optional[str]:
    """
    解析各种时间戳格式

    支持:
    - Unix 时间戳（秒）
    - ISO 8601 格式
    - 空字符串返回 None
    """
    if not time_str:
        return None

    try:
        # 尝试 Unix 时间戳
        timestamp = int(time_str)
        if timestamp > 1000000000000:  # 毫秒时间戳
            timestamp = timestamp // 1000
        return datetime.fromtimestamp(timestamp).isoformat()
    except (ValueError, OSError):
        pass

    try:
        # 尝试 ISO 格式
        # 处理各种 ISO 变体
        time_str = time_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(time_str)
        return dt.isoformat()
    except ValueError:
        pass

    return None


def _parse_iso_time(time_str: Optional[str]) -> Optional[str]:
    """解析 ISO 8601 时间字符串"""
    if not time_str:
        return None
    try:
        time_str = time_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(time_str)
        return dt.isoformat()
    except ValueError:
        return None
