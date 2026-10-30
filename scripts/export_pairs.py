# -*- coding: utf-8 -*-
"""导出「块号 + 字段 + 英文原文」对照，专治分片翻译写错键号。

长书必须分片翻译，而分片最常见的错是凭记忆写 "12|text"，实际块号不是 12。
这个脚本把真实骨架摊平成一列，照着左边的键抄就不会错。

用法：
  python export_pairs.py <包名> <起块> <止块> [每行截断字数]

输出示例：
  ## 8 list
     item0    Explosive growth of digital transactions—The sheer volume ...
     item1    Dynamic customer account and profile information —While ...
  ## 9 p
     text     Factors driving fraud detection and prevention systems

注意：code / figkey 字段会被跳过（代码不用翻，图 key 不占译文位）。
"""
import os
import re
import sys

from bookconf import cfg

PACK = os.path.join(cfg('root'), 'work', 'pack')


def main():
    name = sys.argv[1]
    lo = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    hi = int(sys.argv[3]) if len(sys.argv) > 3 else 10 ** 9
    cut = int(sys.argv[4]) if len(sys.argv) > 4 else 90
    src = open(os.path.join(PACK, name + '_src.txt'), encoding='utf-8').read()
    for chunk in src.split('\n---\n'):
        head = chunk.split('\n', 1)[0].strip()
        m = re.match(r'#(\d+)\s+(\S+)', head)
        if not m:
            continue
        idx = int(m.group(1))
        if not (lo <= idx <= hi):
            continue
        print('## %d %s' % (idx, m.group(2)))
        for line in chunk.split('\n')[1:]:
            lm = re.match(r'\s{2}(\w+)\s+(.*)$', line)
            if not lm:
                continue
            f, en = lm.group(1), lm.group(2)
            if f in ('code', 'figkey'):
                continue
            print('   %-8s %s' % (f, en[:cut]))


if __name__ == '__main__':
    main()
