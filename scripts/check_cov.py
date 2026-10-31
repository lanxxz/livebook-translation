# -*- coding: utf-8 -*-
"""骨架文本流水线的覆盖率检查（convert.py 的搭档）。

为什么需要它：骨架流水线不写 Python 分片、不写 JSON，直接写 `_zh.txt`。
块号写错时 convert.py 不会报错（它只按已有的 @@B 解析），错位会一路带到 docx。
这个脚本把 `_zh.txt` 的块号与 `_layout.json` 的真实块序列逐个比对。

判读规则（与 cov.py 一致）：
  - **多余必须为 0** —— 大于 0 说明块号写错了（写到了不存在的块）。
  - **缺可以为非 0** —— 说明这份文档还没译完，继续写就行。
  - 两个都为 0，且图内也不缺 = 这份文档可以出图出文档了。

用法：
  python check_cov.py <doc> [<doc> ...]
  python check_cov.py --all            # 跑 docs.json 里的全部文档
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


def parse_zh(path):
    """返回 `_zh.txt` 里出现过的块号集合。

    注意：块头格式是 `@@B 12 p   # p45`——**块号后面跟着类型和注释**，
    不是只有块号。早期的 `^@@B\\s+(\\d+)\\s*$` 会一条都匹配不到，
    于是「多余 0 / 缺全部」看着像没开工。这里按「块号 + 任意尾随」解析。
    """
    keys = set()
    for raw in open(path, encoding='utf-8-sig').read().split('\n'):
        m = re.match(r'^@@B\s+(\d+)\b', raw.strip().lstrip('\ufeff'))
        if m:
            keys.add(int(m.group(1)))
    return keys


def parse_fig_zh(path):
    """返回 {(fig_key, block_id): 译文}，只收有内容的。"""
    key, tid, buf = None, None, []
    cur = {}

    def commit():
        if key and tid is not None:
            t = '\n'.join(buf).strip()
            if t:
                cur[(key, str(tid))] = t

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
        if tid is not None and s.startswith('ZH'):
            buf = [s[2:].strip()] if s[2:].strip() else []
            continue
        if tid is not None:
            buf.append(s)
    commit()
    return cur


def needs_translation(text):
    """判断一个图内文字组是否**应当**译成中文。

    判定必须与「渲染器实际会不会画中文」一致，否则会误报缺译：
      · 不含字母/汉字（纯数字、`</>`、``` ```` ）→ 渲染器 SKIP_SYMBOL，不译
      · 代码围栏或以 `{` 开头 → SKIP_CODE，不译
      · 长且含大量代码符号（diff/路径/花括号）→ SKIP_CODE，不译
    只有「会被渲染」的组才计入待译数。
    """
    s = str(text or '').strip()
    if not s:
        return False
    if not re.search(r'[A-Za-z\u4e00-\u9fff]', s):
        return False
    if re.match(r'^\s*(```|~~~)', s) or s.startswith('{'):
        return False
    strong = re.search(r'--git|@@|def \w+\(|\w+\.(py|js|ts|java|go|yaml|json)\b', s)
    if strong:
        sym = len(re.findall(r'[{}\[\]();=<>|]|(?:^|\s)--git|(?:^|\s)[-+@]{1,3}\s',
                             s, re.M))
        if sym > len(s) * 0.025:
            return False
    return True


def check(doc, verbose=True):
    lay_p = os.path.join(WORK, doc + '_layout.json')
    if not os.path.exists(lay_p):
        print('%-8s 缺 %s' % (doc, lay_p))
        return False
    lay = json.load(open(lay_p, encoding='utf-8'))['pages']
    total = sum(len(v) for v in lay.values())

    zh_p = os.path.join(WORK, doc + '_zh.txt')
    if not os.path.exists(zh_p):
        print('%-8s 缺 %s' % (doc, zh_p))
        return False
    have = parse_zh(zh_p)
    allk = set(range(total))
    extra = sorted(have - allk)
    miss = sorted(allk - have)

    # 图内待译项：两种来源都要认
    #   ① `_figtexts.json`（extract_fig_texts.py 产出，块式结构）
    #   ② `_layout.json` 里 figure 块的 `groups`/`blocks`（本项目直接解析进 layout）
    ft_p = os.path.join(WORK, doc + '_figtexts.json')
    need = set()
    if os.path.exists(ft_p):
        ft = json.load(open(ft_p, encoding='utf-8'))
        need = {(k, str(b['id'])) for k, v in ft.items()
                for b in v.get('blocks') or []
                if needs_translation(b.get('text') or b.get('en'))}
    else:
        for pn, blks in lay.items():
            fi = 0
            for b in blks:
                if b.get('type') != 'figure':
                    continue
                key = b.get('key') or ('p%s_f%d' % (pn, fi))
                fi += 1
                grp = b.get('groups') or b.get('blocks') or []
                for gi, g in enumerate(grp):
                    if needs_translation(g.get('en') or g.get('text')):
                        need.add((key, str(gi)))
    fmiss, fextra = [], []
    if need:
        got = set()
        tr_p = os.path.join(WORK, doc + '_figtrans.json')
        if os.path.exists(tr_p):
            try:
                tr = json.load(open(tr_p, encoding='utf-8'))
            except Exception:
                tr = {}
            got = {(k, str(i)) for k, v in tr.items()
                   for i, t in v.items() if str(t).strip()}
        elif os.path.exists(os.path.join(WORK, doc + '_figzh.txt')):
            got = set(parse_fig_zh(os.path.join(WORK, doc + '_figzh.txt')).keys())
        fmiss = sorted(need - got)
        fextra = sorted(got - need)

    # 「图内多余」只是提示，不算失败：译文里给了被判定为免译的组（纯符号、
    # 重复标签），渲染器会照常采用，不会报错。真正要清零的是「块号多余」。
    fextra_note = ''
    if fextra:
        fextra_note = '  图内多 %d（提示）' % len(fextra)

    ok = not extra and not miss and not fmiss
    print('%-8s 块 %3d  多余 %d  缺 %d   图内 %3d 条  缺 %d%s %s'
          % (doc, total, len(extra), len(miss), len(need),
             len(fmiss), fextra_note, 'OK' if ok else ''))
    if verbose:
        if extra:
            print('      多余块号:', extra[:20], '…' if len(extra) > 20 else '')
        if miss:
            print('      缺块号  :', miss[:20], '…' if len(miss) > 20 else '')
        if fmiss:
            print('      图内缺  :', fmiss[:12])
        if fextra:
            print('      图内多余:', fextra[:12],
                  '← 图 key 可能变了（解析规则改动后要核对 figtexts）')
    return ok


def all_docs():
    p = os.path.join(ROOT, 'docs.json')
    if os.path.exists(p):
        return [d['id'] for d in json.load(open(p, encoding='utf-8'))]
    conf = os.path.join(ROOT, 'book.json')
    if os.path.exists(conf):
        cfg = json.load(open(conf, encoding='utf-8'))
        if cfg.get('docs'):
            return [d['id'] for d in cfg['docs']]
    return []


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    docs = all_docs() if args[0] == '--all' else args
    if not docs:
        sys.exit('没有可检查的文档（缺 docs.json）')
    results = [(d, check(d)) for d in docs]
    bad = [d for d, ok in results if not ok]
    if bad:
        print('\n未通过：%s' % ', '.join(bad))
    else:
        print('\n全部 %d 份文档覆盖率 100%%，可以出文档。' % len(results))


if __name__ == '__main__':
    main()
