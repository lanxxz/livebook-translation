# -*- coding: utf-8 -*-
"""给每张图分类：diagram（示意图）/ chart（统计图）/ shot（界面截图）。

**为什么是三类而不是两类**（pitfalls Z8）：把 matplotlib/seaborn 统计图当成「截图」
保留，会让中文版里有一堆英文图表。统计图的标题、轴名、图例都是独立文字块，
位置就是最终坐标，**和示意图一样可以原地中文化**；只有刻度数字不该动。

自动判据 + 人工修正表，两层叠加：

  自动（够用，但会被界面截图骗到）
    · 深色像素占比 > 0.45          → shot（深色 IDE / 终端）
    · OCR 文字块 > 60              → shot（表格状界面 / 报告页）
    · 其余                          → diagram

  人工（必须做，做完还要看 contact sheet）
    · CHART  集合：明确是统计图（有坐标轴/网格线/图例）
    · SHOT   集合：明确是界面截图，强制保留
    · 优先级：SHOT > CHART > 自动

用法：
    python fig_kind.py                # 分类并写 work/fig_kind.json
    python fig_kind.py --sheet        # 顺带出 contact sheet（24 张/版）
"""
import json
import os
import sys

from common import ROOT  # 项目根：向上找 book.json/docs.json，或 BOOK_ROOT

WORK = os.path.join(ROOT, 'work')
FIGS = os.path.join(ROOT, 'figs')

# 人工分类表放在 work/fig_kind_manual.json（不是写死在脚本里），
# 因为按新书重填时改 JSON 比改代码安全，也便于交付时附在项目里。

COLS, TW, TH, PER = 6, 300, 230, 24


def auto_kind(key, meta):
    """**只能做兜底初筛，不要当结论。**

    实测教训：75 张图里，把「深色占比」当判据会把 3 张示意图判成截图；
    换成「顶部白带 + 密集小字」又会把 70 张判成截图 —— **自动判据在这件事上不可靠**，
    因为示意图、统计图、网页截图在像素层面高度相似（都是白底 + 深色文字）。

    所以正确做法是：
      1. `--init` 出一份全部标成 diagram 的草稿表；
      2. 人（或代理）用 `--sheet` 出的 contact sheet 逐张改成 chart / shot；
      3. 分类结果存回 `work/fig_kind_manual.json`，这是唯一真相。

    本函数只处理两个极端，其余一律返回 None 交给人工表：
      · 深色占比 > 0.55 → shot（深色 IDE / 终端，几乎不会误判）
      · 其余            → None
    """
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        return None
    doc = key.split('_')[0]
    p = os.path.join(FIGS, doc, key + '.png')
    if not os.path.exists(p):
        return None
    a = np.array(Image.open(p).convert('L'))
    if float((a < 70).mean()) > 0.55:
        return 'shot'
    return None


def contact_sheet(ocr, kinds, outdir):
    """每版 24 张、标 key 的缩略图汇总 —— 75 张图 4 版就能看完全部分类。"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print('!! 需要 Pillow 才能出 contact sheet')
        return
    os.makedirs(outdir, exist_ok=True)
    keys = sorted(ocr)
    fnt = ImageFont.load_default()
    n = 0
    for si in range(0, len(keys), PER):
        chunk = keys[si:si + PER]
        rows = (len(chunk) + COLS - 1) // COLS
        sheet = Image.new('RGB', (COLS * TW, rows * TH), 'white')
        d = ImageDraw.Draw(sheet)
        for i, k in enumerate(chunk):
            doc = k.split('_')[0]
            p = os.path.join(FIGS, doc, k + '.png')
            cx, cy = (i % COLS) * TW, (i // COLS) * TH
            if os.path.exists(p):
                im = Image.open(p).convert('RGB')
                im.thumbnail((TW - 8, TH - 26))
                sheet.paste(im, (cx + 4, cy + 22))
            color = {'diagram': 'darkgreen', 'chart': 'darkorange'}.get(
                kinds.get(k), 'firebrick')
            d.text((cx + 4, cy + 5), '%s  [%s]' % (k, kinds.get(k)), fill=color, font=fnt)
        n += 1
        fp = os.path.join(outdir, 'sheet%d.png' % n)
        sheet.save(fp)
        print('sheet ->', fp)


def main():
    p = os.path.join(WORK, 'fig_ocr.json')
    if not os.path.exists(p):
        sys.exit('缺 work/fig_ocr.json，先跑 ocr_all.py')
    ocr = json.load(open(p, encoding='utf-8'))
    manual_p = os.path.join(WORK, 'fig_kind_manual.json')

    if '--init' in sys.argv or not os.path.exists(manual_p):
        # 草稿表：全部先标 diagram，等人工改（Z8）
        draft = {k: (auto_kind(k, m) or 'diagram') for k, m in sorted(ocr.items())}
        json.dump(draft, open(manual_p, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('已生成草稿分类表 work/fig_kind_manual.json（%d 张）' % len(draft))
        print('  下一步：跑 --sheet 出联系表，逐张把 chart / shot 改进去')
        print('  chart = matplotlib 统计图（标题/轴名/图例可中文化）')
        print('  shot  = IDE/终端/网页/报告页截图（整图保留）')

    manual = json.load(open(manual_p, encoding='utf-8'))
    out = {}
    for k in sorted(ocr):
        out[k] = manual.get(k) or auto_kind(k, ocr[k]) or 'diagram'

    json.dump(out, open(os.path.join(WORK, 'fig_kind.json'), 'w',
                        encoding='utf-8'), ensure_ascii=False, indent=1)
    from collections import Counter
    print(Counter(out.values()))
    for kind in ('diagram', 'chart', 'shot'):
        ks = sorted(k for k, v in out.items() if v == kind)
        print('%s (%d): %s' % (kind, len(ks), ks))
    if '--sheet' in sys.argv:
        contact_sheet(ocr, out, os.path.join(ROOT, 'out', 'sheet'))


if __name__ == '__main__':
    main()
