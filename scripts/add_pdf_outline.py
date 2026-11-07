# -*- coding: utf-8 -*-
"""给合订 PDF 写「章 + 小节」两级书签（X11）。

`build_final_book.py` / `merge_book.py` 通常只写章节级书签；本脚本从各分册
`_trans.json` 的 h2/h3 中文标题出发，在「该分册在合订本中的页区间」内定位
实际页，追加二级书签。**必须接进重建链**（`finalize.py`），否则一重建就退化。

用法：
    python add_pdf_outline.py [合订PDF] [--root 项目根]

依赖：
    docs.json                    文档清单（含 kind / num / title / after）
    work/final_pages.json        各分册在合订本中的起始页（目录两轮校准产物）
    work/<doc>_trans.json        各分册译文（取 h2/h3 标题）
    out/pdf/<分册名>.pdf        各分册 PDF（用于算页区间）
"""
import argparse
import json
import os
import re
import sys

import pymupdf


def find_root(p):
    if p:
        return os.path.abspath(p)
    d = os.getcwd()
    for _ in range(4):
        if os.path.exists(os.path.join(d, 'docs.json')):
            return d
        d = os.path.dirname(d)
    return os.getcwd()


def out_name(d):
    k, n = d.get('kind', 'ch'), d['num']
    if k == 'front':
        return '00_' + d['title']
    if k == 'part':
        return f"P{n}_第{n}部分_{d['title']}"
    if k == 'apx':
        return f"{n}_附录{n}_{d['title']}"
    return f'{int(n):02d}_第{n}章_{d["title"]}'


def label(d):
    k, n = d.get('kind', 'ch'), d['num']
    if k == 'front':
        return '前言与导读'
    if k == 'part':
        return f'第 {n} 部分　{d["title"]}'
    if k == 'apx':
        return f'附录 {n}　{d["title"]}'
    return f'第 {n} 章　{d["title"]}'


def sort_key(d):
    k = d.get('kind', 'ch')
    if k in ('cover', 'front'):
        return (0, 0)
    if k == 'part':
        return (1, float(d.get('after', 0)) + 0.5)
    if k == 'apx':
        return (2, ord(str(d['num'])[0]))
    return (1, int(d['num']))


def norm(s):
    return re.sub(r'\s+', '', s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf', nargs='?', help='合订 PDF 路径')
    ap.add_argument('--root', help='项目根（含 docs.json）')
    a = ap.parse_args()
    root = find_root(a.root)
    work = os.path.join(root, 'work')
    pdfdir = os.path.join(root, 'out', 'pdf')

    pdf = a.pdf
    if not pdf:
        cands = [f for f in os.listdir(pdfdir)
                 if f.endswith('.pdf') and ('全本' in f or '全书' in f)]
        if len(cands) != 1:
            sys.exit('请显式指定合订 PDF 路径（out/pdf 下无法唯一确定）')
        pdf = os.path.join(pdfdir, cands[0])

    cfg = json.load(open(os.path.join(root, 'book.json'), encoding='utf-8'))
    title = cfg.get('book_title', '中文版')
    pages = json.load(open(os.path.join(work, 'final_pages.json'),
                           encoding='utf-8'))
    docs = sorted(json.load(open(os.path.join(root, 'docs.json'),
                                encoding='utf-8')), key=sort_key)
    book = pymupdf.open(pdf)
    toc, stat, last = [], [], 1
    for d in docs:
        did = d['id']
        start = pages.get(did)
        if not start:
            continue
        sub = os.path.join(pdfdir, out_name(d) + '.pdf')
        n = pymupdf.open(sub).page_count if os.path.exists(sub) else 1
        end = min(book.page_count, start + n - 1)
        toc.append([1, label(d), start])
        last = start
        tp = os.path.join(work, did + '_trans.json')
        heads = []
        if os.path.exists(tp):
            heads = [b['text'].strip()
                     for b in json.load(open(tp, encoding='utf-8'))
                     if b.get('type') in ('h2', 'h3') and b.get('text', '').strip()]
        added = 0
        for h in heads:
            key = norm(h)[:14]
            if len(key) < 4:
                continue
            hit = next((i + 1 for i in range(start - 1, end)
                        if key in norm(book[i].get_text())), None)
            if hit and hit >= last:
                toc.append([2, h, hit])
                last = hit
                added += 1
        stat.append((did, len(heads), added))
    toc.append([1, '中英术语索引', book.page_count])
    # 校验
    backwards = sum(1 for i in range(1, len(toc)) if toc[i][2] < toc[i - 1][2])
    outside = [x for x in toc if not 1 <= x[2] <= book.page_count]
    book.set_toc(toc)
    book.saveIncr()
    print(f'{title}：一级 {sum(1 for x in toc if x[0]==1)} 条 / '
          f'二级 {sum(1 for x in toc if x[0]==2)} 条，合计 {len(toc)} 条；'
          f'页码回跳 {backwards}，越界 {len(outside)}')
    for did, total, added in stat:
        print(f'  {did:8s} 标题 {total:3d} → 定位 {added:3d}')
    if backwards or outside:
        sys.exit(1)
    book.close()


if __name__ == '__main__':
    main()
