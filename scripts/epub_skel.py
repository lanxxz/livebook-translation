# -*- coding: utf-8 -*-
"""生成待译骨架 + 待译清单（按单元 id 与槽位）。

用法：
    python tools/mk_skel.py ch01
    python tools/mk_skel.py --all

产出：
    work/<doc>_skel.txt   人读骨架（英文原文，供翻译时对照）
    work/<doc>_slots.json 结构化槽位表 [{uid, kind, slot, en}]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_docs, WORK, dump_json  # noqa: E402
from tree import units, slots, value_of  # noqa: E402


def build(doc):
    us = units(doc)
    rows = []
    for uid, b in us:
        for slot in slots(b['type'], b):
            rows.append({'uid': uid, 'kind': b['type'], 'slot': slot,
                         'en': value_of(b['type'], b, slot)})
    dump_json(rows, os.path.join(WORK, doc + '_slots.json'))
    # 人读骨架
    lines = []
    for uid, b in us:
        t = b['type']
        tag = t
        if t == 'heading':
            tag = 'h%d' % b['level']
        elif t == 'dialog':
            tag = 'dialog:%s' % b['kind']
        lines.append('### %s  [%s]' % (uid, tag))
        for slot in slots(t, b):
            en = value_of(t, b, slot)
            lines.append('   %-12s %s' % (slot, en))
        if t == 'code':
            for ln in b['text'].split('\n'):
                lines.append('   CODE|' + ln)
        lines.append('')
    open(os.path.join(WORK, doc + '_skel.txt'), 'w', encoding='utf-8').write(
        '\n'.join(lines))
    return len(rows)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    docs = [d['id'] for d in load_docs()] if '--all' in sys.argv else args
    tot = 0
    for d in docs:
        n = build(d)
        tot += n
        print('%-8s slots=%d' % (d, n))
    print('TOTAL slots', tot)


if __name__ == '__main__':
    main()
