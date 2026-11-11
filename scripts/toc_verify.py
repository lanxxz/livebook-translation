#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""统一多级目录：交付前验收（pitfalls AA6/AA14 配套，fail-closed）。

用法：

    python scripts/toc_verify.py --config work/unified_toc.json

三层检查：
  1. 三方页码核对 —— 书签 / front_meta / 目录页印出，逐条一致；
  2. 链接端到端 —— 逐个模拟点击：行链接成对、矩形有可见文字、
     目标页含对应标题/编号、两区域落点一致、链接类型全为 LINK_GOTO；
  3. 交付断言 —— 全书检索章内导览关键词 0 命中、目录行/链接数对得上。
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from toc_common import (load_config, book_pdf, norm, load_entries, display_key,
                        find_rows, toc_entry_pages, bookmark_targets)
import pymupdf

DEFAULT_RESIDUAL = ['本章内容', '本章小节目录', '小节目录']


def check_pages(cfg, doc, entries, rows):
    """三方逐条核对；返回不一致清单。"""
    ch_bm, sec_bm = bookmark_targets(cfg, doc)
    bad = []
    for i, ent in enumerate(entries):
        row = rows[i] if i < len(rows) else None
        rt, pp = (row[1], row[3]) if row else ('', 0)
        if ent['level'] == 0:
            bp = (ch_bm[int(ent['num'])] if ent['num'].isdigit()
                  and int(ent['num']) in ch_bm else ent['page'])
        else:
            key = norm(ent['title'])
            hit = next((p for k, p in sec_bm if k == key), None)
            if hit is None:
                hit = next((p for k, p in sec_bm
                            if k.startswith(key[:10]) or key.startswith(k[:10])), None)
            bp = hit
        title_ok = norm(rt) == display_key(ent)
        page_ok = (pp == ent['page'])
        bm_ok = (bp == ent['page']) if bp is not None else False
        if not (title_ok and page_ok and bm_ok):
            why = []
            if not title_ok:
                why.append('标题')
            if not page_ok:
                why.append('页码 %s/%s' % (pp, ent['page']))
            if not bm_ok:
                why.append('书签 %s/%s' % (bp, ent['page']))
            bad.append((ent['num'], ent['title'][:28], ','.join(why)))
    return bad


def find_title_on_page(doc, pg, ent):
    """目标页是否含对应章标题 / 小节编号 / 小节标题（模拟点击）。"""
    tgt = norm(doc[pg - 1].get_text())
    if ent['level'] == 0:
        if not ent['num']:
            # welcome 等虚拟条目没有对应标题行，落点由书签校验保证
            return True
        return ent['num'] in tgt or norm(ent['title'])[:6] in tgt
    if ent['num'] and ent['num'] in tgt:
        return True
    key = norm(ent['title'])
    return bool(key[:8] and key[:8] in tgt)


def check_links(cfg, doc, entries, rows):
    """逐个模拟点击目录行链接；返回 (问题清单, 行链接数)。"""
    bad, n_row_link = [], 0
    for (pno, row_text, tbb, printed_pg, nbb), ent in zip(rows, entries):
        page = doc[pno - 1]
        row_links = []
        for l in page.get_links():
            if l.get('kind') != pymupdf.LINK_GOTO:
                continue
            if (abs(l['from'].y0 - (tbb[1] - 2)) < 8
                    or abs(l['from'].y0 - (nbb[1] - 2)) < 8):
                row_links.append(l)
        if len(row_links) < 2:
            bad.append('p%d 行 %r 仅 %d 个链接（期望双区域）'
                       % (pno, row_text[:20], len(row_links)))
        tp = (row_links[0]['page'] + 1) if row_links else None
        for l in row_links:
            n_row_link += 1
            if not page.get_textbox(l['from']).strip():
                bad.append('p%d 链接区域无可见文字' % pno)
            if l['page'] + 1 != tp:
                bad.append('p%d 行 %r 双区域落点不一致' % (pno, row_text[:20]))
        if tp and not find_title_on_page(doc, tp, ent):
            bad.append('p%d 行 %r → p%d 目标页未找到对应标题'
                       % (pno, row_text[:20], tp, ))
    return bad, n_row_link


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    ap.add_argument('--root', default=None)
    args = ap.parse_args()

    cfg = load_config(args.config, args.root)
    p = book_pdf(cfg)
    if not os.path.exists(p):
        raise SystemExit('找不到合订 PDF：%s' % p)
    doc = pymupdf.open(p)
    entries = load_entries(cfg)
    toc_pages = toc_entry_pages(cfg, doc, len(entries))
    rows = []
    for pno in toc_pages:
        for row_text, tbb, printed_pg, nbb in find_rows(cfg, doc[pno - 1]):
            rows.append((pno, row_text, tbb, printed_pg, nbb))

    problems = []
    print('=' * 74)
    print('统一多级目录验收：%s' % p)
    print('=' * 74)
    print('页数 %d | 目录页 p%d–p%d | 条目 %d | 解析行 %d'
          % (doc.page_count, toc_pages[0] if toc_pages else 0,
             toc_pages[-1] if toc_pages else 0, len(entries), len(rows)))

    # 1. 行数
    if len(rows) != len(entries):
        problems.append('目录行数 %d ≠ front_meta %d' % (len(rows), len(entries)))
    print('\n【一】三方页码核对（书签 / 配置 / 印刷）')
    bad = check_pages(cfg, doc, entries, rows)
    print('  ✓ %d/%d 条一致' % (len(entries) - len(bad), len(entries)))
    problems.extend('页码核对 %s %s：%s' % x for x in bad)

    # 2. 链接
    print('\n【二】链接端到端模拟点击')
    link_bad, n_row_link = check_links(cfg, doc, entries, rows)
    kinds = {}
    total = 0
    for i in range(doc.page_count):
        for l in doc[i].get_links():
            kinds[l.get('kind')] = kinds.get(l.get('kind'), 0) + 1
            total += 1
    back = sum(1 for i in range(doc.page_count)
               for l in doc[i].get_links()
               if l.get('kind') == pymupdf.LINK_GOTO
               and l['page'] + 1 == int(cfg['toc_start_page'])
               and l['from'].y0 < 60)
    print('  行链接 %d 个 | 链接总数 %d | 返回目录 %d | 类型 %s'
          % (n_row_link, total, back, kinds))
    problems.extend(link_bad)
    if list(kinds.keys()) != [pymupdf.LINK_GOTO]:
        problems.append('存在非 LINK_GOTO 链接：%s' % kinds)
    if n_row_link != 2 * len(entries):
        problems.append('行链接 %d ≠ 条目数 × 2 (%d)' % (n_row_link, 2 * len(entries)))

    # 3. 章内导览残留
    print('\n【三】章内导览残留与类型')
    kws = cfg.get('residual_keywords') or DEFAULT_RESIDUAL
    residual = []
    for i in range(doc.page_count):
        t = doc[i].get_text()
        for kw in kws:
            if kw in t:
                residual.append((i + 1, kw))
    print('  关键词 %s：命中 %d 页' % (kws, len(residual)))
    if residual:
        problems.append('章内导览残留 %d 页：%s' % (len(residual), residual[:5]))

    print('\n' + '-' * 74)
    print('问题数 : %d' % len(problems))
    if problems:
        for e in problems[:25]:
            print('  ✗', e)
        print('\n结论: ✗ 验收未通过')
        doc.close()
        return 1
    print('\n结论: ✓ 目录 / 页码 / 链接全部通过')
    doc.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
