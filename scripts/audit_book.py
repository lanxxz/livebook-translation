# -*- coding: utf-8 -*-
"""交付前全书体检：块序列 / 漏译 / 代码完整性 / 图内溢出 / 图片与表格计数。

用法：python audit_book.py <chapters.json>
chapters.json 形如：
[
  {"ch":"1","layout":"work/ch1_layout.json","trans":"work/ch1_trans.json",
   "docx":"out/01_第1章.docx","figs":"figs/ch01"}
]

检查项：
  1. 块序列一致（跨页拆分的表格自动折叠为一块）
  2. 漏译（整块不含中文，排除代码/专有名词/URL/引号字面量）
  3. 代码块不得含中文（代码正文不译）
  4. 图内文字：无 OVERFLOW、无 MISSING，最小字号不低于阈值
"""
import json
import os
import re
import sys

CJK = re.compile(r'[\u4e00-\u9fff]')

# 合理的"无中文"内容：标识符、短专有名词、URL、纯标点、引号字面量
ALLOW = re.compile(
    r'^(?:'
    r'[A-Za-z_@][\w.$\-]*[。，、]?'
    r'|[A-Za-z][\w .\-（）()]*'
    r'|https?://\S+[。，]?'
    r'|[\s\W]*'
    r')$')

MIN_FS_PT = 4.6          # 与 render_figs.MIN_PT_HARD 一致


def is_proper_noun(s):
    s = s.strip()
    if re.fullmatch(r'["“”\'‘’「」][^"“”\'‘’「」]{1,40}["“”\'‘’「」][。，、]?', s):
        return True
    if not ALLOW.match(s):
        return False
    words = re.findall(r'[A-Za-z][\w\-]*', s)
    return len(words) <= 4 and len(s) <= 40


def layout_seq(layout_p):
    """原书块类型序列；相邻两个 table 折叠为一个（跨页续表）。"""
    pages = json.load(open(layout_p, encoding='utf-8'))['pages']
    seq = []
    for pno in sorted(pages, key=int):
        for b in pages[pno]:
            t = b['type']
            if t == 'heading':
                seq.append('h%d' % b['level'])
            elif t == 'para':
                seq.append('p')
            else:
                seq.append(t)
    out, i = [], 0
    while i < len(seq):
        if i + 1 < len(seq) and seq[i] == 'table' and seq[i + 1] == 'table':
            out.append('table')
            i += 2
            continue
        out.append(seq[i])
        i += 1
    return out


def check_chapter(item):
    ch = item.get('ch', '?')
    r = {'ch': ch, 'ok': True, 'notes': []}

    # 1) 块序列
    if item.get('layout') and os.path.exists(item['layout']) \
            and item.get('trans') and os.path.exists(item['trans']):
        a = layout_seq(item['layout'])
        tr = json.load(open(item['trans'], encoding='utf-8'))
        b = [x['type'] for x in tr]
        r['n_src'], r['n_tr'] = len(a), len(b)
        if a != b:
            r['ok'] = False
            first = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), None)
            r['notes'].append('块序列不一致（原文 %d / 译文 %d）首处差异 %s'
                              % (len(a), len(b), first))

    # 2/3) 漏译 + 代码含中文
    if item.get('trans') and os.path.exists(item['trans']):
        tr = json.load(open(item['trans'], encoding='utf-8'))
        miss, code_cn, cn_chars = [], 0, 0
        for i, blk in enumerate(tr):
            t = blk['type']
            vals = []
            if t in ('p', 'sidebar', 'h2', 'h3'):
                vals = [blk.get('text') or '']
            elif t in ('list', 'numlist'):
                vals = blk.get('items') or []
            elif t == 'chapter_open':
                vals = [blk.get('title') or '', blk.get('intro') or '']
            for v in vals:
                cn_chars += len(CJK.findall(v))
                if v.strip() and not CJK.search(v) and not is_proper_noun(v):
                    miss.append((i, t, v[:40]))
            if t == 'code' and CJK.search(blk.get('text') or ''):
                code_cn += 1
            if t == 'table':
                for c in (blk.get('head') or []):
                    cn_chars += len(CJK.findall(c))
                for row in (blk.get('rows') or []):
                    for c in row:
                        cn_chars += len(CJK.findall(c))
        r['miss'], r['code_cn'], r['cn'] = len(miss), code_cn, cn_chars
        if miss:
            r['ok'] = False
            r['notes'].append('漏译 %d 处：%s' % (len(miss), miss[:3]))
        if code_cn:
            r['ok'] = False
            r['notes'].append('代码块含中文 %d 个' % code_cn)

    # 4) 图内文字
    if item.get('figs'):
        rep_p = os.path.join(item['figs'], '_report.json')
        if os.path.exists(rep_p):
            rep = json.load(open(rep_p, encoding='utf-8'))
            bad, fs_min, n = [], 99, 0
            for key, entries in rep.items():
                for e in entries if isinstance(entries, list) else []:
                    if not isinstance(e, dict):
                        continue
                    n += 1
                    if e.get('status') not in ('OK', 'KEEP'):
                        bad.append((key, e.get('id'), e.get('status')))
                    if 'fs_pt' in e:
                        fs_min = min(fs_min, e['fs_pt'])
            r['fig_n'], r['fig_bad'] = n, len(bad)
            r['fig_fs_min'] = fs_min if n else 0
            if bad:
                r['ok'] = False
                r['notes'].append('图内异常 %d 处：%s' % (len(bad), bad[:4]))
            if n and fs_min < MIN_FS_PT:
                r['ok'] = False
                r['notes'].append('图内字号 %.1fpt 低于下限 %.1fpt'
                                  % (fs_min, MIN_FS_PT))

    # 5) docx 图片数
    if item.get('docx') and os.path.exists(item['docx']):
        try:
            from docx import Document
            doc = Document(item['docx'])
            r['docx_img'] = len(doc.inline_shapes)
            r['docx_tbl'] = len(doc.tables)
        except Exception as e:
            r['notes'].append('读 docx 失败：%s' % e)
    return r


def main():
    cfg_p = sys.argv[1]
    chapters = json.load(open(cfg_p, encoding='utf-8'))
    rows = [check_chapter(c) for c in chapters]

    print('%-5s %-8s %-8s %-8s %-6s %-6s %-6s %-6s %s'
          % ('章', '原文块', '译文块', '中文字', '漏译', '代码中', '图块', '图异常', '结论'))
    print('-' * 92)
    all_ok = True
    total_cn = 0
    for r in rows:
        total_cn += r.get('cn', 0)
        flag = '✓' if r['ok'] else '✗'
        if not r['ok']:
            all_ok = False
        print('%-5s %-8s %-8s %-8s %-6s %-6s %-6s %-6s %s'
              % (r['ch'], r.get('n_src', '-'), r.get('n_tr', '-'),
                 r.get('cn', '-'), r.get('miss', '-'), r.get('code_cn', '-'),
                 r.get('fig_n', '-'), r.get('fig_bad', '-'), flag))
        for nt in r['notes']:
            print('      · ' + nt)
    print('-' * 92)
    print('全书中文约 %d 字' % total_cn)
    print('结论：' + ('✓ 全部通过' if all_ok else '✗ 有章节需修'))
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
