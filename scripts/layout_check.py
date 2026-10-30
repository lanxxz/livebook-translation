# -*- coding: utf-8 -*-
"""整书排版体检：专治"audit 全过、但排版看着不满意"。

audit.py / check_all.py 验的是**内容完整性**（块序列、漏译、图内溢出），
本脚本验的是**呈现质量**（页码、页眉、留白、行距、孤立碎片）。

用法：
    python layout_check.py out/pdf/全书.pdf

输出五项硬指标，全部为 0 / 正常才算排版过关：
  1. 页码错位页数        必须 0
  2. 页眉逐章变化        抽查页的页眉章名应各不相同
  3. 空白过半页数        章末页允许；正文中部出现就是问题
  4. 孤立碎片代码页      只有一行的灰底代码块（正文里不该有）
  5. 行距众数            应 ≈ 正文字号 × 1.4~1.6
"""
import collections
import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    import pymupdf
except ImportError:
    sys.exit('需要 pymupdf：pip install pymupdf')

FOOT_H = 60      # 页脚区高度
HEAD_H = 52      # 页眉区高度
BODY_TOP = 60
MIN_USED = 0.50  # 版心使用率低于此值算"留白过多"


def main():
    if len(sys.argv) < 2:
        sys.exit('用法：python layout_check.py <全书.pdf>')
    path = sys.argv[1]
    d = pymupdf.open(path)
    n = d.page_count
    print(f'== {path}  共 {n} 页 ==\n')

    # ---------- 1. 页码连续性 ----------
    bad_page = []
    for i in range(n):
        r = d[i].rect
        t = d[i].get_text(
            'text', clip=pymupdf.Rect(0, r.height - FOOT_H, r.width, r.height)
        ).strip()
        m = re.fullmatch(r'\d+', t)
        if m and int(m.group()) != i + 1:
            bad_page.append((i + 1, int(m.group())))
    print(f'1) 页码错位页数：{len(bad_page)}', end='')
    print('  ✓' if not bad_page else f'  ✗ {bad_page[:8]}')

    # ---------- 2. 页眉逐章 ----------
    heads = []
    step = max(1, n // 8)
    for i in range(1, n, step):
        r = d[i].rect
        h = d[i].get_text(
            'text', clip=pymupdf.Rect(0, 0, r.width, HEAD_H)
        ).strip().replace('\n', ' ')
        heads.append((i + 1, h))
    uniq = {h for _, h in heads}
    print(f'2) 页眉样式数：{len(uniq)}（抽查 {len(heads)} 页）', end='')
    print('  ✓' if len(uniq) > 1 else '  ✗ 全是同一个页眉，分组页眉没生效')
    for p, h in heads[:6]:
        print(f'     p{p}: {h[:64]}')

    # ---------- 3. 留白 ----------
    semi = []
    for i in range(n):
        r = d[i].rect
        body = pymupdf.Rect(r.x0, BODY_TOP, r.x1, r.height - FOOT_H)
        bl = [b for b in d[i].get_text('blocks', clip=body) if b[4].strip()]
        if not bl:
            semi.append((i + 1, 'EMPTY'))
            continue
        used = (max(b[3] for b in bl) - BODY_TOP) / (r.height - BODY_TOP - FOOT_H)
        if used < MIN_USED:
            semi.append((i + 1, round(used, 2)))
    print(f'\n3) 空白过半页数：{len(semi)}', end='')
    print('  （章末页属正常，正文中部请人工确认）')
    print(f'     {semi[:12]}')

    # ---------- 4. 孤立碎片代码页 ----------
    frag_pages = []
    for i in range(n):
        r = d[i].rect
        body = pymupdf.Rect(r.x0, BODY_TOP, r.x1, r.height - FOOT_H)
        bl = [b for b in d[i].get_text('blocks', clip=body) if b[4].strip()]
        if len(bl) == 1:
            txt = bl[0][4].strip()
            if len(txt) <= 40:
                frag_pages.append((i + 1, txt[:30]))
    print(f'\n4) 整页只有一行的页数：{len(frag_pages)}', end='')
    print('  ✓' if not frag_pages else f'  ✗ {frag_pages[:6]}')

    # ---------- 5. 行距与字号 ----------
    gaps = collections.Counter()
    sizes = collections.Counter()
    rng = range(20, min(n, 80))
    for i in rng:
        for b in d[i].get_text('dict')['blocks']:
            if b['type'] != 0:
                continue
            ys = [l['bbox'][3] for l in b['lines']]
            for a, c in zip(ys, ys[1:]):
                g = round(c - a, 1)
                if 10 < g < 40:
                    gaps[g] += 1
            for l in b['lines']:
                for s in l['spans']:
                    sizes[round(s['size'], 1)] += len(s['text'])
    if gaps:
        g, _ = gaps.most_common(1)[0]
        body_pt = sizes.most_common(1)[0][0] if sizes else 0
        # 注意：PDF 里量到的是**基线间距**，不含首行上方的行高。
        # 中文正文的基线间距经验区间是 字号 × 1.05~1.25；
        # 换算成 Word 的"多倍行距"约等于 (基线间距 / 字号) × 1.18。
        base_ratio = g / body_pt if body_pt else 0
        word_mult = base_ratio * 1.18 if body_pt else 0
        ok = 1.05 <= base_ratio <= 1.28
        print(f'\n5) 基线间距 {g}pt，正文字号 {body_pt}pt，'
              f'基线比 {base_ratio:.2f}（≈ Word 行距 {word_mult:.2f}）', end='')
        print('  ✓' if ok else '  ✗ 基线比建议 1.05~1.28；换算后 Word 行距 1.4~1.6 最耐读')

    print('\n判读：1、2、4 必须全绿；3 抽查章末页；5 只做参考。')


if __name__ == '__main__':
    main()
