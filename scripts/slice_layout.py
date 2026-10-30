# -*- coding: utf-8 -*-
"""把整本 layout 按文档（章/附录/前言）切片，产出每份文档的：
  <doc>_layout.json   本档的块序列
  <doc>_dump.txt      人可读的英文版面 dump（翻译时看这个）
  <doc>_figtexts.json 本档的图内文字清单

用法：
    python slice_layout.py [docs.json]

docs.json 格式（也可以直接在 book.json 里放 "docs" 键）：
    [{"id":"ch01","title":"本地 AI 入门","num":"1","kind":"ch","from":28,"to":46},
     {"id":"apA","title":"命令速查","num":"A","kind":"apx","from":272,"to":280},
     {"id":"front","title":"前言与导读","num":"","kind":"front","from":2,"to":27}]

依赖 work/book_layout.json 与 work/book_figtexts.json
（parse_layout / extract_fig_texts 的产物）。
"""
import json
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def project_root():
    """定位项目根：含 book.json 或 docs.json 的目录。

    依次尝试：脚本所在目录向上 4 级 → 当前工作目录向上 4 级。
    这样脚本放在 <项目>/scripts/ 或直接放在技能目录里都能用。
    """
    def _up(start):
        d = os.path.abspath(start)
        for _ in range(4):
            if (os.path.exists(os.path.join(d, "book.json"))
                    or os.path.exists(os.path.join(d, "docs.json"))):
                return d
            d = os.path.dirname(d)
        return None

    for start in (os.path.dirname(os.path.abspath(__file__)), os.getcwd()):
        hit = _up(start)
        if hit:
            return hit
    # 兜底：脚本在 <项目>/scripts/ 里
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ROOT = project_root()
WORK = os.path.join(ROOT, 'work')


def load_docs(argv):
    """优先级：命令行路径 → 项目根 docs.json → book.json 的 docs 键。"""
    if len(argv) > 1 and os.path.exists(argv[1]):
        return json.load(open(argv[1], encoding='utf-8'))
    p = os.path.join(ROOT, 'docs.json')
    if os.path.exists(p):
        return json.load(open(p, encoding='utf-8'))
    conf = os.path.join(ROOT, 'book.json')
    if os.path.exists(conf):
        cfg = json.load(open(conf, encoding='utf-8'))
        if cfg.get('docs'):
            return cfg['docs']
    sys.exit('缺少 docs.json（或在 book.json 里提供 docs 列表）')


def dump_page(lines, pn, blocks):
    lines.append('=' * 12 + ' p' + pn)
    for blk in blocks:
        t = blk['type']
        if t == 'chapter_open':
            lines.append(f"  [CH {blk['num']}] apx={blk.get('appendix')} {blk['title']}")
            for it in blk.get('toc_items') or []:
                lines.append(f"       TOC: {it}")
            if blk.get('intro'):
                lines.append(f"       INTRO: {blk['intro']}")
        elif t == 'part_open':
            lines.append(f"  [PART {blk['num']}] {blk['title']}")
            for pp in blk.get('body') or []:
                lines.append(f"       BODY: {pp}")
        elif t == 'heading':
            lines.append(f"  [H{blk['level']}] {blk['text']}")
        elif t == 'para':
            lines.append(f"  [P] {blk['text']}")
        elif t in ('list', 'numlist'):
            for i, it in enumerate(blk['items'], 1):
                lines.append(f"  [{t}#{i}] {it}")
        elif t == 'code':
            lines.append(f"  [CODE {blk.get('lines', 0)}L]")
            for ln in blk['text'].split('\n'):
                lines.append('      |' + ln)
        elif t == 'figure':
            txts = ' ¦ '.join(x['text'] for x in blk.get('texts') or [])
            lines.append(f"  [FIG] cap={blk.get('caption', '')!r}")
            if txts:
                lines.append(f"      TEXTS: {txts}")
        elif t == 'table':
            g = blk['grid']
            lines.append(f"  [TABLE {g['rows']}x{g['cols']}] "
                         f"cap={blk.get('caption', '')!r}")
            for row in g['data']:
                lines.append('      | ' + ' | '.join(row))


def main():
    docs = load_docs(sys.argv)
    book = json.load(open(os.path.join(WORK, 'book_layout.json'),
                          encoding='utf-8'))['pages']
    fig_all = json.load(open(os.path.join(WORK, 'book_figtexts.json'),
                             encoding='utf-8'))

    for d in docs:
        a, b = d['from'], d['to']
        pages = {k: v for k, v in book.items() if a <= int(k) <= b}
        base = os.path.join(WORK, d['id'])

        json.dump({'pages': pages},
                  open(base + '_layout.json', 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)

        lines = []
        for pn in sorted(pages, key=int):
            dump_page(lines, pn, pages[pn])
        open(base + '_dump.txt', 'w', encoding='utf-8').write('\n'.join(lines))

        keys = [k for k in fig_all if a <= fig_all[k]['page'] <= b]
        json.dump({k: fig_all[k] for k in keys},
                  open(base + '_figtexts.json', 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)

        nblk = sum(len(v) for v in pages.values())
        print(f"{d['id']}: p{a}-{b}  pages={len(pages)}  figs={len(keys)}  blocks={nblk}")


if __name__ == '__main__':
    main()
