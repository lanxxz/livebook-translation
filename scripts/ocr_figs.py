# -*- coding: utf-8 -*-
"""从栅格图提取图内文字（OCR），产出 figtexts.json。

配合 fig_raster.py 使用：本脚本只负责「认出文字 + 给出坐标」，
擦除与写入由 fig_raster.py 完成。

用法：
    python ocr_figs.py <pdf> <out_figtexts.json> [--pages 1-374] [--dpi 300]

输出结构（与 render_figs.py 的 figtexts 完全兼容）：
    {"p120_f0": {"page":120, "bbox":[...pt], "img_px":[w,h], "scale":4.1667,
                 "blocks":[{"id":0, "en":"...", "bbox":[...pt],
                            "px_bbox":[...px], "h_pt":7.2, "size":6.2,
                            "conf":0.93}]}}

两个关键设计（见 references/pitfalls.md T4）：
  · **同时存 px_bbox 与 bbox**：擦除用像素、字号用 pt，缺一套就会反复出错。
  · **按图缓存 `*.ocr.json`**：OCR 约 3 秒/图，重跑渲染不该重新识别。
"""
import json
import os
import re
import sys

import numpy as np
import pymupdf

BAD = re.compile(r'^[\W_]+$')


def keep(text, conf, min_conf=0.30):
    t = text.strip()
    if not t or conf < min_conf:
        return False
    if BAD.match(t):
        return False
    if len(t) == 1 and not re.match(r'[A-Za-z0-9]', t):
        return False
    return True


def plain(res):
    """easyocr 返回 numpy 标量，必须先转成 Python 原生类型再存 JSON。"""
    return [[[[float(p[0]), float(p[1])] for p in bb], str(txt), float(conf)]
            for bb, txt, conf in res]


def group(res, gapx=26):
    """把 OCR box 按「同一基线的相邻碎片」合并成语义块。"""
    items = []
    for bb, txt, conf in res:
        xs = [p[0] for p in bb]
        ys = [p[1] for p in bb]
        items.append({'px': [min(xs), min(ys), max(xs), max(ys)],
                      'text': txt.strip(), 'conf': float(conf)})
    items.sort(key=lambda i: (i['px'][1], i['px'][0]))
    groups = []
    for it in items:
        placed = False
        for g in groups:
            h = min(g['px'][3], it['px'][3]) - max(g['px'][1], it['px'][1])
            hmin = min(g['px'][3] - g['px'][1], it['px'][3] - it['px'][1])
            if hmin <= 0:
                continue
            if h > 0.55 * hmin and -gapx <= it['px'][0] - g['px'][2] <= gapx:
                g['px'][2] = max(g['px'][2], it['px'][2])
                g['px'][1] = min(g['px'][1], it['px'][1])
                g['px'][3] = max(g['px'][3], it['px'][3])
                g['parts'].append(it)
                g['conf'] = min(g['conf'], it['conf'])
                placed = True
                break
        if not placed:
            groups.append({'px': list(it['px']), 'parts': [it],
                           'conf': it['conf']})
    for g in groups:
        g['parts'].sort(key=lambda p: p['px'][0])
        g['en'] = ' '.join(p['text'] for p in g['parts'])
        g['h'] = g['px'][3] - g['px'][1]
    groups.sort(key=lambda g: (g['px'][1], g['px'][0]))
    return groups


def fig_list(doc, page_from=0, page_to=None):
    """枚举插图，排除封面整页图与版权页 logo。"""
    out = []
    for pno in range(doc.page_count):
        if pno + 1 < page_from or (page_to and pno + 1 > page_to):
            continue
        for info in doc[pno].get_image_info():
            r = pymupdf.Rect(info['bbox'])
            if r.width < 60 or r.height < 14:
                continue
            if pno == 0:                    # 封面整页位图
                continue
            out.append({'page': pno + 1, 'bbox': [r.x0, r.y0, r.x1, r.y1],
                        'px': [info['width'], info['height']]})
    out.sort(key=lambda f: (f['page'], f['bbox'][1]))
    seen = {}
    for f in out:
        i = seen.get(f['page'], 0)
        f['key'] = 'p%d_f%d' % (f['page'], i)
        seen[f['page']] = i + 1
    return out


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    pdf, outp = sys.argv[1], sys.argv[2]
    dpi = 300
    pfrom, pto = 0, None
    if '--dpi' in sys.argv:
        dpi = int(sys.argv[sys.argv.index('--dpi') + 1])
    if '--pages' in sys.argv:
        a, _, b = sys.argv[sys.argv.index('--pages') + 1].partition('-')
        pfrom, pto = int(a), int(b or a)
    scale = dpi / 72.0

    import easyocr
    reader = easyocr.Reader(['en'], gpu=False, verbose=False)

    cache = os.path.join(os.path.dirname(os.path.abspath(outp)), 'ocr_cache')
    os.makedirs(cache, exist_ok=True)
    doc = pymupdf.open(pdf)
    figs = fig_list(doc, pfrom, pto)
    out = {}

    for i, f in enumerate(figs):
        png = os.path.join(cache, f['key'] + '.png')
        if not os.path.exists(png):
            doc[f['page'] - 1].get_pixmap(
                dpi=dpi, clip=pymupdf.Rect(*f['bbox'])).save(png)
        ck = os.path.join(cache, f['key'] + '.ocr.json')
        if os.path.exists(ck):
            try:
                res = [(r[0], r[1], r[2])
                       for r in json.load(open(ck, encoding='utf-8'))]
            except Exception:
                res = plain(reader.readtext(png, detail=1, paragraph=False))
        else:
            res = plain(reader.readtext(png, detail=1, paragraph=False))
            json.dump(res, open(ck, 'w', encoding='utf-8'), ensure_ascii=False)

        res = [r for r in res if keep(r[1], r[2])]
        blocks = []
        for gi, g in enumerate(group(res)):
            if not g['en'].strip():
                continue
            blocks.append({
                'id': gi,
                'en': g['en'],
                'px_bbox': [round(v, 1) for v in g['px']],
                'bbox': [round(g['px'][0] / scale + f['bbox'][0], 2),
                         round(g['px'][1] / scale + f['bbox'][1], 2),
                         round(g['px'][2] / scale + f['bbox'][0], 2),
                         round(g['px'][3] / scale + f['bbox'][1], 2)],
                'h_pt': round(g['h'] / scale, 2),
                'size': round(g['h'] / scale * 0.86, 2),
                'conf': round(g['conf'], 2),
            })
        out[f['key']] = {'page': f['page'],
                         'bbox': [round(v, 1) for v in f['bbox']],
                         'img_px': list(f['px']), 'scale': scale,
                         'blocks': blocks}
        sys.stderr.write('[%d/%d] %s %d blocks\n'
                         % (i + 1, len(figs), f['key'], len(blocks)))

    json.dump(out, open(outp, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('figs=%d blocks=%d -> %s'
          % (len(out), sum(len(v['blocks']) for v in out.values()), outp))


if __name__ == '__main__':
    main()
