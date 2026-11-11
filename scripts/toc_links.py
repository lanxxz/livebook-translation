#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""统一多级目录：给每行挂可点击跳转链接（pitfalls AA5/AA6/AA7 配套）。

用法：

    python scripts/toc_links.py --config work/unified_toc.json
    python scripts/toc_links.py --config work/unified_toc.json --in <pdf> --out <pdf>

职责：
  A. 目录每行（标题区 + 页码区双区域）挂 LINK_GOTO，落点为对应标题行；
  B. 各章页眉「返回目录」链接，形成双向导航。

挂链接前做 **fail-closed 四方一致性校验**：行数 / 标题 / 印刷页码 /
书签页任一不符立即中止，不产出「看起来对」的坏文件。
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from toc_common import (load_config, book_pdf, norm, load_entries, display_key,
                        find_rows, toc_entry_pages, bookmark_targets, get_lines)
import pymupdf

MARGIN_L = 68.2          # 页眉左侧「返回目录」热区；可用配置 header_link 覆盖


def find_head_y(page, cfg):
    """目标页上第一个标题行的 y（章首页）。"""
    lo, hi = (cfg.get('head_y_range') or [60, 170])
    for txt, bb in get_lines(page):
        if lo < bb[1] < hi:
            return bb[1]
    return None


def find_title_y(page, title):
    """目标页上 title（编号前缀）所在标题行的 y。"""
    key = norm(title)[:10]
    if len(key) < 2:
        return None
    best = None
    for txt, bb in get_lines(page):
        n = norm(txt)
        if n == norm(title) or n.startswith(key):
            if best is None or bb[1] < best:
                best = bb[1]
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    ap.add_argument('--root', default=None)
    ap.add_argument('--in', dest='src', default=None)
    ap.add_argument('--out', dest='dst', default=None)
    args = ap.parse_args()

    cfg = load_config(args.config, args.root)
    src = os.path.abspath(args.src or book_pdf(cfg))
    dst = os.path.abspath(args.dst or src)
    if not os.path.exists(src):
        raise SystemExit('找不到合订 PDF：%s' % src)

    doc = pymupdf.open(src)
    ch_bm, sec_bm = bookmark_targets(cfg, doc)
    entries = load_entries(cfg)
    toc_pages = toc_entry_pages(cfg, doc, len(entries))
    log, bad = [], []

    # ---- 1. 收集目录行，与 front_meta 逐条配对 ----
    rows = []
    for pno in toc_pages:
        for row_text, tbb, printed_pg, nbb in find_rows(cfg, doc[pno - 1]):
            rows.append((pno, row_text, tbb, printed_pg, nbb))
    log.append('目录页 %d 页（p%d–p%d），解析行 %d 条 / 期望 %d 条'
               % (len(toc_pages), toc_pages[0] if toc_pages else 0,
                  toc_pages[-1] if toc_pages else 0, len(rows), len(entries)))
    if len(rows) != len(entries):
        print('行数与 front_meta 不一致，中止（fail-closed）')
        for r in rows[:5]:
            print('  row:', r[1][:40], r[3])
        return 1

    n_link = 0
    for (pno, row_text, tbb, printed_pg, nbb), ent in zip(rows, entries):
        if norm(row_text) != display_key(ent):
            bad.append((ent['num'], ent['title'], '标题不符: %r' % row_text))
            continue
        if printed_pg != ent['page']:
            bad.append((ent['num'], ent['title'],
                        '印刷 %d ≠ meta %d' % (printed_pg, ent['page'])))
            continue
        if ent['level'] == 0:
            target = (ch_bm[int(ent['num'])] if ent['num'].isdigit()
                      and int(ent['num']) in ch_bm else ent['page'])
            ty = find_head_y(doc[target - 1], cfg)
        else:
            key = norm(ent['title'])
            hit = next((pg for k, pg in sec_bm if k == key), None)
            if hit is None:
                hit = next((pg for k, pg in sec_bm
                            if k.startswith(key[:10]) or key.startswith(k[:10])), None)
            if hit is None:
                bad.append((ent['num'], ent['title'], '书签无匹配'))
                continue
            if hit != ent['page']:
                bad.append((ent['num'], ent['title'],
                            '书签 p%d ≠ meta p%d' % (hit, ent['page'])))
                continue
            target = hit
            ty = find_title_y(doc[target - 1], ent['title'])

        for bb in (tbb, nbb):
            r = pymupdf.Rect(bb[0] - 2, bb[1] - 2, bb[2] + 2, bb[3] + 2)
            doc[pno - 1].insert_link({
                'kind': pymupdf.LINK_GOTO,
                'from': r,
                'page': target - 1,
                'to': pymupdf.Point(r.x0, ty if ty is not None else 0),
            })
            n_link += 1
    log.append('目录行链接 %d 个（标题区+页码区双区域）' % n_link)
    if bad:
        print('目录行一致性失败 %d 条（fail-closed）：' % len(bad))
        for b in bad[:20]:
            print('  ✗', b)
        return 1

    # ---- 2. 页眉「返回目录」----
    hdr_cfg = cfg.get('header_link') or {}
    x0 = hdr_cfg.get('x0', MARGIN_L)
    x1 = hdr_cfg.get('x1', MARGIN_L + 30)
    ymax = hdr_cfg.get('y_max', 60)
    back = 0
    for lvl, title, pg in doc.get_toc():
        if lvl != 1:
            continue
        page = doc[pg - 1]
        hdr = None
        for txt, bb in get_lines(page):
            if cfg['header_text'] in txt and bb[1] < ymax:
                hdr = bb
                break
        if not hdr:
            continue
        page.insert_link({
            'kind': pymupdf.LINK_GOTO,
            'from': pymupdf.Rect(x0, hdr[1] - 1, x1, hdr[3] + 1),
            'page': int(cfg['toc_start_page']) - 1,
            'to': pymupdf.Point(0, 0),
        })
        back += 1
        n_link += 1
    log.append('页眉「返回目录」链接 %d 个' % back)

    # ---- 3. 保存（同文件必须 tmp + replace，AA7）----
    if os.path.normcase(dst) == os.path.normcase(src):
        tmp = dst + '.tmp'
        doc.save(tmp, garbage=4, deflate=True)
        doc.close()
        os.replace(tmp, dst)
    else:
        doc.save(dst, garbage=4, deflate=True)
        doc.close()

    print('=' * 74)
    print('统一目录跳转链接构建完成')
    print('=' * 74)
    for line in log:
        print(' ', line)
    print('-' * 74)
    print('链接总数 : %d' % n_link)
    print('输出     : %s' % dst)
    with pymupdf.open(dst) as v:
        tot = sum(len(v[i].get_links()) for i in range(v.page_count))
        print('回读校验 : %d 页，链接 %d 个，书签 %d 条'
              % (v.page_count, tot, len(v.get_toc())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
