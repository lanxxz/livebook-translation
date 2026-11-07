# -*- coding: utf-8 -*-
"""生成"待译骨架"：把 layout 的每块列成 EN + 空 ZH 槽，供人工/代理逐块填空。

用法：python mk_skeleton.py <doc_id> [<doc_id> ...]
      python mk_skeleton.py --all      # 跑 docs.json / book.json 里的全部文档

输出 work/<doc>_skel.txt 与 work/<doc>_figskel.txt
骨架格式（只用 %%ZH … %%END 之间是可改区域，其余行不许动）：

@@BLOCK 12 p
%%EN
英文原文（只读）
%%ZH
%%END
"""
import json
import os
import sys


def project_root():
    """向上找含 book.json / docs.json 的目录（脚本放项目根或 scripts/ 都能用）。"""
    def _up(start):
        d = os.path.abspath(start)
        for _ in range(4):
            if (os.path.exists(os.path.join(d, 'book.json'))
                    or os.path.exists(os.path.join(d, 'docs.json'))):
                return d
            d = os.path.dirname(d)
        return None

    for start in (os.path.dirname(os.path.abspath(__file__)), os.getcwd()):
        hit = _up(start)
        if hit:
            return hit
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ROOT = project_root()
WORK = os.path.join(ROOT, 'work')


def all_docs():
    """docs.json → book.json 的 docs 键；都没有则返回空列表。"""
    p = os.path.join(ROOT, 'docs.json')
    if os.path.exists(p):
        return [d['id'] for d in json.load(open(p, encoding='utf-8'))]
    conf = os.path.join(ROOT, 'book.json')
    if os.path.exists(conf):
        cfg = json.load(open(conf, encoding='utf-8-sig'))
        if cfg.get('docs'):
            return [d['id'] for d in cfg['docs']]
    return []


def emit(fh, idx, kind, en_lines, hint):
    fh.append(f'@@BLOCK {idx} {kind}\n')
    if hint:
        fh.append(f'@@  {hint}\n')
    fh.append('%%EN\n')
    for ln in en_lines:
        fh.append(ln + '\n')
    fh.append('%%ZH\n')
    fh.append('%%END\n\n')


def main():
    args = [a for a in sys.argv[1:] if a != '--all']
    docs = all_docs() if '--all' in sys.argv else args
    if not docs:
        sys.exit(__doc__)
    for doc in docs:
        lay = json.load(open(os.path.join(WORK, doc + '_layout.json'), encoding='utf-8'))['pages']
        out = []
        idx = 0
        for pno in sorted(lay, key=int):
            for b in lay[pno]:
                t = b['type']
                if t == 'chapter_open':
                    en = [f"TITLE: {b['title']}"]
                    en.append('APPENDIX: ' + ('yes' if b.get('appendix') else 'no'))
                    en.append('NUM: ' + b['num'])
                    for it in b['toc_items']:
                        en.append('TOC: ' + it)
                    if b['intro']:
                        en.append('INTRO: ' + b['intro'])
                    emit(out, idx, 'chapter_open', en,
                         '只译 TITLE/TOC/INTRO 三行的值，KEY 名与 APPENDIX/NUM 行保持原样；'
                         'TOC 每项一行')
                elif t == 'part_open':
                    en = [f"NUM: {b['num']}", f"TITLE: {b['title']}"]
                    for pp in b['body']:
                        en.append('BODY: ' + pp)
                    emit(out, idx, 'part_open', en, '只译 TITLE/BODY 的值，NUM 保持原样；BODY 每段一行')
                elif t == 'heading':
                    emit(out, idx, 'h2' if b['level'] == 2 else 'h3', [b['text']],
                         '标题译文：保留 1.1 / 1.1.1 这类编号，用 \t 或空格分隔')
                elif t == 'para':
                    emit(out, idx, 'p', [b['text']], '整段译文；`行内代码` 用反引号保留')
                elif t in ('list', 'numlist'):
                    emit(out, idx, t, b['items'], '每项一行；不要在行首加 "-" 或编号')
                elif t == 'code':
                    emit(out, idx, 'code', b['text'].split('\n'),
                         '代码不译：原样抄回（缩进保留）。仅在确有必要时用行内注释')
                elif t == 'figure':
                    key = b.get('key') or ''
                    emit(out, idx, 'figure', ['CAP: ' + b.get('caption', '')],
                         f"图注译文一行，写在 CAP: 之后；key={key}")
                elif t == 'table':
                    g = b['grid']
                    en = ['CAP: ' + b.get('caption', '')]
                    en.append('HDR: ' + ' | '.join(g['data'][0]))
                    for row in g['data'][1:]:
                        en.append('ROW: ' + ' | '.join(row))
                    emit(out, idx, 'table', en,
                         'CAP 是表标题；HDR 是表头；ROW 每行一条；用 " | " 分隔单元格，'
                         '单元格数与原文一致；命令/代码保持英文')
                idx += 1
        open(os.path.join(WORK, doc + '_skel.txt'), 'w', encoding='utf-8').write(
            ''.join(x for x in _chunks(out)))
        # 图内文字骨架
        ft = json.load(open(os.path.join(WORK, doc + '_figtexts.json'), encoding='utf-8'))
        fo = [f'# 图内文字：图 {len(ft)} 个，块 '
              f'{sum(len(v["blocks"]) for v in ft.values())} 个\n'
              '# 译文必须短（图内标签空间小）；英文标识符/命令不译\n']
        for key in sorted(ft, key=lambda k: (ft[k]['page'], k)):
            v = ft[key]
            fo.append(f'@@FIG {key}  bbox={v["bbox"]}  blocks={len(v["blocks"])}\n')
            for b in v['blocks']:
                w = round(b['bbox'][2] - b['bbox'][0], 1)
                h = round(b['bbox'][3] - b['bbox'][1], 1)
                fo.append(f'@@T {b["id"]} {b["size"]}pt {w}x{h}pt L{len(b["line_bboxes"])} '
                          f'{"ROT " if b["rotated"] else ""}{"CODE " if b.get("code_like") else ""}\n')
                fo.append(f'EN {b["en"]}\n')
                fo.append('ZH \n\n')
        open(os.path.join(WORK, doc + '_figskel.txt'), 'w', encoding='utf-8').write(''.join(fo))
        print(f'{doc}: blocks={idx} figkeys={len(ft)}')


def _chunks(out):
    return out


if __name__ == '__main__':
    main()
