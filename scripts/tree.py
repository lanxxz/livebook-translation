# -*- coding: utf-8 -*-
"""扁平化：把嵌套块树摊平成稳定的译文单元列表，供骨架/译文/校验共用。

单元 id 用点号表示嵌套：`14` 是顶层块，`14.16` 是它第 16 个 part。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_docs, load_json, WORK  # noqa: E402


def walk(blocks, prefix='', acc=None):
    if acc is None:
        acc = []
    for i, b in enumerate(blocks):
        pid = ('%s.%d' % (prefix, i)) if prefix else str(i)
        acc.append((pid, b))
        if isinstance(b, dict) and b.get('parts'):
            walk(b['parts'], pid, acc)
    return acc


def units(doc):
    pages = load_json(os.path.join(WORK, doc + '_layout.json'))['pages']
    blocks = []
    for k in pages:
        blocks.extend(pages[k])
    return walk(blocks)


TEXT_FIELDS = {
    'chapter_open': ['title'],
    'heading': ['text'],
    'para': ['text'],
    'code': ['caption'],
    'figure': ['caption'],
    'table': ['caption'],
    'equation': ['text'],
    'quote': ['text'],
    'dialog': ['speaker'],
    'callout': ['label'],
    'sidebar': ['title'],
    'list': [],
    'numlist': [],
}


def slots(kind, b):
    """返回该单元需要翻译的槽位名列表（有序）。"""
    out = list(TEXT_FIELDS.get(kind, []))
    if kind == 'chapter_open':
        out += ['toc[%d]' % i for i in range(len(b['toc_items']))]
        if b.get('intro'):
            out.append('intro')
    elif kind in ('list', 'numlist'):
        out += ['item[%d]' % i for i in range(len(b['items']))]
    elif kind == 'code':
        out += ['note:%s' % k for k, _ in b['notes']]
    elif kind == 'table':
        g = b['grid']['data']
        for r in range(len(g)):
            for c in range(len(g[r])):
                out.append('cell[%d][%d]' % (r, c))
    return out


def value_of(kind, b, slot):
    if slot == 'intro':
        return b.get('intro', '')
    if slot.startswith('toc['):
        return b['toc_items'][int(slot[4:-1])]
    if slot.startswith('item['):
        return b['items'][int(slot[5:-1])]
    if slot.startswith('note:'):
        key = slot[5:]
        for k, v in b['notes']:
            if k == key:
                return v
        return ''
    if slot.startswith('cell['):
        r, c = slot[5:-1].split('][')
        return b['grid']['data'][int(r)][int(c)]
    return b.get(slot, '')


def set_value(kind, b, slot, val):
    if slot == 'intro':
        b['intro'] = val
    elif slot.startswith('toc['):
        b['toc_items'][int(slot[4:-1])] = val
    elif slot.startswith('item['):
        b['items'][int(slot[5:-1])] = val
    elif slot.startswith('note:'):
        key = slot[5:]
        b['notes'] = [[k, val if k == key else v] for k, v in b['notes']]
    elif slot.startswith('cell['):
        r, c = slot[5:-1].split('][')
        b['grid']['data'][int(r)][int(c)] = val
    else:
        b[slot] = val
