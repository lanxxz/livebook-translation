# -*- coding: utf-8 -*-
"""从 EPUB 的 XHTML 解析块序列（递归遍历，正确处理容器内嵌结构）。

产出：
    work/book_layout.json     {"pages": {"<doc序号>": [block,...]}}
    work/docs.json            文档清单
    work/book_figtexts.json   {figkey: {...}}
    work/<doc>_layout.json / _dump.txt

块类型：
    chapter_open  num/title/toc_items/intro
    heading       level=2..5, text
    para          text
    list/numlist  items
    code          caption, text, notes
    figure        key, img, caption
    table         caption, grid{rows,cols,data}
    dialog        kind(prompt|response), speaker, parts[子块]
    callout       label, parts[子块]
    sidebar       title, parts[子块]
    equation      text
    quote         text
"""
import json
import os
import re
import sys
import zipfile

from lxml import html as LH

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

EPUB = (r"D:/Downloads/Vibe Engineering (MEAP Version 7) "
        r"(Tomasz Lelek, Artur Skowroński) (z-library.sk, 1lib.sk, z-lib.sk).epub")
from common import ROOT  # 项目根：向上找 book.json/docs.json，或 BOOK_ROOT
_HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, 'work')

DOCS = [
    ('welcome', 'OEBPS/Text/welcome.html', '前言', ''),
    ('ch01', 'OEBPS/Text/chapter-1.html', '在流沙上盖楼：氛围工程的挑战', '1'),
    ('ch02', 'OEBPS/Text/chapter-2.html', '构建由氛围工程驱动的遗留系统现代化框架', '2'),
    ('ch03', 'OEBPS/Text/chapter-3.html', '上下文织体：为 AI 智能体优化上下文', '3'),
    ('ch04', 'OEBPS/Text/chapter-4.html', 'LLM 驱动的数据科学', '4'),
    ('ch05', 'OEBPS/Text/chapter-5.html', 'AI 原生 SDLC 的持续 AI 开发', '5'),
    ('ch06', 'OEBPS/Text/chapter-6.html', '验证 LLM 方案的科学方法', '6'),
    ('ch07', 'OEBPS/Text/chapter-7.html', '氛围性能工程：当假设误导我们', '7'),
    ('ch08', 'OEBPS/Text/chapter-8.html', '评估为王：如何信任不是你写的代码', '8'),
    ('ch09', 'OEBPS/Text/chapter-9.html', '氛围工程经济学：规模化成本优化', '9'),
    ('ch10', 'OEBPS/Text/chapter-10.html', '你的代码库才是瓶颈：智能体时代的代码组织', '10'),
]

WS = re.compile(r'[ \t\r\n]+')
CONTAINER = 'figure-container listing-container browsable-table-container ' \
            'equation-container'.split()


def squash(s):
    return WS.sub(' ', (s or '').replace('\u00a0', ' ')).strip()


def cls(el):
    return (el.get('class') or '').split()


def has(el, name):
    return name in cls(el)


def inline(el):
    """行内标记：em→*x*、strong→**x**、kbd/code→`x`。"""
    out = []

    def walk(node):
        tag = node.tag if isinstance(node.tag, str) else ''
        if tag in ('em', 'i'):
            inner = inline(node).strip()
            if inner:
                out.append('*%s*' % inner)
            return
        if tag in ('strong', 'b'):
            inner = inline(node).strip()
            if inner:
                out.append('**%s**' % inner)
            return
        if tag in ('kbd', 'code', 'tt'):
            inner = inline(node).strip()
            if inner:
                out.append('`%s`' % inner)
            return
        if tag in ('sup', 'sub'):
            out.append(inline(node).strip())
            return
        if tag == 'br':
            out.append(' ')
            return
        if node.text:
            out.append(node.text)
        for ch in node:
            if isinstance(ch.tag, str):
                walk(ch)
            if ch.tail:
                out.append(ch.tail)

    if el.text:
        out.append(el.text)
    for ch in el:
        if isinstance(ch.tag, str):
            walk(ch)
        if ch.tail:
            out.append(ch.tail)
    return squash(''.join(out))


def pre_text(el):
    raw = LH.tostring(el, encoding='unicode', method='html')
    m = re.search(r'<pre[^>]*>(.*)</pre>', raw, re.S)
    if not m:
        return ''
    s = m.group(1)
    s = re.sub(r'<span[^>]*/>', '', s)
    s = re.sub(r'<br\s*/?>', '\n', s)
    s = re.sub(r'</(p|div)>', '\n', s)
    s = re.sub(r'<[^>]+>', '', s)
    for a, b in (('&quot;', '"'), ('&#39;', "'"), ('&apos;', "'"),
                 ('&lt;', '<'), ('&gt;', '>'), ('&nbsp;', ' '), ('&amp;', '&')):
        s = s.replace(a, b)
    lines = [l.rstrip().replace('\u00a0', ' ') for l in s.split('\n')]
    while lines and not lines[-1].strip():
        lines.pop()
    while lines and not lines[0].strip():
        lines.pop(0)
    return '\n'.join(lines)


def cap_of(el):
    h5 = el.cssselect('h5')
    return squash(h5[0].text_content()) if h5 else ''


def notes_of(el):
    out = []
    for ann in el.cssselect('div.code-annotations-overlay-container'):
        raw = LH.tostring(ann, encoding='unicode', method='html')
        raw = re.sub(r'<br\s*/?>', '\n', raw)
        raw = re.sub(r'<[^>]+>', '', raw)
        for ln in raw.split('\n'):
            ln = squash(ln)
            m = re.match(r'^(#[A-Z])\s+(.+)$', ln)
            if m:
                out.append([m.group(1), m.group(2)])
    return out


def grid_of_table(tb):
    data = []
    for tr in tb.cssselect('tr'):
        row = [inline(td) for td in tr.cssselect('td,th')]
        if row:
            data.append(row)
    if not data:
        return None
    return {'rows': len(data), 'cols': max(len(r) for r in data), 'data': data}


def table_grid(el):
    tb = el.cssselect('table')
    if not tb:
        return None
    return grid_of_table(tb[0])


SKIP_IN_PARTS = {'h5'}


def walk(container, ctx, depth=0):
    """递归解析容器，产出块列表。ctx 携带 doc_id / fig 计数器。"""
    blocks = []
    for el in container.iterchildren():
        if not isinstance(el.tag, str):
            continue
        tag = el.tag
        c = cls(el)
        if tag == 'h5':
            continue
        # ---- 容器类 ----
        if 'figure-container' in c:
            img = el.cssselect('img')
            if img:
                src = (img[0].get('src') or '').replace('../', '')
                if src:
                    ctx['fig'] += 1
                    blocks.append({'type': 'figure', 'page': 0,
                                   'key': '%s_f%02d' % (ctx['doc'], ctx['fig']),
                                   'img': src, 'caption': cap_of(el)})
            continue
        if 'listing-container' in c:
            pre = el.cssselect('pre')
            if pre:
                blocks.append({'type': 'code', 'page': 0,
                               'caption': cap_of(el),
                               'text': pre_text(pre[0]),
                               'notes': notes_of(el)})
            continue
        if 'browsable-table-container' in c:
            # 一个容器里可能有多个 <table>（如 ch04 的 p72 双表）
            tbs = el.cssselect('table')
            cap = cap_of(el)
            for ti, tb in enumerate(tbs):
                g = grid_of_table(tb)
                if g:
                    blocks.append({'type': 'table', 'page': 0,
                                   'caption': cap if ti == 0 else
                                   (cap + ' (%d)' % (ti + 1) if cap else ''),
                                   'grid': g})
            continue
        if 'equation-container' in c:
            blocks.append({'type': 'equation', 'page': 0,
                           'text': squash(el.text_content())})
            continue
        if 'admonition-block' in c:
            blocks.append({'type': 'callout', 'page': 0,
                           'label': cap_of(el).upper() or 'NOTE',
                           'parts': walk(el, ctx, depth + 1)})
            continue
        if 'prompt-response-sidebar' in c:
            head = el.cssselect('strong')
            spk = ''
            ini = ''
            if head:
                h = head[0]
                sp = h.cssselect('span.prompt-initials')
                if sp:
                    ini = squash(sp[0].text_content())
                spk = squash(h.text_content())
                if ini and spk.startswith(ini):
                    spk = spk[len(ini):].strip()
            kind = 'prompt' if 'prompt-sidebar' in c else 'response'
            blocks.append({'type': 'dialog', 'page': 0, 'kind': kind,
                           'speaker': spk, 'initials': ini,
                           'parts': walk(el, ctx, depth + 1)})
            continue
        if 'sidebar-container' in c:
            blocks.append({'type': 'sidebar', 'page': 0,
                           'title': cap_of(el),
                           'parts': walk(el, ctx, depth + 1)})
            continue
        # ---- 标题（h1 是章名，已进 chapter_open，跳过）----
        if tag == 'h1':
            continue
        if tag in ('h2', 'h3', 'h4', 'h5'):
            t = inline(el)
            if t:
                blocks.append({'type': 'heading', 'page': 0,
                               'level': int(tag[1]), 'text': t})
            continue
        # ---- 列表 ----
        if tag in ('ul', 'ol'):
            kind = 'list' if tag == 'ul' else 'numlist'
            items = [inline(li) for li in el.cssselect('li')]
            items = [i for i in items if i]
            if items:
                blocks.append({'type': kind, 'page': 0, 'items': items})
            continue
        if tag == 'p':
            t = inline(el)
            if t:
                blocks.append({'type': 'para', 'page': 0, 'text': t})
            continue
        if tag == 'blockquote':
            t = squash(el.text_content())
            if t:
                blocks.append({'type': 'quote', 'page': 0, 'text': t})
            continue
        if tag == 'pre':
            blocks.append({'type': 'code', 'page': 0, 'caption': '',
                           'text': pre_text(el), 'notes': []})
            continue
        if tag == 'table':
            g = grid_of_table(el)
            if g:
                blocks.append({'type': 'table', 'page': 0,
                               'caption': '', 'grid': g})
            continue
        if tag == 'div':
            blocks.extend(walk(el, ctx, depth + 1))
            continue
        # 其他：递归兜底
        blocks.extend(walk(el, ctx, depth + 1))
    return blocks


def parse_doc(doc_id, path, z):
    doc = LH.fromstring(z.read(path))
    body = doc.body
    ctx = {'doc': doc_id, 'fig': 0}
    h1 = body.cssselect('h1')
    num, title = '', ''
    if h1:
        ns = h1[0].cssselect('span.num-string')
        if ns:
            num = squash(ns[0].text_content())
        title = squash(h1[0].text_content())
        if num and title.startswith(num):
            title = title[len(num):].strip()
    summary = body.cssselect('div.introduction-summary')
    toc = [inline(li) for li in summary[0].cssselect('li')] if summary else []
    toc = [t for t in toc if t]

    blocks = [{'type': 'chapter_open', 'page': 0, 'num': num, 'title': title,
               'toc_items': toc, 'intro': '', 'appendix': False}]

    # 章首导言：summary 之后、第一个 h2 之前的所有 para
    intro = []
    seen_summary = False
    body_children = [e for e in body.iterchildren() if isinstance(e.tag, str)]
    for el in body_children:
        if el is (summary[0] if summary else None):
            seen_summary = True
            continue
        if not seen_summary:
            continue
        if el.tag == 'div' and el.cssselect('h2'):
            break
        if el.tag == 'div' and 'readable-text' in cls(el):
            for p in el.cssselect('p'):
                t = inline(p)
                if t:
                    intro.append(t)
            continue
        break
    blocks[0]['intro'] = ' '.join(intro)

    # 正文：跳过 h1 / summary / 已消费的导言 div
    intro_left = len(intro)
    for el in body_children:
        if el is h1[0] if h1 else False:
            continue
        if el is (summary[0] if summary else None):
            continue
        if el.tag == 'div' and 'readable-text' in cls(el) and intro_left > 0 \
                and not el.cssselect('h2'):
            ps = [inline(p) for p in el.cssselect('p')]
            ps = [p for p in ps if p]
            if ps and ps == intro[len(intro) - intro_left:
                                   len(intro) - intro_left + len(ps)]:
                intro_left -= len(ps)
                continue
        blocks.extend(walk_wrap(el, ctx))
    return blocks


def walk_wrap(el, ctx):
    return walk(_Single(el), ctx)


class _Single:
    def __init__(self, el):
        self._el = el

    def iterchildren(self):
        return iter([self._el])


def dump_block(idx, b):
    t = b['type']
    h = '[%03d] ' % idx
    if t == 'chapter_open':
        s = h + 'CH %s | %s' % (b['num'], b['title'])
        for it in b['toc_items']:
            s += '\n      TOC: ' + it
        if b['intro']:
            s += '\n      INTRO: ' + b['intro']
        return s
    if t == 'heading':
        return h + 'H%d %s' % (b['level'], b['text'])
    if t == 'para':
        return h + 'P ' + b['text']
    if t in ('list', 'numlist'):
        return h + t.upper() + '\n' + '\n'.join('      - ' + i for i in b['items'])
    if t == 'code':
        s = h + 'CODE(%dL) cap=%s' % (b['text'].count('\n') + 1, b['caption'])
        for ln in b['text'].split('\n'):
            s += '\n      |' + ln
        for n in b['notes']:
            s += '\n      NOTE %s %s' % (n[0], n[1])
        return s
    if t == 'figure':
        return h + 'FIG %s img=%s cap=%s' % (b['key'], b['img'], b['caption'])
    if t == 'table':
        s = h + 'TABLE %dx%d cap=%s' % (b['grid']['rows'], b['grid']['cols'],
                                        b['caption'])
        for row in b['grid']['data']:
            s += '\n      | ' + ' ｜ '.join(row)
        return s
    if t in ('dialog', 'callout', 'sidebar'):
        tag = t.upper()
        if t == 'dialog':
            head = '%s(%s) %s' % (tag, b['kind'], b['speaker'])
        elif t == 'callout':
            head = '%s [%s]' % (tag, b['label'])
        else:
            head = '%s %s' % (tag, b['title'])
        s = h + head
        for j, sub in enumerate(b['parts']):
            inner = dump_block(j, sub).split('] ', 1)[-1]
            s += '\n      ┆ ' + inner.replace('\n', '\n      ┆ ')
        return s
    if t == 'equation':
        return h + 'EQ ' + b['text']
    if t == 'quote':
        return h + 'QUOTE ' + b['text']
    return h + t


def main():
    z = zipfile.ZipFile(EPUB)
    os.makedirs(WORK, exist_ok=True)
    pages, docs, figs = {}, [], {}
    for i, (doc_id, path, cn_title, num) in enumerate(DOCS, start=1):
        blocks = parse_doc(doc_id, path, z)
        if num and not blocks[0]['num']:
            blocks[0]['num'] = num
        pages[str(i)] = blocks
        docs.append({'id': doc_id, 'title': cn_title, 'num': num,
                     'kind': 'front' if doc_id == 'welcome' else 'ch',
                     'from': i, 'to': i})
        for b in blocks:
            if b['type'] == 'figure':
                figs[b['key']] = {'page': i, 'img': b['img'], 'doc': doc_id,
                                  'caption': b['caption']}
    json.dump({'pages': pages}, open(os.path.join(WORK, 'book_layout.json'), 'w',
                                     encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(docs, open(os.path.join(WORK, 'docs.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    json.dump(figs, open(os.path.join(WORK, 'book_figtexts.json'), 'w',
                         encoding='utf-8'), ensure_ascii=False, indent=1)

    for d in docs:
        pid = str(d['from'])
        bl = pages[pid]
        json.dump({'pages': {pid: bl}},
                  open(os.path.join(WORK, d['id'] + '_layout.json'), 'w',
                       encoding='utf-8'), ensure_ascii=False, indent=1)
        open(os.path.join(WORK, d['id'] + '_dump.txt'), 'w',
             encoding='utf-8').write(
            '\n'.join(dump_block(i, b) for i, b in enumerate(bl)))
        n = {k: 0 for k in ('para', 'code', 'figure', 'table', 'dialog',
                            'callout', 'sidebar', 'heading', 'list', 'numlist',
                            'equation', 'quote')}
        for b in bl:
            n[b['type']] = n.get(b['type'], 0) + 1
        print('%-8s %3d  ' % (d['id'], len(bl)) +
              ' '.join('%s=%d' % (k, v) for k, v in n.items() if v))
    print('TOTAL blocks', sum(len(v) for v in pages.values()),
          'figs', len(figs))


if __name__ == '__main__':
    main()
