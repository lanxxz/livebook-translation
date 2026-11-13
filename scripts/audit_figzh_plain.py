# -*- coding: utf-8 -*-
"""内容层复核：把图内「纯英文」条目按性质分类，找出应译未译（AB3/AB4）。

图内译文生成脚本的兜底常是「映射表没命中 → 写英文原文」，而 `check_cov.py`
只校验「键是否存在」，不校验「译文是否等于原文」。于是 45% 的英文保留里
混进真漏译：流程图节点、代码清单箭头注释、表格说明列。

本脚本把纯英文条目拆成六档，只有「PLAIN」必须译：

    标识符 / 短标签 / 数据 / URL / 全大写清单标题  →  规范允许保留
    PLAIN（普通英文句子，含虚词）                →  必须译

判定单位是**图**而不是条目（AB4）：短节点名的流程图会被「短标签」判据漏掉，
所以额外给出「整图疑似应译」清单。

用法：
    python audit_figzh_plain.py [--root 项目根] [--json 结果.json]

依赖：`work/<doc>_figzh.txt`。
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

# 代码/标识符特征
CODE = re.compile(r'[_\.\(\)\[\]{}<>«»/]|^[a-z]+[A-Z]|https?://|www\.')
# 英文虚词：出现即说明是句子/短语，不是标识符
STOPW = set('''the a an of to in for with and or is are be been this that these those your you
we they it its can will would should may might when how what where which who use used using
from by as at on into over under after before while if then than such more most other some any
each both all not no yes'''.split())


def find_root(p):
    if p:
        return os.path.abspath(p)
    d = os.getcwd()
    for _ in range(4):
        if os.path.exists(os.path.join(d, 'docs.json')) or \
           os.path.exists(os.path.join(d, 'book.json')):
            return d
        d = os.path.dirname(d)
    return os.getcwd()


def classify(s):
    """单条判定。返回 None 表示已中文化（不用管）。"""
    s = s.strip()
    if not s:
        return None
    if re.search(r'[\u4e00-\u9fff]', s):
        return None
    if re.search(r'https?://|www\.', s):
        return 'URL'
    if CODE.search(s):
        return '标识符'
    words = re.findall(r"[A-Za-z][A-Za-z'\-]+", s)
    if len(words) < 3:
        return '短标签'
    if sum(1 for w in words if w.lower() in STOPW) >= 1:
        letters = [c for c in s if c.isalpha()]
        if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.85:
            return '全大写清单标题'
        return 'PLAIN'
    return '数据/名称'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', help='项目根')
    ap.add_argument('--json', help='明细写成 JSON')
    a = ap.parse_args()

    root = find_root(a.root)
    work = os.path.join(root, 'work')

    stat = Counter()
    plain = []                       # (doc, fig, text)
    per_fig = defaultdict(list)      # (doc, fig) -> [(kind, text)]

    for f in sorted(glob.glob(os.path.join(work, '*_figzh.txt'))):
        doc = os.path.basename(f)[:-len('_figzh.txt')]
        cur = None
        for ln in open(f, encoding='utf-8'):
            ln = ln.rstrip('\n')
            if ln.startswith('@@FIG '):
                cur = ln.split()[1]
                continue
            if not ln.startswith('ZH '):
                continue
            v = ln[3:]
            k = classify(v)
            if k is None:
                stat['已中文化'] += 1
                continue
            stat[k] += 1
            per_fig[(doc, cur)].append((k, v.strip()))
            if k == 'PLAIN':
                plain.append((doc, cur, v.strip()))

    total = sum(stat.values())
    print(f'图内条目合计 {total}')
    for k in ('已中文化', '标识符', '短标签', '数据/名称', 'URL', '全大写清单标题', 'PLAIN'):
        if stat.get(k):
            pct = stat[k] / total
            print(f'  {k:12s} {stat[k]:5d}  {pct:5.1%}')
    print(f'\n★ 应译未译（PLAIN）：{len(plain)} 条')
    if plain:
        print('按文档：', Counter(d for d, _, _ in plain).most_common())
        for d, fig, v in plain:
            print(f'   {d}/{fig}: {v[:90]}')

    # 整图疑似应译（AB4）：整图全英文 + 条目 ≥3 + ≥70% 是普通英文词组成
    whole = []
    for (doc, fig), items in per_fig.items():
        kinds = [k for k, _ in items]
        if len(items) < 3:
            continue
        normal = sum(1 for k in kinds if k in ('PLAIN', '短标签', '全大写清单标题'))
        if normal / len(items) >= 0.7 and 'PLAIN' not in kinds:
            whole.append((doc, fig, len(items), [t for _, t in items][:6]))
    print(f'\n△ 整图疑似应译（短节点名流程图会被「短标签」漏掉）：{len(whole)} 张')
    for doc, fig, n, sample in whole:
        print(f'   {doc}/{fig}（{n} 条）: {sample}')

    print('\n判读要求：')
    print('  1. PLAIN 一般都要译（流程图节点、代码箭头注释、表格说明列）。')
    print('  2. 「整图疑似应译」要逐张看图确认：流程图 → 译；图例条/坐标轴 → 保留。')
    print('  3. 数据表按项目口径整表统一，不要逐格决定（AB5）。')

    if a.json:
        json.dump({'stat': dict(stat), 'plain': plain,
                   'whole_figures': whole},
                  open(a.json, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print(f'\n明细已写入 {a.json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
