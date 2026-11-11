#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""统一多级目录工具 —— 公共配置与工具（pitfalls AA 组配套）。

本模块不含任何书名 / 路径 / 机器相关的硬编码：所有项目差异都来自
`--config` 指向的 JSON（模板见 `assets/unified_toc.json.example`）。

被 `toc_build.py` / `toc_links.py` / `toc_verify.py` 共用，保证
「目录行解析、条目收集、页码计算」只有一份实现（AA3/AA6）。
"""
import copy
import glob
import json
import os
import re
import shutil
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import pymupdf

DEFAULTS = {
    'root': None,                      # 项目根；null = 从配置文件/脚本位置/cwd 向上找 docs.json
    'book_title': '',                  # 只用于页眉文字，缺省取 front_meta.book_title
    'docs': 'docs.json',
    'front_meta': 'work/front_meta.json',
    'chapter_pages': 'work/chapter_pages.json',
    'out_dir': 'out',
    'pdf_dir': 'out/pdf',
    'front_name': '00_封面与版权',      # 封面+版权+目录所在的 docx/PDF 基名
    'book_name': '',                   # 合订 PDF/docx 基名；空 = book_title
    'header_text': '',                 # 页眉匹配文字；空 = book_title
    'front_fixed_pages': 2,            # 目录之前的固定页数（通常封面 1 + 版权 1）
    'toc_start_page': 3,               # 目录首页的全书页号（1-based）
    'toc_title': '目录',
    'welcome': {
        'name_template': '00_{title}',
        'label': '前言与导读',
        'toc_title': '',               # 空 = 用 docs.json 里 front 文档的 title
    },
    'chapter': {
        'name_template': '{num:02d}_第{num}章_{title}',
        'label_template': '第 {num} 章　{title}',
        'bookmark_regex': '^第(\\d+)章',
    },
    'outline': {
        'level_map': {'1': 1, '2': 2, '3': 2},   # 分册书签级别 -> 目录级别
        'num_regex': '^(\\d+(?:\\.\\d+)*)',
    },
    'footer': {'min_y': 786.0, 'max_y': 830.0, 'center_tol': 40.0},
    'page_number': {'fontsize': 9, 'from_bottom': 30, 'color': [0.5, 0.5, 0.5]},
    'toc_rows': {
        'y_min': 55,          # 必须 < 目录续页首行 y（AA5：100 会静默漏行）
        'y_max': 780,
        'right_x_min': 480,   # 右对齐页码的最小右边界
        'title_x_max': 480,   # 标题行最左边界
        'pair_tol': 8,        # 标题与页码 y 配对容差
    },
    'soffice': '',            # 显式指定 soffice/libreoffice 可执行文件；空 = 自动探测
    'skip_docx_merge': False, # 只出 PDF 时跳过 docxcompose
}


def _merge(a, b):
    """浅层递归合并（b 覆盖 a）。"""
    out = copy.deepcopy(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def find_root(start):
    d = os.path.abspath(start or os.getcwd())
    for _ in range(6):
        if (os.path.exists(os.path.join(d, 'docs.json'))
                or os.path.exists(os.path.join(d, 'book.json'))):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return os.path.abspath(start or os.getcwd())


def load_config(config_path=None, root=None, overrides=None):
    """加载配置并解析 root；返回可直接使用的 dict（含 `_root`）。"""
    cfg = copy.deepcopy(DEFAULTS)
    if config_path:
        p = os.path.abspath(config_path)
        if not os.path.exists(p):
            raise SystemExit('配置文件不存在：%s' % p)
        cfg = _merge(cfg, json.load(open(p, encoding='utf-8-sig')))
    if overrides:
        cfg = _merge(cfg, overrides)

    env_root = os.environ.get('BOOK_ROOT')
    r = root or env_root or cfg.get('root')
    if not r:
        base = os.path.dirname(os.path.abspath(config_path)) if config_path else os.getcwd()
        r = find_root(base)
    cfg['_root'] = os.path.abspath(r)

    # 书名/页眉可从 front_meta.json 推断，配置优先
    fm_path = cpath(cfg, 'front_meta')
    fm = {}
    if os.path.exists(fm_path):
        try:
            fm = json.load(open(fm_path, encoding='utf-8'))
        except Exception:
            fm = {}
    cfg['book_title'] = cfg.get('book_title') or fm.get('book_title') or 'Book'
    cfg['book_name'] = cfg.get('book_name') or cfg['book_title']
    cfg['header_text'] = cfg.get('header_text') or cfg['book_title']
    cfg['toc_title'] = cfg.get('toc_title') or fm.get('toc_title') or '目录'
    if not cfg['welcome'].get('toc_title'):
        cfg['welcome']['toc_title'] = ''
    cfg['_front_meta'] = fm
    return cfg


def cpath(cfg, key):
    """配置里的相对路径 -> 绝对路径。"""
    p = cfg[key]
    return p if os.path.isabs(p) else os.path.join(cfg['_root'], p)


def sub_pdf(cfg, name):
    return os.path.join(cpath(cfg, 'pdf_dir'), name + '.pdf')


def sub_docx(cfg, name):
    return os.path.join(cpath(cfg, 'out_dir'), name + '.docx')


def book_pdf(cfg):
    return os.path.join(cpath(cfg, 'pdf_dir'), cfg['book_name'] + '.pdf')


def book_docx(cfg):
    return os.path.join(cpath(cfg, 'out_dir'), cfg['book_name'] + '.docx')


def find_soffice(cfg=None):
    """跨平台探测 LibreOffice（SOFFICE 环境变量 > PATH > 常见安装路径）。"""
    cand = []
    if cfg:
        cand.append(cfg.get('soffice') or '')
    cand.append(os.environ.get('SOFFICE') or '')
    cand.append(os.environ.get('SOFFICE_PATH') or '')
    for c in cand:
        if c and os.path.exists(c):
            return c
    for name in ('soffice', 'libreoffice', 'soffice.bin'):
        hit = shutil.which(name)
        if hit:
            return hit
    paths = [
        r'C:\Program Files\LibreOffice\program\soffice.exe',
        r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
        '/usr/bin/soffice', '/usr/local/bin/soffice',
        '/opt/libreoffice/program/soffice',
        '/Applications/LibreOffice.app/Contents/MacOS/soffice',
    ]
    for base in (r'C:\Program Files', r'C:\Program Files (x86)'):
        paths.extend(glob.glob(os.path.join(base, 'LibreOffice*', 'program', 'soffice.exe')))
    for p in paths:
        if os.path.exists(p):
            return p
    raise SystemExit(
        '未找到 LibreOffice：请安装后把可执行文件写进配置 soffice 字段，'
        '或设环境变量 SOFFICE=/path/to/soffice')


def convert_front(cfg):
    """前置页 docx -> PDF，返回页数。"""
    so = find_soffice(cfg)
    pdfdir = cpath(cfg, 'pdf_dir')
    os.makedirs(pdfdir, exist_ok=True)
    docx = sub_docx(cfg, cfg['front_name'])
    r = subprocess.run([so, '--headless', '--norestore',
                        '--convert-to', 'pdf:writer_pdf_Export',
                        '--outdir', pdfdir, docx],
                       capture_output=True, text=True, timeout=600)
    dst = sub_pdf(cfg, cfg['front_name'])
    if not os.path.exists(dst) or os.path.getsize(dst) < 1000:
        raise SystemExit('前置页 docx→PDF 失败：%s %s' % (r.stdout[-300:], r.stderr[-300:]))
    with pymupdf.open(dst) as d:
        return d.page_count


def norm(s):
    """去所有空白（含 EN SPACE）与目录装饰符 ▪（用实际字符，避免源码转义坑）。"""
    return ''.join((s or '').split()).replace('▪', '')


def load_docs(cfg):
    p = cpath(cfg, 'docs')
    if not os.path.exists(p):
        raise SystemExit('缺 docs.json：%s（用配置 docs 字段指定）' % p)
    return json.load(open(p, encoding='utf-8'))


def _tpl(tpl, d):
    """用 docs.json 的字段渲染命名模板；num 同时给 int 与 str。"""
    ctx = dict(d)
    raw = str(d.get('num') or '')
    if raw.isdigit():
        ctx['num'] = int(raw)
        ctx['num_s'] = raw
    else:
        ctx['num'] = 0
        ctx['num_s'] = raw
    try:
        return tpl.format(**ctx)
    except (KeyError, ValueError, IndexError) as e:
        raise SystemExit('命名模板 %r 渲染失败：%s。可用字段：%s'
                         % (tpl, e, sorted(ctx)))


def build_plan(cfg):
    """合订顺序：[(name, label, kind, num, title)]，与 merge/toc 共用。"""
    docs = load_docs(cfg)
    plan = [(cfg['front_name'], '', 'front', '', '')]
    fronts = [d for d in docs if d.get('kind') in ('front', 'welcome')]
    chapters = sorted([d for d in docs if d.get('kind') in ('ch', 'chapter', '')],
                      key=lambda d: int(d.get('num') or 0))
    if fronts:
        d = fronts[0]
        w = cfg['welcome']
        plan.append((_tpl(w['name_template'], d), w.get('label') or '', 'welcome',
                     str(d.get('num') or ''), d.get('title') or ''))
        if not w.get('toc_title'):
            w['toc_title'] = d.get('title') or '前言'
    for d in chapters:
        c = cfg['chapter']
        plan.append((_tpl(c['name_template'], d), _tpl(c['label_template'], d),
                     'chapter', str(d.get('num') or ''), d.get('title') or ''))
    return plan


def sub_pages(cfg, name):
    with pymupdf.open(sub_pdf(cfg, name)) as d:
        return d.page_count


def sub_outline(cfg, name):
    with pymupdf.open(sub_pdf(cfg, name)) as d:
        return [(lvl, t.strip(), pg) for lvl, t, pg in d.get_toc() if t.strip()]


def collect_entries(cfg, plan):
    """从分册 PDF 书签收集目录条目（AA3：唯一真相来源）。

    返回 (entries, chapters)：
      entries = [(level, num, title, chapter_name, local_page)]
      chapters = [(chapter_name, page_count)]
    """
    entries, chapters = [], []
    welcome = next((p for p in plan if p[2] == 'welcome'), None)
    if welcome:
        entries.append((0, '', cfg['welcome']['toc_title'], None, None))

    lvl_map = {int(k): int(v) for k, v in cfg['outline']['level_map'].items()}
    num_re = re.compile(cfg['outline']['num_regex'])
    for name, label, kind, num, title in plan:
        if kind != 'chapter':
            continue
        n = sub_pages(cfg, name)
        chapters.append((name, n))
        entries.append((0, num, title, name, None))
        for olvl, t, lp in sub_outline(cfg, name):
            m = num_re.match(t)
            level = lvl_map.get(olvl, max(lvl_map.values()) if lvl_map else 2)
            entries.append((level, m.group(1) if m else '', t, name, lp))
    return entries, chapters


def compute_pages(cfg, entries, plan, chapters, P):
    """给定目录页数 P 算每条最终页码（AA4 第 2 遍）。返回 (pages, total, ch_start, welcome_start)。"""
    fixed = int(cfg['front_fixed_pages'])
    front_total = fixed + P
    welcome_name = next((p[0] for p in plan if p[2] == 'welcome'), None)
    welcome_pages = sub_pages(cfg, welcome_name) if welcome_name else 0
    welcome_start = front_total + 1
    cur = front_total + welcome_pages

    ch_start, ch_pages = {}, dict(chapters)
    pages = {}
    for i, (level, num, title, ch_name, lp) in enumerate(entries):
        if level == 0 and ch_name is None:
            pages[i] = welcome_start
            continue
        if level == 0:
            ch_start[ch_name] = cur + 1
            pages[i] = cur + 1
            cur += ch_pages[ch_name]
        else:
            pages[i] = ch_start[ch_name] + lp - 1
    return pages, cur, ch_start, welcome_start


def load_entries(cfg):
    """front_meta.toc -> [{num,title,page,level}]（兼容三/四元组）。"""
    fm = cfg.get('_front_meta') or {}
    out = []
    for item in fm.get('toc') or []:
        it = list(item) + ['', '', '', 0]
        out.append({'num': str(it[0]), 'title': str(it[1]),
                    'page': int(it[2]) if str(it[2]).isdigit() else 0,
                    'level': int(it[3] or 0)})
    return out


def display_key(ent):
    """目录印刷行的匹配键：章级拼章号，小节标题自带编号（AA6）。"""
    return norm(ent['num'] + ent['title']) if ent['level'] == 0 else norm(ent['title'])


def get_lines(page):
    out = []
    for blk in page.get_text('dict')['blocks']:
        if blk.get('type') != 0:
            continue
        for ln in blk.get('lines', []):
            txt = ''.join(s.get('text', '') for s in ln.get('spans', []))
            if txt.strip():
                out.append((txt, ln['bbox']))
    return out


def find_rows(cfg, page):
    """目录页行：左标题 + 右页码按 y 配对（AA5 的 y 带用配置）。"""
    r = cfg['toc_rows']
    titles, nums = [], []
    for txt, bb in get_lines(page):
        t = txt.strip()
        if t.isdigit() and bb[2] > r['right_x_min'] and r['y_min'] < bb[1] < r['y_max']:
            nums.append((int(t), bb))
        elif bb[1] > r['y_min'] and bb[3] < r['y_max'] and bb[0] < r['title_x_max']:
            titles.append((txt, bb))
    rows, used = [], set()
    for txt, bb in titles:
        for j, (pg, nb) in enumerate(nums):
            if j in used:
                continue
            if abs(nb[1] - bb[1]) < r['pair_tol']:
                rows.append((txt, bb, pg, nb))
                used.add(j)
                break
    rows.sort(key=lambda x: x[1][1])
    return rows


def toc_entry_pages(cfg, doc, need):
    """目录页范围：从 toc_start_page 起累计行，收满 need 条即止。"""
    pages, got = [], 0
    for i in range(int(cfg['toc_start_page']) - 1, doc.page_count):
        rows = find_rows(cfg, doc[i])
        if not rows:
            if pages:
                break
            continue
        pages.append(i + 1)
        got += len(rows)
        if got >= need:
            break
    return pages


def bookmark_targets(cfg, doc):
    """书签 -> ({章号: page}, [(norm_title, page)])。"""
    ch, sec = {}, []
    rx = re.compile(cfg['chapter']['bookmark_regex'])
    for lvl, title, pg in doc.get_toc():
        if lvl == 1:
            m = rx.match(norm(title))
            if m:
                ch[int(m.group(1))] = pg
        elif lvl == 2:
            sec.append((norm(title), pg))
    return ch, sec


def save_meta(cfg, entries, pages, ch_start):
    """写回 front_meta.toc 与 chapter_pages.json。"""
    fm = copy.deepcopy(cfg.get('_front_meta') or {})
    fm['toc'] = [[e[1], e[2], str(pages[i]), e[0]]
                 for i, e in enumerate(entries)]
    fm.setdefault('book_title', cfg['book_title'])
    fm.setdefault('toc_title', cfg['toc_title'])
    for key in ('front_meta', 'chapter_pages'):
        p = cpath(cfg, key)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(fm if key == 'front_meta' else ch_start,
                  open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    cfg['_front_meta'] = fm
    return fm


def build_front(cfg, meta):
    """调用技能自带 build_front_pages.front_pages 生成多级目录前置页。"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from build_front_pages import front_pages
    out = sub_docx(cfg, cfg['front_name'])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    front_pages(out, meta)
    return out
