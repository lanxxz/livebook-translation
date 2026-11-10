# -*- coding: utf-8 -*-
"""EPUB 源流程 / 锚点槽位流水线的公共定义与工具。

项目根定位与技能其他脚本一致：**向上查找含 book.json 或 docs.json 的目录**，
所以本组脚本既可以放在 <项目>/tools/、<项目>/scripts/，也可以直接放在项目根。
不在项目根运行时用 `BOOK_ROOT` 环境变量指向项目目录。
"""
import json
import os
import re
import sys

CJK = re.compile(r'[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef\u201c\u201d\u2018\u2019]')


def project_root():
    def _up(start):
        d = os.path.abspath(start)
        for _ in range(5):
            if (os.path.exists(os.path.join(d, 'book.json'))
                    or os.path.exists(os.path.join(d, 'docs.json'))):
                return d
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
        return None

    env = os.environ.get('BOOK_ROOT')
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    for start in (os.path.dirname(os.path.abspath(__file__)), os.getcwd()):
        hit = _up(start)
        if hit:
            return hit
    return os.getcwd()


ROOT = project_root()
WORK = os.path.join(ROOT, 'work')


def load_json(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def dump_json(obj, p):
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def load_docs():
    return load_json(os.path.join(ROOT, 'docs.json'))


def layout_of(doc):
    """返回该文档的顶层块列表。"""
    p = os.path.join(WORK, doc + '_layout.json')
    pages = load_json(p)['pages']
    out = []
    for k in pages:
        out.extend(pages[k])
    return out


# ---------------------------------------------------------------- 骨架
def skel_lines(blocks):
    """生成待译骨架文本。"""
    out = []
    for i, b in enumerate(blocks):
        t = b['type']
        out.append('@@BLOCK %d %s' % (i, t))
        if t == 'chapter_open':
            out.append('NUM: %s' % b['num'])
            out.append('TITLE: %s' % b['title'])
            for it in b['toc_items']:
                out.append('TOC: %s' % it)
            if b['intro']:
                out.append('INTRO: %s' % b['intro'])
        elif t == 'heading':
            out.append('LEVEL: %d' % b['level'])
            out.append('TEXT: %s' % b['text'])
        elif t == 'para':
            out.append('TEXT: %s' % b['text'])
        elif t in ('list', 'numlist'):
            for it in b['items']:
                out.append('ITEM: %s' % it)
        elif t == 'code':
            out.append('CAPTION: %s' % b['caption'])
            for ln in b['text'].split('\n'):
                out.append('C|' + ln)
            for k, v in b['notes']:
                out.append('NOTE %s %s' % (k, v))
        elif t == 'figure':
            out.append('KEY: %s' % b['key'])
            out.append('IMG: %s' % b['img'])
            out.append('CAPTION: %s' % b['caption'])
        elif t == 'table':
            out.append('CAPTION: %s' % b['caption'])
            out.append('HDR: ' + ' | '.join(b['grid']['data'][0]))
            for row in b['grid']['data'][1:]:
                out.append('ROW: ' + ' | '.join(row))
        elif t in ('dialog', 'callout', 'sidebar'):
            out.append('SPEAKER: %s' % b.get('speaker', ''))
            out.append('LABEL: %s' % b.get('label', ''))
            out.append('TITLE: %s' % b.get('title', ''))
            for j, sub in enumerate(b['parts']):
                out.append('@@PART %d %s' % (j, sub['type']))
                if sub['type'] == 'para':
                    out.append('P|' + sub['text'])
                elif sub['type'] in ('list', 'numlist'):
                    for it in sub['items']:
                        out.append('I|' + it)
                elif sub['type'] == 'code':
                    out.append('CAPTION: %s' % sub['caption'])
                    for ln in sub['text'].split('\n'):
                        out.append('C|' + ln)
                elif sub['type'] == 'table':
                    out.append('CAPTION: %s' % sub['caption'])
                    out.append('HDR: ' + ' | '.join(sub['grid']['data'][0]))
                    for row in sub['grid']['data'][1:]:
                        out.append('ROW: ' + ' | '.join(row))
                elif sub['type'] == 'heading':
                    out.append('TEXT: %s' % sub['text'])
                elif sub['type'] == 'figure':
                    out.append('IMG: %s' % sub['img'])
                else:
                    out.append('TEXT: %s' % sub.get('text', ''))
                out.append('')
        elif t == 'equation':
            out.append('TEXT: %s' % b['text'])
        elif t == 'quote':
            out.append('TEXT: %s' % b['text'])
        out.append('')
    return out
