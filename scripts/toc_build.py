#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""统一多级目录：两遍构建 + 全书合订（pitfalls AA3/AA4/AA8/AA10 配套）。

用法（配置模板见 assets/unified_toc.json.example）：

    python scripts/toc_build.py --config work/unified_toc.json --step all
    python scripts/toc_build.py --config work/unified_toc.json --step rebuild
    python scripts/toc_build.py --config work/unified_toc.json --step merge
    python scripts/toc_build.py --config work/unified_toc.json --check

`--root` 可覆盖配置里的项目根；`BOOK_ROOT` 环境变量同样有效。
所有书名、路径、命名模板均来自配置，无任何机器相关硬编码。
"""
import argparse
import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from toc_common import (load_config, cpath, build_plan, collect_entries,
                        compute_pages, build_front, convert_front, save_meta,
                        sub_pdf, sub_docx, sub_outline, book_pdf, book_docx,
                        norm, load_docs)
import pymupdf


# ---------------------------------------------------------------- 两遍构建
def rebuild(cfg, check_only=False):
    plan = build_plan(cfg)
    entries, chapters = collect_entries(cfg, plan)
    n0 = sum(1 for e in entries if e[0] == 0)
    n1 = sum(1 for e in entries if e[0] == 1)
    n2 = sum(1 for e in entries if e[0] == 2)
    print('目录条目：%d 章级 + %d 小节(h2) + %d 子小节(h3) = %d 行'
          % (n0, n1, n2, len(entries)))

    fixed = int(cfg['front_fixed_pages'])

    # ---- 第 1 遍：占位页码量出目录页数 P ----
    probe = copy.deepcopy(cfg.get('_front_meta') or {})
    probe.setdefault('book_title', cfg['book_title'])
    probe.setdefault('toc_title', cfg['toc_title'])
    probe['toc'] = [[e[1], e[2], '0', e[0]] for e in entries]
    build_front(cfg, probe)
    total_probe = convert_front(cfg)
    P = total_probe - fixed
    if P < 1:
        raise SystemExit('目录页数异常 P=%d（前置页 %d 页 / 固定页 %d）'
                         % (P, total_probe, fixed))
    print('第 1 遍：前置页 %d 页 → 目录 %d 页' % (total_probe, P))

    pages, total, ch_start, welcome_start = compute_pages(
        cfg, entries, plan, chapters, P)
    print('预期全书 %d 页；welcome 起 p%d' % (total, welcome_start))
    for k in sorted(ch_start):
        print('  %s 起 p%d' % (k, ch_start[k]))

    if check_only:
        p = book_pdf(cfg)
        if not os.path.exists(p):
            raise SystemExit('复核需要已合订 PDF：%s' % p)
        rx = re.compile(cfg['chapter']['bookmark_regex'])
        with pymupdf.open(p) as doc:
            ok = True
            for lvl, t, pg in doc.get_toc():
                if lvl != 1:
                    continue
                m = rx.match(norm(t))
                if not m:
                    continue
                num = int(m.group(1))
                name = next((x[0] for x in plan
                             if x[2] == 'chapter' and x[3] == str(num)), None)
                if name and ch_start.get(name) != pg:
                    print('  ✗ %s 期望 p%s 实际 p%s'
                          % (name, ch_start.get(name), pg))
                    ok = False
        print('书签一致性：%s' % ('OK' if ok else 'FAIL'))
        return 0 if ok else 1

    # ---- 第 2 遍：真实页码重建，复核收敛 ----
    fm = save_meta(cfg, entries, pages, ch_start)
    build_front(cfg, fm)
    total2 = convert_front(cfg)
    if total2 != fixed + P:
        raise SystemExit('第 2 遍目录页数漂移：%d ≠ %d，请检查排版'
                         % (total2 - fixed, P))
    print('第 2 遍：前置页 %d 页（目录 %d 页），页数收敛 ✓' % (total2, P))
    print('front_meta.json / chapter_pages.json 已更新')
    return 0


# ---------------------------------------------------------------- PDF 合并
def strip_footer_number(pg, cfg):
    """redaction 真删子文档页脚页码（AA8：白矩形会吃掉正文末行）。"""
    f = cfg['footer']
    r = pg.rect
    victims = []
    for b in list(pg.get_text('blocks')):
        txt = (b[4] or '').strip()
        if not txt or not txt.isdigit():
            continue
        x0, y0, x1, y1 = b[:4]
        if y0 < f['min_y'] or y1 > f['max_y']:
            continue
        if abs((x0 + x1) / 2 - r.width / 2) > f['center_tol']:
            continue
        victims.append(pymupdf.Rect(x0 - 2, y0 - 2, x1 + 2, y1 + 2))
    for rect in victims:
        pg.add_redact_annot(rect, fill=(1, 1, 1))
    if victims:
        pg.apply_redactions()
    return len(victims)


def write_page_number(pg, num, cfg):
    pn = cfg['page_number']
    r = pg.rect
    txt = str(num)
    tw = pymupdf.get_text_length(txt, fontname='helv', fontsize=pn['fontsize'])
    pg.insert_text((r.width / 2 - tw / 2, r.height - pn['from_bottom']), txt,
                   fontname='helv', fontsize=pn['fontsize'],
                   color=tuple(pn['color']))


def merge_pdf(cfg, plan):
    book = pymupdf.open()
    starts, start = {}, 0
    for name, label, kind, num, title in plan:
        p = sub_pdf(cfg, name)
        if not os.path.exists(p):
            raise SystemExit('缺分册 PDF：%s' % p)
        with pymupdf.open(p) as sub:
            n = sub.page_count
            book.insert_pdf(sub)
        starts[name] = start + 1
        start += n
    erased = sum(strip_footer_number(pg, cfg) for pg in book)
    print('  擦除子文档页脚页码 %d 处' % erased)
    for i in range(book.page_count):
        write_page_number(book[i], i + 1, cfg)

    # 两级书签：二级定位与目录页码同源于分册书签（AA3）
    toc, stat = [], []
    for name, label, kind, num, title in plan:
        st = starts[name]
        toc.append([1, label or name, st])
        if name == cfg['front_name']:
            stat.append((name, 0, 0))
            continue
        with pymupdf.open(sub_pdf(cfg, name)) as sub:
            n = sub.page_count
            ol = sub_outline(cfg, name)
        end = min(book.page_count, st + n - 1)
        added = 0
        for olvl, t, lp in ol:
            hit = st + lp - 1
            if 1 <= hit <= end:
                toc.append([2, t, hit])
                added += 1
        stat.append((name, len(ol), added))

    book.set_toc([])
    book.set_toc(toc)
    target = book_pdf(cfg)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    book.save(target, garbage=4, deflate=True)
    book.close()

    with pymupdf.open(target) as d:
        t = d.get_toc()
        back = sum(1 for i in range(1, len(t)) if t[i][2] < t[i - 1][2])
        oob = [x for x in t if not 1 <= x[2] <= d.page_count]
        print('  PDF：%s' % target)
        print('  总页数 %d | 一级 %d | 二级 %d | 回跳 %d | 越界 %d | %.1f MB' % (
            d.page_count, sum(1 for x in t if x[0] == 1),
            sum(1 for x in t if x[0] == 2), back, len(oob),
            os.path.getsize(target) / 1048576))
    for n, tt, a in stat:
        print('    %-40s 标题 %3d → 定位 %3d' % (n, tt, a))
    return target


# ---------------------------------------------------------------- docx 合并
def set_header(section, label, cfg):
    """每节独立页眉（自包含，不依赖项目里的 merge_book.py）。"""
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn

    fonts = cfg.get('fonts') or {}
    cn = fonts.get('cn_head', '微软雅黑')
    en = fonts.get('en_head', 'Arial')
    section.header.is_linked_to_previous = False
    section.footer.is_linked_to_previous = False
    hp = section.header.paragraphs[0]
    for r in list(hp.runs):
        r._element.getparent().remove(r._element)
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    text = ('%s　|　%s' % (cfg['header_text'], label)) if label else cfg['header_text']
    run = hp.add_run(text)
    run.font.size = Pt(8.5)
    run.font.name = en
    run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        from docx.oxml import OxmlElement
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:eastAsia'), cn)
    rFonts.set(qn('w:ascii'), en)
    rFonts.set(qn('w:hAnsi'), en)


def merge_docx(cfg, plan):
    from docx import Document
    from docx.enum.section import WD_SECTION
    from docx.oxml.ns import qn
    from docxcompose.composer import Composer

    master = Document(sub_docx(cfg, plan[0][0]))
    set_header(master.sections[0], plan[0][1], cfg)
    comp = Composer(master)
    for name, label, kind, num, title in plan[1:]:
        sub = Document(sub_docx(cfg, name))
        sec = comp.doc.add_section(WD_SECTION.NEW_PAGE)
        sec.header.is_linked_to_previous = False
        sec.footer.is_linked_to_previous = False
        comp.append(sub)
        set_header(comp.doc.sections[-1], label, cfg)
    for sec in comp.doc.sections:
        for el in sec._sectPr.findall(qn('w:pgNumType')):
            sec._sectPr.remove(el)
    target = book_docx(cfg)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    comp.save(target)
    print('  docx：%s | %.1f MB' % (target, os.path.getsize(target) / 1048576))
    return target


def merge(cfg, pdf_only=False, docx_only=False):
    plan = build_plan(cfg)
    print('合订顺序：')
    for name, label, kind, num, title in plan:
        print('  %-46s %s' % (name, label or '(无页眉)'))
    if not pdf_only and not cfg.get('skip_docx_merge'):
        merge_docx(cfg, plan)
    if not docx_only:
        merge_pdf(cfg, plan)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True, help='统一目录配置 JSON')
    ap.add_argument('--root', default=None, help='覆盖配置里的项目根')
    ap.add_argument('--step', default='all', choices=['all', 'rebuild', 'merge'])
    ap.add_argument('--check', action='store_true', help='只复核书签一致性')
    ap.add_argument('--pdf-only', action='store_true')
    ap.add_argument('--docx-only', action='store_true')
    args = ap.parse_args()

    cfg = load_config(args.config, args.root)
    print('项目根：%s' % cfg['_root'])
    if args.check:
        return rebuild(cfg, check_only=True)
    if args.step in ('all', 'rebuild'):
        rebuild(cfg)
    if args.step in ('all', 'merge'):
        # rebuild 写回的 front_meta 需重新载入
        cfg = load_config(args.config, args.root)
        merge(cfg, pdf_only=args.pdf_only, docx_only=args.docx_only)
    return 0


if __name__ == '__main__':
    sys.exit(main())
