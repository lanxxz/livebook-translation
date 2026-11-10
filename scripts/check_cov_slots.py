# -*- coding: utf-8 -*-
"""覆盖率闸门：检查 <doc>_zh.txt 是否覆盖了骨架的全部槽位。

用法：
    python tools/check_cov.py ch01 [ch02 ...]
    python tools/check_cov.py --all

判据（两条都要绿）：
  1. 多余槽位 = 0（写错 uid / 写错键名都会落到这里）
  2. 缺失槽位 = 0（原文非空的槽位必须有译文）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_docs, WORK  # noqa: E402
from apply_zh import parse_zh  # noqa: E402
from tree import units, slots, value_of  # noqa: E402


def check(doc, verbose=True):
    us = units(doc)
    zm, dups, bad = parse_zh(os.path.join(WORK, doc + '_zh.txt'))
    if zm is None:
        print('%-8s 未开始' % doc)
        return False, 0, 0
    known = {uid for uid, _ in us}
    missing, extra = [], []
    filled = total = 0
    for uid, b in us:
        want = slots(b['type'], b)
        got = zm.get(uid, {})
        for slot in want:
            total += 1
            v = (got.get(slot) or '').strip()
            if v:
                filled += 1
            elif value_of(b['type'], b, slot).strip():
                missing.append('%s.%s' % (uid, slot))
        for slot in got:
            if slot not in want and (got[slot] or '').strip():
                extra.append('%s.%s' % (uid, slot))
    for uid in zm:
        if uid not in known:
            extra.append('uid=%s' % uid)
    ok = not extra and not missing and not dups and not bad
    print('%-8s %s  填充 %d/%d  缺 %d  多余 %d%s' %
          (doc, 'OK ' if ok else 'BAD', filled, total, len(missing),
           len(extra), '  重复 %d' % len(dups) if dups else ''))
    if verbose and (missing or extra or bad):
        if missing:
            print('   缺:', missing[:14])
        if extra:
            print('   多:', extra[:14])
        if bad:
            print('   格式:', bad[:6])
    return ok, filled, total


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    docs = [d['id'] for d in load_docs()] if '--all' in sys.argv else args
    res = [check(d) for d in docs]
    bad = [d for d, r in zip(docs, res) if not r[0]]
    tot = sum(r[2] for r in res)
    fill = sum(r[1] for r in res)
    print('\n合计 %d/%d 槽位已译；未通过 %d 份%s' %
          (fill, tot, len(bad), (': ' + ', '.join(bad)) if bad else ''))


if __name__ == '__main__':
    main()
