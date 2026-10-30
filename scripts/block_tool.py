# -*- coding: utf-8 -*-
"""骨架块诊断三件套：dump / peek / tail。合并成一个脚本，少记几个命令。

用法：
  python block_tool.py dump <包名> <块号>     # 打印该块的原始 JSON（看有哪些键）
  python block_tool.py peek <包名> <块号...> # 打印结构 + 内容末尾（看是否被折断）
  python block_tool.py pages <包名>          # 列出含 figure 的页及图数

为什么需要它：
  分片翻译时经常需要确认「这个块到底有哪些键」——表格是 head0..r6c3，
  列表是 item0..item15，代码块是 code+note0..N。凭猜写键一定会白干。
"""
import json
import os
import sys

from bookconf import cfg

PACK = os.path.join(cfg('root'), 'work', 'pack')


def load(name):
    return json.load(open(os.path.join(PACK, name + '_skel.json'),
                          encoding='utf-8'))


def dump(name, i):
    skel = load(name)
    if i >= len(skel):
        sys.exit('块号超范围：%d >= %d' % (i, len(skel)))
    print(json.dumps(skel[i], ensure_ascii=False)[:2000])


def peek(name, idxs):
    skel = load(name)
    for i in idxs:
        if i >= len(skel):
            print('#%d 超范围（共 %d 块）' % (i, len(skel)))
            continue
        b = skel[i]
        print('--- #%d %s' % (i, b['type']))
        if b.get('text'):
            print('    text …%r' % b['text'][-80:])
        for n, it in enumerate(b.get('items') or []):
            print('    item%d …%r' % (n, it[-80:]))
        if b.get('caption'):
            print('    caption …%r' % b['caption'][-60:])
        if b.get('code'):
            print('    code …%r' % b['code'][-80:])


def pages(name):
    lay = json.load(open(os.path.join(PACK, name + '_layout.json'),
                         encoding='utf-8'))['pages']
    print('%s：%d 页' % (name, len(lay)))
    for pno in sorted(lay, key=int):
        n = sum(1 for b in lay[pno] if b['type'] == 'figure')
        if n:
            print('  p%-4s figure %d' % (pno, n))


def main():
    cmd = sys.argv[1]
    name = sys.argv[2]
    if cmd == 'dump':
        dump(name, int(sys.argv[3]))
    elif cmd == 'peek':
        peek(name, [int(x) for x in sys.argv[3:]])
    elif cmd == 'pages':
        pages(name)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
