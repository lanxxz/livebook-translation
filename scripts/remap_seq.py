# -*- coding: utf-8 -*-
"""解析规则变更后，把旧译文重新映射到新骨架（键重对齐）。

场景：你给 parse_layout.py 加了一条合并规则（比如"边注聚合"），全书块号
整体前移。此时旧译文键（"12|text"）全部指错块，直接 apply 会张冠李戴。

思路：旧译文键本身携带足够信息来做对齐 ——
  - 字段名集合（text / item0..N / note0..N / caption / head0..N / r{行}c{列}）
  - 字段个数

把「字段签名」组成序列，与「新骨架的块签名序列」做 LCS（最长公共子序列）
对齐，从而自动吸收中间插入/删除的块。序号只作兜底。

用法：
  python remap_seq.py <包名> --dry     # 先看对齐率，不动文件
  python remap_seq.py <包名>           # 落地（改写 fill.json）

判读：
  `对齐 205/205 块，缺 0 项` → 完美，可以落地
  `对齐 157/157 块，缺 83 项` → 缺的都是有意的空旁注续行，也算通过
  `对齐 180/205 块`            → 有关键块没对上，必须人工看
"""
import importlib.util
import json
import os
import sys

from bookconf import cfg

ROOT = cfg('root')
PACK = os.path.join(ROOT, 'work', 'pack')


def load_fill(name):
    """优先读 tx_<包>.py（唯一真源），否则读 fill.json。"""
    tx = os.path.join(ROOT, 'work', 'tx_%s.py' % name)
    if os.path.exists(tx):
        spec = importlib.util.spec_from_file_location('m', tx)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        d = getattr(m, 'FILL', None)
        if d:
            return dict(d)
    p = os.path.join(PACK, name + '_fill.json')
    if os.path.exists(p):
        return json.load(open(p, encoding='utf-8'))
    return {}


def signature(fields):
    """字段名集合 → 可比较的签名元组（与顺序无关，只反映结构）。"""
    def rank(f):
        if f == 'text':
            return (0, 0)
        if f == 'title':
            return (1, 0)
        if f.startswith('toc'):
            return (2, int(f[3:] or 0))
        if f.startswith('intro'):
            return (3, int(f[5:] or 0))
        if f.startswith('item'):
            return (4, int(f[4:] or 0))
        if f.startswith('head'):
            return (5, int(f[4:] or 0))
        if f.startswith('note'):
            return (6, int(f[4:] or 0))
        if f.startswith('r') and 'c' in f:
            return (7, f)
        if f == 'caption':
            return (8, 0)
        return (9, f)
    return tuple(sorted(fields, key=rank))


def blocks_of(fill):
    """把扁平键还原成「块号 → 字段集合」。"""
    out = {}
    for k in fill:
        idx, _, field = k.partition('|')
        if not idx.isdigit():
            continue
        out.setdefault(int(idx), set()).add(field)
    return out


def lcs_pairs(a, b):
    """a、b 为签名序列，返回匹配上的下标对（LCS）。"""
    n, m = len(a), len(b)
    if n * m > 4_000_000:          # 超大就退化为顺序匹配，避免爆内存
        pairs, j = [], 0
        for i in range(n):
            if j < m and a[i] == b[j]:
                pairs.append((i, j))
                j += 1
        return pairs
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = (dp[i + 1][j + 1] + 1 if a[i] == b[j]
                        else max(dp[i + 1][j], dp[i][j + 1]))
    pairs, i, j = [], 0, 0
    while i < n and j < m:
        if a[i] == b[j]:
            pairs.append((i, j))
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1
        else:
            j += 1
    return pairs


def main():
    name = sys.argv[1]
    dry = '--dry' in sys.argv

    skel = json.load(open(os.path.join(PACK, name + '_skel.json'),
                          encoding='utf-8'))
    fill = load_fill(name)

    old = blocks_of(fill)
    old_idx = sorted(old)
    old_sig = [signature(old[i]) for i in old_idx]
    new_sig = []
    for b in skel:
        t = b['type']
        if t in ('p', 'h2', 'h3', 'h4', 'note', 'sidebar'):
            fs = {'text'}
            if t == 'sidebar':
                fs.add('title')
            new_sig.append(signature(fs))
        elif t in ('chapter_open', 'part_open', 'appendix_open'):
            toc = b.get('toc') or []
            fs = {'title'} | {'toc%d' % i for i in range(len(toc))}
            if b.get('intro_paras'):
                fs |= {'intro%d' % i for i in range(len(b['intro_paras']))}
            new_sig.append(signature(fs))
        elif t in ('list', 'numlist'):
            n = len(b.get('items') or [])
            new_sig.append(signature({'item%d' % i for i in range(n)}))
        elif t == 'table':
            fs = set()
            head = b.get('head') or []
            fs |= {'head%d' % i for i in range(len(head))}
            for r, row in enumerate(b.get('rows') or []):
                fs |= {'r%dc%d' % (r, c) for c in range(len(row))}
            if b.get('caption'):
                fs.add('caption')
            new_sig.append(signature(fs))
        elif t == 'code':
            n = len(b.get('notes') or [])
            fs = {'code'} | {'note%d' % i for i in range(n)}
            if b.get('caption'):
                fs.add('caption')
            new_sig.append(signature(fs))
        else:                       # figure 等
            new_sig.append(signature({'key'}))

    pairs = lcs_pairs(old_sig, new_sig)
    new_fill = {}
    for oi, ni in pairs:
        src = old_idx[oi]
        for f in old[src]:
            new_fill['%d|%s' % (ni, f)] = fill.get('%d|%s' % (src, f))

    # 过滤掉骨架里不存在的键
    tpl = json.load(open(os.path.join(PACK, name + '_fill.json'),
                         encoding='utf-8'))
    new_fill = {k: v for k, v in new_fill.items() if k in tpl}
    missing = [k for k in tpl if k not in new_fill
               and not k.split('|')[-1].startswith('note')]

    print('%s：对齐 %d/%d 块，缺 %d 项' % (name, len(pairs), len(old_idx),
                                          len(missing)))
    if dry:
        print('（dry-run，未写文件）')
        return
    if len(pairs) < len(old_idx) * 0.9:
        sys.exit('对齐率低于 90%，拒绝写入。请人工检查或改用 remap_by_text.py')
    json.dump({k: new_fill.get(k, '') for k in tpl},
              open(os.path.join(PACK, name + '_fill.json'), 'w',
                   encoding='utf-8'), ensure_ascii=False, indent=1)
    print('已写出 fill.json')


if __name__ == '__main__':
    main()
