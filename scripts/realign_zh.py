# -*- coding: utf-8 -*-
"""块号错位后的译文抢救工具（骨架文本流水线专用）。

## 什么时候需要它

`_zh.txt` 的块号与 `_layout.json` 的真实块序列不再一一对应。典型成因：

1. **解析规则改过**（多识别出一种块类型，块数从 155 变成 156）→ 全书块号平移；
2. **手写时把一个块写成了另一种类型**（最常见：`figure` 写成 `p`）→ 该点之后
   所有块整体错位一格；
3. **漏写一个块头**（图注续行的小标题、`第 N 轮` 这类短 h3）→ 同上。

## 三条原则

1. **不要手工对块号**。155 块的文档，肉眼对齐必错；脚本按签名比对。
2. **先 dry-run 看对齐率**，再落地。对齐率 100% 才落；低于 100% 要先看差异块。
3. **落地前备份 `_zh.txt`**，落地后立刻跑 `check_zh.py` 复核。

## 三种模式

    # ① 诊断：只报告，不改文件
    python realign_zh.py ch02 --dry

    # ② 按块签名重对齐（解析变更后用）：把旧译文按「类型+正文首 20 字」匹配到新块号
    python realign_zh.py ch02 --by-signature

    # ③ 强制按骨架顺位重建（块号连续化；缺块用 --fill 补，多的块丢弃）
    python realign_zh.py ch09 --rebuild --fill work/ch09_fill.json

`--rebuild` 会以 `_skel.txt` 的块号与类型为准重写整个 `_zh.txt`：
  · 按块号取译文，取不到则按顺序兜底；
  · `--fill` 是 JSON `{"61": "文本", "67": "文本"}`，强制覆盖指定块；
  · 若某块既取不到也无 fill，留空并在报告里列出（code 块允许留空）。

用法示例（实测流程）：
    python realign_zh.py ch09 --dry                 # 看到 61/67/70/73 缺失
    python realign_zh.py ch09 --rebuild --fill f.json
    python check_zh.py ch09                         # 必须 OK
"""
import json
import os
import re
import shutil
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


WORK = os.path.join(project_root(), 'work')


def parse_blocks(path):
    """→ [{'num','type','body'}]，保持出现顺序。"""
    if not os.path.exists(path):
        return []
    text = open(path, encoding='utf-8-sig').read()
    out = []
    for chunk in re.split(r'(?m)^@@B\s+', text):
        if not chunk.strip():
            continue
        m = re.match(r'(\d+)[ \t]*([^\n#]*)\n?(.*)$', chunk, re.S)
        if not m:
            continue
        out.append({'num': int(m.group(1)),
                    'type': m.group(2).strip().split()[0] if m.group(2).strip() else '',
                    'decl': m.group(2).strip(),        # 保留完整声明（含 role= / key=）
                    'body': m.group(3).strip('\n')})
    return out


def signature(blk):
    """块签名：类型 + 正文前 24 个非空白字符。用于跨版本匹配同一块。"""
    body = re.sub(r'^\[[a-z]{1,4}\]\s*', '', blk['body'])
    body = re.sub(r'\s+', '', body)[:24]
    return '%s|%s' % (blk['type'], body)


def write_blocks(path, blocks):
    lines = []
    for b in blocks:
        decl = b.get('decl') or b['type']
        lines.append(('@@B %d %s' % (b['num'], decl)).rstrip())
        lines.append(b['body'].strip('\n'))
        lines.append('')
    open(path, 'w', encoding='utf-8').write('\n'.join(lines))


def main():
    if len(sys.argv) < 2 or sys.argv[1].startswith('-'):
        sys.exit(__doc__)
    doc = sys.argv[1]
    dry = '--dry' in sys.argv
    by_sig = '--by-signature' in sys.argv
    rebuild = '--rebuild' in sys.argv
    fill = {}
    if '--fill' in sys.argv:
        fill = json.load(open(sys.argv[sys.argv.index('--fill') + 1], encoding='utf-8'))

    zh_p = os.path.join(WORK, doc + '_zh.txt')
    sk_p = os.path.join(WORK, doc + '_skel.txt')
    if not os.path.exists(zh_p):
        sys.exit('缺 %s' % zh_p)

    skel = parse_blocks(sk_p)
    zh = parse_blocks(zh_p)
    print('%s: skel %d 块, zh %d 块' % (doc, len(skel), len(zh)))

    # ---- 诊断：逐位比较类型 ----
    # 只比「类型词」（panel / figure / p …），不比 role=、key= 这些声明细节。
    mis = []
    for i in range(min(len(skel), len(zh))):
        a, b = skel[i]['type'], zh[i]['type']
        if a == b:
            continue
        if a == 'heading' and b in ('h2', 'h3'):
            continue
        mis.append((i, skel[i]['num'], a, b))
    print('类型不匹配 %d 处' % len(mis))
    for i, n, a, b in mis[:15]:
        print('  位置 %3d 块 %3d: 骨架 %-9s 译文 %s' % (i, n, a, b))
    if len(mis) > 15:
        print('  …（还有 %d 处）' % (len(mis) - 15))

    # 块号重复检查
    nums = [b['num'] for b in zh]
    dup = sorted({n for n in nums if nums.count(n) > 1})
    if dup:
        print('块号重复:', dup)
    gap = [n for n in range(max(nums) + 1) if n not in set(nums)] if nums else []
    if gap:
        print('块号缺失:', gap[:20])

    if dry:
        return

    backup = zh_p.replace('.txt', '.bak.txt')
    if not os.path.exists(backup):
        shutil.copy2(zh_p, backup)
        print('已备份 →', os.path.basename(backup))

    if by_sig:
        # 用签名把旧译文映射到新骨架的块
        pool = {}
        for b in zh:
            pool.setdefault(signature(b), []).append(b)
        out, matched = [], 0
        for s in skel:
            cand = pool.get(signature(s))
            if cand:
                src = cand.pop(0)
                out.append({'num': s['num'], 'type': s['type'], 'body': src['body']})
                matched += 1
            else:
                out.append({'num': s['num'], 'type': s['type'], 'body': ''})
        write_blocks(zh_p, out)
        print('按签名重对齐：%d/%d 块匹配' % (matched, len(skel)))
        return

    if rebuild:
        # 两种错位，取块方式不同 —— 选错了会把内容串到别的块号上。
        #
        # ① 「块号对、但有块没写」（默认）：按块号取，缺的号留空。
        #    例：漏写块 73 → 73 空着，74 及以后仍在原位。这是最常见的情形。
        # ② 「块号本身错了」（--by-position）：按出现顺序取。
        #    例：多写了一个块头导致后续整体平移 → 位置才是真对应关系。
        #
        # 实测教训：漏写块时若按位置取，会把块 74 的正文塞进块 73，
        # 表面上「0 处不匹配」，实际从 73 起全部串位。
        by_pos = '--by-position' in sys.argv
        by_num = {}
        for b in zh:
            by_num.setdefault(b['num'], b)
        out, filled, empty = [], [], []
        for i, s in enumerate(skel):
            n = s['num']
            src = (zh[i] if i < len(zh) else None) if by_pos else by_num.get(n)
            body = src['body'].strip('\n') if src else ''
            if str(n) in fill and str(fill[str(n)]).strip():
                body = fill[str(n)]
                filled.append(n)
            if not body.strip() and s['type'] != 'code':
                empty.append(n)
            out.append({'num': n, 'type': s['type'], 'body': body})
        write_blocks(zh_p, out)
        print('按骨架重建（%s）：%d 块，fill 覆盖 %d 块 %s'
              % ('按位置' if by_pos else '按块号', len(out), len(filled), filled))
        if empty:
            print('仍为空（code 块除外必须补）：', empty)
            print('  → 若这些块本应有内容，说明块号本身错了，改用 --by-position 重试。')
        return

    print('未指定模式。用 --by-signature 或 --rebuild（或加 --dry 只看诊断）。')


if __name__ == '__main__':
    main()
