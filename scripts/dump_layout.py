# -*- coding: utf-8 -*-
"""把解析结果 dump 成可读文本，便于人工核对。"""
import json, sys

d = json.load(open(sys.argv[1], encoding='utf-8'))['pages']
for pn, blks in d.items():
    print('=' * 12, 'p' + pn)
    for b in blks:
        t = b['type']
        if t == 'chapter_open':
            print(f"  [CH] {b['num']} / {b['title']}")
            print(f"       TOC: {b['toc_items']}")
            print(f"       QUOTE: {b['quote']}  {b['quote_by']}")
            print(f"       INTRO: {b['intro']}")
            print(f"       FIGS: {b['figs']}")
        elif t in ('figure',):
            txt = ' ¦ '.join(x['text'] for x in b['texts'])
            print(f"  [FIG {b['bbox'][2]-b['bbox'][0]:.0f}x{b['bbox'][3]-b['bbox'][1]:.0f}] {txt}")
        elif t == 'table':
            g = b.get('grid')
            print(f"  [TABLE {b['bbox']}] grid={g['rows']}x{g['cols']}" if g else f"  [TABLE {b['bbox']}] no-grid")
            if g:
                for row in g['data']:
                    print('        | ' + ' | '.join(c[:38] for c in row))
        elif t == 'heading':
            print(f"  [H{b['level']}] {b['text']}")
        elif t in ('list', 'numlist'):
            for i, it in enumerate(b['items'], 1):
                print(f"  [{t}#{i}] {it}")
        elif t == 'code':
            print(f"  [CODE {b['lines']}L] {b['text'][:100]}")
        else:
            print(f"  [P] {b['text']}")
