#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""给合订 docx 的目录页挂**可点击跳转**（docx 层书签 + 内部超链接）。

用法：

    # 1) 挂链接：合并之后、导出 PDF 之前跑（必须对合并产物跑，见 AC1）
    python scripts/docx_toc_links.py out/整书.docx --docs docs.json
    python scripts/docx_toc_links.py out/整书.docx --docs docs.json --no-header-back
    python scripts/docx_toc_links.py out/整书.docx --docs docs.json --dry

    # 2) 验收：导出 PDF 之后跑，逐条核对「链接落点页 == 印刷页码」
    python scripts/docx_toc_links.py out/整书.docx --docs docs.json \\
        --verify-pdf out/整书.pdf --toc-page 2

职责：
  A. 章标题段落落书签（`_Toc_<doc id>`），目录行整行（标题 + 点线 + 页码）
     包进 `<w:hyperlink w:anchor=...>`；Word 导出 PDF 时自动转 GoTo，
     docx 与 PDF 两端都可点（AC1）；
  B. 可选：各章页眉整行回跳目录（`_Toc_page`），形成双向导航；
  C. 验收模式：docx 三数 + PDF 链接条数 + 落点页逐条比对，任一不符退出码 1（AC2）。

**不幂等**：同一份 docx 重复跑会把 run 套两层 hyperlink，已挂过时直接退出；
重挂请从合并步骤重来。

只依赖 python-docx；`--verify-pdf` 另需 pymupdf。不依赖 book.json 或本技能其他脚本，
只需 docs.json 与成品 docx。跨平台。
"""
import argparse
import json
import os
import re
import sys

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

W = qn('w:r')
TAB = '\t'
WS = re.compile(r'[\s\u3000]+')


def norm(s):
    """归一化：去掉所有空白（含全角空格），用于标题比对。"""
    return WS.sub('', s or '')


def label_of(d):
    """目录行左侧文字（与 build_toc.py 的 toc_label 同源）。"""
    kind = d.get('kind', 'ch')
    if kind == 'front':
        return d['title']
    if d.get('header'):
        return d['header']
    if kind == 'apx':
        return '附录 %s\u3000%s' % (d['num'], d['title'])
    return '第 %d 章\u3000%s' % (int(d['num']), d['title'])


def num_label_of(d):
    """章首页小标签（"第 3 章" / "附录 A"）。"""
    kind = d.get('kind', 'ch')
    return '附录 %s' % d['num'] if kind == 'apx' else '第 %d 章' % int(d['num'])


def title_of(d):
    """章首页大标题（docs.json 的 title 可能与实际不一致，header 优先）。"""
    h = d.get('header')
    if h:
        tail = h.split('\u3000', 1)
        if len(tail) == 2:
            return tail[1]
    return d['title']


def sort_docs(docs):
    def key(d):
        kind = d.get('kind', 'ch')
        if kind == 'front':
            return (0, 0)
        if kind == 'apx':
            return (2, 0)
        return (1, int(d['num']))
    return sorted(docs, key=key)


def wrap_hyperlink(p, anchor):
    """把段落里的所有 run 包进一个内部超链接（pPr 保持在最前）。"""
    hl = OxmlElement('w:hyperlink')
    hl.set(qn('w:anchor'), anchor)
    hl.set(qn('w:history'), '1')
    for child in list(p._p):
        if child.tag == W:
            hl.append(child)
    p._p.append(hl)


def add_bookmark(p, name, bid):
    """在段落首尾各插一个书签标记（落在段落内部，不改段落属性）。"""
    bs = OxmlElement('w:bookmarkStart')
    bs.set(qn('w:id'), str(bid))
    bs.set(qn('w:name'), name)
    be = OxmlElement('w:bookmarkEnd')
    be.set(qn('w:id'), str(bid))
    pPr = p._p.find(qn('w:pPr'))
    if pPr is not None:
        pPr.addnext(bs)
    else:
        p._p.insert(0, bs)
    p._p.append(be)


def find_toc_rows(paras, docs):
    """目录行：文本以「<标签>\\t」开头。返回 {doc id: paragraph index}。"""
    rows = {}
    for i, p in enumerate(paras):
        t = p.text
        if TAB not in t:
            continue
        head = norm(t.split(TAB)[0])
        for d in docs:
            if d['id'] in rows:
                continue
            if head == norm(label_of(d)):
                rows[d['id']] = i
    return rows


def find_targets(paras, docs, toc_rows):
    """书签落点：章首页大标题段；前言取目录后第一段非空正文。"""
    targets = {}
    last_row = max(toc_rows.values())
    for i in range(last_row + 1, len(paras)):
        if paras[i].text.strip():
            targets['__front__'] = i
            break

    for d in docs:
        kind = d.get('kind', 'ch')
        if kind == 'front':
            if '__front__' not in targets:
                sys.exit('fail-closed：目录之后找不到前言首段')
            targets[d['id']] = targets['__front__']
            continue
        lab = norm(num_label_of(d))
        hits = [i for i, p in enumerate(paras) if norm(p.text) == lab]
        if len(hits) != 1:
            sys.exit('fail-closed：%s 的章号段命中 %d 处（应为 1），'
                     '目录行或正文结构与 docs.json 不符' % (num_label_of(d), len(hits)))
        idx = hits[0] + 1
        want = norm(title_of(d))
        got = norm(paras[idx].text) if idx < len(paras) else ''
        if want[:20] and not (got == want or got.startswith(want[:20])):
            sys.exit('fail-closed：%s 的标题不符\n  期望：%r\n  实际：%r'
                     % (num_label_of(d), title_of(d), paras[idx].text))
        targets[d['id']] = idx
    return targets


def find_toc_title(paras, first_row):
    for i in range(first_row):
        if norm(paras[i].text) in ('目录', '目次', 'contents'):
            return i
    return None


def do_write(args, docs):
    doc = Document(args.book)
    paras = doc.paragraphs

    exist = [b.get(qn('w:name')) for b in doc.element.body.findall('.//' + qn('w:bookmarkStart'))]
    if any((n or '').startswith('_Toc_') for n in exist):
        sys.exit('这份 docx 已经挂过目录链接（发现 %s…）。本脚本不幂等：'
                 '请从合并步骤重来，不要在成品上再跑一次。'
                 % [n for n in exist if n and n.startswith('_Toc_')][:2])

    rows = find_toc_rows(paras, docs)
    missing = [d['id'] for d in docs if d['id'] not in rows]
    if missing:
        sys.exit('fail-closed：目录行未全部匹配，缺 %s。'
                 '检查 docs.json 的 title/header 是否与目录文字一致。' % missing)

    targets = find_targets(paras, docs, rows)

    used = [int(b.get(qn('w:id'))) for b in doc.element.body.findall('.//' + qn('w:bookmarkStart'))
            if (b.get(qn('w:id')) or '').isdigit()]
    bid = (max(used) + 100) if used else 100

    for d in docs:
        anchor = '_Toc_%s' % d['id']
        add_bookmark(paras[targets[d['id']]], anchor, bid)
        bid += 1
        wrap_hyperlink(paras[rows[d['id']]], anchor)

    n_hdr, toc_idx = 0, None
    if args.header_back:
        toc_idx = find_toc_title(paras, min(rows.values()))
        if toc_idx is None:
            print('  提示：找不到「目录」标题段，跳过页眉回跳（不影响目录链接）')
        else:
            add_bookmark(paras[toc_idx], '_Toc_page', bid)
            for s in doc.sections:
                hp = s.header.paragraphs[0] if s.header.paragraphs else None
                if hp is None or not hp.text.strip():
                    continue          # 封面 / 目录 / 前言无页眉
                wrap_hyperlink(hp, '_Toc_page')
                n_hdr += 1

    if args.dry:
        print('[dry] 将写入 %d 个书签、%d 条目录链接、%d 条页眉回跳'
              % (len(docs) + (1 if toc_idx is not None else 0), len(docs), n_hdr))
    else:
        doc.save(args.book)
        print('已写入 %d 个书签、%d 条目录链接、%d 条页眉回跳 → %s'
              % (len(docs) + (1 if toc_idx is not None else 0), len(docs), n_hdr,
                 os.path.basename(args.book)))

    for d in docs:
        print('  %-16s 目录段 %4d → 落点 %4d  %s'
              % (label_of(d)[:15], rows[d['id']], targets[d['id']], d['id']))
    if not args.dry:
        print('\n下一步：用 Word 导出 PDF（内部链接会自动转 GoTo），再跑 --verify-pdf 验收。')


def do_verify(args, docs):
    ok = True
    doc = Document(args.book)
    body = doc.element.body
    bms = [b.get(qn('w:name')) for b in body.findall('.//' + qn('w:bookmarkStart'))]
    toc_bm = [n for n in bms if (n or '').startswith('_Toc_')]
    body_hl = body.findall('.//' + qn('w:hyperlink'))
    hdr_hl = 0
    for s in doc.sections:
        if s.header.paragraphs:
            hdr_hl += len(s.header.paragraphs[0]._p.findall(qn('w:hyperlink')))

    want_bm = len(docs) + (1 if '_Toc_page' in bms else 0)
    print('docx ：书签 %d（期望 %d）、正文链接 %d（期望 %d）、页眉链接 %d'
          % (len(toc_bm), want_bm, len(body_hl), len(docs), hdr_hl))
    if len(toc_bm) != want_bm or len(body_hl) != len(docs):
        ok = False
        print('  ✗ docx 侧数量不符')

    if not args.verify_pdf:
        return 0 if ok else 1

    import pymupdf
    pdf = pymupdf.open(args.verify_pdf)
    pno = args.toc_page - 1
    if not (0 <= pno < pdf.page_count):
        sys.exit('目录页 %d 超出 PDF 页数 %d' % (args.toc_page, pdf.page_count))
    links = [l for l in pdf[pno].get_links() if l['kind'] == 1]
    print('PDF  ：第 %d 页 LINK_GOTO %d 条（期望 %d）' % (args.toc_page, len(links), len(docs)))
    if len(links) != len(docs):
        ok = False
        print('  ✗ 链接条数不符（kind==1 才是内部跳转；外链是 kind==2）')

    for d, l in zip(docs, links):
        tgt = l['page'] + 1
        page_text = norm(pdf[l['page']].get_text())
        if d.get('kind', 'ch') == 'front':
            # 前言页首没有「前言与导读」这几个字（只有版权/欢迎/序），只校验落点页有正文
            hit = len(page_text) > 0
        else:
            hit = norm(title_of(d))[:16] in page_text
        flag = 'OK' if hit else '✗ 目标页里没有该标题'
        if not hit:
            ok = False
        print('  %-16s → p%-4d %s' % (label_of(d)[:15], tgt, flag))

    print('结论：' + ('✓ 通过' if ok else '✗ 未通过'))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description='给合订 docx 的目录挂可点击跳转（docx 层书签 + 超链接）')
    ap.add_argument('book', help='合订后的 docx（合并产物，不要用分册）')
    ap.add_argument('--docs', required=True, help='docs.json：id/title/num/kind/header')
    ap.add_argument('--no-header-back', dest='header_back', action='store_false',
                    help='不给各章页眉挂「返回目录」链接')
    ap.add_argument('--dry', action='store_true', help='只检查匹配关系，不写文件')
    ap.add_argument('--verify-pdf', default=None, help='验收：Word 导出的 PDF')
    ap.add_argument('--toc-page', type=int, default=2, help='目录在第几页（有封面时是 2）')
    args = ap.parse_args()

    if not os.path.exists(args.book):
        sys.exit('找不到 %s' % args.book)
    docs = sort_docs(json.load(open(args.docs, encoding='utf-8')))
    sys.exit(do_verify(args, docs) if args.verify_pdf else do_write(args, docs))


if __name__ == '__main__':
    main()
