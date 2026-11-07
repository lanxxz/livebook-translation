# -*- coding: utf-8 -*-
"""栅格图的图内文字擦除 + 中文写入（可直接复用，改两处常量即可）。

这份实现是 374 页 / 80 张 PNG 图实战里重写 9 次后的稳定版。
每一条判据都对应一次真实失败，见 references/pitfalls.md 的 T1–T5。

依赖：numpy / Pillow / scipy（不需要 cv2；inpaint 会把灰条重建出黑抹）

对外只有一个入口：

    from fig_raster import process_figure
    report = {}
    process_figure(png_path, blocks, trans, report)

    blocks / trans 的格式与 render_figs.py 的 figtexts/figtrans 一致：
      blocks = [{'id':0,'en':'Send Data','px_bbox':[x0,y0,x1,y1],
                 'h_pt':7.2,'bbox':[...]}, ...]
      trans  = {'0': '发送数据', '1': 'SAME', ...}

报告键：rendered / kept / MISSING / OVERFLOW / SMALL
交付闸门：MISSING 必须 0、OVERFLOW 必须 0；SMALL 与 kept 写进交付说明。
"""
import os
import re
from collections import Counter

# W13：必须在 import numpy 之前固化，防止 OpenBLAS 多线程内存错误导致擦图进程静默退出
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- 配置
CN_FONT_CANDIDATES = [
    r'C:\Windows\Fonts\msyh.ttc',
    r'C:\Windows\Fonts\simhei.ttf',
    r'C:\Windows\Fonts\simsun.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/System/Library/Fonts/PingFang.ttc',
]
MIN_FS = 6.0            # 像素
MAX_FS = 120.0          # 像素
PITCH_MIN = 1.14        # 行距下限（再压就挤在一起）
OVERFLOW_H = 6.0        # 高度超出百分比阈值

# 术语保护：这些复合词整体不拆，否则「提示词模板」会被切成「提示/词/模板」
PROTECTED = []

FPATH = None


def _font_path():
    global FPATH
    if FPATH is None:
        if os.path.exists('book.json'):
            # 项目内运行：book.json 的 font_cn 配置优先（配错会报错，不静默回退）
            from bookconf import font_file
            FPATH = font_file('font_cn')
        else:
            for p in CN_FONT_CANDIDATES:
                if os.path.exists(p):
                    FPATH = p
                    break
            if FPATH is None:
                raise SystemExit('未找到中文字体，请改 CN_FONT_CANDIDATES '
                                 '或在 book.json 配置 "font_cn"')
    return FPATH


def _font(size):
    return ImageFont.truetype(_font_path(), max(6, int(round(size))))


# ---------------------------------------------------------------- 断行
_TOKEN = re.compile(r'[A-Za-z0-9_\-\.\'\(\)\[\]\{\}\*/:=<>!&|%#@$~\^\\]+|\s+|.')
NO_HEAD = set('，。、；：？！）》」』】,.;:?!)%')
NO_TAIL = set('（《「『【(')


def tokenize(text):
    """中英混排 token 化：英文/标识符整体、中文按术语保护表优先整体。"""
    toks = []
    for t in _TOKEN.findall(text):
        if not t:
            continue
        if t.isspace():
            if toks and toks[-1] != ' ':
                toks.append(' ')
            continue
        if not re.match(r'[\u4e00-\u9fff]', t):
            toks.append(t)
            continue
        i = 0
        while i < len(t):
            hit = None
            for term in sorted(PROTECTED, key=len, reverse=True):
                if t.startswith(term, i):
                    hit = term
                    break
            if hit:
                toks.append(hit)
                i += len(hit)
            else:
                toks.append(t[i])
                i += 1
    while toks and toks[0] == ' ':
        toks.pop(0)
    while toks and toks[-1] == ' ':
        toks.pop()
    return toks


def wrap_cn(text, font, limit):
    """按词断行；禁标点行首、禁开括号行尾。"""
    toks = tokenize(text)
    if not toks:
        return ['']
    lines, cur = [], ''
    for tk in toks:
        if tk == ' ' and not cur:
            continue
        cand = cur + tk
        if font.getlength(cand) <= limit or not cur:
            cur = cand
        else:
            lines.append(cur.rstrip())
            cur = '' if tk == ' ' else tk
    if cur.strip():
        lines.append(cur.rstrip())
    for i in range(1, len(lines)):
        while lines[i] and lines[i][0] in NO_HEAD and len(lines[i - 1]) > 1:
            lines[i] = lines[i - 1][-1] + lines[i]
            lines[i - 1] = lines[i - 1][:-1]
    for i in range(len(lines) - 1):
        while lines[i] and lines[i][-1] in NO_TAIL:
            lines[i + 1] = lines[i][-1] + lines[i + 1]
            lines[i] = lines[i][:-1]
    return [l for l in lines if l.strip()]


# ---------------------------------------------------------------- 颜色判据
def fg_is_light(arr):
    """底色偏深且存在明显更亮的像素 → 图上写的是浅色字（彩块白字）。

    #FF9800 中位亮度 ≈152、#00ADD8 ≈121 → 触发；白纸 ≈255 → 不触发。
    不看这一步会把整块彩色当墨涂白、白字也被擦掉（pitfalls T2）。
    """
    lum = arr[:, :, :3].astype(float).mean(2)
    if lum.size < 16:
        return False
    med = float(np.median(lum))
    if med > 170:
        return False
    return float(np.percentile(lum, 95)) - med > 60


def visible_ratio(arr):
    """文字是否真的可见。用亮度差，不用颜色差（彩色底上颜色差恒成立）。"""
    h, w = arr.shape[:2]
    sub = arr[int(h * .25):max(1, int(h * .75)),
              int(w * .25):max(1, int(w * .75)), :3].astype(float)
    lum = sub.mean(2)
    if lum.size < 4:
        return 0.0
    return float((np.abs(lum - np.median(lum)) > 40).mean())


# ---------------------------------------------------------------- 擦除
def erase_labels(img, arr, block):
    """擦掉本块字形，用**本地底色**填回。

    判据 = 「bbox 内墨 − 长线/厚块保护」；填充 = 「掩膜以外像素的中位色」。
    九次失败换来的唯一稳定组合（pitfalls T1）。
    """
    from scipy import ndimage

    H, W = arr.shape[:2]
    x0, y0, x1, y1 = [int(round(v)) for v in block['px_bbox']]
    bh = max(6, y1 - y0)
    pad_x = int(bh * 0.35)
    rx0, rx1 = max(0, x0 - pad_x), min(W, x1 + pad_x)
    ry0 = max(0, y0 - max(2, int(bh * 0.12)))
    ry1 = min(H, y1 + max(2, int(bh * 0.12)))
    if rx1 - rx0 < 8 or ry1 - ry0 < 8:
        return None

    sub = arr[ry0:ry1, rx0:rx1, :3]
    lum = sub.astype(float).mean(2)
    med = float(np.median(lum))
    light = fg_is_light(sub)

    ink = (lum > med + 40) if light else (lum < float(np.percentile(lum, 92)) - 45)
    if ink.sum() < 6:
        return None

    # 结构保护：长横线 / 长竖线 / 厚块（方框边、箭头杆、连线）
    kx = max(9, int(bh * 1.5))
    kk = max(9, int(bh * 0.5))
    guard = ndimage.binary_dilation(
        ndimage.binary_opening(ink, np.ones((1, kx)))
        | ndimage.binary_opening(ink, np.ones((kx, 1)))
        | ndimage.binary_opening(ink, np.ones((kk, kk))),
        np.ones((3, 3)))

    kill = ink & ~guard
    if kill.sum() < 6:
        return None
    kill = ndimage.binary_dilation(kill, np.ones((3, 3))) & ~guard

    ys, xs = np.where(kill)
    tight = (max(rx0 + int(xs.min()), x0 - pad_x),
             max(ry0 + int(ys.min()), y0 - 4),
             min(rx0 + int(xs.max()) + 1, x1 + pad_x),
             min(ry0 + int(ys.max()) + 1, y1 + 4))

    # 本地底色（不是全图纸色：灰条 #B0B0B0 / 白框 #FFFFFF 都能就地取到）
    bgmask = ~ndimage.binary_dilation(kill, np.ones((5, 5)))
    bg = (np.median(sub[bgmask], axis=0) if bgmask.sum() >= 30
          else np.array([float(np.percentile(lum, 85))] * 3))

    patch = sub.copy()
    patch[kill] = bg
    arr[ry0:ry1, rx0:rx1, :3] = patch
    # ← 这一行漏了，输出就与原图字节相同（pitfalls T5）
    img.paste(Image.fromarray(arr))
    return tight


# ---------------------------------------------------------------- 排版
def fit(cn, bw, bh, h_pt, scale):
    """在给定框内求字号与断行。宽高都要检查（只查宽度会上下各溢出半个字）。"""
    fs = min(MAX_FS, max(MIN_FS, h_pt * scale * 0.92))
    limit = bw + max(1.0, bw * 0.06)
    best = None
    while fs >= MIN_FS:
        f = _font(fs)
        lines = wrap_cn(cn, f, limit)
        pitch = 1.22
        if len(lines) * fs * pitch > bh:
            pitch = max(PITCH_MIN, bh / max(1, len(lines) * fs))
        tw = max((f.getlength(l) for l in lines), default=0)
        th = len(lines) * fs * pitch
        ow = (tw - bw) / max(1.0, bw) * 100
        oh = (th - bh) / max(1.0, bh) * 100
        best = (fs, lines, pitch, ow, oh)
        if ow <= 4.0 and oh <= 4.0:
            break
        fs -= max(0.5, fs * 0.06)
    return best


# ---------------------------------------------------------------- 主入口
ASCII_ONLY = re.compile(r'[A-Za-z0-9\s_\-\.\'\(\):;,\[\]\{\}\*/=<>!&|%#@$~^\\]+')


def should_keep(block):
    """这些块保留英文原样。只看**原文**，不看译文（中文当然不含拉丁字母）。"""
    w = block['bbox'][2] - block['bbox'][0]
    h = block['bbox'][3] - block['bbox'][1]
    en = (block.get('en') or '').strip()
    if w < 12 and h < 12:
        return True, '迷你框'
    if not re.search(r'[A-Za-z]', en):
        return True, '原文无字母'
    if ASCII_ONLY.fullmatch(en) and len(en) <= 3:
        return True, '短标识符'
    return False, ''


def process_figure(png_path, blocks, trans, report, scale=None,
                   out_path=None):
    """处理一张图。两阶段：先擦完所有块，再统一画中文（pitfalls T3）。"""
    img = Image.open(png_path).convert('RGB')
    arr = np.array(img)
    if scale is None:
        # 由 px_bbox 与 bbox 反推 px-per-pt，避免写死 300dpi
        for b in blocks:
            bw_px = b['px_bbox'][2] - b['px_bbox'][0]
            bw_pt = b['bbox'][2] - b['bbox'][0]
            if bw_px > 0 and bw_pt > 0:
                scale = bw_px / bw_pt
                break
        scale = scale or (300 / 72.0)

    # 纵向避让带：只与横向重叠的邻块比，且不低于原字高 80%
    plan = []
    bs = list(blocks)
    for i, b in enumerate(bs):
        cn = (trans.get(str(b['id'])) or '').strip()
        if cn in ('SAME', '='):
            report['kept'].append({'id': b['id'], 'en': b['en'], 'why': 'SAME'})
            continue
        if not cn:
            report['MISSING'].append({'id': b['id'], 'en': b['en']})
            continue
        keep, why = should_keep(b)
        if keep:
            report['kept'].append({'id': b['id'], 'en': b['en'], 'why': why})
            continue
        bx0, bx1 = b['px_bbox'][0], b['px_bbox'][2]
        cy = (b['px_bbox'][1] + b['px_bbox'][3]) / 2.0
        bh = max(6.0, b['px_bbox'][3] - b['px_bbox'][1])
        near = max(bh * 1.8, 20.0)
        cols = [c for j, c in enumerate(bs) if j != i
                and min(bx1, c['px_bbox'][2]) - max(bx0, c['px_bbox'][0])
                > 0.25 * min(bx1 - bx0, c['px_bbox'][2] - c['px_bbox'][0])]
        above = [(c['px_bbox'][1] + c['px_bbox'][3]) / 2.0 for c in cols
                 if (c['px_bbox'][1] + c['px_bbox'][3]) / 2.0 < cy
                 and cy - (c['px_bbox'][1] + c['px_bbox'][3]) / 2.0 < near]
        below = [(c['px_bbox'][1] + c['px_bbox'][3]) / 2.0 for c in cols
                 if (c['px_bbox'][1] + c['px_bbox'][3]) / 2.0 > cy
                 and (c['px_bbox'][1] + c['px_bbox'][3]) / 2.0 - cy < near]
        b = dict(b)
        b['_lo'] = (max(above) + cy) / 2.0 if above else None
        b['_hi'] = (min(below) + cy) / 2.0 if below else None
        plan.append((b, cn))

    # 阶段 1：全部擦除
    prepared = []
    for b, cn in plan:
        x0, y0, x1, y1 = [int(round(v)) for v in b['px_bbox']]
        sub = arr[max(0, y0):y1, max(0, x0):x1]
        vis = visible_ratio(sub) if sub.size else 0
        box = None
        if vis >= 0.004:
            box = erase_labels(img, arr, b)
            arr = np.array(img)
        if box:
            x0, y0, x1, y1 = box
        if b.get('_lo') is not None:
            y0 = max(y0, int(b['_lo']))
        if b.get('_hi') is not None:
            y1 = min(y1, int(b['_hi']))
        bw, bh = x1 - x0, y1 - y0
        bh = max(bh, int((b.get('h_pt') or 8.0) * scale * 0.8))
        if bw < 4 or bh < 4:
            continue
        fs, lines, pitch, ow, oh = fit(cn, bw, bh, b.get('h_pt') or 8.0, scale)
        if oh > OVERFLOW_H:
            report['OVERFLOW'].append({'id': b['id'], 'en': b['en'], 'cn': cn,
                                       'over_w': round(ow, 1),
                                       'over_h': round(oh, 1)})
        f = _font(fs)
        tw = max((f.getlength(l) for l in lines), default=0)
        th = len(lines) * fs * pitch
        prepared.append({'fs': fs, 'lines': lines, 'pitch': pitch,
                         'fg': (255, 255, 255) if fg_is_light(sub) else (0, 0, 0),
                         'tx': x0 + max(0, (bw - tw) / 2),
                         'ty': y0 + max(0, (bh - th) / 2),
                         'id': b['id'], 'en': b['en'], 'cn': cn,
                         'fs_pt': round(fs / scale, 2)})

    # 阶段 2：统一绘制
    draw = ImageDraw.Draw(img)
    for d in prepared:
        f = _font(d['fs'])
        for i, ln in enumerate(d['lines']):
            draw.text((d['tx'], d['ty'] + i * d['fs'] * d['pitch']), ln,
                      font=f, fill=d['fg'])
        report['rendered'].append(d)
        if d['fs_pt'] < 5.0:
            report['SMALL'].append(d)

    dst = out_path or png_path
    img.save(dst)
    # 自检：输出必须与原图不同（防「报告全绿但图没变」）
    return not np.array_equal(np.array(Image.open(png_path).convert('RGB')), arr)
