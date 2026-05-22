"""
ReadLater v1.2.0 - 多格式导出模块
支持 PDF、TXT、XML、MOBI 格式的文章导出
"""

import os
import json
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from io import BytesIO
from typing import List, Dict, Optional
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

from fpdf import FPDF


class ChineseFPDF(FPDF):
    """
    支持中文的 PDF 生成器
    使用系统自带的中文字体
    """

    def __init__(self):
        super().__init__()
        # 尝试加载系统中文字体
        font_paths = [
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        ]

        self.has_chinese_font = False
        for font_path in font_paths:
            if os.path.exists(font_path):
                self.add_font("Chinese", "", font_path, uni=True)
                self.add_font("Chinese", "B", font_path, uni=True)
                self.has_chinese_font = True
                break

        if not self.has_chinese_font:
            # 没有中文字体，使用默认字体（中文可能显示为方块）
            # 但 PDF 结构仍然正常
            pass

    def get_font_name(self):
        """返回可用字体名"""
        return "Chinese" if self.has_chinese_font else "Helvetica"


def export_to_pdf(conn: sqlite3.Connection, article_ids: Optional[List[int]] = None) -> bytes:
    """
    将文章导出为 PDF 格式

    Args:
        conn: 数据库连接
        article_ids: 要导出的文章 ID 列表，None 表示全部导出

    Returns:
        PDF 文件的字节内容
    """
    # 查询文章
    if article_ids:
        placeholders = ",".join("?" * len(article_ids))
        rows = conn.execute(
            f"SELECT * FROM articles WHERE id IN ({placeholders}) ORDER BY created_at DESC",
            article_ids
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM articles ORDER BY created_at DESC"
        ).fetchall()

    # 创建 PDF
    pdf = ChineseFPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    font_name = pdf.get_font_name()

    for row in rows:
        pdf.add_page()

        # 标题
        pdf.set_font(font_name, "B", 18)
        title = row["title"] or "无标题"
        pdf.multi_cell(0, 10, title)

        # 元信息
        pdf.set_font(font_name, "", 9)
        pdf.set_text_color(128, 128, 128)
        meta_parts = []
        if row["domain"]:
            meta_parts.append(f"来源: {row['domain']}")
        meta_parts.append(f"字数: {row['word_count']}")
        meta_parts.append(f"阅读时间: {row['reading_time']}分钟")
        meta_parts.append(f"保存时间: {row['created_at'][:10]}")
        pdf.cell(0, 6, " | ".join(meta_parts), new_x="LMARGIN", new_y="NEXT")

        # 标签
        tags = json.loads(row["tags"])
        if tags:
            pdf.cell(0, 6, f"标签: {', '.join(tags)}", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(5)

        # 正文
        pdf.set_text_color(0, 0, 0)
        pdf.set_font(font_name, "", 11)
        content = row["content"] or ""
        # 简单处理：将内容按段落分割
        paragraphs = content.split("\n")
        for para in paragraphs:
            para = para.strip()
            if para:
                pdf.multi_cell(0, 6, para)
                pdf.ln(2)

    return pdf.output()


def export_to_txt(conn: sqlite3.Connection, article_ids: Optional[List[int]] = None) -> str:
    """
    将文章导出为纯文本格式

    Args:
        conn: 数据库连接
        article_ids: 要导出的文章 ID 列表

    Returns:
        纯文本内容
    """
    if article_ids:
        placeholders = ",".join("?" * len(article_ids))
        rows = conn.execute(
            f"SELECT * FROM articles WHERE id IN ({placeholders}) ORDER BY created_at DESC",
            article_ids
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM articles ORDER BY created_at DESC"
        ).fetchall()

    lines = []
    lines.append("=" * 60)
    lines.append("ReadLater 导出")
    lines.append(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"共 {len(rows)} 篇文章")
    lines.append("=" * 60)
    lines.append("")

    for i, row in enumerate(rows, 1):
        lines.append(f"{'─' * 60}")
        lines.append(f"[{i}] {row['title'] or '无标题'}")
        lines.append(f"{'─' * 60}")
        lines.append(f"URL: {row['url']}")

        tags = json.loads(row["tags"])
        if tags:
            lines.append(f"标签: {', '.join(tags)}")

        meta_parts = []
        if row["domain"]:
            meta_parts.append(f"来源: {row['domain']}")
        meta_parts.append(f"字数: {row['word_count']}")
        lines.append(" | ".join(meta_parts))
        lines.append("")

        # 正文
        lines.append(row["content"] or "")
        lines.append("")
        lines.append("")

    return "\n".join(lines)


def export_to_xml(conn: sqlite3.Connection, article_ids: Optional[List[int]] = None) -> str:
    """
    将文章导出为 XML 格式（OPML 风格）

    Args:
        conn: 数据库连接
        article_ids: 要导出的文章 ID 列表

    Returns:
        格式化的 XML 字符串
    """
    if article_ids:
        placeholders = ",".join("?" * len(article_ids))
        rows = conn.execute(
            f"SELECT * FROM articles WHERE id IN ({placeholders}) ORDER BY created_at DESC",
            article_ids
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM articles ORDER BY created_at DESC"
        ).fetchall()

    # 构建 XML 树
    root = Element("readlater-export")
    root.set("version", "1.2.0")
    root.set("exported-at", datetime.now().isoformat())
    root.set("article-count", str(len(rows)))

    articles_elem = SubElement(root, "articles")

    for row in rows:
        article_elem = SubElement(articles_elem, "article")
        article_elem.set("id", str(row["id"]))

        # 基本信息
        SubElement(article_elem, "title").text = row["title"] or "无标题"
        SubElement(article_elem, "url").text = row["url"]
        SubElement(article_elem, "domain").text = row["domain"] or ""
        SubElement(article_elem, "excerpt").text = row["excerpt"] or ""
        SubElement(article_elem, "content").text = row["content"] or ""

        # 状态
        status_elem = SubElement(article_elem, "status")
        status_elem.set("is-read", str(row["is_read"]).lower())
        status_elem.set("is-favorite", str(row["is_favorite"]).lower())
        status_elem.set("is-archived", str(row["is_archived"]).lower())

        # 标签
        tags_elem = SubElement(article_elem, "tags")
        for tag in json.loads(row["tags"]):
            tag_elem = SubElement(tags_elem, "tag")
            tag_elem.text = tag

        # 统计
        stats_elem = SubElement(article_elem, "stats")
        stats_elem.set("word-count", str(row["word_count"]))
        stats_elem.set("reading-time", str(row["reading_time"]))

        # 时间
        SubElement(article_elem, "created-at").text = row["created_at"]
        if row["updated_at"]:
            SubElement(article_elem, "updated-at").text = row["updated_at"]

    # 格式化输出
    raw_xml = tostring(root, encoding="unicode")
    return parseString(raw_xml).toprettyxml(indent="  ")


def export_to_mobi(conn: sqlite3.Connection, article_ids: Optional[List[int]] = None) -> bytes:
    """
    将文章导出为 MOBI 格式（通过 EPUB 转换）

    实际上生成 EPUB 文件（MOBI 需要额外工具转换，EPUB 可直接在 Kindle 等设备上使用）

    Args:
        conn: 数据库连接
        article_ids: 要导出的文章 ID 列体

    Returns:
        EPUB 文件的字节内容
    """
    from ebooklib import epub

    if article_ids:
        placeholders = ",".join("?" * len(article_ids))
        rows = conn.execute(
            f"SELECT * FROM articles WHERE id IN ({placeholders}) ORDER BY created_at DESC",
            article_ids
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM articles ORDER BY created_at DESC"
        ).fetchall()

    # 创建 EPUB 书籍
    book = epub.EpubBook()
    book.set_identifier(f"readlater-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    book.set_title("ReadLater 导出")
    book.set_language("zh-CN")
    book.add_author("ReadLater")

    # 添加样式
    style = epub.EpubItem(
        uid="style",
        file_name="style/default.css",
        media_type="text/css",
        content=b"""
        body { font-family: serif; line-height: 1.8; margin: 1em; }
        h1 { color: #333; border-bottom: 2px solid #4f46e5; padding-bottom: 0.5em; }
        .meta { color: #666; font-size: 0.9em; margin-bottom: 1em; }
        .tag { background: #f0f0f0; padding: 2px 8px; border-radius: 10px; font-size: 0.8em; }
        p { text-indent: 2em; margin: 0.5em 0; }
        """
    )
    book.add_item(style)

    # 创建目录页
    toc_content = "<html><body><h1>目录</h1><ul>"
    chapters = []

    for i, row in enumerate(rows):
        # 每篇文章一个章节
        chapter = epub.EpubHtml(
            title=row["title"] or f"文章 {i + 1}",
            file_name=f"chapter_{i + 1}.xhtml",
            lang="zh-CN"
        )
        chapter.add_item(style)

        # 构建章节内容
        tags = json.loads(row["tags"])
        tags_html = " ".join([f'<span class="tag">{t}</span>' for t in tags])

        content_html = f"""
        <html><body>
        <h1>{row['title'] or '无标题'}</h1>
        <div class="meta">
            {row['domain'] or ''} | {row['word_count']}字 | {row['reading_time']}分钟
            {'<br>标签: ' + tags_html if tags else ''}
        </div>
        <hr>
        """

        # 将纯文本转为段落
        for para in (row["content"] or "").split("\n"):
            para = para.strip()
            if para:
                content_html += f"<p>{para}</p>\n"

        content_html += "</body></html>"
        chapter.content = content_html.encode("utf-8")

        book.add_item(chapter)
        chapters.append(chapter)
        toc_content += f'<li><a href="chapter_{i + 1}.xhtml">{row["title"] or f"文章 {i + 1}"}</a></li>'

    toc_content += "</ul></body></html>"

    # 目录页
    intro = epub.EpubHtml(title="目录", file_name="intro.xhtml")
    intro.add_item(style)
    intro.content = toc_content.encode("utf-8")
    book.add_item(intro)

    # 设置目录和 spine
    book.toc = [intro] + chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", intro] + chapters

    # 生成 EPUB
    epub_bytes = BytesIO()
    epub.write_epub(epub_bytes, book)
    return epub_bytes.getvalue()
