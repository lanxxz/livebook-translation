# -*- coding: utf-8 -*-
"""把 <doc>_trans.json 渲染成中文技术书 Word 文档。

支持本书全部块类型：chapter_open / heading / para / list / numlist /
code / figure / table / dialog / callout / sidebar / equation / quote
（dialog、callout、sidebar 内部可再嵌套任意上述块）。
"""
import json
import os
import re
import sys

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, WORK, load_json  # noqa: E402

CN_BODY = '宋体'
CN_HEAD = '微软雅黑'
CN_HAND = '楷体'
EN_BODY = 'Times New Roman'
EN_HEAD = 'Segoe UI'
BODY_PT = 10.5
PAGE_W_CM = 21.0
MARGIN_CM = 2.4
TEXT_W_CM = PAGE_W_CM - MARGIN_CM * 2
ACCENT = RGBColor(0x1F, 0x3A, 0x5F)
ACCENT2 = RGBColor(0x0E, 0x6B, 0x6B)
GREY = RGBColor(0x4A, 0x4A, 0x4A)
LIGHT = RGBColor(0x80, 0x80, 0x80)
NBSP = '\u00a0'


def set_run(r, size=BODY_PT, bold=False, color=None, cn=CN_BODY, en=EN_BODY,
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


def para_fmt(p, before=0, after=6, line=1.5, indent=0, align=None, keep=False,
             left=0.0):
    pf = p.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = line
    if indent:
        pf.first_line_indent = Pt(BODY_PT * indent)
    if left:
        pf.left_indent = Cm(left)
    if align is not None:
        p.alignment = align
    pf.keep_with_next = keep
    return p


def add_rich(p, text, size=BODY_PT, color=None, cn=CN_BODY, en=EN_BODY,
             bold=False):
    """支持 **粗体**、*斜体*、`行内代码`。"""
    text = strip_emoji(text) if text else text
    toks = re.split(r'(\*\*.+?\*\*|`[^`]+`|\*[^*\s][^*]*\*)', text)
    for seg in toks:
        if not seg:
            continue
        if seg.startswith('**') and seg.endswith('**') and len(seg) > 4:
            r = p.add_run(seg[2:-2])
            set_run(r, size=size, bold=True, color=color, cn=cn, en=en)
        elif seg.startswith('`') and seg.endswith('`') and len(seg) > 2:
            r = p.add_run(seg[1:-1])
            set_run(r, size=size - 0.4, color=color, cn='Consolas',
                    en='Consolas')
        elif seg.startswith('*') and seg.endswith('*') and len(seg) > 2 \
                and not seg.startswith('**'):
            r = p.add_run(seg[1:-1])
            set_run(r, size=size, italic=True, color=color, cn=CN_HAND, en=en)
        else:
            r = p.add_run(seg)
            set_run(r, size=size, bold=bold, color=color, cn=cn, en=en)
    return p


def rule(doc, color='1F3A5F', size=10, after=10):
    p = doc.add_paragraph()
    para_fmt(p, before=0, after=after, line=1.0)
    pPr = p._p.get_or_add_pPr()
    pbdr = OxmlElement('w:pBdr')
    b = OxmlElement('w:bottom')
    b.set(qn('w:val'), 'single')
    b.set(qn('w:sz'), str(size))
    b.set(qn('w:space'), '1')
    b.set(qn('w:color'), color)
    pbdr.append(b)
    pPr.append(pbdr)


def shade_par(p, fill):
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill)
    pPr.append(shd)


def _bdr(p, edges=('left',), color='0E6B6B', sz=18, space=8):
    pPr = p._p.get_or_add_pPr()
    pbdr = OxmlElement('w:pBdr')
    for e in edges:
        el = OxmlElement('w:' + e)
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), str(sz))
        el.set(qn('w:space'), str(space))
        el.set(qn('w:color'), color)
        pbdr.append(el)
    pPr.append(pbdr)


def shade_cell(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill)
    tcPr.append(shd)


def cell_margins(cell, top=60, bottom=60, left=100, right=100):
    tcPr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement('w:tcMar')
    for k, v in (('top', top), ('left', left), ('bottom', bottom),
                 ('right', right)):
        el = OxmlElement('w:' + k)
        el.set(qn('w:w'), str(v))
        el.set(qn('w:type'), 'dxa')
        mar.append(el)
    tcPr.append(mar)


def _row_flag(row, tag):
    trPr = row._tr.get_or_add_trPr()
    if trPr.find(qn(tag)) is None:
        el = OxmlElement(tag)
        el.set(qn('w:val'), 'true')
        trPr.append(el)


def keep_row(row):
    _row_flag(row, 'w:cantSplit')


def repeat_header(row):
    _row_flag(row, 'w:tblHeader')


def keep_indent(line):
    n = len(line) - len(line.lstrip(' '))
    if n <= 0:
        return line
    return NBSP * n + line[n:]


def add_header_footer(doc, book_title, ch_label):
    sec = doc.sections[0]
    hp = sec.header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = hp.add_run('%s　|　%s' % (book_title, ch_label) if ch_label
                   else book_title)
    set_run(r, size=8.5, color=LIGHT, cn=CN_HEAD, en=EN_HEAD)
    pPr = hp._p.get_or_add_pPr()
    pbdr = OxmlElement('w:pBdr')
    b = OxmlElement('w:bottom')
    b.set(qn('w:val'), 'single')
    b.set(qn('w:sz'), '4')
    b.set(qn('w:space'), '1')
    b.set(qn('w:color'), 'CCCCCC')
    pbdr.append(b)
    pPr.append(pbdr)
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run()
    set_run(r, size=9, color=LIGHT)
    fld = OxmlElement('w:fldSimple')
    fld.set(qn('w:instr'), 'PAGE')
    r._element.addnext(fld)


# ---------------------------------------------------------------- 渲染
class Renderer:
    def __init__(self, doc, figdir):
        self.doc = doc
        self.figdir = figdir
        self.zhdir = figdir
        self.zh_kind = {}
        self.missing_fig = []
        self.used_fig = []
        self.used_zh = []

    # ---- 基础块 ----
    def heading(self, text, level):
        sizes = {2: 15.5, 3: 12.5, 4: 11, 5: 10.5}
        colors = {2: ACCENT, 3: RGBColor(0x2B, 0x2B, 0x2B),
                  4: RGBColor(0x40, 0x40, 0x40), 5: RGBColor(0x50, 0x50, 0x50)}
        before = {2: 18, 3: 13, 4: 10, 5: 8}[level]
        after = {2: 8, 3: 6, 4: 5, 5: 4}[level]
        p = self.doc.add_paragraph()
        para_fmt(p, before=before, after=after, line=1.25, keep=True)
        if level in (2, 3):
            p.style = self.doc.styles['Heading %d' % min(level, 3)]
        r = p.add_run(text)
        set_run(r, size=sizes[level], bold=True, color=colors[level],
                cn=CN_HEAD, en=EN_HEAD)
        if level == 2:
            rule(self.doc, color='D6DCE5', size=6, after=6)

    def para(self, text, indent=2, size=BODY_PT, left=0.0):
        # 顶层段落里也可能出现「🔹 xxx」这类原书分层标记，同样提为小标题
        if EMOJI.match(text.strip()) and len(text) <= 90:
            p = self.doc.add_paragraph()
            para_fmt(p, before=8, after=3, line=1.3, keep=True)
            r = p.add_run(strip_emoji(text))
            set_run(r, size=10.5, bold=True, color=ACCENT2,
                    cn=CN_HEAD, en=EN_HEAD)
            return
        p = self.doc.add_paragraph()
        para_fmt(p, before=0, after=8, line=1.6, indent=indent, left=left)
        add_rich(p, text, size=size)

    def bullets(self, items, ordered=False):
        for n, it in enumerate(items, 1):
            p = self.doc.add_paragraph()
            para_fmt(p, before=0, after=3, line=1.45, left=0.85)
            p.paragraph_format.first_line_indent = Cm(-0.52)
            mark = ('%d. ' % n) if ordered else '· '
            r = p.add_run(mark)
            set_run(r, size=BODY_PT, bold=ordered, color=ACCENT2)
            add_rich(p, strip_leading_num(it) if ordered else it)

    def code(self, text, caption='', notes=None, small=False):
        if caption:
            p = self.doc.add_paragraph()
            para_fmt(p, before=6, after=2, line=1.25, keep=True)
            r = p.add_run(caption)
            set_run(r, size=9.5, bold=True, color=ACCENT2, cn=CN_HEAD,
                    en=EN_HEAD)
        p = self.doc.add_paragraph()
        para_fmt(p, before=4 if not caption else 0,
                 after=6 if not notes else 3, line=1.12, left=0.15)
        shade_par(p, 'F4F5F7')
        _bdr(p, edges=('left',), color='C9CED6', sz=12, space=6)
        size = 8.2 if small else 8.8
        lines = text.split('\n')
        for i, line in enumerate(lines):
            r = p.add_run(keep_indent(line) if line else ' ')
            set_run(r, size=size, cn='Consolas', en='Consolas')
            if i < len(lines) - 1:
                r.add_break()
        if notes:
            for k, v in notes:
                p = self.doc.add_paragraph()
                para_fmt(p, before=0, after=1, line=1.35, left=0.85)
                p.paragraph_format.first_line_indent = Cm(-0.55)
                r = p.add_run(k + ' ')
                set_run(r, size=9, bold=True, color=ACCENT2, cn='Consolas',
                        en='Consolas')
                add_rich(p, v, size=9)
            p = self.doc.add_paragraph()
            para_fmt(p, before=0, after=4, line=1.0)

    def figure(self, key, caption):
        """示意图优先用 figs_zh 的中文化版本；截图/统计图用原图。"""
        path = os.path.join(self.figdir, key + '.png')
        zhp = os.path.join(self.zhdir, key + '.png')
        if self.zh_kind.get(key) == 'diagram' and os.path.exists(zhp):
            path = zhp
            self.used_zh.append(key)
        if not os.path.exists(path):
            self.missing_fig.append(key)
            p = self.doc.add_paragraph()
            para_fmt(p, before=6, after=6, line=1.2,
                     align=WD_ALIGN_PARAGRAPH.CENTER)
            r = p.add_run('［图缺失 %s］' % key)
            set_run(r, size=9, color=LIGHT)
            return
        self.used_fig.append(key)
        with Image.open(path) as im:
            iw, ih = im.size
        w_cm = TEXT_W_CM
        dpi_cap = 260.0
        w_max = iw * 2.54 / dpi_cap
        w_cm = min(w_cm, w_max)
        w_cm = max(6.0, w_cm)
        max_h = 18.5
        if iw > 0 and w_cm * ih / iw > max_h:
            w_cm = max_h * iw / ih
        p = self.doc.add_paragraph()
        para_fmt(p, before=8, after=2, line=1.0,
                 align=WD_ALIGN_PARAGRAPH.CENTER, keep=True)
        p.add_run().add_picture(path, width=Cm(w_cm))
        if caption:
            p = self.doc.add_paragraph()
            para_fmt(p, before=0, after=10, line=1.4,
                     align=WD_ALIGN_PARAGRAPH.CENTER)
            add_rich(p, caption, size=9)

    def table(self, head, rows, caption=''):
        if caption:
            p = self.doc.add_paragraph()
            para_fmt(p, before=8, after=3, line=1.3, keep=True,
                     align=WD_ALIGN_PARAGRAPH.CENTER)
            r = p.add_run(caption)
            set_run(r, size=9.5, bold=True, color=ACCENT2, cn=CN_HEAD,
                    en=EN_HEAD)
        ncol = max(len(head), max((len(r) for r in rows), default=0))
        tb = self.doc.add_table(rows=1 + len(rows), cols=ncol)
        tb.style = 'Table Grid'
        tb.alignment = WD_TABLE_ALIGNMENT.CENTER
        tb.autofit = True
        for j in range(ncol):
            c = tb.cell(0, j)
            c.text = ''
            p = c.paragraphs[0]
            para_fmt(p, before=2, after=2, line=1.2,
                     align=WD_ALIGN_PARAGRAPH.CENTER)
            add_rich(p, head[j] if j < len(head) else '', size=9, bold=True,
                     color=ACCENT, cn=CN_HEAD, en=EN_HEAD)
            shade_cell(c, 'E8EEF4')
            cell_margins(c)
        keep_row(tb.rows[0])
        repeat_header(tb.rows[0])
        for i, row in enumerate(rows, 1):
            keep_row(tb.rows[i])
            for j in range(ncol):
                c = tb.cell(i, j)
                c.text = ''
                p = c.paragraphs[0]
                para_fmt(p, before=2, after=2, line=1.28)
                add_rich(p, row[j] if j < len(row) else '', size=8.8)
                cell_margins(c)
        p = self.doc.add_paragraph()
        para_fmt(p, before=0, after=6, line=1.0)

    def equation(self, text):
        p = self.doc.add_paragraph()
        para_fmt(p, before=6, after=6, line=1.4,
                 align=WD_ALIGN_PARAGRAPH.CENTER)
        r = p.add_run(text)
        set_run(r, size=10.5, italic=True, color=RGBColor(0x20, 0x20, 0x20),
                cn=CN_BODY, en='Cambria Math')

    def quote(self, text):
        p = self.doc.add_paragraph()
        para_fmt(p, before=10, after=4, line=1.5, left=0.9)
        _bdr(p, edges=('left',), color='9AA7B8', sz=18, space=10)
        add_rich(p, text, size=10, color=GREY)
        p = self.doc.add_paragraph()
        para_fmt(p, before=0, after=8, line=1.0)

    # ---- 容器块 ----
    def dialog(self, b, kind):
        head = self.doc.add_paragraph()
        para_fmt(head, before=10, after=3, line=1.2, keep=True)
        _bdr(head, edges=('left',), color='0E6B6B' if kind == 'prompt'
            else '1F3A5F', sz=24, space=8)
        shade_par(head, 'EAF3F3' if kind == 'prompt' else 'EDF1F6')
        lbl = '提示词' if kind == 'prompt' else '模型响应'
        spk = (b.get('speaker') or '').strip()
        if spk and spk not in (lbl, 'AI Prompt Begin', '响应'):
            lbl = '%s · %s' % (lbl, spk)
        r = head.add_run(lbl.upper() if False else lbl)
        set_run(r, size=9, bold=True,
                color=ACCENT2 if kind == 'prompt' else ACCENT,
                cn=CN_HEAD, en=EN_HEAD)
        self.parts(b.get('parts') or [], boxed=True, box_kind=kind)

    def parts(self, parts, boxed=False, box_kind='prompt'):
        for sub in parts:
            t = sub['type']
            if boxed:
                self._boxed_part(sub, box_kind)
            else:
                self.block(sub)

    def _boxed_part(self, sub, kind):
        t = sub['type']
        left = 0.45
        if t == 'para':
            txt = sub['text']
            # 原书用 emoji 当分层标记（🧪 一级、📁/📈 二级）。
            # 直接删掉会让层级坍塌成一堆同级段落，所以带 emoji 的短行提为小标题。
            if EMOJI.match(txt.strip()) and len(txt) <= 90:
                lvl2 = any(e in txt[:2] for e in '📁📈📥👉⚙️✅⚠️📌👉')
                p = self.doc.add_paragraph()
                para_fmt(p, before=6 if not lvl2 else 4,
                         after=2, line=1.3, left=left, keep=True)
                r = p.add_run(strip_emoji(txt))
                set_run(r, size=9.5 if not lvl2 else 9,
                        bold=True,
                        color=ACCENT2 if not lvl2 else GREY,
                        cn=CN_HEAD, en=EN_HEAD)
                return
            p = self.doc.add_paragraph()
            para_fmt(p, before=0, after=5, line=1.55, indent=0, left=left)
            _bdr(p, edges=('left',), color='0E6B6B' if kind == 'prompt'
                else '1F3A5F', sz=12, space=8)
            add_rich(p, txt, size=9.8)
        elif t in ('list', 'numlist'):
            for n, it in enumerate(sub['items'], 1):
                p = self.doc.add_paragraph()
                para_fmt(p, before=0, after=3, line=1.5, left=left + 0.45)
                p.paragraph_format.first_line_indent = Cm(-0.45)
                _bdr(p, edges=('left',), color='B9C4D2', sz=8, space=8)
                r = p.add_run(('%d. ' % n) if t == 'numlist' else '· ')
                set_run(r, size=9.5, color=ACCENT2)
                add_rich(p, it, size=9.5)
        elif t == 'code':
            self.code(sub['text'], sub.get('caption', ''),
                      sub.get('notes'), small=True)
        elif t == 'table':
            self.table(sub['grid']['data'][0], sub['grid']['data'][1:],
                       sub.get('caption', ''))
        elif t == 'heading':
            self.heading(sub['text'], sub.get('level', 4))
        elif t == 'figure':
            self.figure(sub['img'], sub.get('caption', ''))
        else:
            self.para(sub.get('text', ''), indent=0, left=left)

    def callout(self, b):
        label = (b.get('label') or 'NOTE').strip()
        cn_label = {'NOTE': '注意', 'TIP': '提示', 'WARNING': '警告',
                    'DEFINITION': '定义', 'IMPORTANT': '重要'}.get(
                        label.upper(), label)
        p = self.doc.add_paragraph()
        para_fmt(p, before=10, after=3, line=1.2, keep=True)
        shade_par(p, 'FBF3E6')
        _bdr(p, edges=('left',), color='C08A2E', sz=24, space=8)
        r = p.add_run(cn_label)
        set_run(r, size=9, bold=True, color=RGBColor(0x8A, 0x5D, 0x10),
                cn=CN_HEAD, en=EN_HEAD)
        for sub in b.get('parts') or []:
            if sub['type'] == 'para':
                p = self.doc.add_paragraph()
                para_fmt(p, before=0, after=4, line=1.55, left=0.45)
                shade_par(p, 'FDF9F2')
                _bdr(p, edges=('left',), color='C08A2E', sz=12, space=8)
                add_rich(p, sub['text'], size=9.8)
            else:
                self.block(sub)
        p = self.doc.add_paragraph()
        para_fmt(p, before=0, after=6, line=1.0)

    def sidebar(self, b):
        title = (b.get('title') or '').strip()
        cn_t = translate_head(title)
        p = self.doc.add_paragraph()
        para_fmt(p, before=10, after=3, line=1.25, keep=True)
        shade_par(p, 'EEF2F6')
        _bdr(p, edges=('top', 'left', 'right'), color='8899AA', sz=6, space=6)
        r = p.add_run(cn_t or '侧栏')
        set_run(r, size=9.5, bold=True, color=ACCENT, cn=CN_HEAD, en=EN_HEAD)
        for sub in b.get('parts') or []:
            if sub['type'] == 'para':
                p = self.doc.add_paragraph()
                para_fmt(p, before=0, after=4, line=1.5, left=0.4)
                shade_par(p, 'F5F8FA')
                _bdr(p, edges=('left', 'right'), color='8899AA', sz=6,
                     space=6)
                add_rich(p, sub['text'], size=9.5)
            else:
                self.block(sub)
        p = self.doc.add_paragraph()
        para_fmt(p, before=0, after=6, line=1.0)

    # ---- 分发 ----
    def block(self, b):
        t = b['type']
        if t == 'chapter_open':
            self.chapter_open(b)
        elif t == 'heading':
            self.heading(b['text'], b.get('level', 3))
        elif t == 'para':
            self.para(b['text'])
        elif t == 'list':
            self.bullets(b['items'], ordered=False)
        elif t == 'numlist':
            self.bullets(b['items'], ordered=True)
        elif t == 'code':
            self.code(b['text'], b.get('caption', ''), b.get('notes'))
        elif t == 'figure':
            self.figure(b['key'], b.get('caption', ''))
        elif t == 'table':
            g = b['grid']['data']
            self.table(g[0], g[1:], b.get('caption', ''))
        elif t == 'dialog':
            self.dialog(b, b.get('kind', 'response'))
        elif t == 'callout':
            self.callout(b)
        elif t == 'sidebar':
            self.sidebar(b)
        elif t == 'equation':
            self.equation(b['text'])
        elif t == 'quote':
            self.quote(b['text'])
        else:
            print('!! 未知块类型', t)

    def chapter_open(self, b):
        num = (b.get('num') or '').strip()
        if num.isdigit():
            p = self.doc.add_paragraph()
            para_fmt(p, before=0, after=2, line=1.0)
            r = p.add_run('第 %s 章' % num)
            set_run(r, size=10.5, bold=True, color=ACCENT2, cn=CN_HEAD,
                    en=EN_HEAD)
        p = self.doc.add_paragraph()
        para_fmt(p, before=0, after=4, line=1.2)
        r = p.add_run(b['title'])
        set_run(r, size=24, bold=True, color=ACCENT, cn=CN_HEAD, en=EN_HEAD)
        if b.get('intro'):
            rule(self.doc, color='1F3A5F', size=10, after=10)
        if b.get('toc_items'):
            p = self.doc.add_paragraph()
            para_fmt(p, before=4, after=4, line=1.3, keep=True)
            r = p.add_run('本章内容')
            set_run(r, size=10.5, bold=True, color=ACCENT2, cn=CN_HEAD,
                    en=EN_HEAD)
            for it in b['toc_items']:
                p = self.doc.add_paragraph()
                para_fmt(p, before=0, after=3, line=1.5, left=0.85)
                p.paragraph_format.first_line_indent = Cm(-0.55)
                r = p.add_run('· ')
                set_run(r, size=BODY_PT, bold=True, color=ACCENT2)
                add_rich(p, it, size=10)
            p = self.doc.add_paragraph()
            para_fmt(p, before=0, after=8, line=1.0)
        if b.get('intro'):
            p = self.doc.add_paragraph()
            para_fmt(p, before=6, after=10, line=1.6, indent=2)
            add_rich(p, b['intro'])


HEAD_MAP = {
    'AI Prompt Begin': '提示词',
    'Response': '模型响应',
}


def strip_leading_num(s):
    """去掉条目自带的「2. 」「3）」「• 」前缀，避免与 Word 自动编号重复。"""
    return re.sub(r'^\s*(?:\d+[.、)]|•|·|·)\s+', '', s)


# 原文里用 emoji 当项目符号（🧪 📁 📈 ⚙️ 📥 👉 📌 ⚠️ ✅ ① ② …），
# 文档里已有真项目符号，保留会显得脏；标题级别的位置保留（有信息量）
EMOJI = re.compile(
    '[\U0001F300-\U0001FAFF\u2190-\u21FF\u2600-\u27BF\uFE0F\u20E3'
    '\u2460-\u24FF\u2B00-\u2BFF]+')


def strip_emoji(s):
    return re.sub(r'\s{2,}', ' ', EMOJI.sub('', s)).strip()


def translate_head(s):
    return HEAD_MAP.get(s, s)


def build(doc_id, out_path, ch_label='', title='氛围工程'):
    trans = load_json(os.path.join(WORK, doc_id + '_trans.json'))
    blocks = trans['blocks']
    figdir = os.path.join(ROOT, 'figs', doc_id)
    zhdir = os.path.join(ROOT, 'figs_zh', doc_id)
    zh_kind = {}
    kp = os.path.join(WORK, 'fig_kind.json')
    if os.path.exists(kp):
        zh_kind = load_json(kp)
    doc = Document()
    add_header_footer(doc, title, ch_label)
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(MARGIN_CM)
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.2)
    st = doc.styles['Normal']
    st.font.name = EN_BODY
    st.font.size = Pt(BODY_PT)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), CN_BODY)
    st.paragraph_format.line_spacing = 1.5
    st.paragraph_format.space_after = Pt(6)

    rd = Renderer(doc, figdir)
    rd.zhdir = zhdir
    rd.zh_kind = zh_kind
    first = True
    for b in blocks:
        if b['type'] == 'chapter_open' and not first:
            doc.add_page_break()
        rd.block(b)
        first = False
    doc.save(out_path)
    print('saved %s  blocks=%d  figs=%d' % (out_path, len(blocks),
                                            len(rd.used_fig)))
    if rd.missing_fig:
        print('!! 缺图:', rd.missing_fig)
    return rd


if __name__ == '__main__':
    did = sys.argv[1]
    outp = sys.argv[2]
    lbl = sys.argv[3] if len(sys.argv) > 3 else ''
    build(did, outp, lbl)
