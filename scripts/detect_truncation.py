# -*- coding: utf-8 -*-
"""内容层复核：检测「正文段落尾部整段漏译」（AB2）。

双闸门（`check_cov.py` / `check_zh.py`）只查「块号/键是否对齐」，不查译文内容是否
等长——一个 1139 字符的英文段落只译了 163 字符，在闸门眼里依然完美通过。

本脚本补这一层。核心思路：**中文会意译动词与名词，但专有名词（`Scout`、`watsonx`）
和数字（`2.788M`、`$6M`）必定原样出现**。所以只用这两类锚点，避开「同义改写」误报：

    前半段锚点命中率 ≥ 0.5  且  后半段锚点命中率 ≤ 0.2  →  尾部被截断

用法：
    python detect_truncation.py [--root 项目根] [--json 结果.json] [doc …]

依赖：`work/<doc>_skel.txt`（英文原文）与 `work/<doc>_trans.json`（译文）。
命中**不要求为 0**，但每条都要人工判读：确为缺陷就补译，误报就写清原因。
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import Counter

# 句首高频词：不作为专名锚点
SKIP_CAP = set('''The This These That Those You Your For When While However Then But And Its It
In On At As By With From Each Both Some Many Most Other Another Such After Before During Once
Here There What How Why Where Which Who Not Now Also Additionally First Second Third Finally
Moreover Furthermore Despite Instead Unlike Like Because Since Although Though'''.split())


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


def load_skel(work, doc):
    """读骨架里的英文原文：{块号: EN 文本}。"""
    p = os.path.join(work, doc + '_skel.txt')
    if not os.path.exists(p):
        return {}
    txt = open(p, encoding='utf-8').read()
    out = {}
    for b in re.split(r'^@@BLOCK ', txt, flags=re.M)[1:]:
        n = int(b.split()[0])
        m = re.search(r'%%EN\n(.*?)\n?%%ZH', b, re.S)
        out[n] = m.group(1).strip() if m else ''
    return out


def split_sents(t):
    t = re.sub(r'\s+', ' ', t).strip()
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z“"(\[])', t)
    return [p.strip() for p in parts if len(p.strip()) > 10]


def anchors(text):
    """提取专名与数字。句首词不算（多为 The/This/You）。"""
    t = re.sub(r'`[^`]*`', ' ', text)
    t = re.sub(r'https?://\S+', ' ', t)
    props = set()
    for m in re.finditer(r'(?<=[a-z,;:\)\]]\s)([A-Z][A-Za-z0-9\-]{2,})', t):
        w = m.group(1)
        if w not in SKIP_CAP:
            props.add(w)
    nums = set(re.findall(r'(?<![\w.])\d[\d,]*\.?\d*[BMKGT%]?(?=[\s,.;:)\]）]|$)', t))
    nums = {n for n in nums if len(n) >= 2 or n.isdigit()}
    return props, nums


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('docs', nargs='*', help='只查这些文档（默认全部）')
    ap.add_argument('--root', help='项目根（含 docs.json / work）')
    ap.add_argument('--json', help='把命中明细写成 JSON')
    a = ap.parse_args()

    root = find_root(a.root)
    work = os.path.join(root, 'work')
    only = a.docs or None

    rows = []
    for f in sorted(glob.glob(os.path.join(work, '*_trans.json'))):
        doc = os.path.basename(f)[:-len('_trans.json')]
        if only and doc not in only:
            continue
        sk = load_skel(work, doc)
        if not sk:
            continue
        tr = json.load(open(f, encoding='utf-8'))
        for i, b in enumerate(tr):
            if b.get('type') not in ('p', 'list', 'numlist'):
                continue
            en = sk.get(i, '')
            if len(en) < 150:
                continue
            sents = split_sents(en)
            if len(sents) < 3:
                continue
            zh = b.get('text') or ' '.join(b.get('items') or [])
            if not zh:
                continue
            half = len(sents) // 2
            hp, hn = anchors(' '.join(sents[:half]))
            tp, tn = anchors(' '.join(sents[half:]))
            h_all, t_all = hp | hn, tp | tn
            if len(h_all) < 2 or len(t_all) < 2:
                continue
            hr = len({x for x in h_all if x in zh}) / len(h_all)
            tr_ = len({x for x in t_all if x in zh}) / len(t_all)
            if hr >= 0.5 and tr_ <= 0.2:
                rows.append({
                    'doc': doc, 'blk': i, 'type': b.get('type'),
                    'nsent': len(sents), 'head_rate': round(hr, 2),
                    'tail_rate': round(tr_, 2),
                    'tail_miss': sorted(t_all - {x for x in t_all if x in zh}),
                    'tail_sents': sents[half:], 'zh_tail': zh[-120:],
                    'en_len': len(en), 'zh_len': len(zh),
                })

    rows.sort(key=lambda r: (r['tail_rate'], -len(r['tail_miss'])))
    print(f'疑似「尾部截断」块：{len(rows)}')
    if rows:
        print('按文档：', Counter(r['doc'] for r in rows).most_common())
    for r in rows:
        print(f"\n  {r['doc']} B{r['blk']} ({r['type']}, {r['nsent']} 句, "
              f"前半锚点 {r['head_rate']} / 后半 {r['tail_rate']}, "
              f"EN {r['en_len']}→ZH {r['zh_len']})")
        print(f"     后半段未出现的锚点：{r['tail_miss']}")
        print(f"     疑似未译：{' | '.join(s[:110] for s in r['tail_sents'])[:400]}")
        print(f"     ZH 结尾：{r['zh_tail']}")
    if rows:
        print('\n判读要求：命中不等于缺陷。中文压缩意译（把三句并成一句）也会命中，')
        print('必须回看原文与译文全文再定。确为缺陷就补译后重跑本脚本。')
    if a.json:
        json.dump(rows, open(a.json, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print(f'\n明细已写入 {a.json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
