# -*- coding: utf-8 -*-
"""对 figs/<doc>/*.png 做 OCR，产出 work/fig_ocr.json。

结构：
    {"ch01_f01": {"doc":"ch01", "img":"figs/ch01/ch01_f01.png",
                  "size":[w,h], "scale": 1.0,
                  "blocks":[{"id":0,"en":"...","px_bbox":[x0,y0,x1,y1],
                             "h_px":16,"conf":0.9}]}}
scale = px per pt，本处图已是位图，视作 1.0（字号直接用像素高估算）。
"""
import json
import os
import re
import sys

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

from common import ROOT  # 项目根：向上找 book.json/docs.json，或 BOOK_ROOT
_HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(ROOT, 'figs')
WORK = os.path.join(ROOT, 'work')
CACHE = os.path.join(WORK, 'ocr_cache')

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


def group(res, gapx=26):
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


def plain(res):
    return [[[[float(p[0]), float(p[1])] for p in bb], str(txt), float(conf)]
            for bb, txt, conf in res]


def main():
    import easyocr
    from PIL import Image

    os.makedirs(CACHE, exist_ok=True)
    reader = easyocr.Reader(['en'], gpu=False, download_enabled=False,
                            verbose=False)
    out = {}
    if os.path.exists(os.path.join(WORK, 'fig_ocr.json')) and '--force' not in sys.argv:
        out = json.load(open(os.path.join(WORK, 'fig_ocr.json'),
                             encoding='utf-8'))
    docs = [d for d in sorted(os.listdir(FIG)) if os.path.isdir(os.path.join(FIG, d))]
    todo = []
    for d in docs:
        for f in sorted(os.listdir(os.path.join(FIG, d))):
            if not f.endswith('.png'):
                continue
            key = f[:-4]
            if key in out and out[key].get('blocks'):
                continue
            todo.append((d, key))
    print('todo', len(todo))
    for i, (d, key) in enumerate(todo):
        png = os.path.join(FIG, d, key + '.png')
        ck = os.path.join(CACHE, key + '.ocr.json')
        if os.path.exists(ck):
            res = [(r[0], r[1], r[2])
                   for r in json.load(open(ck, encoding='utf-8'))]
        else:
            res = plain(reader.readtext(png, detail=1, paragraph=False))
            json.dump(res, open(ck, 'w', encoding='utf-8'), ensure_ascii=False)
        res = [r for r in res if keep(r[1], r[2])]
        blocks = []
        for gi, g in enumerate(group(res)):
            if not g['en'].strip():
                continue
            blocks.append({'id': gi, 'en': g['en'],
                           'px_bbox': [int(round(v)) for v in g['px']],
                           'h_px': int(round(g['h'])),
                           'conf': round(g['conf'], 2)})
        with Image.open(png) as im:
            size = list(im.size)
        out[key] = {'doc': d, 'img': png, 'size': size, 'scale': 1.0,
                    'blocks': blocks}
        print('[%d/%d] %-12s %d blocks' % (i + 1, len(todo), key, len(blocks)))
    json.dump(out, open(os.path.join(WORK, 'fig_ocr.json'), 'w',
                        encoding='utf-8'), ensure_ascii=False, indent=1)
    print('figs=%d blocks=%d' % (len(out),
                                 sum(len(v['blocks']) for v in out.values())))


if __name__ == '__main__':
    main()
