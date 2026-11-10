# -*- coding: utf-8 -*-
"""图内中文化渲染器（本书专用，针对白底矢量框图优化）。

与通用 fig_raster 的区别 —— 逐条对应实测失败：
  E1 擦除不净：OCR bbox 往往比字形窄 2–6px，行尾留半截字母。
     → 擦除矩形按 **整行可见墨迹** 向外扩张，直到该行内不再有墨迹。
  E2 行内残留：一行由多个 OCR 块组成时，块间空隙里的字被漏掉。
     → 擦除前先把同一基线的块并成一个矩形（fig_lines 已做），再向外扩 pad。
  E3 结构受伤：方框边、箭头杆、连线被当成字擦掉。
     → 擦除前做「长线/厚块」结构保护（与 fig_raster 同思路，阈值按位图调）。
  E4 底色污染：擦成纯白，彩色底（浅黄卡片、浅蓝框）上留白补丁。
     → 用该矩形内**非墨迹像素的中位色**填回。

用法：
    python tools/draw_figs.py            # 全部 diagram
    python tools/draw_figs.py ch01_f02   # 指定
"""
import json
import os
import re
import sys

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

from common import ROOT  # 项目根：向上找 book.json/docs.json，或 BOOK_ROOT
_HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, 'work')
OUTDIR = os.path.join(ROOT, 'figs_zh')

FONT = r'C:/Windows/Fonts/msyh.ttc'
FONT_BD = r'C:/Windows/Fonts/msyhbd.ttc'

PROTECTED = ['上下文压舱物', '上下文窗口', '检索增强', '思维链', '验证链',
             '子智能体', '氛围工程', '氛围编程', '提示词', '可观测性',
             '单元测试', '集成测试', '契约测试', '端到端', '代码库',
             '依赖图', '智能体', '工作流', '上下文', '单仓']

TOKEN = re.compile(r'[A-Za-z0-9_\-\.\'\(\)\[\]\{\}\*/:=<>!&|%#@$~\^\\]+'
                   r'|[\u4e00-\u9fff]+|\s+|.', re.S)
NO_HEAD = set('，。、；：？！）》」』】,.;:?!)%')
NO_TAIL = set('（《「『【(')


def font(size, bold=False):
    return ImageFont.truetype(FONT_BD if bold else FONT,
                              max(6, int(round(size))))


def tokenize(text):
    toks = []
    for t in TOKEN.findall(text or ''):
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


def wrap_cn(text, f, limit):
    toks = tokenize(text)
    if not toks:
        return ['']
    lines, cur = [], ''
    for tk in toks:
        if tk == ' ' and not cur:
            continue
        cand = cur + tk
        if f.getlength(cand) <= limit or not cur:
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
    return [l for l in lines if l.strip()] or ['']


# ---------------------------------------------------------------- 擦除
def fg_is_light(sub):
    lum = sub[:, :, :3].astype(float).mean(2)
    if lum.size < 16:
        return False
    med = float(np.median(lum))
    return med <= 170 and float(np.percentile(lum, 95)) - med > 60


def ink_mask(sub):
    """该子图的墨迹掩膜（相对底色）。"""
    lum = sub.astype(float).mean(2)
    med = float(np.median(lum))
    if fg_is_light(sub):
        return lum > med + 40
    return lum < float(np.percentile(lum, 88)) - 32


def expand_to_ink(arr, box, bh, bg_lum):
    """把矩形向外扩，直到四周一圈不再有墨迹。

    扩张必须有硬上限：无上限时白字会一路扩到白纸，整张图都被吃掉
    （实测 ch01_f03 标题条从 114×18 扩成 516×163）。
    上限取「行高的固定系数」，并只在**同底色**区域内判定墨迹。
    """
    H, W = arr.shape[:2]
    x0, y0, x1, y1 = box
    max_x = max(8, int(bh * 0.9))
    max_y = max(2, int(bh * 0.30))
    dx = dy = 0
    step = max(2, int(bh * 0.18))
    for _ in range(8):
        nx0, ny0 = max(0, x0 - dx - step), max(0, y0 - dy - step)
        nx1, ny1 = min(W, x1 + dx + step), min(H, y1 + dy + step)
        if (nx0, ny0, nx1, ny1) == (x0, y0, x1, y1):
            break
        sub = arr[ny0:ny1, nx0:nx1, :3]
        lum = sub.astype(float).mean(2)
        # 只把「与底色同类但明显更极端」的像素视为可擦墨迹
        if bg_lum <= 170:
            ink = lum > bg_lum + 45
        else:
            ink = lum < bg_lum - 45
        band = np.zeros_like(ink)
        t = max(2, step)
        band[:t, :] = True
        band[-t:, :] = True
        band[:, :t] = True
        band[:, -t:] = True
        x0, y0, x1, y1 = nx0, ny0, nx1, ny1
        dx, dy = min(dx + step, max_x), min(dy + step, max_y)
        if not (ink & band).any():
            break
    return x0, y0, x1, y1


def dominant_color(sub):
    """矩形内出现最多的颜色（量化到 8 级桶后取中位）。

    为什么不用「扩展窗口的中位数」：标题条上下就是白纸，把白纸算进底色，
    会让 bg_lum 变成 255 → 判成白底黑字 → 蓝色标题条反而被当作墨迹擦成白块
    （实测正是这个症状）。方框内字只占 30~50%，底面颜色必定是众数。
    """
    q = (sub.astype(np.int16) // 12)
    flat = q.reshape(-1, 3)
    key = (flat[:, 0].astype(np.int32) << 16) | (flat[:, 1].astype(np.int32) << 8) | flat[:, 2]
    vals, counts = np.unique(key, return_counts=True)
    best = vals[int(np.argmax(counts))]
    m = key == best
    return np.median(sub.reshape(-1, 3)[m], axis=0)


def erase_region(img, arr, box, bh):
    """擦掉矩形内文字墨迹，用底色填回；只保护长横线/长竖线（方框边、箭头杆）。"""
    H, W = arr.shape[:2]
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    y0 = max(0, y0 - max(2, int(bh * 0.20)))
    y1 = min(H, y1 + max(2, int(bh * 0.20)))
    x0, x1 = max(0, x0), min(W, x1)
    if x1 - x0 < 6 or y1 - y0 < 6:
        return None

    sub = arr[y0:y1, x0:x1, :3]
    bg = dominant_color(sub)
    bg_lum = float(bg.astype(float).mean())
    lum = sub.astype(float).mean(2)

    # 阈值取得低：只抓「核心」会把抗锯齿边缘留下，与底色混成浅色残影
    if bg_lum > 170:                 # 亮底：擦暗字
        ink = lum < bg_lum - 32
    else:                            # 深底：擦亮字
        ink = lum > bg_lum + 28
    if ink.sum() < 5:
        return None

    # 结构保护：只保护长横线 / 长竖线。不能加「厚块」保护 ——
    # 粗体大字会被整片保下来，蓝条上的粗体白字就擦不掉。
    kx = max(15, int(bh * 2.2))
    guard = ndimage.binary_dilation(
        ndimage.binary_opening(ink, np.ones((1, kx)))
        | ndimage.binary_opening(ink, np.ones((kx, 1))),
        np.ones((2, 2)))
    kill = ink & ~guard
    if kill.sum() < 5:
        return None
    kill = ndimage.binary_dilation(kill, np.ones((3, 3))) & ~guard
    # 膨胀后夹回矩形内侧：否则会顺着底色一路吃出去，把整条卡片边擦成白块
    inner = np.zeros_like(kill)
    inset = max(1, int((y1 - y0) * 0.08))
    inner[inset:kill.shape[0] - inset, :] = True
    kill = kill & inner

    patch = sub.copy()
    patch[kill] = bg
    arr[y0:y1, x0:x1, :3] = patch
    # ← 必须 paste 回 img，否则输出与原图字节相同（pitfalls T5）
    img.paste(Image.fromarray(arr))
    return (x0, y0, x1, y1)


# ---------------------------------------------------------------- 排版
def fit_multi(cn, bw, bh, h_ref, vertical=False):
    """译文里带 \\n 时，按显式换行分段，每段独立求字号后取最小值。

    为什么需要：原图一个方框内的多行本是**分开的 OCR 块**，合并成一个区域后
    若仍按单段自动折行，行数会算错、文字互相压盖（实测 ch04_f09 步骤框全叠在一起）。
    """
    if '\n' not in cn:
        return fit(cn, bw, bh, h_ref, vertical)
    segs = [x.strip() for x in cn.split('\n') if x.strip()]
    n = len(segs)
    per_h = bh / max(1, n)
    fs = max(7.0, min(h_ref * 0.98, per_h * 0.94))
    while fs >= 7.0:
        f = font(fs)
        ok = True
        for sg in segs:
            if f.getlength(sg) > bw + max(1.0, bw * 0.06):
                ok = False
                break
        if ok:
            break
        fs -= max(0.4, fs * 0.06)
        fs = max(7.0, fs)
    f = font(fs)
    lines = []
    for sg in segs:
        lines.extend(wrap_cn(sg, f, bw + max(1.0, bw * 0.05)))
    pitch = min(1.24, per_h / max(1.0, fs) * 1.05)
    return fs, lines, pitch, 0.0, 0.0


def fit(cn, bw, bh, h_ref, vertical=False):
    """vertical=True 时按「一列一字」排（竖排标签用）。"""
    if vertical:
        clean = cn.replace(' ', '')
        n = max(1, len(clean))
        fs = min(bh / max(1.0, n * 1.12), max(7.0, bw * 0.92))
        fs = max(7.0, fs)
        return fs, list(clean), 1.12, 0.0, 0.0
    fs = max(7.0, h_ref * 0.98)
    limit = bw + max(1.0, bw * 0.05)
    best = None
    while fs >= 7.0:
        f = font(fs)
        lines = wrap_cn(cn, f, limit)
        pitch = 1.24
        if len(lines) * fs * pitch > bh + 2:
            pitch = max(1.1, (bh + 2) / max(1, len(lines) * fs))
        tw = max((f.getlength(l) for l in lines), default=0)
        th = len(lines) * fs * pitch
        ow = (tw - bw) / max(1.0, bw) * 100
        oh = (th - bh) / max(1.0, bh) * 100
        best = (fs, lines, pitch, ow, oh)
        if ow <= 5 and oh <= 5:
            break
        fs -= max(0.4, fs * 0.06)
    return best


def sweep_residual(img, arr, safe_boxes, min_area=28):
    """扫掉「没被任何译文框覆盖」的文字残片。

    为什么要单独扫：OCR 会漏检小字（`s`、`x`、被框线切断的半行），
    它们不在 regions 里，逐框擦除永远碰不到（实测每张图都有零星残片）。
    做法：整图取墨迹 → 减去长线/厚块结构 → 减去所有译文框（含 padding）
    → 剩下的连通域面积达标就擦掉。
    """
    H, W = arr.shape[:2]
    lum = arr[:, :, :3].astype(float).mean(2)
    ink = lum < 200
    kx = max(25, int(H * 0.06))
    guard = ndimage.binary_dilation(
        ndimage.binary_opening(ink, np.ones((1, kx)))
        | ndimage.binary_opening(ink, np.ones((kx, 1))),
        np.ones((2, 2)))
    cand = ink & ~guard
    mask = np.zeros((H, W), bool)
    for bx in safe_boxes:
        x0, y0, x1, y1 = [int(round(v)) for v in bx]
        mask[max(0, y0):y1, max(0, x0):x1] = True
    cand &= ~mask
    lab, n = ndimage.label(cand)
    if n == 0:
        return 0
    sizes = ndimage.sum(cand, lab, range(1, n + 1))
    killed = 0
    for i, sz in enumerate(sizes, 1):
        if sz < min_area or sz > 60000:
            continue
        ys, xs = np.where(lab == i)
        h = ys.max() - ys.min()
        w = xs.max() - xs.min()
        if h > 90 or w > 700:      # 大块是图形元素，不是文字
            continue
        pad = 2
        y0, y1 = max(0, ys.min() - pad), min(H, ys.max() + pad + 1)
        x0, x1 = max(0, xs.min() - pad), min(W, xs.max() + pad + 1)
        sub = arr[y0:y1, x0:x1, :3]
        bg = dominant_color(sub)
        region = (lab[y0:y1, x0:x1] == i) & cand[y0:y1, x0:x1]
        region = ndimage.binary_dilation(region, np.ones((3, 3)))
        seg = sub.copy()
        seg[region] = bg
        arr[y0:y1, x0:x1, :3] = seg
        killed += 1
    if killed:
        img.paste(Image.fromarray(arr))
    return killed


def render(png, regions, trans, out_path):
    img = Image.open(png).convert('RGB')
    arr = np.array(img)
    prepared = []
    missing = []
    kept = []
    over = []
    small = []

    for r in regions:
        rid = str(r['id'])
        cn = (trans.get(rid) or '').strip()
        if cn in ('SAME', '='):
            kept.append((r['id'], r['en'], 'SAME'))
            continue
        if not cn:
            if re.search(r'[A-Za-z]', r['en']):
                missing.append((r['id'], r['en']))
            continue
        x0, y0, x1, y1 = r['px_bbox']
        bh = max(8, y1 - y0)
        # 不做「按墨迹扩张」：扩张会把框带出标题条，混进白纸后
        # 底色众数变成白色，蓝色条反而被当墨迹擦白（实测）。
        # 固定 padding 足够覆盖 OCR 框偏窄的问题。
        pad = max(2, int(bh * 0.22))
        ex = (max(0, x0 - pad), max(0, y0 - pad),
              min(arr.shape[1], x1 + pad), min(arr.shape[0], y1 + pad))
        box = erase_region(img, arr, ex, bh)
        arr = np.array(img)
        if box:
            bx0, by0, bx1, by1 = box
        else:
            bx0, by0, bx1, by1 = ex
        bw, bhh = bx1 - bx0, by1 - by0
        if bw < 8 or bhh < 6:
            continue
        vertical = bool(r.get('vertical'))
        fs, lines, pitch, ow, oh = fit_multi(cn, bw, bhh, bh * 0.94, vertical)
        if oh > 10:
            over.append((r['id'], r['en'], cn, ow, oh))
        f = font(fs)
        tw = max((f.getlength(l) for l in lines), default=0)
        th = len(lines) * fs * pitch
        # 文字色：按擦除后框内实际底色决定（深底白字 / 白底黑字）
        _seg = arr[by0:by1, bx0:bx1, :3] if False else None
        _lum_now = float(np.median(arr[by0:by1, bx0:bx1, :3].astype(float).mean(2)))
        fg = (26, 26, 26) if _lum_now > 150 else (255, 255, 255)
        prepared.append({
            'lines': lines, 'fs': fs, 'pitch': pitch, 'fg': fg,
            'tx': bx0 + max(0, (bw - tw) / 2),
            'ty': by0 + max(0, (bhh - th) / 2),
            'cx': bx0 + bw / 2.0,
            'vertical': vertical,
            'id': r['id'], 'en': r['en'], 'cn': cn,
            'fs_pt': fs,
        })

    # 不做全图残片清扫：实测会把与文字形状相近的图形件（箭头、圆点、
    # 表格线）一起擦掉，ch10_f03 的「CI」「C」被清成空白。
    # 零散残片改为「按 OCR 行整体加高擦除」来消除（见 render 里的 pad）。
    swept = 0

    draw = ImageDraw.Draw(img)
    for d in prepared:
        f = font(d['fs'])
        if d.get('vertical'):
            for i, ln in enumerate(d['lines']):
                w = f.getlength(ln)
                draw.text((d['cx'] - w / 2, d['ty'] + i * d['fs'] * d['pitch']),
                          ln, font=f, fill=d['fg'])
            continue
        for i, ln in enumerate(d['lines']):
            draw.text((d['tx'], d['ty'] + i * d['fs'] * d['pitch']), ln,
                      font=f, fill=d['fg'])
        if d['fs_pt'] < 9:
            small.append(d)

    img.save(out_path)
    return {'rendered': prepared, 'missing': missing, 'kept': kept,
            'over': over, 'small': small, 'swept': swept}


def main():
    kinds = json.load(open(os.path.join(WORK, 'fig_kind.json'), encoding='utf-8'))
    ocr = json.load(open(os.path.join(WORK, 'fig_ocr.json'), encoding='utf-8'))
    regions = json.load(open(os.path.join(WORK, 'fig_regions.json'),
                             encoding='utf-8'))
    tpath = os.path.join(WORK, 'fig_zh.json')
    trans = json.load(open(tpath, encoding='utf-8')) if os.path.exists(tpath) else {}

    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    keys = args or [k for k in sorted(ocr) if kinds[k] == 'diagram']
    tot = {'rendered': 0, 'missing': [], 'kept': [], 'over': [], 'small': []}
    for k in keys:
        doc = ocr[k]['doc']
        os.makedirs(os.path.join(OUTDIR, doc), exist_ok=True)
        dst = os.path.join(OUTDIR, doc, k + '.png')
        rep = render(ocr[k]['img'], regions.get(k, []), trans.get(k, {}), dst)
        print('%-12s rendered=%2d missing=%2d over=%2d' %
              (k, len(rep['rendered']), len(rep['missing']), len(rep['over'])))
        tot['rendered'] += len(rep['rendered'])
        for key in ('missing', 'kept', 'over', 'small'):
            for x in rep[key]:
                tot[key].append((k,) + tuple(x) if isinstance(x, tuple)
                                else (k, x))
    print('\n合计 rendered=%d missing=%d over=%d small=%d' %
          (tot['rendered'], len(tot['missing']), len(tot['over']),
           len(tot['small'])))
    for m in tot['missing'][:40]:
        print('  MISS %s #%s %r' % m)
    for m in tot['over'][:30]:
        print('  OVER %s #%s %r -> %r w%+.0f%% h%+.0f%%' % m)
    json.dump({'missing': tot['missing'], 'over': tot['over'],
               'small': [x[0] + ' #' + str(x[1]) for x in tot['small']]},
              open(os.path.join(WORK, 'fig_report.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
