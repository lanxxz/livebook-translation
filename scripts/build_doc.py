# -*- coding: utf-8 -*-
"""单文档流水线：convert → 渲染图 → 出 docx → 体检。一条命令跑完一份文档。

用法：
    python build_doc.py <doc_id> [<doc_id> ...]

约定（与 slice_layout / mk_skeleton / convert 一致）：
    work/<doc>_layout.json     本档块序列
    work/<doc>_zh.txt          译文草稿（@@B n 逐块）
    work/<doc>_figskel.txt     图内待译骨架
    work/<doc>_figzh.txt       图内译文（@@FIG / @@T）
    figs/<doc>/                渲染出的图
    out/<doc>.docx             产物

文档元数据（标题/编号/类型）从 docs.json 或 book.json 的 docs 键读取。
"""
import json
import os
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def project_root():
    """定位项目根：含 book.json 或 docs.json 的目录。

    依次尝试：脚本所在目录向上 4 级 → 当前工作目录向上 4 级。
    这样脚本放在 <项目>/scripts/ 或直接放在技能目录里都能用。
    """
    def _up(start):
        d = os.path.abspath(start)
        for _ in range(4):
            if (os.path.exists(os.path.join(d, "book.json"))
                    or os.path.exists(os.path.join(d, "docs.json"))):
                return d
            d = os.path.dirname(d)
        return None

    for start in (os.path.dirname(os.path.abspath(__file__)), os.getcwd()):
        hit = _up(start)
        if hit:
            return hit
    # 兜底：脚本在 <项目>/scripts/ 里
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ROOT = project_root()
WORK = os.path.join(ROOT, 'work')
SDIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'out')


def sib(name):
    """同目录兄弟脚本的带引号路径（不依赖当前工作目录）。"""
    return '"%s"' % os.path.join(SDIR, name)


def run(cmd, quiet=False):
    # W13：BLAS 限单线程。否则 OpenBLAS 内存错误会让渲染子进程静默退出，
    # figs/<doc>/ 为空而 docx 照常生成，整章插图消失且 audit 看不出异常。
    env = dict(os.environ, PYTHONIOENCODING='utf-8',
               OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=env, cwd=ROOT)
    if r.returncode != 0 and not quiet:
        print('!! FAIL:', cmd)
        print((r.stdout or '')[-800:])
        print((r.stderr or '')[-800:])
    return (r.stdout or '') + (r.stderr or '')


def load_docs():
    p = os.path.join(ROOT, 'docs.json')
    if os.path.exists(p):
        return {d['id']: d for d in json.load(open(p, encoding='utf-8'))}
    conf = os.path.join(ROOT, 'book.json')
    if os.path.exists(conf):
        cfg = json.load(open(conf, encoding='utf-8'))
        if cfg.get('docs'):
            return {d['id']: d for d in cfg['docs']}
    sys.exit('缺少 docs.json（或在 book.json 里提供 docs 列表）')


def out_name(d):
    """输出文件名与页眉标签，由文档类型决定。"""
    kind = d.get('kind', 'ch')
    if kind == 'front':
        return '00_' + d['title'], ''
    if kind == 'apx':
        return f"{d['num']}_附录{d['num']}_{d['title']}", f"附录 {d['num']}　{d['title']}"
    num = int(d['num'])
    return (f'{num:02d}_第{num}章_{d["title"]}',
            f'第 {num} 章　{d["title"]}')


def one(doc, meta):
    py = sys.executable
    zh = os.path.join(WORK, doc + '_zh.txt')
    if not os.path.exists(zh):
        sys.exit(f'缺译文草稿 {zh}')

    print(run(f'"{py}" {sib("convert.py")} {doc}').strip())

    fzh = os.path.join(WORK, doc + '_figzh.txt')
    if not os.path.exists(fzh):
        open(fzh, 'w', encoding='utf-8').write('')

    # 图渲染
    figdir = os.path.join(ROOT, 'figs', doc)
    rep = run(f'"{py}" {sib("render_figs.py")} work/{doc}_layout.json '
              f'work/{doc}_figtexts.json work/{doc}_figtrans.json figs/{doc}')
    bad = [l for l in rep.split('\n') if 'OVERFLOW' in l or 'MISSING' in l]
    tail = [l for l in rep.split('\n') if l.startswith('合计')]
    print('图渲染:', tail[0] if tail else '（无图）')
    if bad:
        print('  !! 图内问题', len(bad))
        for b in bad[:5]:
            print('   ', b.strip())

    base, head = out_name(meta)
    docx = os.path.join(OUT, base + '.docx')
    print(run(f'"{py}" {sib("build_docx.py")} work/{doc}_trans.json '
              f'work/{doc}_figtexts.json work/{doc}_figtrans.json figs/{doc} '
              f'"{docx}" "{head}"').strip()[-120:])

    aud = run(f'"{py}" {sib("audit.py")} work/{doc}_layout.json '
              f'work/{doc}_trans.json "{docx}" figs/{doc}')
    keep = [l for l in aud.split('\n')
            if ('✓' in l or '✗' in l or '块序列' in l or '结论' in l
                or '漏译' in l or '中文' in l)]
    print('\n'.join(keep))


def main():
    if len(sys.argv) < 2:
        sys.exit('用法：python build_doc.py <doc_id> [<doc_id> ...]')
    docs = load_docs()
    for doc in sys.argv[1:]:
        if doc not in docs:
            sys.exit(f'未知文档 {doc}；可选：{", ".join(docs)}')
        one(doc, docs[doc])


if __name__ == '__main__':
    main()
