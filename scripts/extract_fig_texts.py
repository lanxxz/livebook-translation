# -*- coding: utf-8 -*-
"""从图块中提取"可翻译文字块"（按段落聚合），产出待译清单 JSON。

用法：python extract_fig_texts.py <layout.json> <out.json>
"""
import json, sys, re, pymupdf

from bookconf import cfg
PDF = cfg('pdf')
CODE = {'CourierNewPSMT', 'CourierNewPS-BoldMT', 'CourierNewPS-ItalicMT'}


def fn(f):
    return f.split('+')[-1]


def group_blocks(lines):
    n = len(lines)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            a, b = lines[i]['bbox'], lines[j]['bbox']
            xo = min(a[2], b[2]) - max(a[0], b[0])
            wmin = min(a[2] - a[0], b[2] - b[0])
            if wmin <= 0:
                continue
            gapy = (a[1] - b[3]) if a[1] > b[1] else (b[1] - a[3])
            fam = lambda fs: {'MyriadPro'} & set(f.split('-')[0] for f in fs)
            same_fam = fam(lines[i]['fonts']) == fam(lines[j]['fonts'])
            # 中心点接近（居中排版的两行，宽度可以差很多）
            ca, cb = (a[0] + a[2]) / 2, (b[0] + b[2]) / 2
            centered = abs(ca - cb) < max(wmin * 0.6, 6.0)
            if (xo > 0.42 * wmin or centered) \
               and gapy < lines[i]['size'] * 1.75 \
               and abs(lines[i]['size'] - lines[j]['size']) < 1.2 and same_fam:
                ra, rb = find(i), find(j)
                if ra != rb:
                    parent[rb] = ra
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    out = []
    for idxs in groups.values():
        idxs.sort(key=lambda i: lines[i]['bbox'][1])
        out.append([lines[i] for i in idxs])
    out.sort(key=lambda g: (g[0]['bbox'][1], g[0]['bbox'][0]))
    return out


def norm(t):
    return re.sub(r'[^0-9A-Za-z]', '', t).lower()


def dedupe(lines):
    """同一视觉位置的重叠文本层只留一条（原书图内有重复字模）。"""
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
                    break
        if not dup:
            out.append(ln)
    return out


def area(r):
    return max(0, r[2] - r[0]) * max(0, r[3] - r[1])


def main():
    layout = json.load(open(sys.argv[1], encoding='utf-8'))['pages']
    doc = pymupdf.open(PDF)
    result = {}
    for pno, blks in layout.items():
        page = doc[int(pno) - 1]
        figs = []
        fi = 0
        for b in blks:
            if b['type'] in ('figure', 'table'):
                if b['type'] == 'figure':
                    figs.append({'key': f'p{pno}_f{fi}', 'bbox': b['bbox'], 'lines': []})
                fi += 1
        if not figs:
            continue
        cand = []
        for blk in page.get_text('dict')['blocks']:
            if blk['type'] != 0:
                continue
            for l in blk['lines']:
                spans = [s for s in l['spans'] if s['text'].strip()]
                if not spans:
                    continue
                if max(s2['size'] for s2 in spans) >= 16:
                    continue      # 16pt 以上是章节标题，不属于图
                bb = l['bbox']
                cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
                owners = [f for f in figs
                          if f['bbox'][0] - 3 <= cx <= f['bbox'][2] + 3
                          and f['bbox'][1] - 3 <= cy <= f['bbox'][3] + 3]
                if not owners:
                    continue
                owner = min(owners, key=lambda f: area(f['bbox']))
                txt = ''
                prev = None
                for s in spans:
                    if prev is not None and s['bbox'][0] - prev['bbox'][2] > 0.8 and not txt.endswith(' '):
                        txt += ' '
                    txt += s['text']
                    prev = s
                cand.append({'bbox': tuple(bb), 'text': txt.replace('\u00ad', ''),
                             'size': max(s['size'] for s in spans),
                             'fonts': [fn(s['font']) for s in spans],
                             'dir': l.get('dir', (1, 0)),
                             'owner': owner['key']})
        cand = dedupe(cand)
        for c in cand:
            for f in figs:
                if f['key'] == c['owner']:
                    f['lines'].append(c)

        for f in figs:
            bb0 = f['bbox']
            if not f['lines']:
                result[f['key']] = {'page': int(pno),
                                    'bbox': [round(bb0[0] - 2, 1), round(bb0[1] - 2, 1),
                                             round(bb0[2] + 2, 1), round(bb0[3] + 2, 1)],
                                    'blocks': []}
                continue
            groups = group_blocks(f['lines'])
            blocks = []
            for gi, g in enumerate(groups):
                u = list(g[0]['bbox'])
                for l in g[1:]:
                    u = [min(u[0], l['bbox'][0]), min(u[1], l['bbox'][1]),
                         max(u[2], l['bbox'][2]), max(u[3], l['bbox'][3])]
                en = ' '.join(l['text'].strip() for l in g)
                en = re.sub(r'\s+', ' ', en).strip()
                if not en:
                    continue
                blocks.append({'id': gi, 'en': en,
                               'bbox': [round(v, 1) for v in u],
                               'line_bboxes': [[round(v, 1) for v in l['bbox']] for l in g],
                               'size': round(g[0]['size'], 1),
                               'rotated': abs(g[0]['dir'][1]) > 0.05,
                               'code_like': all(any(x in CODE for x in l['fonts']) for l in g)})
            bb = f['bbox']
            result[f['key']] = {'page': int(pno),
                                'bbox': [round(bb[0] - 2, 1), round(bb[1] - 2, 1),
                                         round(bb[2] + 2, 1), round(bb[3] + 2, 1)],
                                'blocks': blocks}
    json.dump(result, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    tot = sum(len(v['blocks']) for v in result.values())
    ch = sum(len(b['en']) for v in result.values() for b in v['blocks'])
    print(f'图 {len(result)} 个，文字块 {tot} 个，{ch} 字符')


if __name__ == '__main__':
    main()
