# -*- coding: utf-8 -*-
"""生成封面 + 目录页（整页文字排版，不产生任何图片）。

用法：
    python tools/build_front.py                 # 生成 00_封面.docx / 00_目录.docx
    python tools/build_front.py --toc-only
"""
import json
import os
import re
import sys

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, WORK, load_docs  # noqa: E402

OUT = os.path.join(ROOT, 'out')
PDF = os.path.join(OUT, '分册_pdf')
CN_HEAD = '微软雅黑'
CN_BODY = '宋体'
EN = 'Georgia'
ACCENT = RGBColor(0x1F, 0x3A, 0x5F)
ACCENT2 = RGBColor(0x0E, 0x6B, 0x6B)
LIGHT = RGBColor(0x70, 0x70, 0x70)


def set_run(r, size=12, bold=False, color=None, cn=CN_HEAD, en=EN,
            italic=False):
    r.font.name = en
    r.font.size = Pt(size)
    r.bold = bold
    r.italic = italic
    if color is not None:
        r.font.color.rgb = color
    rPr = r._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:eastAsia'), cn)
    rFonts.set(qn('w:ascii'), en)
    rFonts.set(qn('w:hAnsi'), en)
    return r


def fmt(p, before=0, after=6, line=1.4, align=None):
    pf = p.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = line
    if align is not None:
        p.alignment = align
    return p


def blank(doc, n=1, size=12):
    for _ in range(n):
        p = doc.add_paragraph()
        fmt(p)
        set_run(p.add_run(' '), size=size)


def rule(doc, color='1F3A5F', sz=12, width_cm=None):
    p = doc.add_paragraph()
    fmt(p, before=6, after=6)
    pPr = p._p.get_or_add_pPr()
    pbdr = OxmlElement('w:pBdr')
    b = OxmlElement('w:bottom')
    b.set(qn('w:val'), 'single')
    b.set(qn('w:sz'), str(sz))
    b.set(qn('w:space'), '1')
    b.set(qn('w:color'), color)
    pbdr.append(b)
    pPr.append(pbdr)


def page_setup(doc):
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.6)
    sec.top_margin = Cm(2.6)
    sec.bottom_margin = Cm(2.6)
    st = doc.styles['Normal']
    st.font.name = EN
    st.font.size = Pt(11)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), CN_BODY)


def build_cover(path):
    doc = Document()
    page_setup(doc)
    # 行数必须压到一页内：多了会溢出到第 2 页，
    # 合订时目录就被顶到第 3 页，目录里的页码全部偏移（实测差 1 页）
    blank(doc, 3)
    p = doc.add_paragraph()
    fmt(p, after=3, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_run(p.add_run('VIBE ENGINEERING'), size=14, color=ACCENT2, cn=CN_HEAD)
    p = doc.add_paragraph()
    fmt(p, after=8, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_run(p.add_run('Best Practices, Mistakes, and Tradeoffs'), size=10.5,
            color=LIGHT, italic=True)
    rule(doc, color='1F3A5F', sz=10)
    blank(doc, 1)
    p = doc.add_paragraph()
    fmt(p, before=4, after=4, line=1.15, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_run(p.add_run('氛　围　工　程'), size=42, bold=True, color=ACCENT)
    p = doc.add_paragraph()
    fmt(p, after=4, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_run(p.add_run('最佳实践、错误与权衡'), size=17, color=ACCENT2)
    blank(doc, 1)
    rule(doc, color='D6DCE5', sz=6)
    blank(doc, 2)
    p = doc.add_paragraph()
    fmt(p, after=3, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_run(p.add_run('Tomasz Lelek　　Artur Skowroński　著'), size=12.5)
    p = doc.add_paragraph()
    fmt(p, after=3, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_run(p.add_run('Manning Publications'), size=10.5, color=LIGHT)
    blank(doc, 4)
    p = doc.add_paragraph()
    fmt(p, after=2, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_run(p.add_run('中　文　版'), size=11.5, color=ACCENT2, bold=True)
    doc.save(path)
    print('saved', path)


def chapter_titles():
    """从各章 trans.json 取章号与章名，并按输出顺序排列。"""
    rows = []
    for d in load_docs():
        tp = os.path.join(WORK, d['id'] + '_trans.json')
        num, title = d['num'], d['title']
        if os.path.exists(tp):
            blocks = json.load(open(tp, encoding='utf-8'))['blocks']
            for b in blocks:
                if b['type'] == 'chapter_open':
                    num = (b.get('num') or num).strip()
                    title = b.get('title') or title
                    break
        rows.append((num, title))
    return rows


def page_map():
    """各章 PDF 页数 → 目录页码（封面 1 页 + 目录页 n 页之后）。"""
    import pymupdf
    out = {}
    for f in sorted(os.listdir(PDF)):
        if not f.endswith('.pdf'):
            continue
        m = re.match(r'^(\d{2})_', f)
        if m:
            out[m.group(1)] = pymupdf.open(
                os.path.join(PDF, f)).page_count
    return out


def build_toc(path):
    rows = chapter_titles()
    pages = page_map()
    doc = Document()
    page_setup(doc)
    p = doc.add_paragraph()
    fmt(p, before=0, after=10)
    set_run(p.add_run('目　　录'), size=24, bold=True, color=ACCENT)
    rule(doc, color='1F3A5F', sz=10, )
    blank(doc, 1)

    # 目录里写的是**页脚页码**（合订 PDF 从正文第 1 页开始计 1）。
    # 封面 1 页 + 目录 1 页共 2 页前置，所以正文首页的页脚号是 1。
    cur = 1
    for num, title in rows:
        n = int(num) if num.isdigit() else 0
        cnt = pages.get('%02d' % n, 0) if n else pages.get('00', 0)
        p = doc.add_paragraph()
        fmt(p, before=8, after=2, line=1.35)
        p.paragraph_format.left_indent = Cm(0)
        label = ('第 %s 章　%s' % (num, title)) if num else title
        set_run(p.add_run(label), size=12.5, bold=True, color=ACCENT)
        r = p.add_run('　' + ('%d' % cur if cnt else ''))
        set_run(r, size=11, color=LIGHT)
        cur += max(cnt, 0)
    blank(doc, 2)
    p = doc.add_paragraph()
    fmt(p)
    set_run(p.add_run('说明：本译本按章分册交付；合订本页码见全书 PDF 页脚。'),
            size=9, color=LIGHT)
    doc.save(path)
    print('saved', path, '（目录页码基于各分册页数累加）')


def main():
    os.makedirs(OUT, exist_ok=True)
    build_cover(os.path.join(OUT, '00_封面.docx'))
    build_toc(os.path.join(OUT, '00_目录.docx'))


if __name__ == '__main__':
    main()
