# -*- coding: utf-8 -*-
"""把 diagram 类图的 OCR 块导出成待译清单（带图尺寸，便于判断可用空间）。"""
import json
import os
import sys

from common import ROOT  # 项目根：向上找 book.json/docs.json，或 BOOK_ROOT
_HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, 'work')

ocr = json.load(open(os.path.join(WORK, 'fig_ocr.json'), encoding='utf-8'))
kinds = json.load(open(os.path.join(WORK, 'fig_kind.json'), encoding='utf-8'))
keys = [a for a in sys.argv[1:] if not a.startswith('-')] or \
       [k for k in sorted(ocr) if kinds[k] == 'diagram']
for k in keys:
    v = ocr[k]
    print('#### %s  %dx%d  blocks=%d' % (k, v['size'][0], v['size'][1],
                                         len(v['blocks'])))
    for b in v['blocks']:
        x0, y0, x1, y1 = b['px_bbox']
        print('  %2d|%3dx%-3d|%s' % (b['id'], x1 - x0, y1 - y0, b['en']))
    print()