"""
ReadLater 数据导入模块
支持从 Pocket、Wallabag、浏览器书签、Instapaper 导入
"""
import io
import json
import sqlite3
import csv
from datetime import datetime
from typing import List, Optional, Dict, Any, Callable
from xml.etree import ElementTree as ET

# HTML 解析
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


def import_from_pocket_csv(conn: sqlite3.Connection, csv_content: str, 
                          fetcher_func: Optional[Callable] = None) -> Dict[str, Any]:
    """
    从 Pocket CSV 导入
    
    Pocket CSV 格式：title, url, time, tags
    
    Args:
        conn: 数据库连接
        csv_content: CSV 内容
        fetcher_func: 文章抓取函数，如果提供则抓取内容
    
    Returns:
        导入结果统计
    """
    reader = csv.reader(io.StringIO(csv_content))
    imported = 0
    skipped = 0
    errors = []
    
    # 跳过标题行（如果有）
    rows = list(reader)
    start_idx = 0
    if rows and rows[0] and 'url' in rows[0][0].lower():
        start_idx = 1
    
    for row in rows[start_idx:]:
        if len(row) < 2:
            continue
        
        try:
            title = row[0] if row[0] else "无标题"
            url = row[1]
            tags_str = row[3] if len(row) > 3 else ""
            
            # 检查是否已存在
            existing = conn.execute("SELECT id FROM articles WHERE url = ?", (url,)).fetchone()
            if existing:
                skipped += 1
                continue
            
            # 解析标签
            tags = [t.strip() for t in tags_str.split('|') if t.strip()] if tags_str else []
            
            # 抓取文章内容（如果提供了抓取函数）
            if fetcher_func:
                try:
                    data = fetcher_func(url, title)
                    content = data.get('content', '')
                    word_count = data.get('word_count', len(content))
                    reading_time = data.get('reading_time', max(1, word_count // 500))
                except Exception as e:
                    # 抓取失败，使用基本信息
                    content = f"[导入自 Pocket] 标题: {title}\nURL: {url}"
                    word_count = len(content)
                    reading_time = 1
            else:
                content = f"[导入自 Pocket] 标题: {title}\nURL: {url}"
                word_count = len(content)
                reading_time = 1
            
            # 生成摘要
            excerpt = content[:200].replace('\n', ' ').strip()
            if len(content) > 200:
                excerpt += "..."
            
            # 插入数据库
            now = datetime.now().isoformat()
            conn.execute("""
                INSERT INTO articles (url, title, content, excerpt, tags, created_at, word_count, reading_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (url, title, content, excerpt, json.dumps(tags, ensure_ascii=False), now, word_count, reading_time))
            
            imported += 1
        
        except Exception as e:
            errors.append(f"行 {rows.index(row) + 1}: {str(e)}")
    
    conn.commit()
    
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "total": imported + skipped + len(errors)
    }


def import_from_wallabag_json(conn: sqlite3.Connection, json_content: str,
                             fetcher_func: Optional[Callable] = None) -> Dict[str, Any]:
    """
    从 Wallabag JSON 导入
    
    Wallabag JSON 格式：{export: [{title, url, content, tags, is_archived, is_starred}]}
    
    Args:
        conn: 数据库连接
        json_content: JSON 内容
        fetcher_func: 文章抓取函数
    
    Returns:
        导入结果统计
    """
    try:
        data = json.loads(json_content)
    except json.JSONDecodeError as e:
        return {"imported": 0, "skipped": 0, "errors": [f"JSON 解析错误: {str(e)}"], "total": 0}
    
    # Wallabag 导出格式可能是数组或对象
    articles_data = data if isinstance(data, list) else data.get('export', [])
    
    imported = 0
    skipped = 0
    errors = []
    
    for i, item in enumerate(articles_data):
        try:
            url = item.get('url', '')
            title = item.get('title', '无标题')
            
            if not url:
                errors.append(f"项目 {i + 1}: 缺少 URL")
                continue
            
            # 检查是否已存在
            existing = conn.execute("SELECT id FROM articles WHERE url = ?", (url,)).fetchone()
            if existing:
                skipped += 1
                continue
            
            # 解析标签
            tags_data = item.get('tags', [])
            if isinstance(tags_data, list):
                tags = [t if isinstance(t, str) else t.get('label', '') for t in tags_data]
            else:
                tags = []
            
            # 获取内容
            content = item.get('content', '')
            is_archived = item.get('is_archived', False)
            is_starred = item.get('is_starred', False)
            
            # 如果没有内容，尝试抓取
            if not content and fetcher_func:
                try:
                    data = fetcher_func(url, title)
                    content = data.get('content', '')
                except Exception:
                    content = f"[导入自 Wallabag] 标题: {title}\nURL: {url}"
            
            if not content:
                content = f"[导入自 Wallabag] 标题: {title}\nURL: {url}"
            
            # 计算字数
            word_count = len(content)
            reading_time = max(1, word_count // 500)
            
            # 生成摘要
            excerpt = content[:200].replace('\n', ' ').strip()
            if len(content) > 200:
                excerpt += "..."
            
            # 插入数据库
            now = datetime.now().isoformat()
            conn.execute("""
                INSERT INTO articles (url, title, content, excerpt, tags, is_read, is_favorite, is_archived, created_at, word_count, reading_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                url, title, content, excerpt, 
                json.dumps(tags, ensure_ascii=False),
                1 if is_archived else 0,
                1 if is_starred else 0,
                1 if is_archived else 0,
                now, word_count, reading_time
            ))
            
            imported += 1
        
        except Exception as e:
            errors.append(f"项目 {i + 1}: {str(e)}")
    
    conn.commit()
    
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "total": imported + skipped + len(errors)
    }


def import_from_bookmarks_html(conn: sqlite3.Connection, html_content: str,
                              fetcher_func: Optional[Callable] = None) -> Dict[str, Any]:
    """
    从浏览器书签 HTML 导入（Netscape 格式）
    
    格式：<a href="..." add_date="...">title</a>
    
    Args:
        conn: 数据库连接
        html_content: HTML 内容
        fetcher_func: 文章抓取函数
    
    Returns:
        导入结果统计
    """
    if BeautifulSoup is None:
        return {"imported": 0, "skipped": 0, "errors": ["需要安装 beautifulsoup4"], "total": 0}
    
    soup = BeautifulSoup(html_content, 'lxml')
    links = soup.find_all('a')
    
    imported = 0
    skipped = 0
    errors = []
    
    for i, link in enumerate(links):
        try:
            url = link.get('href', '')
            title = link.get_text(strip=True) or '无标题'
            
            if not url or not url.startswith('http'):
                continue
            
            # 检查是否已存在
            existing = conn.execute("SELECT id FROM articles WHERE url = ?", (url,)).fetchone()
            if existing:
                skipped += 1
                continue
            
            # 从文件夹结构推断标签
            tags = []
            parent = link.parent
            while parent:
                if parent.name == 'dl':
                    prev = parent.find_previous_sibling()
                    if prev and prev.name == 'h3':
                        tags.append(prev.get_text(strip=True))
                parent = parent.parent
            
            # 抓取文章内容
            if fetcher_func:
                try:
                    data = fetcher_func(url, title)
                    content = data.get('content', '')
                    word_count = data.get('word_count', len(content))
                    reading_time = data.get('reading_time', max(1, word_count // 500))
                except Exception:
                    content = f"[导入自书签] 标题: {title}\nURL: {url}"
                    word_count = len(content)
                    reading_time = 1
            else:
                content = f"[导入自书签] 标题: {title}\nURL: {url}"
                word_count = len(content)
                reading_time = 1
            
            # 生成摘要
            excerpt = content[:200].replace('\n', ' ').strip()
            if len(content) > 200:
                excerpt += "..."
            
            # 插入数据库
            now = datetime.now().isoformat()
            conn.execute("""
                INSERT INTO articles (url, title, content, excerpt, tags, created_at, word_count, reading_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (url, title, content, excerpt, json.dumps(tags, ensure_ascii=False), now, word_count, reading_time))
            
            imported += 1
        
        except Exception as e:
            errors.append(f"链接 {i + 1}: {str(e)}")
    
    conn.commit()
    
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "total": imported + skipped + len(errors)
    }


def import_from_instapaper_csv(conn: sqlite3.Connection, csv_content: str,
                              fetcher_func: Optional[Callable] = None) -> Dict[str, Any]:
    """
    从 Instapaper CSV 导入
    
    Instapaper CSV 格式：URL, Title, Selection, Folder, Time
    
    Args:
        conn: 数据库连接
        csv_content: CSV 内容
        fetcher_func: 文章抓取函数
    
    Returns:
        导入结果统计
    """
    reader = csv.reader(io.StringIO(csv_content))
    imported = 0
    skipped = 0
    errors = []
    
    # 跳过标题行
    rows = list(reader)
    start_idx = 0
    if rows and rows[0] and 'url' in rows[0][0].lower():
        start_idx = 1
    
    for row in rows[start_idx:]:
        if len(row) < 2:
            continue
        
        try:
            url = row[0]
            title = row[1] if len(row) > 1 and row[1] else "无标题"
            folder = row[3] if len(row) > 3 else ""
            
            if not url or not url.startswith('http'):
                continue
            
            # 检查是否已存在
            existing = conn.execute("SELECT id FROM articles WHERE url = ?", (url,)).fetchone()
            if existing:
                skipped += 1
                continue
            
            # 使用文件夹作为标签
            tags = [folder] if folder else []
            
            # 抓取文章内容
            if fetcher_func:
                try:
                    data = fetcher_func(url, title)
                    content = data.get('content', '')
                    word_count = data.get('word_count', len(content))
                    reading_time = data.get('reading_time', max(1, word_count // 500))
                except Exception:
                    content = f"[导入自 Instapaper] 标题: {title}\nURL: {url}"
                    word_count = len(content)
                    reading_time = 1
            else:
                content = f"[导入自 Instapaper] 标题: {title}\nURL: {url}"
                word_count = len(content)
                reading_time = 1
            
            # 生成摘要
            excerpt = content[:200].replace('\n', ' ').strip()
            if len(content) > 200:
                excerpt += "..."
            
            # 插入数据库
            now = datetime.now().isoformat()
            conn.execute("""
                INSERT INTO articles (url, title, content, excerpt, tags, created_at, word_count, reading_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (url, title, content, excerpt, json.dumps(tags, ensure_ascii=False), now, word_count, reading_time))
            
            imported += 1
        
        except Exception as e:
            errors.append(f"行 {rows.index(row) + 1}: {str(e)}")
    
    conn.commit()
    
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "total": imported + skipped + len(errors)
    }


def detect_import_format(content: str) -> str:
    """
    自动检测导入格式
    
    Args:
        content: 导入内容
    
    Returns:
        格式类型：'pocket_csv', 'wallabag_json', 'bookmarks_html', 'instapaper_csv', 'unknown'
    """
    content_stripped = content.strip()
    
    # 检测 JSON
    if content_stripped.startswith('{') or content_stripped.startswith('['):
        try:
            data = json.loads(content_stripped)
            if isinstance(data, list) and data and 'url' in data[0]:
                return 'wallabag_json'
            elif isinstance(data, dict) and 'export' in data:
                return 'wallabag_json'
        except json.JSONDecodeError:
            pass
    
    # 检测 HTML 书签
    if '<!DOCTYPE NETSCAPE-Bookmark' in content or '<a href=' in content:
        return 'bookmarks_html'
    
    # 检测 CSV
    lines = content_stripped.split('\n')
    if lines:
        first_line = lines[0].lower()
        if 'url' in first_line and 'title' in first_line:
            return 'pocket_csv'
        elif 'url' in first_line and 'folder' in first_line:
            return 'instapaper_csv'
    
    # 尝试解析为 CSV
    try:
        reader = csv.reader(io.StringIO(content_stripped))
        rows = list(reader)
        if len(rows) > 1 and len(rows[0]) >= 2:
            # 检查第二列是否像 URL
            if rows[1][1].startswith('http'):
                return 'pocket_csv'
    except Exception:
        pass
    
    return 'unknown'