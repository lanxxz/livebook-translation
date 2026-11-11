# -*- coding: utf-8 -*-
"""前置页（封面 / 版权页 / 目录）专用构建器 —— 整页文字排版，不产生任何图片。

为什么要单独的构建器：前置页在原书里大量使用**矢量装饰元素**，
走通用图块流程必出事故：

  - 出版社 logo 是白色填充路径（fill=(1,1,1)），裁剪渲染成白底白图 → 页面一片空白
  - 简目左侧的竖排章号是图形，按原始像素宽度插入 → 横在页面上盖住章名
  - 目录页码照抄原书 → 与中文版实际页全错

用法一：作为库被别的脚本调用

    from build_front_pages import front_pages
    front_pages('out/00_封面与版权.docx', meta)

用法二：命令行（只读 book.json / docs.json 的通用字段）

    python build_front_pages.py [输出.docx] [--meta meta.json]

meta 结构（全部可选，缺省从 book.json 读）：

    {
      "book_title": "大语言模型如何工作",
      "en_title": "How Large Language Models Work",
      "authors": ["Edward Raff", "Drew Farris", "Stella Biderman"],
      "press": "MANNING", "press_sub": "SHELTER ISLAND",
      "copyright": ["段落1", "段落2", ...],     # 版权页各段，按顺序
      "toc_title": "内容提要",
      "toc": [["1", "全景图：大语言模型是什么", "9"], ...]   # 章号/标题/页
    }

toc 的页码可以直接给，也可以留空字符串 `""` —— 留空时从
`work/chapter_pages.json`（由 chapter_pages.py 生成）读实际页码。
"""
import json
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_LINE_SPACING
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


# ---------------- 配置 ----------------
def project_root():
    def _up(start):
        d = os.path.abspath(start)
        for _ in range(4):
            if (os.path.exists(os.path.join(d, 'book.json'))
                    or os.path.exists(os.path.join(d, 'docs.json'))):
                return d
            d = os.path.dirname(d)
        return None

    for start in (os.path.dirname(os.path.abspath(__file__)), os.getcwd()):
        hit = _up(start)
        if hit:
            return hit
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ROOT = project_root()


def cfg(key, default=None):
    """读 book.json 的键；没有就返回 default。"""
    p = os.path.join(ROOT, 'book.json')
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding='utf-8')).get(key, default)
        except Exception:
            pass
    return default


CN_BODY = cfg('cn_body', '宋体')
CN_HEAD = cfg('cn_head', '微软雅黑')
EN_BODY = cfg('en_body', 'Georgia')
EN_HEAD = cfg('en_head', 'Arial')
MARGIN_CM = float(cfg('margin_cm', 2.4))
TEXT_W_CM = 21.0 - MARGIN_CM * 2

NAVY = RGBColor(0x2E, 0x5C, 0x7A)          # 标题蓝（Manning 系列同款）
GOLD = RGBColor(0xD3, 0xA9, 0x08)          # 简目菱形金
GREY = RGBColor(0x59, 0x59, 0x59)
LIGHT = RGBColor(0x80, 0x80, 0x80)
DARK = RGBColor(0x22, 0x22, 0x22)


# ---------------- 基础排版函数 ----------------
def set_run(r, size=10.5, bold=False, italic=False, color=None,
            cn=None, en=None, spacing=None):
    """写字形。spacing 是字距，单位 1/20pt（w:spacing）。"""
    cn = cn or CN_BODY
    en = en or EN_BODY
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
    if spacing:
        sp = OxmlElement('w:spacing')
        sp.set(qn('w:val'), str(spacing))
        rPr.append(sp)
    return r


def pf(p, before=0, after=0, line=None, align=None,
       left_cm=0, right_cm=0, first_cm=0, keep=False, page_break=False):
    f = p.paragraph_format
    f.space_before = Pt(before)
    f.space_after = Pt(after)
    if line:
        f.line_spacing = Pt(line)
        f.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    if left_cm:
        f.left_indent = Cm(left_cm)
    if right_cm:
        f.right_indent = Cm(right_cm)
    if first_cm:
        f.first_line_indent = Cm(first_cm)
    if align is not None:
        p.alignment = align
    f.keep_with_next = keep
    if page_break:
        f.page_break_before = True
    return p


def hr(doc, color='2E5C7A', sz=8, before=0, after=0):
    """一条细分隔线（用段落下边框实现，比表格线干净）。"""
    p = doc.add_paragraph()
    pf(p, before=before, after=after, line=6)
    pPr = p._p.get_or_add_pPr()
    pbdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), str(sz))
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), color)
    pbdr.append(bottom)
    pPr.append(pbdr)


def blank(doc, n=1, line=14):
    """留白：固定行高的空段落，比 space_before 好控。"""
    for _ in range(n):
        pf(doc.add_paragraph(), line=line)


def add_header_footer(doc, title):
    sec = doc.sections[0]
    hp = sec.header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_run(hp.add_run(title), size=8, color=LIGHT, cn=CN_HEAD, en=EN_HEAD)
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fld = OxmlElement('w:fldSimple')
    fld.set(qn('w:instr'), 'PAGE')
    r = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')
    sz = OxmlElement('w:sz')
    sz.set(qn('w:val'), '18')
    rPr.append(sz)
    r.append(rPr)
    t = OxmlElement('w:t')
    t.text = '1'
    r.append(t)
    fld.append(r)
    fp._p.append(fld)


# ---------------- 三种页 ----------------
def cover(doc, meta):
    """封面：右对齐骨架（中文大标题 → 英文斜体副标题 → 分隔线 → 作者 → 出版社）。"""
    blank(doc, 5)
    p = pf(doc.add_paragraph(), after=4, line=42, align=WD_ALIGN_PARAGRAPH.RIGHT)
    set_run(p.add_run(meta.get('book_title') or '书名'),
            size=30, bold=True, color=NAVY, cn=CN_HEAD, en=EN_HEAD, spacing=4)
    if meta.get('en_title'):
        p = pf(doc.add_paragraph(), after=6, line=22, align=WD_ALIGN_PARAGRAPH.RIGHT)
        set_run(p.add_run(meta['en_title']), size=12, italic=True,
                color=LIGHT, cn=CN_HEAD, en=EN_HEAD)
    hr(doc, sz=6, before=10)

    blank(doc, 9)
    for name in meta.get('authors') or []:
        p = pf(doc.add_paragraph(), after=8, line=18, align=WD_ALIGN_PARAGRAPH.RIGHT)
        set_run(p.add_run(name), size=13, color=DARK, cn=CN_HEAD, en=EN_HEAD,
                spacing=12)

    blank(doc, 11)
    press = meta.get('press') or ''
    if press:
        p = pf(doc.add_paragraph(), after=3, line=18, align=WD_ALIGN_PARAGRAPH.RIGHT)
        set_run(p.add_run(press), size=14, color=DARK, cn=EN_HEAD, en=EN_HEAD,
                spacing=100)
    if meta.get('press_sub'):
        p = pf(doc.add_paragraph(), line=15, align=WD_ALIGN_PARAGRAPH.RIGHT)
        set_run(p.add_run(meta['press_sub']), size=9, color=RGBColor(0x44, 0x44, 0x44),
                cn=EN_HEAD, en=EN_HEAD, spacing=45)


def copyright_page(doc, meta):
    """版权页：按语义分块（联系信息 / 法律声明 / 出版信息），块间留白。"""
    paras = [x for x in (meta.get('copyright') or []) if str(x).strip()]
    if not paras:
        return
    # 用空字符串作为"分块符"：作者在 meta 里插入 "" 即可分组
    first = True
    prev_blank = True
    for txt in paras:
        if not str(txt).strip():
            prev_blank = True
            continue
        p = pf(doc.add_paragraph(),
               before=(0 if first else (14 if prev_blank else 4)),
               line=13.6, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
               page_break=first)
        set_run(p.add_run(str(txt)), size=8.6, color=RGBColor(0x33, 0x33, 0x33))
        first = False
        prev_blank = False


def toc_page(doc, meta, pages=None):
    """目录：多级混排（章 / 小节 / 子小节）+ 右对齐页码。

    toc 条目两种格式（向后兼容）：
      [num, title, page]        → level 0（章级：章号 + 金色方块 + 章名）
      [num, title, page, level] → level 1/2（小节/子小节：缩进，无方块）
    小节行的 title 含编号（如「1.1 LLM 规模化面临的挑战」），num 仅为核对用。
    """
    pages = pages or {}
    p = pf(doc.add_paragraph(), after=6, line=30, keep=True, page_break=True)
    set_run(p.add_run(meta.get('toc_title') or '目录'),
            size=24, bold=True, color=NAVY, cn=CN_HEAD, en=EN_HEAD, spacing=2)
    hr(doc, sz=8, before=2, after=12)

    first = True
    for item in meta.get('toc') or []:
        it = list(item) + ['', '', '', 0]
        num, title, page, level = it[0], it[1], it[2], int(it[3] or 0)
        # 页码留空 → 用 chapter_pages.json 的实际页
        if not page:
            key = ('ap%s' % num) if not str(num).isdigit() else ('ch%02d' % int(num))
            page = str(pages.get(key, ''))
        p = doc.add_paragraph()
        if level == 0:
            pf(p, before=(0 if first else 6), after=4, line=19, keep=True)
            p.paragraph_format.tab_stops.add_tab_stop(Cm(1.35), WD_TAB_ALIGNMENT.LEFT)
            p.paragraph_format.tab_stops.add_tab_stop(Cm(TEXT_W_CM), WD_TAB_ALIGNMENT.RIGHT)
            set_run(p.add_run(str(num)), size=11.5, italic=True, color=NAVY,
                    cn=CN_HEAD, en=EN_HEAD)
            set_run(p.add_run('\u2002\u25AA  '), size=11, color=GOLD,
                    cn=CN_HEAD, en=EN_HEAD)
            set_run(p.add_run(str(title)), size=11, color=DARK)
            set_run(p.add_run('\t'), size=11)
            set_run(p.add_run(str(page)), size=11, color=GREY, cn=CN_HEAD, en=EN_HEAD)
            first = False
        elif level == 1:
            pf(p, before=0, after=1.5, line=14.5, left_cm=1.25)
            p.paragraph_format.tab_stops.add_tab_stop(Cm(TEXT_W_CM), WD_TAB_ALIGNMENT.RIGHT)
            set_run(p.add_run(str(title)), size=10, color=RGBColor(0x2A, 0x2A, 0x2A))
            set_run(p.add_run('\t'), size=10)
            set_run(p.add_run(str(page)), size=9.5, color=GREY, cn=CN_HEAD, en=EN_HEAD)
        else:
            pf(p, before=0, after=1, line=12.5, left_cm=2.3)
            p.paragraph_format.tab_stops.add_tab_stop(Cm(TEXT_W_CM), WD_TAB_ALIGNMENT.RIGHT)
            set_run(p.add_run(str(title)), size=9, color=RGBColor(0x44, 0x44, 0x44))
            set_run(p.add_run('\t'), size=9)
            set_run(p.add_run(str(page)), size=9, color=LIGHT, cn=CN_HEAD, en=EN_HEAD)


# ---------------- 入口 ----------------
def load_pages():
    p = os.path.join(ROOT, 'work', 'chapter_pages.json')
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding='utf-8'))
        except Exception:
            pass
    return {}


def front_pages(out_path, meta=None):
    """生成三页前置页并保存。meta 缺省从 book.json 推断。"""
    meta = dict(meta or {})
    meta.setdefault('book_title', cfg('book_title', '书名'))
    meta.setdefault('toc_title', '目录')

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(MARGIN_CM)
    sec.top_margin = sec.bottom_margin = Cm(2.4)
    st = doc.styles['Normal']
    st.font.name = EN_BODY
    st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), CN_BODY)

    add_header_footer(doc, meta['book_title'])
    cover(doc, meta)
    copyright_page(doc, meta)
    toc_page(doc, meta, load_pages())

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or '.', exist_ok=True)
    doc.save(out_path)
    print('saved', out_path)
    return out_path


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    meta = {}
    for a in sys.argv[1:]:
        if a.startswith('--meta='):
            meta = json.load(open(a.split('=', 1)[1], encoding='utf-8'))
    out = args[0] if args else os.path.join(ROOT, 'out', '00_封面与版权.docx')
    front_pages(out, meta)


if __name__ == '__main__':
    main()
