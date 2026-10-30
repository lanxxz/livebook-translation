# -*- coding: utf-8 -*-
"""计算各章在中文版里的起始页，写入 work/chapter_pages.json（供简目使用）。"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import pymupdf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'out')


def out_name(d):
    k = d.get('kind', 'ch')
    if k == 'front':
        return '00_' + d['title']
    if k == 'apx':
        return '%s_附录%s_%s' % (d['num'], d['num'], d['title'])
    n = int(d['num'])
    return '%02d_第%d章_%s' % (n, n, d['title'])


def sk(d):
    k = d.get('kind', 'ch')
    if k == 'front':
        return (0, 0 if d['id'] == 'front' else 1)
    if k == 'apx':
        return (2, ord(str(d['num'])[0]))
    return (1, int(d['num']))


def main():
    docs = json.load(open(os.path.join(ROOT, 'docs.json'), encoding='utf-8'))
    pages, cur = {}, 0
    for d in sorted(docs, key=sk):
        pdf = os.path.join(OUT, 'pdf', out_name(d) + '.pdf')
        n = pymupdf.open(pdf).page_count if os.path.exists(pdf) else 0
        if d.get('kind') == 'ch':
            pages['ch%02d' % int(d['num'])] = cur + 1
        elif d.get('kind') == 'apx':
            pages['ap%s' % d['num']] = cur + 1
        cur += n
    json.dump(pages, open(os.path.join(ROOT, 'work', 'chapter_pages.json'), 'w',
                          encoding='utf-8'), ensure_ascii=False, indent=1)
    print(pages)


if __name__ == '__main__':
    main()