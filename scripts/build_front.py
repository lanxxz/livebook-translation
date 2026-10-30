# -*- coding: utf-8 -*-
"""生成前置与附录文档（00_前言与附录.docx），复用 build_docx 的样式函数。"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from build_docx import (set_run, para_fmt, add_rich, hr_rule, add_header_footer,
                        CN_BODY, CN_HEAD, EN_BODY, EN_HEAD, ACCENT, GREY, LIGHT,
                        BODY_PT, MARGIN_CM, shade)


def build(trans_p, out_p):
    blocks = json.load(open(trans_p, encoding='utf-8'))
    doc = Document()
    add_header_footer(doc, '图解流处理系统', '前言与附录')
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(MARGIN_CM)
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.2)
    st = doc.styles['Normal']
    st.font.name = EN_BODY
    st.font.size = Pt(BODY_PT)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), CN_BODY)
    st.paragraph_format.line_spacing = 1.45
    st.paragraph_format.space_after = Pt(6)

    for blk in blocks:
        t = blk['type']
        if t == 'title':
            p = doc.add_paragraph()
            para_fmt(p, before=90, after=6, line=1.2, align=WD_ALIGN_PARAGRAPH.CENTER)
            r = p.add_run(blk['title'])
            set_run(r, size=34, bold=True, color=ACCENT, cn=CN_HEAD, en=EN_HEAD)
            p = doc.add_paragraph()
            para_fmt(p, before=0, after=4, line=1.2, align=WD_ALIGN_PARAGRAPH.CENTER)
            r = p.add_run(blk['sub'])
            set_run(r, size=15, color=GREY, italic=True, cn=CN_HEAD, en='Georgia')
            p = doc.add_paragraph()
            para_fmt(p, before=0, after=30, line=1.4, align=WD_ALIGN_PARAGRAPH.CENTER)
            r = p.add_run(blk['line'])
            set_run(r, size=11, color=LIGHT, cn=CN_HEAD, en=EN_HEAD)
            hr_rule(doc)
            p = doc.add_paragraph()
            para_fmt(p, before=10, after=0, line=1.5, align=WD_ALIGN_PARAGRAPH.CENTER)
            r = p.add_run(blk['by'])
            set_run(r, size=12, color=GREY, cn=CN_HEAD, en=EN_HEAD)
            doc.add_page_break()

        elif t == 'h1':
            p = doc.add_paragraph()
            para_fmt(p, before=6, after=4, line=1.25)
            r = p.add_run(blk['text'])
            set_run(r, size=24, bold=True, color=ACCENT, cn=CN_HEAD, en=EN_HEAD)
            hr_rule(doc, size=8)

        elif t == 'h2':
            p = doc.add_paragraph()
            para_fmt(p, before=14, after=6, line=1.3, keep=True)
            r = p.add_run(blk['text'])
            set_run(r, size=13, bold=True, color=RGBColor(0x40, 0x40, 0x40), cn=CN_HEAD, en=EN_HEAD)

        elif t == 'p':
            p = doc.add_paragraph()
            para_fmt(p, before=0, after=8, line=1.6, indent_chars=2)
            add_rich(p, blk['text'])

        elif t == 'sign':
            p = doc.add_paragraph()
            para_fmt(p, before=2, after=14, line=1.4, align=WD_ALIGN_PARAGRAPH.RIGHT)
            r = p.add_run(blk['text'])
            set_run(r, size=10.5, color=GREY, italic=True, cn='楷体', en='Georgia')

        elif t == 'bullet':
            for it in blk['items']:
                p = doc.add_paragraph(style='List Bullet')
                para_fmt(p, before=0, after=4, line=1.55)
                add_rich(p, it)

        elif t == 'terms':
            rows = blk['items']
            tb = doc.add_table(rows=1 + len(rows), cols=3)
            tb.style = 'Table Grid'
            tb.alignment = WD_TABLE_ALIGNMENT.CENTER
            for j, h in enumerate(['英文术语', '中文译名', '首次出现']):
                c = tb.cell(0, j)
                c.text = ''
                p = c.paragraphs[0]
                para_fmt(p, before=3, after=3, line=1.2, align=WD_ALIGN_PARAGRAPH.CENTER)
                r = p.add_run(h)
                set_run(r, size=9.5, bold=True, color=ACCENT, cn=CN_HEAD, en=EN_HEAD)
                shade(c, 'F5EDEF')
            for i, (en, cn, ch) in enumerate(rows, 1):
                for j, val in enumerate([en, cn, ch]):
                    c = tb.cell(i, j)
                    c.text = ''
                    p = c.paragraphs[0]
                    para_fmt(p, before=2, after=2, line=1.3,
                             align=WD_ALIGN_PARAGRAPH.CENTER if j else WD_ALIGN_PARAGRAPH.LEFT)
                    r = p.add_run(val)
                    set_run(r, size=9, cn=CN_BODY if j == 1 else EN_BODY,
                            en=EN_BODY, color=None if j == 1 else GREY)

        else:
            print('!! 未知块', t)

    doc.save(out_p)
    print('saved', out_p)


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2])
