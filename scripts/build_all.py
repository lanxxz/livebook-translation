# -*- coding: utf-8 -*-
"""批量构建：每章 docx → PDF，再合并成整本。

用法：
    python tools/build_all.py            # 全部章节
    python tools/build_all.py ch01 ch02  # 指定
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, WORK, load_docs  # noqa: E402

OUT = os.path.join(ROOT, 'out')
DOCX = os.path.join(OUT, '分册_docx')
PDF = os.path.join(OUT, '分册_pdf')
SOFFICE = r'C:/Program Files/LibreOffice/program/soffice.exe'

SKIP = set()


def out_name(d):
    num = d['num']
    if not num:
        return '00_%s' % d['title'], '氛围工程'
    return ('%02d_第%s章_%s' % (int(num), num, d['title']),
            '第 %s 章　%s' % (num, d['title']))


def main():
    docs = load_docs()
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    if args:
        docs = [d for d in docs if d['id'] in args]
    os.makedirs(PDF, exist_ok=True)
    env = dict(os.environ, PYTHONIOENCODING='utf-8',
               OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    made = []
    for d in docs:
        if d['id'] in SKIP:
            continue
        tp = os.path.join(WORK, d['id'] + '_trans.json')
        if not os.path.exists(tp):
            print('!! 跳过 %s：缺 trans.json' % d['id'])
            continue
        base, head = out_name(d)
        os.makedirs(DOCX, exist_ok=True)
        docx = os.path.join(DOCX, base + '.docx')
        r = subprocess.run(
            [sys.executable, os.path.join(ROOT, 'tools', 'build_docx.py'),
             d['id'], docx, head],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            env=env, cwd=ROOT)
        tail = (r.stdout or '').strip().split('\n')
        print('%-8s %s' % (d['id'], tail[-1] if tail else r.stderr[-200:]))
        if r.returncode != 0:
            print((r.stderr or '')[-500:])
            continue
        made.append(docx)
    print('\n生成 docx %d 份' % len(made))
    for docx in made:
        subprocess.run([SOFFICE, '--headless', '--convert-to', 'pdf',
                        '--outdir', PDF, docx],
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace')
    n = len([f for f in os.listdir(PDF) if f.endswith('.pdf')])
    print('PDF 共 %d 份' % n)


if __name__ == '__main__':
    main()
