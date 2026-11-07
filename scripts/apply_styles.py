# -*- coding: utf-8 -*-
"""从原书 PDF 还原版式语义，给 book_layout.json 的块加 `style` 字段。

**只加字段，不改块数/顺序/type**，所以骨架与译文块号不变，双闸门不受影响。
style 需由 convert.py 透传到 _trans.json，再由 build_docx.py 渲染（见 pitfalls X19）。

用法：
    python apply_styles.py --config styles.json [--root 项目根]

配置 styles.json（全部可选）：
{
  "sidebar_fill": [0.97, 0.96, 0.91],   // 侧栏框填充色，容差 0.03
  "sidebar_min_w": 200, "sidebar_min_h": 25,
  "chapter_open_pages": [20, 35],        // 这些页的框由 chapter_open 自己渲染，跳过
  "part_pages": [19, 55],                // 部分扉页，打 part_title
  "dialog_blocks": {"ch02": [29,30,31,32]},  // 按分册块号指定对话块
  "warning_prefix": ["WARNING"],
  "tip_prefix": ["TIP", "NOTE", "DEFINITION"]
}

打完标后必须重跑：slice_layout.py → clean_front.py → mk_skeleton.py。
渲染层需要：段落底纹 w:shd + 侧边线 w:pBdr；带 style 的块不参与段落自动合并。
"""
import argparse
import json
import os
import re
import sys

try:
    import pymupdf
except ImportError:
    sys.exit('需要 pymupdf：pip install pymupdf')


def find_root(p):
    if p:
        return os.path.abspath(p)
    d = os.getcwd()
    for _ in range(4):
        if os.path.exists(os.path.join(d, 'book.json')):
            return d
        d = os.path.dirname(d)
    return os.getcwd()


def block_rect(b):
    r = b.get('bbox')
    if r and len(r) == 4:
        return pymupdf.Rect(r)
    y0, y1 = b.get('y0'), b.get('y1')
    if y0 is not None and y1 is not None:
        return pymupdf.Rect(0, y0, 600, y1)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    ap.add_argument('--root')
    a = ap.parse_args()
    root = find_root(a.root)
    work = os.path.join(root, 'work')
    cfg = json.load(open(a.config, encoding='utf-8'))
    fill = cfg.get('sidebar_fill', [0.97, 0.96, 0.91])
    min_w = cfg.get('sidebar_min_w', 200)
    min_h = cfg.get('sidebar_min_h', 25)
    skip_pages = set(cfg.get('chapter_open_pages') or [])
    part_pages = set(cfg.get('part_pages') or [])
    warn_re = re.compile(r'^(?:' + '|'.join(
        cfg.get('warning_prefix') or ['WARNING']) + r')\b', re.I)
    tip_re = re.compile(r'^(?:' + '|'.join(
        cfg.get('tip_prefix') or ['TIP', 'NOTE', 'DEFINITION']) + r')\b', re.I)

    book = json.load(open(os.path.join(work, 'book_layout.json'),
                          encoding='utf-8'))
    pdf = json.load(open(os.path.join(root, 'book.json'),
                         encoding='utf-8'))['pdf']
    doc = pymupdf.open(pdf)
    counts = {}

    def mark(b, style):
        b['style'] = style
        counts[style] = counts.get(style, 0) + 1

    # 1. 侧栏框：按 fill 色从 drawings 提取 bbox
    boxes = {}
    for i in range(doc.page_count):
        pno = i + 1
        if pno in skip_pages:
            continue
        for dr in doc[i].get_drawings():
            f, r = dr.get('fill'), dr.get('rect')
            if not f or not r or r.width < min_w or r.height < min_h:
                continue
            if all(abs(f[k] - fill[k]) < 0.03 for k in range(3)):
                boxes.setdefault(pno, []).append(pymupdf.Rect(r))

    for pn, blks in book['pages'].items():
        pno = int(pn)
        sbs = boxes.get(pno, [])
        if sbs:
            hit = []
            for j, b in enumerate(blks):
                r = block_rect(b)
                if r is None:
                    continue
                for box in sbs:
                    inter = r & box
                    if not inter.is_empty and \
                            inter.get_area() > 0.35 * max(1, r.get_area()):
                        hit.append(j)
                        break
            titles = []
            for box in sbs:
                t = doc[pno - 1].get_text(clip=box).strip()
                if t:
                    titles.append(t.split('\n')[0].strip())
            for j, b in enumerate(blks):
                txt = (b.get('text') or '').strip()
                is_title = any(t and (t[:24] in txt or txt[:24] in t)
                               for t in titles)
                if j in hit:
                    mark(b, 'sidebar_head' if is_title else 'sidebar_body')
                elif b['type'] == 'heading' and is_title:
                    mark(b, 'sidebar_head')

        for b in blks:
            t = (b.get('text') or '').strip()
            if warn_re.match(t):
                mark(b, 'warning')
            elif tip_re.match(t):
                mark(b, 'tip')

        if pno in part_pages:
            for b in blks:                     # 第一块常是被过滤的装饰 figure
                if b['type'] not in ('figure', 'table'):
                    mark(b, 'part_title')
                    break

    # 2. 对话块：按分册块号清单，用 (页, 文本前缀) 回写全书
    for did, nums in (cfg.get('dialog_blocks') or {}).items():
        p = os.path.join(work, did + '_layout.json')
        if not os.path.exists(p):
            print(f'!! 缺 {did}_layout.json，跳过对话标记', file=sys.stderr)
            continue
        lay = json.load(open(p, encoding='utf-8'))['pages']
        keys, i = set(), 0
        for pn in sorted(lay, key=int):
            for b in lay[pn]:
                if i in set(nums):
                    t = (b.get('text') or
                         ' '.join(b.get('items') or [])).strip()[:60]
                    keys.add((pn, t))
                i += 1
        for pn, blks in book['pages'].items():
            for b in blks:
                if b.get('style'):
                    continue
                t = (b.get('text') or
                     ' '.join(b.get('items') or [])).strip()[:60]
                if (pn, t) in keys:
                    mark(b, 'dialog')

    json.dump(book, open(os.path.join(work, 'book_layout.json'), 'w',
                         encoding='utf-8'), ensure_ascii=False, indent=1)
    print('样式标记：', counts)
    print('侧栏框：', sum(len(v) for v in boxes.values()), '个 /',
          len(boxes), '页')
    doc.close()


if __name__ == '__main__':
    main()
