# -*- coding: utf-8 -*-
"""逐份文档体检：块数 / 类型 / 空块 / 图内缺译，一张表看完。

与 `check_cov.py` 的分工：
  - `check_cov.py` 只看「块号集合」，快，适合边写边查。
  - `check_zh.py` 还核 **块类型是否与 layout 一致**，并查 **空块**、
    **块数是否严格相等**（多一个块头也要报）。

为什么需要第二道闸门（实测踩过）：
  `convert.py` 只在「`_zh.txt` 块数**少于** layout」时报缺块；
  如果多写了块头，它**静默忽略**，不报任何错。于是块号整体错位一格，
  docx 里段落与标题全串位，而 convert 的输出看起来是正常的。
  典型触发：把一个 `figure` 块当成正文 `p` 写（figure 与紧随的 p 是两个独立块）。

判据：
  · 块数必须严格相等（不等就是多写或漏写）
  · 每块类型必须落在 layout 类型允许的集合里（`heading` 允许 `h2`/`h3`）
  · 非 code 块必须有内容（code 由原版面按坐标重建，`_zh.txt` 里可留空）

用法：
  python check_zh.py            # 跑 book.json 里 docs 列出的全部文档
  python check_zh.py ch03 ch08  # 只查指定的
  python check_zh.py --verbose  # 打印每处不匹配的块号
"""
import json
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def project_root():
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

# layout 类型 → _zh.txt 里允许写的类型
TYPE_MAP = {
    'heading': ('h2', 'h3'),
    'para': ('p',),
    'list': ('list',),
    'numlist': ('numlist',),
    'figure': ('figure',),
    'table': ('table',),
    'code': ('code',),
    'panel': ('panel',),
    'callout': ('callout',),
    'sidebar': ('sidebar',),
    'sidebar_head': ('sidebar_head', 'sidebar'),
    'part_open': ('part_open',),
    'chapter_open': ('chapter_open',),
}


def load_blocks(path):
    """解析 `@@B <num> <type> [注释]` 开头的块文件 → {num: (type, body)}。"""
    if not os.path.exists(path):
        return None
    text = open(path, encoding='utf-8-sig').read()
    out = {}
    for chunk in re.split(r'(?m)^@@B\s+', text):
        if not chunk.strip():
            continue
        m = re.match(r'(\d+)[ \t]*([^\n#]*)\n?(.*)$', chunk, re.S)
        if not m:
            continue
        out[int(m.group(1))] = (m.group(2).strip(), m.group(3))
    return out


def layout_seq(path):
    """layout 的 [[页号, 类型], ...]，按文档顺序。"""
    lay = json.load(open(path, encoding='utf-8'))['pages']
    seq = []
    for pn in sorted(lay, key=int):
        for b in lay[pn]:
            seq.append((int(pn), b['type']))
    return seq


def parse_figzh(path):
    """`_figzh.txt` → {"p46_f0": {"0": "中文", ...}}（仅用于没生成 figtrans.json 时兜底）。"""
    out = {}
    key, tid, buf = None, None, []

    def commit():
        if key is not None and tid is not None:
            t = '\n'.join(buf).strip()
            if t:
                out.setdefault(key, {})[str(tid)] = t

    for raw in open(path, encoding='utf-8-sig').read().split('\n'):
        s = raw.rstrip().lstrip('\ufeff')
        m = re.match(r'^@@FIG\s+(\S+)', s)
        if m:
            commit()
            key, tid, buf = m.group(1), None, []
            continue
        m = re.match(r'^@@T\s+(\d+)', s)
        if m:
            commit()
            tid, buf = int(m.group(1)), []
            continue
        if tid is not None:
            buf.append(s[2:].strip() if s.startswith('ZH') else s)
    commit()
    return out


def check(doc, verbose=False):
    lay_p = os.path.join(WORK, doc + '_layout.json')
    if not os.path.exists(lay_p):
        print('%-6s 缺 %s_layout.json' % (doc, doc))
        return False
    seq = layout_seq(lay_p)

    zh = load_blocks(os.path.join(WORK, doc + '_zh.txt'))
    if zh is None:
        print('%-6s %-6d %-6s %-6s %-6s %-8s %s'
              % (doc, len(seq), '-', '-', '-', '-', '未开始'))
        return False

    problems = []
    if len(zh) != len(seq):
        problems.append('块数 %d≠%d' % (len(zh), len(seq)))

    mismatched = []
    for i, (pn, lt) in enumerate(seq):
        if i not in zh:
            mismatched.append((i, 'MISSING'))
            continue
        ty = zh[i][0]
        allowed = TYPE_MAP.get(lt, (lt,))
        if ty not in allowed:
            mismatched.append((i, '%s≠%s' % (ty, lt)))
    if mismatched:
        problems.append('类型/缺 %d 处' % len(mismatched))

    empty = []
    for i in range(len(seq)):
        if i not in zh:
            continue
        ty, body = zh[i]
        if ty == 'code':
            continue        # code 由版面坐标重建，可留空
        txt = body
        if ty == 'panel':
            txt = ''.join(l for l in body.split('\n')
                          if l.strip().startswith('['))
        if not txt.strip():
            empty.append(i)
    if empty:
        problems.append('空块 %d 处' % len(empty))

    fig_note = '-'
    ft_p = os.path.join(WORK, doc + '_figtexts.json')
    if os.path.exists(ft_p):
        ft = json.load(open(ft_p, encoding='utf-8'))
        # 图内译文有两种落地形式：直接写 _figtrans.json，或写 _figzh.txt 再由
        # convert.py 转成 _figtrans.json。优先用已生成的 json（它是最终真源）。
        tr = {}
        tr_p = os.path.join(WORK, doc + '_figtrans.json')
        if os.path.exists(tr_p):
            try:
                tr = json.load(open(tr_p, encoding='utf-8'))
            except Exception:
                tr = {}
        elif os.path.exists(os.path.join(WORK, doc + '_figzh.txt')):
            tr = parse_figzh(os.path.join(WORK, doc + '_figzh.txt'))
        need = miss = 0
        for key, val in ft.items():
            for b in val.get('blocks') or []:
                need += 1
                if not str(tr.get(key, {}).get(str(b['id']), '')).strip():
                    miss += 1
        fig_note = '%d/%d' % (miss, need)
        if miss:
            problems.append('图内缺 %d' % miss)

    verdict = 'OK' if not problems else 'BAD ' + '; '.join(problems)
    print('%-6s %-6d %-6d %-6d %-6d %-8s %s'
          % (doc, len(seq), len(zh), len(zh), len(empty), fig_note, verdict))
    if verbose:
        for i, why in mismatched[:20]:
            print('        块 %d: %s' % (i, why))
        if empty:
            print('        空块:', empty[:20])
    return not problems


def docs_from_cfg():
    p = os.path.join(ROOT, 'docs.json')
    if os.path.exists(p):
        return [d['id'] for d in json.load(open(p, encoding='utf-8'))]
    c = os.path.join(ROOT, 'book.json')
    if os.path.exists(c):
        return [d['id'] for d in json.load(open(c, encoding='utf-8')).get('docs', [])]
    return []


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    verbose = '-v' in sys.argv or '--verbose' in sys.argv
    docs = args or docs_from_cfg()
    if not docs:
        sys.exit('没有可检查的文档（缺 book.json / docs.json 的 docs 列表）')
    print('%-6s %-6s %-6s %-6s %-6s %-8s %s'
          % ('doc', 'layout', 'skel', 'zh', '空块', '图内缺', '结论'))
    results = [(d, check(d, verbose)) for d in docs]
    bad = [d for d, ok in results if not ok]
    print()
    if bad:
        print('未通过 %d 份：%s' % (len(bad), ', '.join(bad)))
    else:
        print('全部 %d 份文档通过。' % len(results))


if __name__ == '__main__':
    main()
