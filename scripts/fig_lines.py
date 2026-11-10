# -*- coding: utf-8 -*-
"""把 OCR 的碎片块合并成「视觉文本区域」，供图内中文化使用。

为什么需要这一步（实测教训）：
  · OCR 会把同一行切成多块（`linting` 与 `architecture policy;` 基线差 2px 就分家），
    逐块擦写 ⇒ 中文顺序错乱、英文残片留在行尾。
  · 一个卡片里的一段说明常被切成 4~6 行，逐行擦写 ⇒ 行距与对齐全乱。

合并规则：
  1) 行合并：垂直重叠 > 55% 且水平间隙 < 3 倍行高
  2) 区域合并：垂直间隙 < 0.9 倍行高 且 水平重叠 > 50%
反复迭代到不动点。
"""
import json
import os
import sys

from common import ROOT  # 项目根：向上找 book.json/docs.json，或 BOOK_ROOT
_HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, 'work')


def overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def merge_boxes(items):
    """只做**行内**合并（同基线、水平相邻），不做跨行的段落合并。

    跨行合并会把不同卡片/不同列表项连成一整块 —— 实测 ch01_f03 从 35 块合并成
    2 块，整张图的结构信息全丢。行内合并解决的是「OCR 把一行切碎」这一个问题。
    """
    items.sort(key=lambda b: (b['px_bbox'][1], b['px_bbox'][0]))
    out = []
    for it in items:
        a0, b0, a1, b1 = it['px_bbox']
        placed = False
        for g in out:
            x0, y0, x1, y1 = g['px_bbox']
            h = min(y1 - y0, b1 - b0)
            if h <= 0:
                continue
            vov = overlap(y0, y1, b0, b1)
            wgap = max(a0 - x1, x0 - a1)
            # 同基线 + 紧邻 + 字高相近（防把大标题与小注脚并到一起）
            hmax = max(y1 - y0, b1 - b0)
            if (vov > 0.7 * h and wgap < 1.6 * h
                    and h > 0.55 * hmax):
                g['px_bbox'] = [min(x0, a0), min(y0, b0),
                                max(x1, a1), max(y1, b1)]
                g['parts'].append(it)
                placed = True
                break
        if not placed:
            out.append({'px_bbox': list(it['px_bbox']), 'parts': [it]})
    for g in out:
        g['parts'].sort(key=lambda p: p['px_bbox'][0])
        g['en'] = ' '.join(p['en'] for p in g['parts'])
        g['px_bbox'] = [int(round(v)) for v in g['px_bbox']]
    out.sort(key=lambda g: (g['px_bbox'][1], g['px_bbox'][0]))
    return out


def main():
    ocr = json.load(open(os.path.join(WORK, 'fig_ocr.json'), encoding='utf-8'))
    kinds = json.load(open(os.path.join(WORK, 'fig_kind.json'), encoding='utf-8'))
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    keys = args or [k for k in sorted(ocr) if kinds[k] == 'diagram']
    out = {}
    nb = 0
    for k in keys:
        v = ocr[k]
        items = [{'en': b['en'], 'px_bbox': [float(x) for x in b['px_bbox']]}
                 for b in v['blocks']]
        if not items:
            out[k] = []
            continue
        merged = merge_boxes(items)
        rows = []
        for i, g in enumerate(merged):
            x0, y0, x1, y1 = [int(round(t)) for t in g['px_bbox']]
            rows.append({'id': i, 'en': g['en'],
                         'px_bbox': [x0, y0, x1, y1],
                         'bbox': [float(x0), float(y0), float(x1), float(y1)],
                         'h_px': y1 - y0, 'h_pt': (y1 - y0)})
            nb += 1
        out[k] = rows
        print('%s: %d -> %d' % (k, len(items), len(rows)))
    json.dump(out, open(os.path.join(WORK, 'fig_regions.json'), 'w',
                        encoding='utf-8'), ensure_ascii=False, indent=1)
    print('total regions', nb)


if __name__ == '__main__':
    main()
