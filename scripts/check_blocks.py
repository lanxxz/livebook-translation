# -*- coding: utf-8 -*-
"""检查整块是否被分页切开 + 前置页是否残留编号。

两项都是「audit 全绿但用户一眼看出问题」的类型，必须单独跑。

用法：
    python check_blocks.py out/pdf/全书.pdf
    python check_blocks.py out/pdf/全书.pdf --fills 0.969,0.961,0.910

退出码：0 = 通过；1 = 有问题
"""
import argparse
import sys
from collections import defaultdict

try:
    import pymupdf
except ImportError:
    sys.exit('需要 pymupdf：pip install pymupdf')

TOP = 62.0      # 页眉下沿
BOT = 795.0     # 页脚上沿
# 侧栏 / 便签的常见填充色（docx hex → PDF 0~1）
DEFAULT_FILLS = [
    (0.969, 0.961, 0.910),   # F7F5E8 侧栏
    (0.949, 0.961, 0.973),   # F2F5F8 便签
    (0.929, 0.945, 0.961),   # EDF1F5
    (0.984, 0.969, 0.925),   # FBF7EC callout
]


def close(c, t, tol=0.02):
    return all(abs(a - b) <= tol for a, b in zip(c, t))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('--fills', help='逗号分隔的 r,g,b（0~1），覆盖默认色')
    ap.add_argument('--width-tol', type=int, default=12)
    args = ap.parse_args()

    fills = DEFAULT_FILLS
    if args.fills:
        vals = [float(x) for x in args.fills.split(',')]
        fills = [tuple(vals)]

    d = pymupdf.open(args.pdf)
    bot, top = defaultdict(list), defaultdict(list)
    for i in range(d.page_count):
        for dr in d[i].get_drawings():
            f = dr.get('fill')
            if not f or not any(close(f, t) for t in fills):
                continue
            r = dr['rect']
            if r.width < 80 or r.height < 15:
                continue
            if r.y1 >= BOT:
                bot[i + 1].append(round(r.width))
            if r.y0 <= TOP:
                top[i + 1].append(round(r.width))

    pairs = []
    for p, ws in bot.items():
        for w in set(ws):
            if any(abs(w - w2) <= args.width_tol for w2 in top.get(p + 1, [])):
                pairs.append((p, p + 1, w))
                break

    bad_no = [i + 1 for i in range(d.page_count)
              if '第\u3000章' in d[i].get_text('text')]
    cover_imgs = len(d[0].get_image_info())

    print(f'被分页切开的整块: {len(pairs)} 处')
    for a, b, w in pairs[:20]:
        print(f'   p{a} → p{b}  宽≈{w}px')
    print(f'残留「第　章」的页: {len(bad_no)} {bad_no[:10]}')
    print(f'封面图片数: {cover_imgs}')

    ok = (not pairs) and (not bad_no)
    print('结论:', '✓ 通过' if ok else '✗ 需修')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
