# -*- coding: utf-8 -*-
"""版面解析器：把 PDF 页面解析成按阅读顺序排列的内容块序列。

用法：python parse_layout.py 29 46 out.json
输出结构：{"pages": {"29": {"blocks": [...]}}}
块类型：heading / para / list / numlist / code / figure / quote
"""
import pymupdf, json, sys, re

from bookconf import cfg
PDF = cfg('pdf')

BODY_FONTS = {'Minion-Regular', 'Minion-Italic', 'Minion-Bold', 'MinionPro-Regular', 'MinionPro-It', 'MinionPro-Bold'}
CODE_FONTS = {'CourierNewPSMT', 'CourierNewPS-BoldMT', 'CourierNewPS-ItalicMT'}
SENT_END = '.!?:"”’)]'


def fn(font):
    return font.split('+')[-1]


def is_body(font):
    return fn(font) in BODY_FONTS


def is_code(font):
    return fn(font) in CODE_FONTS


def near(a, b, gap):
    return not (a[2] + gap < b[0] or b[2] + gap < a[0] or a[3] + gap < b[1] or b[3] + gap < a[1])


def join(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def area(r):
    return max(0, r[2] - r[0]) * max(0, r[3] - r[1])


def inter(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0


# ---------------- 图形区检测 ----------------

def graphic_regions(page, body_lines):
    """用 drawings/位图聚类得到图形区，再用图内文字行扩展边界。"""
    W, H = page.rect.width, page.rect.height
    elems = []
    for dr in page.get_drawings():
        r = dr['rect']
        # 注意：直线/表格边框的 rect 宽或高可能为 0，必须保留（曾经漏掉整张对比表）
        x0, y0, x1, y1 = r.x0, r.y0, r.x1, r.y1
        if abs(x1 - x0) < 0.8:
            x0 -= 0.6
            x1 += 0.6
        if abs(y1 - y0) < 0.8:
            y0 -= 0.6
            y1 += 0.6
        if (x1 - x0) > 0.5 and (y1 - y0) > 0.5:
            elems.append((max(18, x0), max(60, y0), min(W - 10, x1), min(H - 12, y1)))
    for info in page.get_image_info():
        r = pymupdf.Rect(info['bbox'])
        if r.width > 1 and r.height > 1:
            elems.append((max(18, r.x0), max(60, r.y0), min(W - 10, r.x1), min(H - 12, r.y1)))
    elems = [e for e in elems if e[2] > e[0] and e[3] > e[1]]
    if not elems:
        return []

    elems.sort(key=lambda r: r[1])
    n = len(elems)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    GAP = 13
    for i in range(n):
        for j in range(i + 1, n):
            if elems[j][1] > elems[i][3] + GAP:
                break
            if near(elems[i], elems[j], GAP):
                ra, rb = find(i), find(j)
                if ra != rb:
                    parent[rb] = ra
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    clusters = []
    for idxs in groups.values():
        bb = elems[idxs[0]]
        for i in idxs[1:]:
            bb = join(bb, elems[i])
        clusters.append(bb)

    # 二次生长：把相距 20pt 内的簇合并（同一张图的不同部分）
    clusters.sort(key=lambda c: -area(c))
    merged = []
    for c in clusters:
        hit = None
        for k, m in enumerate(merged):
            if near(c, m, 9):
                hit = k
                break
        if hit is not None:
            merged[hit] = join(merged[hit], c)
        else:
            merged.append(c)

    # 用"落在区域内 / 紧贴区域"的文字行扩展边界（图内文字可能溢出线条外）
    changed = True
    rounds = 0
    while changed and rounds < 6:
        changed = False
        rounds += 1
        for k, m in enumerate(merged):
            for ln, kind in body_lines:
                cx = (ln[0] + ln[2]) / 2
                cy = (ln[1] + ln[3]) / 2
                inside = m[0] - 3 <= cx <= m[2] + 3 and m[1] - 3 <= cy <= m[3] + 3
                touch = inter(ln, m) > 0.35 * area(ln) or near(ln, m, 5)
                if inside or (touch and kind == 'figtext'):
                    nb = join(m, ln)
                    if nb != m:
                        merged[k] = nb
                        changed = True
    return merged


def _vector_bullet_ys(drawings, min_pt=2.0, max_pt=9.0, x_max=150.0):
    """找出「矢量项目符号」的 y 坐标。

    Manning 2025 版式的章首页 TOC 项目符号是画出来的小方块（约 3x3pt），
    不在文字层，get_text() 取不到。靠 drawings 里的 fill 矩形识别。

    drawings：page.get_drawings() 的返回列表。
    """
    ys = []
    for dr in drawings or []:
        r = dr.get('rect')
        if not r:
            continue
        w, h = r[2] - r[0], r[3] - r[1]
        if w < min_pt or h < min_pt or w > max_pt or h > max_pt:
            continue
        if abs(w - h) > 2.0:              # 要接近正方形
            continue
        if r[0] > x_max:                  # 只在左侧栏找
            continue
        if not dr.get('fill'):            # 描边（fill=None）不算
            continue
        ys.append(round(r[1], 1))
    return sorted(set(ys))


def parse_chapter_open(page, pno):
    """章首页：章号 + 章标题 + 'In this chapter' 列表 + 章首引语 + 导言 + 装饰图。"""
    W, H = page.rect.width, page.rect.height
    d = page.get_text('dict')
    num, title, quote, quote_by, intro = '', [], [], '', []
    toc_lines, toc_items = [], []
    extra_figs = []

    for b in d['blocks']:
        if b['type'] != 0:
            r = pymupdf.Rect(b['bbox'])
            if 60 < r.y0 < H - 20 and r.width > 30 and r.height > 30:
                extra_figs.append([round(v, 1) for v in b['bbox']])
            continue
        for l in b['lines']:
            spans = [s for s in l['spans'] if s['text'].strip()]
            if not spans:
                continue
            bb = l['bbox']
            if bb[1] > 608:
                continue
            fonts = [fn(s['font']) for s in spans]
            size = max(s['size'] for s in spans)
            text = join_spans(spans).strip()
            if size >= 40:
                num += text
            elif size >= 17 and any('Semibold' in f or 'Bold' in f for f in fonts) and 'Myriad' in fonts[0]:
                if text.lower().startswith('in this chapter'):
                    pass
                else:
                    title.append(text)
            elif any('MrEavesXL' in f for f in fonts):
                if size < 10:
                    quote_by += text
                else:
                    quote.append(text)
            elif any(f.startswith('MyriadPro') for f in fonts) and size < 13:
                toc_lines.append((bb[1], bb[0], text))
            elif any(f in BODY_FONTS for f in fonts):
                intro.append(text)

    # 'In this chapter' 列表：以项目符号为锚点分组。
    #   锚点有两种来源：
    #     ① 文字层里的 '•'（老版式，符号是字形）
    #     ② drawings 里 3~8pt 的实心小方块（Manning 2025 版式，符号是矢量图形）
    #   只用 ① 的话，② 那类书里 toc 会退化成"每行一项"，折行也拼不回去。
    toc_lines.sort()
    bullets = [y for (y, x, t) in toc_lines if re.fullmatch(r'[•·▪\s]+', t)]
    if not bullets:
        bullets = _vector_bullet_ys(page.get_drawings())
    if bullets:
        groups = [[] for _ in bullets]
        for (y, x, t) in toc_lines:
            if re.fullmatch(r'[•·▪\s]+', t):
                continue
            idx = 0
            for i, by in enumerate(bullets):
                if y >= by - 6:
                    idx = i
            groups[idx].append(t.strip())
        toc_items = [clean_text(' '.join(g)) for g in groups if g]
    else:
        toc_items = [clean_text(t) for (_, _, t) in toc_lines if t.strip()]

    return {'type': 'chapter_open', 'page': pno,
            'num': num.strip(),
            'title': ' '.join(' '.join(title).split()),
            'toc_items': toc_items,
            'quote': ' '.join(' '.join(quote).split()),
            'quote_by': quote_by.strip(),
            'intro': ' '.join(' '.join(intro).split()),
            'figs': extra_figs}


def join_spans(spans):
    """拼接 span 文本：按 x 间隙补空格（PDF 常在字体切换处丢掉空格）。"""
    txt = spans[0]['text']
    for prev, cur in zip(spans, spans[1:]):
        gap = cur['bbox'][0] - prev['bbox'][2]
        if gap > 0.8 and not prev['text'].endswith((' ', '\u00ad')) and not cur['text'].startswith(' '):
            txt += ' '
        txt += cur['text']
    return txt


def clean_text(t):
    t = t.replace('\u00ad', '')
    t = re.sub(r'[\u2010\u2011]', '-', t)
    t = re.sub(r'[ \t]+', ' ', t)
    return t.strip()


def merge_same_row(lines):
    """PDF 会把同一视觉行拆成多个 line（如行内代码前后），按 y 相同 + x 相邻合并。"""
    lines.sort(key=lambda x: (x['bbox'][1], x['bbox'][0]))
    out = []
    for ln in lines:
        if out:
            pv = out[-1]
            yc1 = (pv['bbox'][1] + pv['bbox'][3]) / 2
            yc2 = (ln['bbox'][1] + ln['bbox'][3]) / 2
            gapx = ln['bbox'][0] - pv['bbox'][2]
            if abs(yc1 - yc2) < 3.2 and -1 <= gapx < 15:
                pv['text'] = pv['text'].rstrip() + ' ' + ln['text'].lstrip()
                pv['bbox'] = (pv['bbox'][0], min(pv['bbox'][1], ln['bbox'][1]),
                              ln['bbox'][2], max(pv['bbox'][3], ln['bbox'][3]))
                pv['fonts'] = pv['fonts'] + ln['fonts']
                pv['text'] = pv['text']
                continue
        out.append(ln)
    return out


def dedupe_lines(lines):
    """去掉视觉重叠的重复文本层（原书列表项存在同一位置的双层文本）。"""
    def norm(t):
        return re.sub(r'[^0-9A-Za-z]', '', t).lower()

    out = []
    for ln in sorted(lines, key=lambda x: -len(x['text'])):
        dup = False
        for o in out:
            yo = min(ln['bbox'][3], o['bbox'][3]) - max(ln['bbox'][1], o['bbox'][1])
            xo = min(ln['bbox'][2], o['bbox'][2]) - max(ln['bbox'][0], o['bbox'][0])
            hmin = min(ln['bbox'][3] - ln['bbox'][1], o['bbox'][3] - o['bbox'][1])
            wmin = min(ln['bbox'][2] - ln['bbox'][0], o['bbox'][2] - o['bbox'][0])
            if hmin <= 0 or wmin <= 0:
                continue
            if yo > 0.55 * hmin and xo > 0.25 * wmin:
                a, b = norm(ln['text']), norm(o['text'])
                if a and b and (a in b or b in a):
                    dup = True
                    # 短行带项目符号 → 把符号标记转移给保留行
                    if re.match(r'^\s*[•·▪]', ln['text']) and not re.match(r'^\s*[•·▪]', o['text']):
                        o['bullet'] = True
                    break
        if not dup:
            out.append(ln)
    return out


def extract_grid_table(page, bbox):
    """用横竖线条还原网格表格；返回 {rows, cols, cells} 或 None。"""
    hs, vs = [], []
    for dr in page.get_drawings():
        r = dr['rect']
        if r.height < 1.4 and r.width > 20 and bbox[1] - 4 < r.y0 < bbox[3] + 4:
            hs.append(round(r.y0, 0))
        elif r.width < 1.4 and r.height > 20 and bbox[0] - 4 < r.x0 < bbox[2] + 4:
            vs.append(round(r.x0, 0))
    hs = sorted(set(hs))
    vs = sorted(set(vs))
    if len(hs) < 2 or len(vs) < 2:
        return None
    # 收集区域内的文字行
    rows, cols = len(hs) - 1, len(vs) - 1
    cells = [[[] for _ in range(cols)] for _ in range(rows)]
    for b in page.get_text('dict')['blocks']:
        if b['type'] != 0:
            continue
        for l in b['lines']:
            spans = [s for s in l['spans'] if s['text'].strip()]
            if not spans:
                continue
            bb = l['bbox']
            cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
            if not (hs[0] - 3 <= cy <= hs[-1] + 3 and vs[0] - 6 <= cx <= vs[-1] + 6):
                continue
            ci, rj = None, None
            for i in range(cols):
                if vs[i] <= cx < vs[i + 1]:
                    ci = i
                    break
            for j in range(rows):
                if hs[j] <= cy < hs[j + 1]:
                    rj = j
                    break
            if ci is None:
                ci = 0 if cx < vs[0] else cols - 1
            if rj is None:
                rj = 0 if cy < hs[0] else rows - 1
            cells[rj][ci].append((bb[1], bb[0], join_spans(spans)))
    def join_cell(items):
        out = ''
        for _, _, t in items:
            t = t.replace('\n', ' ').strip()
            if not t:
                continue
            if not out:
                out = t
            elif out.endswith('\u00ad'):
                out = out[:-1] + t
            elif out.endswith('-') and not out.endswith(' -'):
                out = out + t
            else:
                out = out + ' ' + t
        return clean_text(out)

    data = []
    for j in range(rows):
        row = []
        for i in range(cols):
            row.append(join_cell(sorted(cells[j][i])))
        data.append(row)
    return {'rows': rows, 'cols': cols, 'data': data,
            'ys': hs, 'xs': vs}


# ---------------------------------------------------------------- 代码缩进

def measure_mono_cw(doc, pages=40):
    """从本书的代码行自动测出等宽字符宽度（pt）。

    取"纯等宽字体且不含空格"的行，用 行宽/字符数 的中位数。
    不同书的代码字体不同，所以不能写死。
    """
    import statistics
    widths = []
    n = min(pages, doc.page_count)
    for i in range(n):
        try:
            d = doc[i].get_text('dict')
        except Exception:
            continue
        for b in d['blocks']:
            if b['type'] != 0:
                continue
            for l in b['lines']:
                spans = l['spans']
                if not spans:
                    continue
                if not all(any(cf in fn(sp['font']) for cf in CODE_FONTS)
                           for sp in spans if sp['text'].strip()):
                    continue
                txt = ''.join(sp['text'] for sp in spans)
                if not txt.strip() or ' ' in txt:
                    continue
                w = l['bbox'][2] - l['bbox'][0]
                if w > 0 and len(txt) >= 4:
                    widths.append(w / len(txt))
    if not widths:
        return None
    return statistics.median(widths)


MONO_CW = None      # 由 main() 在解析前填入


def _code_indent_spaces(line, base_x):
    """按 x 坐标算出该代码行的缩进空格数。"""
    if not MONO_CW:
        return 0
    dx = line['bbox'][0] - line.get('base_x', base_x)
    if dx <= 1.2:
        return 0
    n = int(round(dx / MONO_CW))
    # 缩进通常成对出现（2/4 空格），奇数说明是折行续行的对齐，保留原值
    return max(0, n)


# 折行续行判定用：这些结尾表示语句已结束
NO_WRAP_TAIL = ('{', '}', ';', ':', ')', ']')
# 这些开头表示新语句，即使上一行看起来没结束也不合并
NO_WRAP_HEAD = ('return', 'if ', 'if(', 'for ', 'for(', 'while ', 'public',
                'private', 'protected', 'static', 'final', 'var ', 'import',
                'package', 'class', '}', '@', '//', 'else', 'try', 'catch')
# 折行处保留连字符的复合词前缀
HYPHEN_KEEP_PREFIX = ('tile', 'open', 'card', 'end', 'set', 'well', 'high',
                      'real', 'multi', 'cross', 'self', 'non', 'pre', 'post',
                      'two', 'three', 'one', 'long', 'short', 'user', 'file',
                      'stream', 'spring', 'chat', 'tool', 'game', 'board')


def keep_hyphen(tail):
    """折行处的 '-' 是否应保留（复合词而非排版断词）。"""
    word = tail.rstrip()
    if not word.endswith('-'):
        return False
    seg = ''
    for ch in reversed(word[:-1]):
        if ch.isalpha():
            seg = ch + seg
        else:
            break
    return bool(seg) and seg.lower() in HYPHEN_KEEP_PREFIX


def is_wrapped(prev, cur, prev_text, cur_text, right):
    """判断 cur 是否是 prev 被 PDF 折行后的续行。"""
    if not prev_text.strip() or not cur_text:
        return False
    gapy = cur['bbox'][1] - prev['bbox'][3]
    if gapy >= 6.0:
        return False
    tail = prev_text.rstrip()
    # SQL 字符串拼接：换行只是排版折行
    if tail.endswith('||'):
        return True
    # 单词中间被折断
    if tail.endswith('-') and cur_text.lstrip()[:1].islower():
        return True
    # 上一行顶到右边界，且本行不是新语句
    if prev['bbox'][2] <= right - (MONO_CW or 4.8) * 2.2:
        return False
    if tail.endswith(NO_WRAP_TAIL):
        return False
    if cur_text.lstrip().startswith(NO_WRAP_HEAD):
        return False
    return True


def autodetect_code_fonts(doc, pages=60):
    """扫描全书字体，把疑似等宽的字体名并进 CODE_FONTS（就地修改全局集合）。"""
    import collections
    seen = collections.Counter()
    n = min(pages, doc.page_count)
    for i in range(n):
        try:
            d = doc[i].get_text('dict')
        except Exception:
            continue
        for b in d['blocks']:
            if b['type'] != 0:
                continue
            for l in b['lines']:
                for sp in l['spans']:
                    if sp['text'].strip():
                        seen[fn(sp['font'])] += len(sp['text'])
    # 名字特征
    hints = ('mono', 'code', 'consol', 'courier', 'menlo', 'inconsolata',
             'cascadia', 'sourcecode', 'fira', 'iosevka', 'jetbrains')
    added = []
    for fname in seen:
        low = fname.lower().replace('-', '').replace(' ', '')
        if any(h in low for h in hints):
            if fname not in CODE_FONTS:
                CODE_FONTS.add(fname)
                added.append(fname)
    return added


def page_blocks(page, pno):
    W, H = page.rect.width, page.rect.height
    d = page.get_text('dict')

    # ---- 1. 收集文字行 ----
    # 本页版心左右边界：取所有正文/代码行的最小左端与最大右端
    _xs0, _xs1 = [], []
    for _b in d['blocks']:
        if _b['type'] != 0:
            continue
        for _l in _b['lines']:
            _sp = [x for x in _l['spans'] if x['text'].strip()]
            if not _sp:
                continue
            _f = [fn(x['font']) for x in _sp]
            if any(ff in BODY_FONTS for ff in _f) or \
                    any(cf in ff for ff in _f for cf in CODE_FONTS):
                _xs0.append(_l['bbox'][0])
                _xs1.append(_l['bbox'][2])
    margin_left = min(_xs0) if _xs0 else 72.0
    margin_right = max(_xs1) if _xs1 else (page.rect.width - 72.0)

    lines = []
    for b in d['blocks']:
        if b['type'] != 0:
            continue
        for l in b['lines']:
            spans = [s for s in l['spans'] if s['text'].strip()]
            if not spans:
                continue
            bb = tuple(l['bbox'])
            if bb[3] < 60 or bb[1] > 608:
                continue
            fonts = [fn(s['font']) for s in spans]
            size = max(s['size'] for s in spans)
            text = join_spans(spans)
            total_ch = sum(len(sp['text']) for sp in spans) or 1
            body_ch = sum(len(sp['text']) for sp in spans if fn(sp['font']) in BODY_FONTS)
            code_ch = sum(len(sp['text']) for sp in spans if fn(sp['font']) in CODE_FONTS)
            _txt = text.strip()
            _inline_ident = bool(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]{0,24}', _txt))
            if code_ch / total_ch > 0.75 and not _inline_ident:
                kind = 'code'
            elif body_ch / total_ch > 0.4:
                kind = 'body'
            elif any(f.startswith('MyriadPro') for f in fonts) and size >= 11:
                kind = 'head'
            else:
                kind = 'figtext'
            # 版心左右边界：由 page 的文本行统计得到，供代码缩进还原用
            lines.append({'bbox': bb, 'text': text, 'size': size,
                          'fonts': fonts, 'kind': kind,
                          'align_x0': bb[0],
                          'base_x': margin_left, 'right_x': margin_right})

    lines = merge_same_row(dedupe_lines(lines))
    g0 = graphic_regions(page, [(ln['bbox'], ln['kind']) for ln in lines])

    # ---- 2. 判断每行归属：是否属于某个图形区 ----
    # 只有 body/code/head 行需要判断；figtext 天然属于图
    def has_grid(bbox):
        hs = vs = 0
        for dr in page.get_drawings():
            rr = dr['rect']
            if rr.height < 1.4 and rr.width > 20 and bbox[1] - 4 < rr.y0 < bbox[3] + 4:
                hs += 1
            elif rr.width < 1.4 and rr.height > 20 and bbox[0] - 4 < rr.x0 < bbox[2] + 4:
                vs += 1
        return hs >= 2 and vs >= 2

    figs = [{'bbox': r, 'raw': r, 'lines': [], 'n_draw': 0, 'grid': has_grid(r)} for r in g0]

    free_lines = []
    for ln in lines:
        owner = None
        cx = (ln['bbox'][0] + ln['bbox'][2]) / 2
        cy = (ln['bbox'][1] + ln['bbox'][3]) / 2
        big_head = ln['kind'] == 'head' and ln['size'] >= 16
        for f in figs:
            r = f['bbox']
            if big_head:
                break        # 18pt 以上的章节标题绝不属于图（图 bbox 常把它带进去）
            if r[0] - 2 <= cx <= r[2] + 2 and r[1] - 2 <= cy <= r[3] + 2:
                owner = f
                break
        if owner is None and ln['kind'] in ('figtext',):
            # 游离图内文字（如只有文字没有线条的便签）：找最近的图形区
            best, bd = None, 1e9
            for f in figs:
                r = f['bbox']
                dx = max(r[0] - ln['bbox'][2], ln['bbox'][0] - r[2], 0)
                dy = max(r[1] - ln['bbox'][3], ln['bbox'][1] - r[3], 0)
                dist = (dx * dx + dy * dy) ** 0.5
                if dist < bd:
                    bd, best = dist, f
            if best is not None and bd < 60:
                owner = best
        if owner is not None:
            owner['lines'].append(ln)
        else:
            free_lines.append(ln)

    # ---- 3. 图形区后处理 ----
    out_figs = []
    for f in figs:
        if len(f['lines']) == 0:
            w = f['bbox'][2] - f['bbox'][0]
            h = f['bbox'][3] - f['bbox'][1]
            if w < 34 or h < 28:      # 纯装饰小图元，丢弃
                continue
            f['bbox'] = (f['bbox'][0], f['bbox'][1], f['bbox'][2], f['bbox'][3])
        else:
            bb = f['bbox']
            for ln in f['lines']:
                bb = join(bb, ln['bbox'])
            f['bbox'] = bb
        w = f['bbox'][2] - f['bbox'][0]
        h = f['bbox'][3] - f['bbox'][1]
        if w < 30 or h < 24:
            continue
        # 版心外的纯装饰小插图（无文字）不收录
        if not f['lines'] and w * h < 13000 and (w < 100 or h < 110):
            continue
        f['lines'].sort(key=lambda x: (round(x['bbox'][1]), x['bbox'][0]))
        # 判断是否表格：有完整网格线优先；否则看 Minion 文字行的列数
        grid = extract_grid_table(page, f['bbox'])
        if grid:
            filled = sum(1 for row in grid['data'] for c in row if c)
            grid['fill_ratio'] = filled / max(1, grid['rows'] * grid['cols'])
        ok_grid = (grid and grid['rows'] >= 2 and grid['cols'] >= 3 and len(f['lines']) >= 6
                   and grid['fill_ratio'] >= 0.7)
        if ok_grid:
            f['is_table'] = True
            f['grid'] = grid
            f['kind'] = 'table'
        else:
            f['is_table'] = False
            f['kind'] = 'figure'
            f['grid'] = None
        f['texts'] = [{'text': ln['text'].strip(), 'bbox': [round(v, 1) for v in ln['bbox']],
                       'size': round(ln['size'], 1), 'kind': ln['kind']} for ln in f['lines']]
        out_figs.append(f)

    # ---- 3.5 合并交叠严重的图块（同一注释被拆到两个图里会导致文字错位）----
    changed = True
    while changed:
        changed = False
        for i in range(len(out_figs)):
            for j in range(i + 1, len(out_figs)):
                a, b = out_figs[i]['bbox'], out_figs[j]['bbox']
                ov = inter(a, b)
                if ov > 0.055 * min(area(a), area(b)):
                    f1, f2 = out_figs[i], out_figs[j]
                    f1['bbox'] = join(a, b)
                    f1['texts'] = f1['texts'] + f2['texts']
                    f1['texts'].sort(key=lambda x: (x['bbox'][1], x['bbox'][0]))
                    out_figs.pop(j)
                    changed = True
                    break
            if changed:
                break

    # ---- 4. 自由行聚合成段落/列表/代码 ----
    free_lines.sort(key=lambda x: (x['bbox'][1], x['bbox'][0]))
    blocks = []
    from collections import Counter as _C
    body_x0 = [round(l['bbox'][0]) for l in free_lines if l['kind'] == 'body']
    base_x = _C(body_x0).most_common(1)[0][0] if body_x0 else 54

    def flush_code(buf):
        if not buf:
            return
        parts = []
        prev = None
        # 正常行距 = 本代码块内出现最多的 y0 间距（众数，按 0.5pt 分桶）
        import collections as _c
        yr = [x['bbox'][1] for x in buf]
        buckets = _c.Counter()
        for a, b in zip(yr, yr[1:]):
            if b > a:
                buckets[round((b - a) * 2) / 2] += 1
        line_pitch = buckets.most_common(1)[0][0] if buckets else 0
        for x in buf:
            if prev is not None and line_pitch > 0:
                pitch = x['bbox'][1] - prev['bbox'][1]
                if pitch > line_pitch * 1.5 + 1.0:
                    parts.append('')
            raw = x['text']
            if not raw.strip():
                prev = x
                continue
            text_stripped = raw.strip()
            # 折行续行：上一行顶到版心右边界、本行紧贴其下 → 拼回同一行
            if prev is not None and parts and is_wrapped(
                    prev, x, parts[-1], text_stripped,
                    x.get('right_x', 504.0)):
                tail = parts[-1].rstrip()
                if tail.endswith('-') and not tail.endswith('--'):
                    if keep_hyphen(tail):
                        parts[-1] = tail + text_stripped
                    else:
                        parts[-1] = tail[:-1] + text_stripped
                else:
                    parts[-1] = parts[-1] + text_stripped
            else:
                # 按 x 坐标还原前导缩进（原书缩进是排版的，不在文本里）
                n_sp = _code_indent_spaces(x, x.get('base_x', 72.0))
                parts.append(' ' * n_sp + text_stripped)
            prev = x
        txt = '\n'.join(parts)
        y0 = min(x['bbox'][1] for x in buf)
        y1 = max(x['bbox'][3] for x in buf)
        x0 = min(x['bbox'][0] for x in buf)
        blocks.append({'type': 'code', 'text': txt, 'page': pno,
                       'bbox': [round(v, 1) for v in buf[0]['bbox']],
                       'y0': y0, 'y1': y1, 'x0': x0,
                       'lines': len(buf)})

    code_buf = []
    for ln in free_lines:
        if ln['kind'] == 'code':
            code_buf.append(ln)
            continue
        flush_code(code_buf)
        code_buf = []
        t = ln['text']
        if ln['kind'] == 'head':
            lvl = 2 if ln['size'] >= 16 else 3
            if blocks and blocks[-1]['type'] == 'heading' and blocks[-1]['level'] == lvl \
               and ln['bbox'][1] - blocks[-1]['y1'] < ln['size'] * 0.8:
                blocks[-1]['text'] += ' ' + t.strip()
                blocks[-1]['y1'] = ln['bbox'][3]
            else:
                blocks.append({'type': 'heading', 'level': lvl, 'text': t.strip(),
                               'page': pno, 'y0': ln['bbox'][1], 'y1': ln['bbox'][3]})
            continue

        # 正文 / 列表
        s = t.strip()
        prevb = blocks[-1] if blocks else None
        is_new_item = bool(re.match(r'^(\d+\.\s|[•·▪])', s))
        if prevb and prevb['type'] in ('list', 'numlist') and not is_new_item \
           and ln['bbox'][1] - prevb.get('last_y0', prevb['y1']) < ln['size'] * 1.55:
            it = prevb['items'][-1].rstrip()
            if it.endswith('\u00ad'):
                prevb['items'][-1] = it[:-1] + s
            elif it.endswith('-') and not it.endswith(' -'):
                prevb['items'][-1] = it + s
            else:
                prevb['items'][-1] = it + ' ' + s
            prevb['y1'] = ln['bbox'][3]
            prevb['last_y0'] = ln['bbox'][1]
            continue
        if ln.get('bullet') or re.match(r'^[•·▪]\s', s) or re.match(r'^\d+\.\s', s) or re.match(r'^[•·]\t', t):
            kind = 'numlist' if re.match(r'^\d+\.', s) else 'list'
            item = re.sub(r'^[•·▪]\s*', '', s)
            item = re.sub(r'^\d+\.\s*', '', item)
            # 同一行里塞了两个项目符号 → 拆成多项（原书列表被 PDF 抽成一行）
            parts = [x.strip() for x in re.split(r'[•·▪]\s+', item) if x.strip()]
            if len(parts) > 1:
                for pi in parts:
                    if blocks and blocks[-1]['type'] == kind and pi is parts[0]:
                        blocks[-1]['items'][-1] += ' ' + pi
                        blocks[-1]['y1'] = ln['bbox'][3]
                    else:
                        blocks.append({'type': kind, 'items': [pi], 'page': pno,
                                       'y0': ln['bbox'][1], 'y1': ln['bbox'][3],
                                       'last_y0': ln['bbox'][1]})
                continue
            if blocks and blocks[-1]['type'] == kind and not is_new_item \
               and ln['bbox'][1] - blocks[-1].get('last_y0', blocks[-1]['y1']) < ln['size'] * 1.55:
                blocks[-1]['items'][-1] += ' ' + item
                blocks[-1]['y1'] = ln['bbox'][3]
                blocks[-1]['last_y0'] = ln['bbox'][1]
            else:
                blocks.append({'type': kind, 'items': [item], 'page': pno,
                               'y0': ln['bbox'][1], 'y1': ln['bbox'][3],
                               'last_y0': ln['bbox'][1]})
            continue

        # 普通段落：合并相邻行
        prev = blocks[-1] if blocks else None
        if prev and prev['type'] == 'para' and ln['bbox'][1] - prev['y1'] < 4.5:
            # 首行相对版心左边距有缩进 → 新段落（缩进量 6~40pt；更大的是环绕排版的窄栏，不是缩进）
            indent = ln['bbox'][0] - base_x
            if 6 < indent < 40:
                blocks.append({'type': 'para', 'text': s, 'page': pno,
                               'y0': ln['bbox'][1], 'y1': ln['bbox'][3], 'x0': ln['bbox'][0],
                               'bbox': list(ln['bbox'])})
            else:
                pt = prev['text']
                if pt.endswith('\u00ad'):
                    prev['text'] = pt[:-1] + s
                elif pt.endswith('-') and not pt.endswith(' -'):
                    prev['text'] = pt + s
                else:
                    prev['text'] = pt + ' ' + s
                prev['y1'] = ln['bbox'][3]
                if 'bbox' in prev:
                    prev['bbox'] = [min(prev['bbox'][0], ln['bbox'][0]), min(prev['bbox'][1], ln['bbox'][1]),
                                    max(prev['bbox'][2], ln['bbox'][2]), max(prev['bbox'][3], ln['bbox'][3])]
        else:
            blocks.append({'type': 'para', 'text': s, 'page': pno,
                           'y0': ln['bbox'][1], 'y1': ln['bbox'][3], 'x0': ln['bbox'][0],
                           'bbox': list(ln['bbox'])})
    flush_code(code_buf)

    # ---- 5. 图块插入阅读顺序 ----
    for f in out_figs:
        blocks.append({'type': f['kind'], 'page': pno,
                       'y0': f['bbox'][1], 'y1': f['bbox'][3],
                       'bbox': [round(v, 1) for v in f['bbox']],
                       'texts': f['texts'], 'is_table': f['is_table'],
                       'grid': f.get('grid')})
    for b in list(blocks):
        if b['type'] != 'para' or len(b['text']) >= 30 or 'bbox' not in b:
            continue
        for f in out_figs:
            r = f['bbox']
            dy = min(abs(r[1] - b['bbox'][3]), abs(b['bbox'][1] - r[3]))
            dxo = min(r[2], b['bbox'][2]) - max(r[0], b['bbox'][0])
            cx = (b['bbox'][0] + b['bbox'][2]) / 2
            cy = (b['bbox'][1] + b['bbox'][3]) / 2
            inside = r[0] <= cx <= r[2] and r[1] <= cy <= r[3]
            if (inside and dxo > 0) or (dxo > 0 and dy < 22):
                f['bbox'] = join(f['bbox'], b['bbox'])
                blocks.remove(b)
                break
    txt_blocks = [b for b in blocks if b['type'] in ('para', 'list', 'numlist', 'code', 'heading')]
    for b in blocks:
        if b['type'] in ('para', 'list', 'numlist', 'code', 'heading', 'chapter_open') or 'y1' not in b:
            continue
        ov = [t2 for t2 in txt_blocks if t2['y1'] > b['y0'] + 2 and t2['y0'] < b['y1'] - 2]
        if ov:
            b['y0'] = max(t2['y1'] for t2 in ov) + 0.5
    blocks.sort(key=lambda b: (round(b['y0'] / 6), b['y0']))

    # ---- 6. 清理字段 ----
    for b in blocks:
        b.pop('y0', None)
        b.pop('y1', None)
        b.pop('x0', None)
        b.pop('last_y0', None)
    return blocks


def is_chapter_open(page):
    for b in page.get_text('dict')['blocks']:
        if b['type'] != 0:
            continue
        for l in b['lines']:
            for s in l['spans']:
                if s['size'] >= 40 and s['text'].strip().isdigit():
                    return True
    return False


def main():
    global MONO_CW
    a, b = int(sys.argv[1]), int(sys.argv[2])
    outp = sys.argv[3]
    doc = pymupdf.open(PDF)
    added = autodetect_code_fonts(doc)
    if added:
        print('自动识别到等宽字体: %s' % ', '.join(added))
    MONO_CW = measure_mono_cw(doc)
    if MONO_CW:
        print('等宽字符宽度 = %.3f pt（用于还原代码缩进）' % MONO_CW)
    else:
        print('!! 未测到等宽字符宽度，代码缩进将不还原')
    res = {}
    for pno in range(a, b + 1):
        page = doc[pno - 1]
        if is_chapter_open(page):
            res[str(pno)] = [parse_chapter_open(page, pno)]
        else:
            res[str(pno)] = page_blocks(page, pno)

    # 跨页续接：上一页末块未收尾 → 与下一页首块合并（段落 / 代码）
    SENT_END = tuple('。！？：；.!?:;"”)）')
    keys = sorted(res, key=int)
    for i in range(len(keys) - 1):
        cur, nxt = res[keys[i]], res[keys[i + 1]]
        if not cur or not nxt:
            continue
        tail, head = cur[-1], nxt[0]
        if tail['type'] == 'para' and head['type'] == 'para' \
                and not tail['text'].rstrip().endswith(SENT_END):
            tail['text'] = tail['text'].rstrip() + ' ' + head['text'].lstrip()
            nxt.pop(0)
        elif tail['type'] == 'code' and head['type'] == 'code':
            tail['text'] = tail['text'] + '\n' + head['text']
            tail['lines'] = tail.get('lines', 0) + head.get('lines', 0)
            nxt.pop(0)

    json.dump({'pages': res}, open(outp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for pno, blks in res.items():
        print(f'--- p{pno}: ' + ', '.join(
            (x['type'] if x['type'] != 'heading' else f"H{x['level']}") for x in blks))


if __name__ == '__main__':
    main()
