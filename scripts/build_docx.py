# -*- coding: utf-8 -*-
"""把译文 JSON 渲染成中文技术书 Word 文档。

用法：
  python build_docx.py <trans.json> <figtexts.json> <figtrans.json> <figdir> <out.docx> [中文书名]
"""
import json
from bookconf import cfg, sys, os, re
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from PIL import Image

CN_BODY = cfg('cn_body')
CN_HEAD = cfg('cn_head')
EN_BODY = cfg('en_body')
EN_HEAD = cfg('en_head')
ACCENT = RGBColor(0x9E, 0x1B, 0x32)
GREY = RGBColor(0x59, 0x59, 0x59)
LIGHT = RGBColor(0x80, 0x80, 0x80)
BODY_PT = cfg('body_pt')
PAGE_W_CM = 21.0
MARGIN_CM = cfg('margin_cm')
TEXT_W_CM = PAGE_W_CM - MARGIN_CM * 2      # 16.2cm
ORIG_TEXT_W_PT = 423.0                      # 原书版心宽（用于按比例换算图宽）


def set_run(r, size=BODY_PT, bold=False, color=None, cn=CN_BODY, en=EN_BODY, italic=False):
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


def para_fmt(p, before=0, after=6, line=1.45, indent_chars=0, align=None, keep=False):
    pf = p.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = line
    if indent_chars:
        pf.first_line_indent = Pt(BODY_PT * indent_chars)
    if align is not None:
        p.alignment = align
    pf.keep_with_next = keep
    return p


def add_rich(p, text, size=BODY_PT, color=None, cn=CN_BODY, en=EN_BODY):
    """支持 **粗体** 与 `行内代码` 标记。"""
    for seg in re.split(r'(\*\*.+?\*\*|`[^`]+`)', text):
        if not seg:
            continue
        if seg.startswith('**') and seg.endswith('**') and len(seg) > 4:
            r = p.add_run(seg[2:-2])
            set_run(r, size=size, bold=True, color=color, cn=cn, en=en)
        elif seg.startswith('`') and seg.endswith('`') and len(seg) > 2:
            r = p.add_run(seg[1:-1])
            set_run(r, size=size - 0.5, color=color, cn='Consolas', en='Consolas')
        else:
            r = p.add_run(seg)
            set_run(r, size=size, color=color, cn=cn, en=en)
    return p


def hr_rule(doc, color='9E1B32', size=12):
    p = doc.add_paragraph()
    para_fmt(p, before=0, after=10, line=1.0)
    pPr = p._p.get_or_add_pPr()
    pbdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), str(size))
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), color)
    pbdr.append(bottom)
    pPr.append(pbdr)


def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hexcolor)
    tcPr.append(shd)


CJK = re.compile(r'[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]')


def join_cn_lines(s):
    """把译文里的手动换行拼回一行：中文之间不加空格。"""
    parts = [x.strip() for x in s.split('\n') if x.strip()]
    out = ''
    for i, part in enumerate(parts):
        if i == 0:
            out = part
            continue
        if out and CJK.match(out[-1]) and CJK.match(part[0]):
            out += part
        else:
            out += ' ' + part
    return out


def add_header_footer(doc, book_title, ch_label):
    sec = doc.sections[0]
    hp = sec.header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = hp.add_run(f'{book_title}　|　{ch_label}')
    set_run(r, size=8.5, color=LIGHT, cn=CN_HEAD, en=EN_HEAD)
    # 页眉下细线
    pPr = hp._p.get_or_add_pPr()
    pbdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '4')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), 'CCCCCC')
    pbdr.append(bottom)
    pPr.append(pbdr)
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run()
    set_run(r, size=9, color=LIGHT)
    fld = OxmlElement('w:fldSimple')
    fld.set(qn('w:instr'), 'PAGE')
    r._element.addnext(fld)


def fig_note_pairs(key, figtexts, figtrans):
    """图内文字对照：去重、跳过未翻译项。"""
    ft = figtexts.get(key)
    tr = figtrans.get(key, {})
    if not ft:
        return []
    out, seen = [], set()
    for b in ft['blocks']:
        cn = tr.get(str(b['id']))
        if not cn:
            continue
        en = re.sub(r'\s+', ' ', b['en']).strip()
        cn1 = join_cn_lines(cn)
        if en == cn1:
            continue
        sig = (en.lower(), cn1)
        if sig in seen:
            continue
        seen.add(sig)
        out.append((en, cn1))
    return out


# 前导缩进改用不换行空格（U+00A0）：等宽字体下同宽，且不会被 Word 折叠
NBSP = '\u00a0'


def keep_indent(line):
    """把行首的连续半角空格替换为不换行空格，保住代码缩进的视觉宽度。"""
    n = len(line) - len(line.lstrip(' '))
    if n <= 0:
        return line
    return NBSP * n + line[n:]


def build(trans_p, figtexts_p, figtrans_p, figdir, out_p, ch_label=''):
    blocks = json.load(open(trans_p, encoding='utf-8'))
    # 合并被"文字环绕图"拆碎的段落：前块不以句末标点结尾 → 与后块直接拼接
    END_PUNCT = tuple('。！？：；.!?:;"”')
    _merged = []
    for _b in blocks:
        if (_b['type'] == 'p' and _merged and _merged[-1]['type'] == 'p'
                and not _merged[-1]['text'].rstrip().endswith(END_PUNCT)):
            _merged[-1] = dict(_merged[-1])
            _merged[-1]['text'] = _merged[-1]['text'].rstrip() + _b['text'].lstrip()
        else:
            _merged.append(dict(_b))
    blocks = _merged
    figtexts = json.load(open(figtexts_p, encoding='utf-8'))
    figtrans = json.load(open(figtrans_p, encoding='utf-8'))

    doc = Document()
    add_header_footer(doc, '图解流处理系统', ch_label or '')
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(MARGIN_CM)
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.2)

    # 默认样式
    st = doc.styles['Normal']
    st.font.name = EN_BODY
    st.font.size = Pt(BODY_PT)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), CN_BODY)
    st.paragraph_format.line_spacing = 1.45
    st.paragraph_format.space_after = Pt(6)

    for blk in blocks:
        t = blk['type']

        if t == 'chapter_open':
            # 章号
            p = doc.add_paragraph()
            para_fmt(p, before=6, after=2, line=1.0)
            r = p.add_run(f"第 {blk['num']} 章")
            set_run(r, size=11, bold=True, color=ACCENT, cn=CN_HEAD, en=EN_HEAD)
            # 章标题
            p = doc.add_paragraph()
            para_fmt(p, before=0, after=4, line=1.15)
            r = p.add_run(blk['title'])
            set_run(r, size=28, bold=True, color=ACCENT, cn=CN_HEAD, en=EN_HEAD)
            if blk.get('orig_title'):
                p = doc.add_paragraph()
                para_fmt(p, before=0, after=10, line=1.2)
                r = p.add_run(blk['orig_title'])
                set_run(r, size=11, color=LIGHT, italic=True, cn=CN_HEAD, en=EN_HEAD)
            hr_rule(doc)
            # 本章内容
            p = doc.add_paragraph()
            para_fmt(p, before=2, after=4, line=1.3, keep=True)
            r = p.add_run('本章内容')
            set_run(r, size=11, bold=True, color=ACCENT, cn=CN_HEAD, en=EN_HEAD)
            for it in blk['toc']:
                p = doc.add_paragraph(style='List Bullet')
                para_fmt(p, before=0, after=2, line=1.4)
                add_rich(p, it, size=10.5)
            # 引语
            p = doc.add_paragraph()
            para_fmt(p, before=16, after=2, line=1.5, align=WD_ALIGN_PARAGRAPH.CENTER)
            r = p.add_run('“' + blk['quote'] + '”')
            set_run(r, size=11.5, italic=True, color=GREY, cn='楷体', en='Georgia')
            if blk.get('quote_by'):
                p = doc.add_paragraph()
                para_fmt(p, before=0, after=14, line=1.4, align=WD_ALIGN_PARAGRAPH.RIGHT)
                r = p.add_run(blk['quote_by'])
                set_run(r, size=10, color=LIGHT, cn='楷体', en='Georgia')
            if blk.get('intro'):
                p = doc.add_paragraph()
                para_fmt(p, before=6, after=10, line=1.55, indent_chars=2)
                add_rich(p, blk['intro'])

        elif t == 'h2':
            p = doc.add_paragraph()
            para_fmt(p, before=18, after=8, line=1.25, keep=True)
            r = p.add_run(blk['text'])
            set_run(r, size=16, bold=True, color=ACCENT, cn=CN_HEAD, en=EN_HEAD)
            p.style = doc.styles['Heading 2']

        elif t == 'h3':
            p = doc.add_paragraph()
            para_fmt(p, before=12, after=6, line=1.25, keep=True)
            r = p.add_run(blk['text'])
            set_run(r, size=12.5, bold=True, color=RGBColor(0x40, 0x40, 0x40), cn=CN_HEAD, en=EN_HEAD)
            p.style = doc.styles['Heading 3']

        elif t == 'p':
            p = doc.add_paragraph()
            para_fmt(p, before=0, after=8, line=1.6, indent_chars=2)
            add_rich(p, blk['text'])

        elif t in ('list', 'numlist'):
            style = 'List Bullet' if t == 'list' else 'List Number'
            for it in blk['items']:
                p = doc.add_paragraph(style=style)
                para_fmt(p, before=0, after=4, line=1.55, indent_chars=0)
                add_rich(p, it)

        elif t == 'figure':
            key = blk['key']
            path = os.path.join(figdir, key + '.png')
            if not os.path.exists(path):
                print('!! 缺图:', path)
                continue
            with Image.open(path) as im:
                iw, ih = im.size
            # 按原书比例换算宽度（原图 pt 宽 / 原书版心 423pt × 本文版心）
            orig_w_pt = blk.get('w_pt')
            if not orig_w_pt:
                orig_w_pt = figtexts.get(key, {}).get('bbox')
                orig_w_pt = (orig_w_pt[2] - orig_w_pt[0]) if orig_w_pt else None
            if orig_w_pt:
                w_cm = min(TEXT_W_CM, max(7.0, orig_w_pt / ORIG_TEXT_W_PT * TEXT_W_CM))
            else:
                w_cm = TEXT_W_CM * 0.8
            # 保证有效 DPI：小图不强行放大
            dpi_cap = 230.0
            w_max_dpi = iw * 2.54 / dpi_cap
            w_cm = max(3.8, min(w_cm, w_max_dpi))
            # 限制单图高度，避免占满整页（A4 正文高约 25.3cm）
            MAX_H_CM = 17.5
            if iw > 0 and w_cm * ih / iw > MAX_H_CM:
                w_cm = MAX_H_CM * iw / ih
            p = doc.add_paragraph()
            para_fmt(p, before=6, after=2, line=1.0, align=WD_ALIGN_PARAGRAPH.CENTER)
            p.add_run().add_picture(path, width=Cm(w_cm))
            # 图内文字对照
            pairs = fig_note_pairs(key, figtexts, figtrans)
            if pairs:
                p = doc.add_paragraph()
                para_fmt(p, before=0, after=10, line=1.3, align=WD_ALIGN_PARAGRAPH.LEFT)
                r = p.add_run('图内文字对照　')
                set_run(r, size=8, bold=True, color=LIGHT, cn=CN_HEAD, en=EN_HEAD)
                txt = '；'.join(f'{en} → {cn}' for en, cn in pairs)
                r = p.add_run(txt)
                set_run(r, size=8, color=LIGHT, cn=CN_HEAD, en=EN_HEAD)

        elif t == 'table':
            head = blk['head']
            rows = blk['rows']
            tb = doc.add_table(rows=1 + len(rows), cols=len(head))
            tb.style = 'Table Grid'
            tb.alignment = WD_TABLE_ALIGNMENT.CENTER
            for j, h in enumerate(head):
                c = tb.cell(0, j)
                c.text = ''
                p = c.paragraphs[0]
                para_fmt(p, before=3, after=3, line=1.25, align=WD_ALIGN_PARAGRAPH.CENTER)
                r = p.add_run(h)
                set_run(r, size=9.5, bold=True, color=ACCENT, cn=CN_HEAD, en=EN_HEAD)
                shade(c, 'F5EDEF')
            for i, row in enumerate(rows, 1):
                for j, cell_txt in enumerate(row):
                    c = tb.cell(i, j)
                    c.text = ''
                    p = c.paragraphs[0]
                    para_fmt(p, before=3, after=3, line=1.3)
                    add_rich(p, cell_txt, size=9)
            # 表后留白
            p = doc.add_paragraph()
            para_fmt(p, before=0, after=6, line=1.0)

        elif t == 'code':
            p = doc.add_paragraph()
            para_fmt(p, before=6, after=6 if not blk.get('notes') else 2, line=1.15)
            pPr = p._p.get_or_add_pPr()
            shd = OxmlElement('w:shd')
            shd.set(qn('w:val'), 'clear')
            shd.set(qn('w:fill'), 'F4F4F4')
            pPr.append(shd)
            for i, line in enumerate(blk['text'].split('\n')):
                r = p.add_run(keep_indent(line) if line else ' ')
                set_run(r, size=9, cn='Consolas', en='Consolas')
                if i < blk['text'].count('\n'):
                    r.add_break()
            # 代码注释中英对照
            if blk.get('notes'):
                p = doc.add_paragraph()
                para_fmt(p, before=0, after=10, line=1.3)
                r = p.add_run('代码注释对照　')
                set_run(r, size=8, bold=True, color=LIGHT, cn=CN_HEAD, en=EN_HEAD)
                r = p.add_run('；'.join(f'{en} → {cn}' for en, cn in blk['notes']))
                set_run(r, size=8, color=LIGHT, cn=CN_HEAD, en=EN_HEAD)

        else:
            print('!! 未知块类型:', t)

    doc.save(out_p)
    print('saved', out_p)


if __name__ == '__main__':
    args = sys.argv[1:]
    build(*args[:6])
