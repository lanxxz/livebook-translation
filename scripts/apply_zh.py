# -*- coding: utf-8 -*-
"""把 <doc>_zh.txt（槽位译文）合并回 layout，产出 <doc>_trans.json。

译文文件格式：

    ### 12 [para]
    text 中文段落（单行即可，长段落不需要手动换行）

    ### 43 [figure]
    caption 图 1.1　氛围工程的循环……

    ### 14 [dialog]
    speaker 提示词

    ### 56 [table]
    cell[0][0] 用例
    cell[0][1] 数据集 A（印度）

规则：
  · `### <uid> [<type>]` 开启一个单元；uid 与 type 都要与 _skel.txt 一致。
  · 槽位行 = 「键 + 一个空格 + 值」；键的形态是 text / caption / speaker /
    title / label / intro / toc[N] / item[N] / cell[R][C] / note:A。
  · 不以合法键开头的行视为上一槽位的续行（自动用空格拼接）。
"""
import copy
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import WORK, load_docs, dump_json, load_json  # noqa: E402
from tree import walk, slots, set_value, value_of  # noqa: E402

UID_RE = re.compile(r'^###\s+([\d.]+)\s*(?:\[([^\]]+)\])?\s*$')
KEY_RE = re.compile(
    r'^(text|caption|speaker|title|label|intro|num|'
    r'toc\[\d+\]|item\[\d+\]|cell\[\d+\]\[\d+\]|note:[#]?[A-Z])'
    r'(?:\s+(.*))?$')


def parse_zh(path):
    if not os.path.exists(path):
        return None, [], []
    out = {}
    dups = []
    badlines = []
    cur_uid = None
    cur_key = None
    buf = []

    def commit():
        nonlocal cur_key, buf
        if cur_uid is None or cur_key is None:
            cur_key, buf = None, []
            return
        txt = ' '.join(x.strip() for x in buf if x.strip())
        d = out.setdefault(cur_uid, {})
        if cur_key in d and d[cur_key] != txt:
            dups.append((cur_uid, cur_key))
        d[cur_key] = txt
        cur_key, buf = None, []

    for raw in open(path, encoding='utf-8-sig').read().split('\n'):
        line = raw.rstrip()
        m = UID_RE.match(line)
        if m:
            commit()
            cur_uid = m.group(1)
            continue
        if cur_uid is None:
            continue
        if not line.strip():
            continue
        m = KEY_RE.match(line.strip())
        if m:
            commit()
            cur_key = m.group(1)
            buf = [m.group(2) or '']
            continue
        if cur_key is None:
            badlines.append((cur_uid, line[:60]))
            continue
        buf.append(line)
    commit()
    return out, dups, badlines


def apply(doc, quiet=False):
    lay = load_json(os.path.join(WORK, doc + '_layout.json'))
    blocks = []
    for k in lay['pages']:
        blocks.extend(copy.deepcopy(lay['pages'][k]))
    us = walk(blocks)
    zm, dups, badlines = parse_zh(os.path.join(WORK, doc + '_zh.txt'))
    if zm is None:
        print('%-8s 未开始（缺 %s_zh.txt）' % (doc, doc))
        return None
    known = {uid for uid, _ in us}
    extra = []
    missing = []
    filled = 0
    total = 0
    for uid, b in us:
        want = slots(b['type'], b)
        got = zm.get(uid, {})
        for slot in want:
            total += 1
            v = got.get(slot, '')
            if v:
                set_value(b['type'], b, slot, v)
                filled += 1
            else:
                # 原文本身为空的槽位（如无标题的代码块）不计为缺失
                if value_of(b['type'], b, slot).strip():
                    missing.append('%s.%s' % (uid, slot))
        for slot in got:
            if slot not in want and got[slot]:
                extra.append('%s.%s' % (uid, slot))
    for uid in zm:
        if uid not in known:
            extra.append('uid=%s' % uid)
    dump_json({'blocks': blocks}, os.path.join(WORK, doc + '_trans.json'))
    if not quiet:
        st = 'OK ' if not extra else 'BAD'
        print('%-8s %s 填充 %d/%d 缺 %d 多余 %d' %
              (doc, st, filled, total, len(missing), len(extra)))
        if dups:
            print('   重复槽位:', dups[:6])
        if badlines:
            print('   无法解析的行:', badlines[:6])
        if extra:
            print('   多余槽位:', extra[:10])
        if missing:
            print('   缺失槽位:', missing[:10])
    return {'filled': filled, 'total': total, 'missing': missing,
            'extra': extra, 'dups': dups, 'bad': badlines}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    docs = [d['id'] for d in load_docs()] if '--all' in sys.argv else args
    for d in docs:
        apply(d)


if __name__ == '__main__':
    main()
