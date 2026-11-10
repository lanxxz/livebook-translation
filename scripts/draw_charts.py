# -*- coding: utf-8 -*-
"""matplotlib 统计图的图内中文化（标题 / 轴名 / 图例 / 标注）。

与 diagram 的差别：
  · 图里有大量**轴刻度数字**（0.70、2500、10^5…），这些不该动；
  · 文字多为深灰/黑色单一前景，白或浅灰底，擦除判据简单；
  · 轴标题是**旋转 90° 的竖排**，必须按竖排重排，否则中文会横着压到轴上。

只处理白名单里的图，输出到 figs_zh/<doc>/<key>.png，覆盖同名 diagram 结果。
用法：
    python tools/draw_charts.py            # 全部白名单
    python tools/draw_charts.py ch04_f03   # 指定
"""
import json
import os
import sys

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

from common import ROOT  # 项目根：向上找 book.json/docs.json，或 BOOK_ROOT
_HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, 'work')
OUTDIR = os.path.join(ROOT, 'figs_zh')
FONT = r'C:/Windows/Fonts/msyh.ttc'

# 只含这些文字的块不处理（轴刻度、纯数字）
import re
NUMERIC = re.compile(r'^[\s\-\+\.,%$€£¥\d\^eE×xX/()]+$')


def font(size):
    return ImageFont.truetype(FONT, max(8, int(round(size))))


def dominant_color(sub):
    q = (sub.astype(np.int16) // 12).reshape(-1, 3)
    key = (q[:, 0].astype(np.int32) << 16) | (q[:, 1].astype(np.int32) << 8) | q[:, 2]
    vals, counts = np.unique(key, return_counts=True)
    best = vals[int(np.argmax(counts))]
    return np.median(sub.reshape(-1, 3)[key == best], axis=0)


def erase(img, arr, box, bg_lum):
    H, W = arr.shape[:2]
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    pad = 2
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(W, x1 + pad), min(H, y1 + pad)
    if x1 - x0 < 5 or y1 - y0 < 5:
        return None
    sub = arr[y0:y1, x0:x1, :3]
    bg = dominant_color(sub)
    lum = sub.astype(float).mean(2)
    ink = (lum < bg_lum - 40) if bg_lum > 170 else (lum > bg_lum + 35)
    if ink.sum() < 4:
        return None
    # 只保护长线（轴线、网格线）
    bh = y1 - y0
    kx = max(25, int(bh * 3))
    guard = ndimage.binary_dilation(
        ndimage.binary_opening(ink, np.ones((1, kx)))
        | ndimage.binary_opening(ink, np.ones((kx, 1))), np.ones((2, 2)))
    kill = ink & ~guard
    if kill.sum() < 4:
        return None
    kill = ndimage.binary_dilation(kill, np.ones((3, 3))) & ~guard
    patch = sub.copy()
    patch[kill] = bg
    arr[y0:y1, x0:x1, :3] = patch
    img.paste(Image.fromarray(arr))
    return (x0, y0, x1, y1)


def wrap(text, f, limit):
    out, cur = [], ''
    for ch in text:
        if f.getlength(cur + ch) <= limit or not cur:
            cur += ch
        else:
            out.append(cur)
            cur = ch
    if cur:
        out.append(cur)
    return out or ['']


def rotate_crop(img, box):
    x0, y0, x1, y1 = box
    return img.crop((x0, y0, x1, y1))


def render(png, blocks, trans, out_path, vertical_ids=()):
    img = Image.open(png).convert('RGB')
    arr = np.array(img)
    plan = []
    for b in blocks:
        cn = (trans.get(str(b['id'])) or '').strip()
        if not cn or cn == 'SAME':
            continue
        if NUMERIC.match(b['en']):
            continue
        x0, y0, x1, y1 = b['px_bbox']
        bh = max(8, y1 - y0)
        sub = arr[max(0, y0 - 4):y1 + 4, max(0, x0 - 4):x1 + 4, :3]
        bg_lum = float(np.median(sub.astype(float).mean(2)))
        box = erase(img, arr, (x0, y0, x1, y1), bg_lum)
        arr = np.array(img)
        bx0, by0, bx1, by1 = box if box else (x0, y0, x1, y1)
        bw, bhh = bx1 - bx0, by1 - by0
        if bw < 8 or bhh < 8:
            continue
        fg = (30, 30, 30) if bg_lum > 150 else (250, 250, 250)
        vertical = str(b['id']) in vertical_ids
        if vertical:
            # 竖排轴名：一列一字。括号里的单位改成短式，否则字太多必然压刻度
            # 轴名不含单位时字太少、太挤；保留单位但要能装下。
            chars = [c for c in cn if c.strip()]
            # 先由原文字宽定上限（原竖排字的字宽≈条宽），再按条长均分，
            # 两者取小；这样 8 个汉字也能排满整条而不越界。
            fs = min(bw * 0.98, bhh / max(1, len(chars)) / 1.06)
            fs = max(8.0, min(fs, 14.0))   # 上限 14px：再大就压到刻度数字
            plan.append({'type': 'v', 'chars': chars, 'fs': fs,
                         'cx': bx0 + bw / 2, 'y0': by0, 'fg': fg})
        else:
            fs = min(bh * 0.95, 26)
            while fs >= 8:
                f = font(fs)
                lines = wrap(cn, f, max(bw + 12, bw * 1.6))
                if len(lines) * fs * 1.2 <= bhh + 3 and max(
                        (f.getlength(l) for l in lines), default=0) <= max(bw + 12, bw * 1.6):
                    break
                fs -= 0.5
            f = font(fs)
            lines = wrap(cn, f, bw + 2)
            tw = max((f.getlength(l) for l in lines), default=0)
            th = len(lines) * fs * 1.2
            plan.append({'type': 'h', 'lines': lines, 'fs': fs,
                         'x': bx0 + max(0, (bw - tw) / 2),
                         'y': by0 + max(0, (bhh - th) / 2), 'fg': fg})

    d = ImageDraw.Draw(img)
    for p in plan:
        f = font(p['fs'])
        if p['type'] == 'v':
            for i, c in enumerate(p['chars']):
                w = f.getlength(c)
                d.text((p['cx'] - w / 2, p['y0'] + i * p['fs'] * 1.12), c,
                       font=f, fill=p['fg'])
        else:
            for i, ln in enumerate(p['lines']):
                d.text((p['x'], p['y'] + i * p['fs'] * 1.2), ln, font=f,
                       fill=p['fg'])
    img.save(out_path)
    return len(plan)


def main():
    cfgp = os.path.join(WORK, 'chart_spec.json')
    if not os.path.exists(cfgp):
        sys.exit('缺 work/chart_spec.json')
    spec = json.load(open(cfgp, encoding='utf-8'))
    ocr = json.load(open(os.path.join(WORK, 'fig_ocr.json'), encoding='utf-8'))
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    keys = args or list(spec)
    tot = 0
    for k in keys:
        s = spec.get(k)
        if not s:
            print('!! 无 spec:', k); continue
        doc = ocr[k]['doc']
        os.makedirs(os.path.join(OUTDIR, doc), exist_ok=True)
        dst = os.path.join(OUTDIR, doc, k + '.png')
        blocks = list(ocr[k]['blocks'])
        zh = dict(s.get('zh', {}))
        vert = set(map(str, s.get('vertical', [])))
        # extra: OCR 漏检的块（多为旋转 90° 的 Y 轴名），手工给坐标
        for ex in s.get('extra', []):
            blocks.append({'id': ex['id'], 'en': ex['en'],
                           'px_bbox': ex['px_bbox']})
            zh[str(ex['id'])] = ex['zh']
            if ex.get('vertical', True):
                vert.add(str(ex['id']))
        n = render(ocr[k]['img'], blocks, zh, dst, vert)
        tot += n
        print('%-12s 渲染 %d 块 -> %s' % (k, n, dst))
    print('合计', tot)


if __name__ == '__main__':
    main()
