# -*- coding: utf-8 -*-
"""合并全书：封面 + 目录 + 各章 → 整本 docx 与整本 PDF（带两级书签）。

为什么「逐份转 PDF 再拼接」而不是「docx 合并后转 PDF」（pitfalls R1/R2）：
  docxcompose 搬 XML 时必须逐张重建 r:embed，否则 rId 撞车、图挤成几个关系；
  且各章页脚都从 1 开始，合订后页码必须**在 PDF 层逐页重写**才能连续。
"""
import json
import os
import re
import sys

import pymupdf
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docxcompose.composer import Composer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, WORK, load_docs  # noqa: E402

OUT = os.path.join(ROOT, 'out')
PDF = os.path.join(OUT, '分册_pdf')
ACCENT = RGBColor(0x1F, 0x3A, 0x5F)


def ordered_pdfs():
    """封面 → 目录 → 前言 → 1..N 章。"""
    files = []
    for name in ('00_封面.pdf', '00_目录.pdf'):
        p = os.path.join(PDF, name)
        if os.path.exists(p):
            files.append(p)
    rest = []
    for f in os.listdir(PDF):
        if not f.endswith('.pdf') or f.startswith('00_'):
            continue
        m = re.match(r'^(\d{2})_', f)
        rest.append((int(m.group(1)) if m else 99, f))
    for _, f in sorted(rest):
        files.append(os.path.join(PDF, f))
    return files


def merge_docx(paths, outp):
    base = Document(paths[0])
    comp = Composer(base)
    for p in paths[1:]:
        comp.append(Document(p))
    comp.save(outp)
    return outp


def merge_pdf(paths, outp, toc_entries):
    """逐份 PDF 拼接；页脚页码在本层重写（各分册都从 1 开始）。"""
    out = pymupdf.open()
    # 用第 1 页尺寸建立空白文档，再逐页 insert_pdf
    first = pymupdf.open(paths[0])
    out.insert_pdf(first)
    first.close()
    for p in paths[1:]:
        src = pymupdf.open(p)
        out.insert_pdf(src)
        src.close()

    # 逐页重写页脚数字。
    # 注意：draw_rect 的 fill 在 insert_pdf 拼接后的页面上不一定立即生效（
    # 页面内容流已冻结），所以这里改用 redaction 真正删掉旧文字，再写新页码。
    for i, page in enumerate(out):
        num = i + 1
        r = page.rect
        foot = pymupdf.Rect(0, r.y1 - 72, r.x1, r.y1)
        page.add_redact_annot(foot, fill=(1, 1, 1))
        page.apply_redactions()
        if i < 2:                      # 封面与目录不编页码
            continue
        txt = str(num - 2)
        w = pymupdf.get_text_length(txt, fontname='helv', fontsize=9.5)
        page.insert_text(((r.x1 - w) / 2, r.y1 - 36), txt,
                         fontsize=9.5, fontname='helv',
                         color=(0.45, 0.45, 0.45))

    out.set_toc(toc_entries)
    out.save(outp, deflate=True, garbage=3)
    out.close()
    return outp


def toc_from_trans():
    """章 + 小节两级书签，页码由分册页数累加得到。"""
    entries = [[1, '封面', 1], [1, '目录', 2]]
    cur = 3
    for d in load_docs():
        tp = os.path.join(WORK, d['id'] + '_trans.json')
        if not os.path.exists(tp):
            continue
        blocks = json.load(open(tp, encoding='utf-8'))['blocks']
        head = None
        subs = []
        for b in blocks:
            if b['type'] == 'chapter_open':
                head = b
            elif b['type'] == 'heading' and b.get('level') == 2 and head is not None:
                subs.append(b['text'])
        if head is None:
            continue
        num = (head.get('num') or d['num']).strip()
        title = head.get('title') or d['title']
        label = ('第 %s 章　%s' % (num, title)) if num else title
        entries.append([1, label, cur])
        # 小节页码：按标题在 PDF 文本里定位
        pf = None
        key_n = int(num) if num.isdigit() else 0
        for f in os.listdir(PDF):
            if not f.endswith('.pdf'):
                continue
            if key_n and f.startswith('%02d_' % key_n):
                pf = os.path.join(PDF, f)
                break
            if not key_n and f.startswith('00_前言'):
                pf = os.path.join(PDF, f)
                break
        if pf and subs:
            doc = pymupdf.open(pf)
            for s in subs:
                key = re.sub(r'\s+', '', s)[:14]
                for i in range(doc.page_count):
                    txt = re.sub(r'\s+', '', doc[i].get_text())
                    if key and key in txt:
                        entries.append([2, s, cur + i])
                        break
            doc.close()
        doc = pymupdf.open(pf)
        for s in subs:
            key = re.sub(r'\s+', '', s)[:12]
            for i in range(doc.page_count):
                txt = re.sub(r'\s+', '', doc[i].get_text())
                if key and key in txt and (cur + i) not in [e[2] for e in entries if e[0] == 2]:
                    entries.append([2, s, cur + i])
                    break
        doc.close()
        n = pymupdf.open(pf).page_count
        cur += n
    return entries


def main():
    paths = ordered_pdfs()
    if not paths:
        sys.exit('没有可合并的 PDF')
    print('合并顺序：')
    for p in paths:
        print('  ', os.path.basename(p))
    docx_out = os.path.join(OUT, '氛围工程（Vibe Engineering）中文版.docx')
    DX = os.path.join(OUT, '分册_docx')
    cand = [os.path.join(DX, os.path.basename(p)[:-4] + '.docx') for p in paths]
    cand = [c for c in cand if os.path.exists(c)]
    if len(cand) >= 2:
        merge_docx(cand, docx_out)
        print('docx:', docx_out, '（%d 份合并）' % len(cand))
    else:
        print('!! docx 合并跳过：分册 docx 只有 %d 份' % len(cand))
    entries = toc_from_trans()
    pdf_out = os.path.join(OUT, '氛围工程（Vibe Engineering）中文版.pdf')
    # 目标文件被预览程序占用时，先写临时名再替换，避免 Permission denied
    tmp = pdf_out + '.tmp'
    merge_pdf(paths, tmp, entries)
    try:
        os.replace(tmp, pdf_out)
    except PermissionError:
        alt = os.path.join(OUT, '氛围工程（Vibe Engineering）中文版_修订.pdf')
        os.replace(tmp, alt)
        pdf_out = alt
        print('!! 原文件被占用，已输出为修订副本:', os.path.basename(alt))
    d = pymupdf.open(pdf_out)
    print('pdf:', pdf_out, 'pages=%d toc=%d' % (d.page_count, len(entries)))


if __name__ == '__main__':
    main()
