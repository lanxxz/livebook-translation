# -*- coding: utf-8 -*-
"""给栅格图补译「旋转 90° 的竖排标签」（ocr_figs 抓不到的那一类）。

easyocr 只识别水平文字，竖排的侧栏名 / 坐标轴名 / 行标签会整条漏检，交付后
表现为「图里还剩几个竖排英文」。本脚本的套路：把图 rotate(-90) 让竖排变横排，
在该空间里擦英文、写中文，再 rotate(90) 转回 —— 中文于是与原书一样是旋转的。

用法：
    python apply_rot_labels.py <figs_dir> [--map work/rot_labels.json]

映射文件（坐标是**旋转后**图像里的像素框，用 rotate(-90, expand=True) 的坐标；
可由「旋转 90° 再 OCR」得到，也可先在 300dpi 图上量）：
{
  "p7_f0": {
    "labels": [
      {"rotbox": [300, 8, 362, 36],  "cn": "核心"},
      {"rotbox": [264, 1038, 398, 1068], "cn": "评估"}
    ]
  }
}

要点（pitfalls AD2）：
- 竖排密集小字多是标识符（Evals·Metrics·LLMOps…），按 KEEP 保留英文，不为「零英文」硬塞；
- 只处理映射里列出的图，其它图跳过；图不存在也跳过（幂等，可整目录跑）；
- 依赖同目录 fig_raster.py 的 erase_labels / _font（本地底色擦除 + 中文字体）。
"""
import argparse
import json
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw            # noqa: E402
import numpy as np                          # noqa: E402
from fig_raster import erase_labels, _font  # noqa: E402


def _fit_cn(text, box_w, box_h):
    """在 box_w×box_h 里求最大可用字号。"""
    for fs in range(int(box_h * 0.92), 6, -1):
        if _font(fs).getlength(text) <= box_w:
            return fs
    return 7


def apply_one(png, spec):
    img = Image.open(png).convert('RGB')
    rot = img.rotate(-90, expand=True)         # 竖排 → 横排
    n = 0
    for lab in spec.get('labels', []):
        rb = [int(v) for v in lab['rotbox']]
        arr = np.array(rot)
        box = erase_labels(rot, arr, {'px_bbox': rb, 'bbox': rb})
        rot.paste(Image.fromarray(arr))
        x0, y0, x1, y1 = box if box else rb
        bw, bh = x1 - x0, y1 - y0
        if bw < 6 or bh < 6:
            continue
        cn = lab['cn']
        fs = _fit_cn(cn, bw - 4, bh)
        f = _font(fs)
        tx = x0 + (bw - f.getlength(cn)) / 2
        ty = y0 + (bh - fs) / 2
        sub = np.array(rot)[y0:y1, x0:x1, :3]
        fg = (0, 0, 0) if (sub.size == 0 or np.median(sub) > 127) else (255, 255, 255)
        ImageDraw.Draw(rot).text((tx, ty), cn, font=f, fill=fg)
        n += 1
    rot.rotate(90, expand=True).save(png)       # 转回原方向
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('figdir', help='渲染后的图目录（含 <key>.png）')
    ap.add_argument('--map', default=None, help='竖排映射 JSON（默认试 work/rot_labels.json）')
    a = ap.parse_args()

    mp = a.map
    if not mp:
        for cand in ('work/rot_labels.json', 'rot_labels.json'):
            if os.path.exists(cand):
                mp = cand
                break
    if not mp or not os.path.exists(mp):
        print('未找到竖排映射 JSON（--map）'); return 0

    spec_all = json.load(open(mp, encoding='utf-8'))
    total = 0
    for key, spec in spec_all.items():
        png = os.path.join(a.figdir, key + '.png')
        if not os.path.exists(png):
            continue
        c = apply_one(png, spec)
        print('  竖排补译 %s: %d 个标签' % (key, c))
        total += c
    print('合计竖排补译 %d 个标签' % total)
    return 0


if __name__ == '__main__':
    sys.exit(main())
