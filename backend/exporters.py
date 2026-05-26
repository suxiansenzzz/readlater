"""
ReadLater 多格式导出模块
支持 PDF、TXT、XML、EPUB、MOBI、CSV、HTML、JSON 格式
"""
import io
import json
import csv
import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any
from xml.etree import ElementTree as ET

# PDF 导出
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# EPUB 导出
try:
    import ebooklib
    from ebooklib import epub
except ImportError:
    epub = None

def export_to_pdf(conn: sqlite3.Connection, article_ids: Optional[List[int]] = None) -> bytes:
    """
    导出为 PDF 格式
    
    Args:
        conn: 数据库连接
        article_ids: 文章 ID 列表，None 表示全部文章
    
    Returns:
        PDF 文件的字节数据
    """
    if FPDF is None:
        raise ImportError("fpdf2 未安装，请运行: pip install fpdf2")
    
    # 获取文章
    articles = _get_articles(conn, article_ids)
    if not articles:
        raise ValueError("没有找到文章")
    
    # 创建 PDF
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # 添加中文字体
    font_added = _add_chinese_font(pdf)
    if not font_added:
        # 如果没有中文字体，使用默认字体（中文可能显示为方块）
        pdf.add_font('DejaVu', '', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', uni=True)
        pdf.set_font('DejaVu', size=12)
    else:
        pdf.set_font('Chinese', size=12)
    
    # 添加标题页
    pdf.add_page()
    pdf.set_font_size(24)
    pdf.cell(0, 20, 'ReadLater 导出', ln=True, align='C')
    pdf.set_font_size(12)
    pdf.cell(0, 10, f'导出时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}', ln=True, align='C')
    pdf.cell(0, 10, f'文章数量: {len(articles)}', ln=True, align='C')
    
    # 添加目录
    pdf.add_page()
    pdf.set_font_size(16)
    pdf.cell(0, 10, '目录', ln=True)
    pdf.set_font_size(10)
    for i, article in enumerate(articles, 1):
        title = article['title'][:50] + ('...' if len(article['title']) > 50 else '')
        pdf.cell(0, 8, f'{i}. {title}', ln=True)
    
    # 添加文章内容
    for article in articles:
        pdf.add_page()
        
        # 文章标题
        pdf.set_font_size(16)
        title = article['title']
        pdf.multi_cell(0, 10, title)
        pdf.ln(5)
        
        # 文章元信息
        pdf.set_font_size(10)
        meta = f"来源: {article['url']}\n保存时间: {article['created_at']}\n字数: {article['word_count']} | 阅读时间: {article['reading_time']} 分钟"
        pdf.multi_cell(0, 6, meta)
        pdf.ln(10)
        
        # 文章内容
        pdf.set_font_size(12)
        content = article['content']
        # 处理长行
        for line in content.split('\n'):
            if line.strip():
                pdf.multi_cell(0, 6, line)
                pdf.ln(2)
    
    # 返回字节数据（注意：fpdf2 的 output() 返回 bytearray）
    return bytes(pdf.output())


def export_to_txt(conn: sqlite3.Connection, article_ids: Optional[List[int]] = None) -> str:
    """
    导出为纯文本格式
    
    Args:
        conn: 数据库连接
        article_ids: 文章 ID 列表
    
    Returns:
        纯文本内容
    """
    articles = _get_articles(conn, article_ids)
    if not articles:
        raise ValueError("没有找到文章")
    
    lines = []
    lines.append("=" * 60)
    lines.append("ReadLater 导出")
    lines.append(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"文章数量: {len(articles)}")
    lines.append("=" * 60)
    lines.append("")
    
    for i, article in enumerate(articles, 1):
        lines.append(f"【{i}】{article['title']}")
        lines.append("-" * 40)
        lines.append(f"来源: {article['url']}")
        lines.append(f"保存时间: {article['created_at']}")
        lines.append(f"字数: {article['word_count']} | 阅读时间: {article['reading_time']} 分钟")
        lines.append("")
        lines.append(article['content'])
        lines.append("")
        lines.append("=" * 60)
        lines.append("")
    
    return '\n'.join(lines)


def export_to_xml(conn: sqlite3.Connection, article_ids: Optional[List[int]] = None) -> str:
    """
    导出为 XML 格式（OPML 风格）
    
    Args:
        conn: 数据库连接
        article_ids: 文章 ID 列表
    
    Returns:
        XML 字符串
    """
    articles = _get_articles(conn, article_ids)
    if not articles:
        raise ValueError("没有找到文章")
    
    # 创建根元素
    root = ET.Element('opml', version='2.0')
    
    # 头部
    head = ET.SubElement(root, 'head')
    ET.SubElement(head, 'title').text = 'ReadLater 导出'
    ET.SubElement(head, 'dateCreated').text = datetime.now().isoformat()
    ET.SubElement(head, 'docs').text = 'http://dev.opml.org/spec2.html'
    
    # 主体
    body = ET.SubElement(root, 'body')
    
    for article in articles:
        outline = ET.SubElement(body, 'outline', 
                              type='article',
                              text=article['title'],
                              title=article['title'],
                              url=article['url'],
                              created=article['created_at'],
                              wordCount=str(article['word_count']),
                              readingTime=str(article['reading_time']))
        
        # 添加内容（CDATA 包裹）
        content_elem = ET.SubElement(outline, 'content')
        content_elem.text = ET.CDATA(article['content'])
    
    # 生成 XML 字符串
    ET.indent(root, space='  ')
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode')


def export_to_epub(conn: sqlite3.Connection, article_ids: Optional[List[int]] = None) -> bytes:
    """
    导出为 EPUB 格式
    
    Args:
        conn: 数据库连接
        article_ids: 文章 ID 列表
    
    Returns:
        EPUB 文件的字节数据
    """
    if epub is None:
        raise ImportError("ebooklib 未安装，请运行: pip install ebooklib")
    
    articles = _get_articles(conn, article_ids)
    if not articles:
        raise ValueError("没有找到文章")
    
    # 创建 EPUB 书籍
    book = epub.EpubBook()
    book.set_identifier('readlater-export-' + datetime.now().strftime('%Y%m%d%H%M%S'))
    book.set_title('ReadLater 导出')
    book.set_language('zh-CN')
    
    # 添加作者
    book.add_author('ReadLater')
    
    # 添加 CSS 样式
    style = '''
    body { font-family: serif; line-height: 1.6; margin: 2em; }
    h1 { font-size: 1.8em; margin-bottom: 0.5em; }
    .meta { color: #666; font-size: 0.9em; margin-bottom: 1em; }
    .content { margin-top: 1em; }
    '''
    css = epub.EpubItem(uid='style', file_name='style/default.css', media_type='text/css', content=style)
    book.add_item(css)
    
    # 创建章节
    chapters = []
    toc = []
    
    for i, article in enumerate(articles, 1):
        # 创建章节
        chapter = epub.EpubHtml(title=article['title'], file_name=f'chapter_{i}.xhtml', lang='zh-CN')
        chapter.add_item(css)
        
        # 构建内容
        content = f'''
        <h1>{article['title']}</h1>
        <div class="meta">
            <p>来源: <a href="{article['url']}">{article['url']}</a></p>
            <p>保存时间: {article['created_at']}</p>
            <p>字数: {article['word_count']} | 阅读时间: {article['reading_time']} 分钟</p>
        </div>
        <div class="content">
            {article['content'].replace('\n', '<br/>')}
        </div>
        '''
        chapter.content = content
        
        book.add_item(chapter)
        chapters.append(chapter)
        toc.append(chapter)
    
    # 定义目录和顺序
    book.toc = toc
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ['nav'] + chapters
    
    # 生成 EPUB
    epub_buffer = io.BytesIO()
    epub.write_epub(epub_buffer, book, {})
    return epub_buffer.getvalue()


def export_to_csv(conn: sqlite3.Connection, article_ids: Optional[List[int]] = None) -> str:
    """
    导出为 CSV 格式
    
    Args:
        conn: 数据库连接
        article_ids: 文章 ID 列表
    
    Returns:
        CSV 字符串
    """
    articles = _get_articles(conn, article_ids)
    if not articles:
        raise ValueError("没有找到文章")
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 写入标题行
    writer.writerow(['ID', '标题', 'URL', '保存时间', '字数', '阅读时间', '已读', '收藏', '标签'])
    
    # 写入数据
    for article in articles:
        tags = ', '.join(article['tags']) if article['tags'] else ''
        writer.writerow([
            article['id'],
            article['title'],
            article['url'],
            article['created_at'],
            article['word_count'],
            article['reading_time'],
            '是' if article['is_read'] else '否',
            '是' if article['is_favorite'] else '否',
            tags
        ])
    
    return output.getvalue()


def export_to_html(conn: sqlite3.Connection, article_ids: Optional[List[int]] = None) -> str:
    """
    导出为 HTML 格式
    
    Args:
        conn: 数据库连接
        article_ids: 文章 ID 列表
    
    Returns:
        HTML 字符串
    """
    articles = _get_articles(conn, article_ids)
    if not articles:
        raise ValueError("没有找到文章")
    
    html_parts = []
    html_parts.append('''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ReadLater 导出</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; border-bottom: 2px solid #4f46e5; padding-bottom: 10px; }
        .meta { color: #666; font-size: 0.9em; margin-bottom: 1em; }
        .article { margin-bottom: 2em; padding-bottom: 2em; border-bottom: 1px solid #eee; }
        .article:last-child { border-bottom: none; }
        .article h2 { color: #1e293b; margin-bottom: 0.5em; }
        .article a { color: #4f46e5; text-decoration: none; }
        .article a:hover { text-decoration: underline; }
        .content { margin-top: 1em; white-space: pre-wrap; }
        .tags { margin-top: 0.5em; }
        .tag { display: inline-block; background: #e0e7ff; color: #4338ca; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; margin-right: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>ReadLater 导出</h1>
        <div class="meta">
            <p>导出时间: ''' + datetime.now().strftime("%Y-%m-%d %H:%M") + '''</p>
            <p>文章数量: ''' + str(len(articles)) + '''</p>
        </div>
''')
    
    for article in articles:
        tags_html = ''
        if article['tags']:
            tags_html = '<div class="tags">' + ''.join(f'<span class="tag">{tag}</span>' for tag in article['tags']) + '</div>'
        
        html_parts.append(f'''
        <div class="article">
            <h2>{article['title']}</h2>
            <div class="meta">
                <p>来源: <a href="{article['url']}" target="_blank">{article['url']}</a></p>
                <p>保存时间: {article['created_at']} | 字数: {article['word_count']} | 阅读时间: {article['reading_time']} 分钟</p>
                {tags_html}
            </div>
            <div class="content">{article['content'].replace('\n', '<br/>')}</div>
        </div>
''')
    
    html_parts.append('''
    </div>
</body>
</html>''')
    
    return '\n'.join(html_parts)


def export_to_json(conn: sqlite3.Connection, article_ids: Optional[List[int]] = None) -> str:
    """
    导出为 JSON 格式
    
    Args:
        conn: 数据库连接
        article_ids: 文章 ID 列表
    
    Returns:
        JSON 字符串
    """
    articles = _get_articles(conn, article_ids)
    if not articles:
        raise ValueError("没有找到文章")
    
    export_data = {
        'export_time': datetime.now().isoformat(),
        'article_count': len(articles),
        'articles': articles
    }
    
    return json.dumps(export_data, ensure_ascii=False, indent=2)


def _get_articles(conn: sqlite3.Connection, article_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    """获取文章列表"""
    if article_ids:
        placeholders = ','.join('?' * len(article_ids))
        query = f"SELECT * FROM articles WHERE id IN ({placeholders}) ORDER BY created_at DESC"
        rows = conn.execute(query, article_ids).fetchall()
    else:
        rows = conn.execute("SELECT * FROM articles ORDER BY created_at DESC").fetchall()
    
    articles = []
    for row in rows:
        articles.append({
            'id': row['id'],
            'url': row['url'],
            'title': row['title'],
            'content': row['content'],
            'excerpt': row['excerpt'],
            'tags': json.loads(row['tags']) if row['tags'] else [],
            'is_read': bool(row['is_read']),
            'is_favorite': bool(row['is_favorite']),
            'created_at': row['created_at'],
            'word_count': row['word_count'],
            'reading_time': row['reading_time']
        })
    
    return articles


def _add_chinese_font(pdf) -> bool:
    """添加中文字体到 PDF"""
    import os
    
    # 常见中文字体路径
    font_paths = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",  # macOS
        "C:/Windows/Fonts/simhei.ttf",  # Windows
    ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                pdf.add_font('Chinese', '', font_path, uni=True)
                return True
            except Exception as e:
                print(f"添加字体失败 {font_path}: {e}")
                continue
    
    return False