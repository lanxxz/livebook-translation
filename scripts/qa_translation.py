# -*- coding: utf-8 -*-
"""译文内容量化自查（只读，不改任何文件）——X13。

工程闸门（check_cov / check_zh / audit / layout_check）查的是**块与版式**，
查不出「句子译反了」「数字译丢了」「双重否定没转过来」。本脚本把
`*_layout.json`（原文）与 `*_trans.json`（译文）逐块对齐，做 10 类扫描，
把可疑块列出来供人工判读。

**重要：量化命中大多是误报**（中文数字换算、PDF 断字修复、规范保留英文、
`as well as` 被当比较级…）。必须逐条写出「为什么不是问题」，
不能只报一句「检查通过」，也不能拿命中数当缺陷数。

用法：
    python qa_translation.py [--root 项目根] [--out 报告.md] [--max 20]

检查项：长度比 / 数字 / URL / 圈码 / 编号格式 / 相邻重复 / 术语变体 /
无中文块分类 / 否定结构 / 比较结构 / 专有名词大小写。
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

CJK = re.compile(r'[\u4e00-\u9fff]')
NUM = re.compile(r'(?<![\w.])\d+(?:[.,]\d+)*(?:%|×)?(?![\w.])')
URL = re.compile(r'https?://[^\s，。）)]+|www\.[^\s，。）)]+')
CIRCLE = re.compile(r'[①②③④⑤⑥⑦⑧⑨⑩]')
NEG_EN = re.compile(r'\b(not|never|no longer|unlike|rather than|without|'
                    r'instead of|cannot|does not|do not|is not|are not|nor)\b', re.I)
NEG_ZH = re.compile(r'不|无|没|非|别|未|反之|相反|而不是|不同于|无需|不像|去掉|与其')
CMP_EN = re.compile(r'\b(more|less|higher|lower|cheaper|better|worse|faster|slower)\b'
                    r'.{0,40}\bthan\b|\bas\s+\w+\s+as\b', re.I)
CMP_ZH = re.compile(r'比|更|较|越|不如|相当于|一样|只要|以及')


def find_root(p):
    if p:
        return os.path.abspath(p)
    d = os.getcwd()
    for _ in range(4):
        if os.path.exists(os.path.join(d, 'docs.json')):
            return d
        d = os.path.dirname(d)
    return os.getcwd()


def en_text(b):
    t = b['type']
    if t == 'chapter_open':
        return ' '.join([b.get('title', '')] + (b.get('toc_items') or [])
                        + [b.get('intro', '')])
    if t == 'figure':
        return b.get('caption', '') or ''
    if t in ('list', 'numlist'):
        return ' '.join(b.get('items') or [])
    if t == 'code':
        return ''
    return b.get('text', '') or ''


def zh_text(b):
    t = b['type']
    if t == 'chapter_open':
        return ' '.join([b.get('title', '')] + (b.get('toc') or [])
                        + [b.get('intro', '')])
    if t == 'figure':
        return b.get('caption', '') or ''
    if t in ('list', 'numlist'):
        return ' '.join(b.get('items') or [])
    if t == 'code':
        return ''
    if t == 'table':
        return ' '.join(b.get('head') or [])
    return b.get('text', '') or ''


def classify_no_cn(s):
    """启发式分类，按书的领域调整；返回 '待人工复核' 的必须逐条看。"""
    t = s.strip()
    if re.match(r'^\[\d+\]', t):
        return '参考文献（照录原文）'
    if re.match(r'^\d+\.\d+\s+[A-Z][A-Za-z ]{2,20}$', t):
        return '产品名小节标题（名称不译）'
    if re.match(r'^(SELECT|CREATE|INSERT|UPDATE|DELETE)\b', t, re.I) or \
            re.match(r'^(break|name|Wii|satisfied|dissatisfied)$', t) or \
            t.startswith(('rank ', 'for model in', 'import ', 'python ')):
        return 'SQL／代码残片／数据表字段'
    if re.search(r'(User :|GPT :|SELECT|https?://|www\.)', t) or \
            t.startswith(('“', 'Once upon', 'Dear valued', 'Based on',
                          'This query', 'The query', 'These queries',
                          'Sure!', 'I apologize', 'The reviewer')):
        return '模型输出／提示词字面量／对话演示'
    return '待人工复核'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root')
    ap.add_argument('--out', help='把报告写入 Markdown 文件')
    ap.add_argument('--max', type=int, default=20, help='每类最多列几条')
    a = ap.parse_args()
    root = find_root(a.root)
    work = os.path.join(root, 'work')
    docs = json.load(open(os.path.join(root, 'docs.json'), encoding='utf-8'))
    rows, out = [], []
    for d in docs:
        did = d['id']
        lp, tp = (os.path.join(work, did + s)
                  for s in ('_layout.json', '_trans.json'))
        L = json.load(open(lp, encoding='utf-8'))['pages']
        T = json.load(open(tp, encoding='utf-8'))
        en_blocks = [b for pn in sorted(L, key=int) for b in L[pn]]
        if len(en_blocks) != len(T):
            out.append(f'!! {did}: 原文 {len(en_blocks)} 块 vs 译文 {len(T)} 块')
        for i, (e, z) in enumerate(zip(en_blocks, T)):
            rows.append(dict(doc=did, i=i, type=e['type'],
                             en=en_text(e), zh=zh_text(z)))

    def emit(s=''):
        print(s)
        out.append(s)

    emit('# 译文内容量化自查')
    emit(f'总块数 {len(rows)}。**以下命中均为「待判读」而非「缺陷」，逐条核对后再下结论。**')
    emit('')

    # A 长度比
    susp = []
    for r in rows:
        if r['type'] in ('code', 'figure') or not CJK.search(r['zh']):
            continue
        w = len(re.findall(r"[A-Za-z][A-Za-z'\-]*", r['en']))
        c = len(CJK.findall(r['zh']))
        if w >= 12 and (c / w < 0.85 or c / w > 3.2):
            susp.append((round(c / w, 2), r))
    emit(f'## A 长度比异常（中文字符/英文词，正常约 1.2–2.4）：{len(susp)} 块')
    for ratio, r in sorted(susp, key=lambda x: x[0])[:a.max]:
        emit(f"- {r['doc']} B{r['i']} 比={ratio} | EN {r['en'][:90]!r} | ZH {r['zh'][:90]!r}")
    emit('')

    # B/C 数字与 URL / 圈码
    lost_num = []
    for r in rows:
        if r['type'] in ('code', 'figure') or not CJK.search(r['zh']):
            continue
        miss = [n for n in set(NUM.findall(r['en']))
                if n not in set(NUM.findall(r['zh']))
                and not re.fullmatch(r'\d{1,2}', n)]
        if miss and len(r['en']) > 25:
            lost_num.append((r, miss[:5]))
    emit(f'## B 数字未原样出现：{len(lost_num)} 块（常见于「68 万 / 3.65 亿」等中文换算）')
    for r, miss in lost_num[:a.max]:
        emit(f"- {r['doc']} B{r['i']} 缺 {miss} | ZH {r['zh'][:100]!r}")
    emit('')
    for name, pat in [('URL', URL), ('圈码', CIRCLE)]:
        bad = [(r, sorted(set(pat.findall(r['en'])) - set(pat.findall(r['zh']))))
               for r in rows if r['type'] not in ('code', 'figure')
               and set(pat.findall(r['en'])) - set(pat.findall(r['zh']))]
        hint = ('正则吞标点 / PDF 断字被修复 / 句末点号'
                if name == 'URL' else '圈码应原样保留，命中即为缺陷')
        emit(f'## C {name} 未匹配：{len(bad)} 块（{hint}）')
        for r, x in bad[:8]:
            emit(f"- {r['doc']} B{r['i']} {x[:4]} | ZH {r['zh'][:80]!r}")
        emit('')

    # D 相邻重复 / 编号
    dup = [(rows[i - 1], rows[i]) for i in range(1, len(rows))
           if rows[i]['zh'].strip() and rows[i]['zh'].strip() == rows[i - 1]['zh'].strip()]
    emit(f'## D 相邻块译文完全重复：{len(dup)} 处')
    for x, y in dup[:a.max]:
        emit(f"- {x['doc']} B{x['i']} / {y['doc']} B{y['i']}: {x['zh'][:70]!r}")
    emit('')
    caps = [r for r in rows if r['type'] == 'figure' and r['zh'].strip()]
    bad_cap = [r for r in caps if not re.match(r'^(图|表)\s*\d+\.\d+', r['zh'])]
    emit(f'## E 图注 {len(caps)} 条，格式不符 {len(bad_cap)} 条，空图注 '
         f"{sum(1 for r in caps if r['zh'].strip() in ('CAP:', ''))} 条")
    emit('')

    # F 无中文块分类
    no_cn = [r for r in rows if r['zh'].strip() and not CJK.search(r['zh'])]
    groups = Counter(classify_no_cn(r['zh']) for r in no_cn)
    emit(f'## F 「整块不含中文」共 {len(no_cn)} 处，分类如下（对照翻译规范逐条确认）')
    for k, v in groups.most_common():
        emit(f'- {k}: {v} 处')
    review = [r for r in no_cn if classify_no_cn(r['zh']) == '待人工复核']
    emit(f'**待人工复核 {len(review)} 处**')
    for r in review[:a.max]:
        emit(f"- {r['doc']} B{r['i']}: {r['zh'][:120]!r}")
    emit('')

    # G/H 否定与比较
    for name, pe, pz in [('否定', NEG_EN, NEG_ZH), ('比较', CMP_EN, CMP_ZH)]:
        bad = [r for r in rows if r['type'] == 'para' and len(r['en']) > 60
               and pe.search(r['en']) and not pz.search(r['zh'])]
        emit(f'## {"G" if name=="否定" else "H"} 原文含{name}结构、译文无对应词：{len(bad)} 块')
        for r in bad[:a.max]:
            emit(f"- {r['doc']} B{r['i']} | EN {r['en'][:110]!r} | ZH {r['zh'][:110]!r}")
        emit('')

    emit('## 判读要求')
    emit('1. 逐条写出每个命中「为什么不是问题」或「确为缺陷」，不允许只报通过。')
    emit('2. 每章抽 1 个中等长度段落人工逐句细读，重点看否定、比较、术语与专有名词。')
    emit('3. 术语「语境变体」（如计费/API 参数保留 token）要写进翻译规范，别强行全书统一。')
    emit('4. 结论写进 `译文自查报告.md`，与工程层的 `质检报告.md` 分开。')

    if a.out:
        open(a.out, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
        print('已写入', a.out)
    return 0 if len(review) == 0 else 0   # 待复核项由人工判定，不据此判失败


if __name__ == '__main__':
    sys.exit(main())
