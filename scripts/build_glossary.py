#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""术语表索引生成：扫各章 trans.json，定位每个术语首次出现，产出附录 terms 块。

用法：
  python build_glossary.py <glossary.json> <trans.json>... [--append <前言trans.json>] [--out <blocks.json>]

  <trans.json> 按全书先后顺序给出（分章 docx 的译文文件）。
  --append  把生成的块直接追加进前言/附录 trans.json（随后跑 build_front.py）
  --out     把块写入文件；两者都不给则打印到 stdout

glossary.json 格式见 assets/glossary.example.json：
  {"英文术语": {"zh": "中文译名", "note": "可选"}, ...}
  值也可以直接是字符串（= 中文译名）。

输出块（build_front.py 的 terms 类型）：
  [{"type":"h1","text":"术语表"},
   {"type":"terms","items":[["英文","中文","第 3 章"], ...]}]

未在正文找到首次出现的术语仍会列出（首次出现记为「—」）并打印提示：
它们可能只出现在图内或代码里，人工核对后再决定去留。
"""
import json
import os
import re
import sys


def block_texts(blk):
    """取出块里可能出现术语的文本字段。"""
    out = []
    for k in ('text', 'title', 'intro', 'quote'):
        v = blk.get(k)
        if isinstance(v, str):
            out.append(v)
    for k in ('items', 'toc'):
        v = blk.get(k)
        if isinstance(v, list):
            out.extend(x for x in v if isinstance(x, str))
    for pair in blk.get('notes') or []:
        if isinstance(pair, (list, tuple)):
            out.extend(x for x in pair if isinstance(x, str))
    return out


def main():
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    gloss_p = args[0]
    rest = args[1:]
    append_p = out_p = None
    trans_ps = []
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == '--append':
            append_p = rest[i + 1]
            i += 2
        elif a == '--out':
            out_p = rest[i + 1]
            i += 2
        else:
            trans_ps.append(a)
            i += 1
    if not trans_ps:
        print('!! 请至少给出一个 trans.json（按全书顺序）')
        return 1

    gloss = json.load(open(gloss_p, encoding='utf-8-sig'))
    terms = {}
    for k, v in gloss.items():
        if k.startswith('_'):
            continue
        terms[k] = v['zh'] if isinstance(v, dict) else str(v)
    if not terms:
        print('!! 术语表为空')
        return 1

    pats = {en: re.compile(r'(?<![A-Za-z0-9])' + re.escape(en) +
                           r'(?![A-Za-z0-9])', re.IGNORECASE)
            for en in terms}
    found = {}  # en -> 首次出现章节

    for tp in trans_ps:
        if not os.path.exists(tp):
            print(f'!! 缺文件: {tp}')
            return 1
        fallback = os.path.splitext(os.path.basename(tp))[0].replace('_trans', '')
        blocks = json.load(open(tp, encoding='utf-8-sig'))
        label = fallback
        for blk in blocks:
            if blk.get('type') == 'chapter_open':
                num = str(blk.get('num', '')).strip()
                if num:
                    label = f'第 {num} 章'
            if len(found) == len(terms):
                break
            for txt in block_texts(blk):
                for en, pat in pats.items():
                    if en not in found and pat.search(txt):
                        found[en] = label

    items = [[en, zh, found.get(en, '—')] for en, zh in terms.items()]
    missing = [en for en in terms if en not in found]
    blocks_out = [{'type': 'h1', 'text': '术语表'},
                  {'type': 'terms', 'items': items}]

    if append_p:
        front = json.load(open(append_p, encoding='utf-8-sig'))
        front.extend(blocks_out)
        json.dump(front, open(append_p, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print(f'已追加 {len(items)} 条术语到 {append_p}')
    elif out_p:
        json.dump(blocks_out, open(out_p, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print(f'saved {out_p}')
    else:
        print(json.dumps(blocks_out, ensure_ascii=False, indent=1))

    print(f'术语 {len(items)} 条，正文定位到 {len(found)} 条')
    if missing:
        print(f'!! 未在正文找到（可能只在图内/代码里，人工核对）: {missing}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
