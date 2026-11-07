# -*- coding: utf-8 -*-
"""把"译文草稿"（work/<doc>_zh.txt）合并进布局信息，生成 build_docx 需要的 trans.json。

译文草稿格式（按块列举，块序必须与 skeleton 一致）：

  @@B 0
  TITLE: 中文标题
  APPENDIX: no
  NUM: 3
  TOC: 本章内容一
  TOC: 本章内容二
  INTRO: 导言中文
  @@B 1
  整段中文……
  @@B 5
  - 列表项中文
  - 列表项中文
  @@B 9
  A. | B. | C.
  @@B 12
  ``` 
  代码原样
  ```

用法：python convert.py <doc_id> [--figs]
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, 'work')
CJK = re.compile(r'[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]')


def parse_zh(path):
    """解析 @@B 块。返回 ({idx: [lines]}, 重复块号列表)。

    重复块号（同一 @@B n 出现多次）只保留最后一次——这是译文错位的常见源头，
    必须上报而不是静默覆盖（见 pitfalls S1）。
    """
    out = {}
    dups = []
    cur = None
    buf = []
    text = open(path, encoding='utf-8-sig').read()
    for raw in text.split('\n'):
        m = re.match(r'^@@B\s+(\d+)\s*$', raw.strip().lstrip('\ufeff'))
        if m:
            if cur is not None:
                if cur in out:
                    dups.append(cur)
                out[cur] = buf
            cur = int(m.group(1))
            buf = []
            continue
        if cur is None:
            continue
        buf.append(raw)
    if cur is not None:
        if cur in out:
            dups.append(cur)
        out[cur] = buf
    # 去掉首尾空行
    for k in out:
        lines = out[k]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
    return out, dups


def parse_fig_zh(path):
    """解析 @@FIG key / @@T id 块。返回 {key: {id: text}}"""
    res = {}
    key = None
    tid = None
    buf = []
    for raw in open(path, encoding='utf-8-sig').read().split('\n'):
        s = raw.rstrip().lstrip('\ufeff')
        m = re.match(r'^@@FIG\s+(\S+)', s)
        if m:
            if key and tid is not None:
                res.setdefault(key, {})[str(tid)] = '\n'.join(buf).strip()
            key, tid, buf = m.group(1), None, []
            continue
        m = re.match(r'^@@T\s+(\d+)', s)
        if m:
            if key and tid is not None:
                res.setdefault(key, {})[str(tid)] = '\n'.join(buf).strip()
            tid, buf = int(m.group(1)), []
            continue
        if tid is not None and s.startswith('ZH'):
            buf = [s[2:].strip()] if s[2:].strip() else []
            continue
        if tid is not None:
            buf.append(s)
    if key and tid is not None:
        res.setdefault(key, {})[str(tid)] = '\n'.join(buf).strip()
    return res


def kv(lines):
    d = {}
    order = []
    for ln in lines:
        if ':' not in ln:
            continue
        k, v = ln.split(':', 1)
        k = k.strip()
        v = v.strip()
        if k in ('TOC', 'BODY'):
            d.setdefault(k, []).append(v)
        else:
            d[k] = v
            order.append(k)
    return d


def main():
    doc = sys.argv[1]
    lay = json.load(open(os.path.join(WORK, doc + '_layout.json'), encoding='utf-8'))['pages']
    zh_p = os.path.join(WORK, doc + '_zh.txt')
    zmap, dups = parse_zh(zh_p)
    if dups:
        print(f'!! {doc}: 块号重复 {sorted(set(dups))}（同号只保留最后一次出现，'
              f'其余被静默丢弃——通常是译文错位的信号，见 pitfalls S1）')

    blocks = []
    idx = 0
    missing = []
    for pno in sorted(lay, key=int):
        for b in lay[pno]:
            t = b['type']
            lines = zmap.get(idx)
            if lines is None:
                missing.append((idx, t))
                lines = []
            if t == 'chapter_open':
                d = kv(lines)
                blocks.append({
                    'type': 'chapter_open',
                    'num': d.get('NUM', b['num']),
                    'appendix': b.get('appendix', False),
                    'title': d.get('TITLE', ''),
                    'orig_title': b['title'],
                    'toc': d.get('TOC', []),
                    'quote': '', 'quote_by': '',
                    'intro': d.get('INTRO', ''),
                })
            elif t == 'part_open':
                d = kv(lines)
                blocks.append({
                    'type': 'part_open',
                    'num': d.get('NUM', b['num']),
                    'title': d.get('TITLE', ''),
                    'orig_title': b['title'],
                    'body': d.get('BODY', []),
                })
            elif t == 'heading':
                txt = ' '.join(x.strip() for x in lines if x.strip())
                blocks.append({'type': 'h2' if b['level'] == 2 else 'h3', 'text': txt})
            elif t == 'para':
                _ls = [x.strip() for x in lines if x.strip()]
                # 目录页等需要逐条列出的段落：以 ■ 开头的新行保留为换行
                if any(x.startswith('■') for x in _ls):
                    blocks.append({'type': 'p', 'text': '\n'.join(_ls)})
                else:
                    blocks.append({'type': 'p', 'text': ' '.join(_ls)})
            elif t in ('list', 'numlist'):
                items = [re.sub(r'^\s*[-*•]\s*', '', x).strip() for x in lines if x.strip()]
                blocks.append({'type': t, 'items': items})
            elif t == 'code':
                if b.get('_code_zh'):
                    pass
                blocks.append({'type': 'code', 'text': b['text']})
            elif t == 'figure':
                cap = ' '.join(x.strip() for x in lines if x.strip())
                cap = re.sub(r'^CAP:\s*', '', cap)
                blocks.append({'type': 'figure', 'key': f'p{b["page"]}_f{b.get("figi", 0)}',
                               'caption': cap, 'w_pt': b['bbox'][2] - b['bbox'][0]})
            elif t == 'table':
                g = b['grid']
                gdata = g['data']
                cap = ''
                hdr = []
                rows = []
                for x in lines:
                    if not x.strip():
                        continue
                    if x.startswith('CAP:'):
                        cap = x[4:].strip()
                    elif x.startswith('HDR:'):
                        hdr = [c.strip() for c in x[4:].split('|')]
                    elif x.startswith('ROW:'):
                        rows.append([c.strip() for c in x[4:].split('|')])
                    else:
                        r = [c.strip() for c in x.split('|')]
                        if not hdr:
                            hdr = r
                        else:
                            rows.append(r)
                if not hdr:
                    hdr = gdata[0]
                blocks.append({'type': 'table', 'head': hdr, 'rows': rows,
                               'caption': cap or b.get('caption', '')})
            idx += 1

    extra = sorted(k for k in zmap if k >= idx)
    if extra:
        print(f'!! {doc}: {len(extra)} 个多余块头被丢弃: {extra[:12]}')
        print('   译文块数比版面多，多半是中途漏写/多写块头导致后续块号整体错位；'
              '请对照 _skel.txt 逐块核对，并跑 check_zh.py 复核（见 pitfalls S1）')
    json.dump(blocks, open(os.path.join(WORK, doc + '_trans.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    if missing:
        print(f'!! {doc}: {len(missing)} 块缺译文 -> {missing[:12]}')
    print(f'{doc}: {len(blocks)} blocks -> {doc}_trans.json')

    # 图内文字
    fzh = os.path.join(WORK, doc + '_figzh.txt')
    if os.path.exists(fzh):
        figtrans = parse_fig_zh(fzh)
        json.dump(figtrans, open(os.path.join(WORK, doc + '_figtrans.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        ft = json.load(open(os.path.join(WORK, doc + '_figtexts.json'), encoding='utf-8'))
        miss = [(k, b['id'], b['en'][:30]) for k, v in ft.items()
                for b in v['blocks'] if not figtrans.get(k, {}).get(str(b['id']))]
        print(f'   图内文字 {sum(len(v) for v in figtrans.values())} 条，缺 {len(miss)}')
        if miss:
            for m in miss[:8]:
                print('     ', m)


if __name__ == '__main__':
    main()
