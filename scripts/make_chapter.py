# -*- coding: utf-8 -*-
"""单章流水线驱动。

用法：
  python make_chapter.py prep  <N> <起页> <止页>      解析 + 提取图内文字 + dump
  python make_chapter.py build <N> <起页> <止页>      渲染图 + 生成 docx + 体检
  python make_chapter.py check <N>                    只跑体检

约定文件名：gss/work/ch{N}_layout.json / ch{N}_figtexts.json / ch{N}_figtrans.json
            gss/work/ch{N}_trans.json（正文译文，需人工准备）
"""
import os, sys, json, subprocess, glob

from bookconf import cfg, work, figs, out
ROOT = cfg('root')
BASE = ROOT + r'\gss'
# 用「当前解释器」而非某个 Agent 的内置 Python；需要指定时可设 BOOK_PYTHON
PY = os.environ.get('BOOK_PYTHON') or sys.executable
WORK = os.path.join(BASE, 'work')
OUT = os.path.join(BASE, 'out')


def p(*a):
    subprocess.run([PY] + list(a), check=True, cwd=ROOT)


def paths(n):
    return dict(
        layout=os.path.join(WORK, f'ch{n}_layout.json'),
        figtexts=os.path.join(WORK, f'ch{n}_figtexts.json'),
        figtrans=os.path.join(WORK, f'ch{n}_figtrans.json'),
        trans=os.path.join(WORK, f'ch{n}_trans.json'),
        figs=os.path.join(BASE, 'figs', f'ch{n:02d}'),
        dump=os.path.join(WORK, f'ch{n}_dump.txt'),
    )


def clean_stale_png(figdir, figtexts_p):
    if not os.path.isdir(figdir):
        return
    keep = set(k + '.png' for k in json.load(open(figtexts_p, encoding='utf-8')))
    removed = []
    for f in os.listdir(figdir):
        if f.endswith('.png') and f not in keep:
            os.remove(os.path.join(figdir, f))
            removed.append(f)
    if removed:
        print(f'清理过期图 {len(removed)} 张: {removed}')


def cmd_prep(n, a, b):
    P = paths(n)
    print('【1/3】解析版面')
    p('gss/work/parse_layout.py', str(a), str(b), P['layout'])
    print('【2/3】导出可读 dump')
    with open(P['dump'], 'w', encoding='utf-8') as fh:
        subprocess.run([PY, 'gss/work/dump_layout.py', P['layout']],
                       stdout=fh, check=True, cwd=ROOT)
    print(f'      → {P["dump"]}')
    print('【3/3】提取图内文字')
    p('gss/work/extract_fig_texts.py', P['layout'], P['figtexts'])
    # 导出待译清单
    d = json.load(open(P['figtexts'], encoding='utf-8'))
    lines = []
    for k, v in d.items():
        lines.append(f'### {k}  bbox={v["bbox"]}')
        for bl in v['blocks']:
            flag = ' [R]' if bl['rotated'] else ''
            lines.append(f'  #{bl["id"]} sz={bl["size"]}{flag} :: {bl["en"]}')
    txt = os.path.join(WORK, f'ch{n}_figtexts.txt')
    open(txt, 'w', encoding='utf-8').write('\n'.join(lines))
    print(f'      → {txt}（待译清单）')
    print('\n下一步：写 ch{n}_figtrans.json 与 ch{N}_trans.json，然后 build'.replace('{n}', str(n)).replace('{N}', str(n)))


def cmd_build(n, a, b):
    P = paths(n)
    if not os.path.exists(P['figtrans']):
        sys.exit(f'缺少 {P["figtrans"]}')
    if not os.path.exists(P['trans']):
        sys.exit(f'缺少 {P["trans"]}')
    os.makedirs(P['figs'], exist_ok=True)
    clean_stale_png(P['figs'], P['figtexts'])
    print('【1/3】渲染图块')
    r = subprocess.run([PY, 'gss/work/render_figs.py', P['layout'], P['figtexts'],
                        P['figtrans'], P['figs']], cwd=ROOT, capture_output=True, text=True)
    print(r.stdout[-3000:] if r.stdout else '')
    if r.returncode != 0:
        print(r.stderr[-2000:])
        sys.exit('渲染失败')
    # 标题与文件名
    blocks = json.load(open(P['trans'], encoding='utf-8'))
    ch = blocks[0]
    title = ch.get('title', f'第{n}章')
    safe = title.replace('/', '·').replace('\\', '·').replace(':', '：')
    docx = os.path.join(OUT, f'{n:02d}_第{n}章_{safe}.docx')
    label = f'第 {n} 章　{title}'
    print('【2/3】生成 docx')
    p('gss/work/build_docx.py', P['trans'], P['figtexts'], P['figtrans'], P['figs'], docx, label)
    print('【3/3】体检')
    r = subprocess.run([PY, 'gss/work/audit.py', P['layout'], P['trans'], docx, P['figs']],
                       cwd=ROOT, capture_output=True, text=True)
    out = r.stdout
    print(out)
    bad = [l for l in out.splitlines() if '⚠' in l or '不一致' in l and '完全一致' not in l]
    print('\n=== 结论 ===')
    print('块序列：', '✓' if '完全一致' in out else '✗ 不一致')
    print('DPI 警告：', '无' if not bad else f'{len(bad)} 处')
    for l in bad[:8]:
        print('  ', l)


def cmd_check(n):
    P = paths(n)
    cand = sorted(glob.glob(os.path.join(OUT, f'{n:02d}_*.docx')))
    if not cand:
        sys.exit('没找到 docx')
    p('gss/work/audit.py', P['layout'], P['trans'], cand[-1], P['figs'])


if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'prep':
        cmd_prep(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
    elif mode == 'build':
        cmd_build(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
    elif mode == 'check':
        cmd_check(int(sys.argv[2]))
    else:
        sys.exit(__doc__)
