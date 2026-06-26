"""
ReadLater - 手动导入工具
用于导入知乎等难以自动抓取的文章
"""
import json
import sqlite3
from datetime import datetime
import os

DB_PATH = os.environ.get("DB_PATH") or os.path.join(os.path.dirname(__file__), "readlater.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def import_article(url: str, title: str, content: str, images: list = None):
    """手动导入文章"""
    conn = get_db()
    
    # 检查是否已存在
    existing = conn.execute("SELECT id FROM articles WHERE url = ?", (url,)).fetchone()
    if existing:
        conn.close()
        print(f"文章已存在，ID: {existing['id']}")
        return existing['id']
    
    # 生成摘要
    excerpt = content[:200].replace('\n', ' ').strip()
    if len(content) > 200:
        excerpt += "..."
    
    # 计算字数和阅读时间
    word_count = len(content)
    reading_time = max(1, word_count // 500)
    
    # 插入文章
    now = datetime.now().isoformat()
    cursor = conn.execute("""
        INSERT INTO articles (url, title, content, excerpt, tags, created_at, word_count, reading_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (url, title, content, excerpt, '[]', now, word_count, reading_time))
    
    article_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    print(f"✅ 文章导入成功，ID: {article_id}")
    return article_id

def import_from_clipboard():
    """从剪贴板内容导入"""
    print("请粘贴文章内容（输入END结束）：")
    print("=" * 50)
    
    lines = []
    while True:
        line = input()
        if line == "END":
            break
        lines.append(line)
    
    content = '\n'.join(lines)
    
    url = input("\n请输入文章URL: ")
    title = input("请输入文章标题: ")
    
    article_id = import_article(url, title, content)
    return article_id

if __name__ == "__main__":
    print("ReadLater 手动导入工具")
    print("=" * 50)
    
    # 测试导入
    url = "https://zhuanlan.zhihu.com/p/2014806418478355736"
    title = "测试文章标题"
    content = """这是一篇测试文章的内容。

文章包含多个段落，
用于测试导入功能。

支持中文和英文混排。"""
    
    import_article(url, title, content)
