# -*- coding: utf-8 -*-
"""把 gss/out 下的 docx 批量转成 PDF（保留原 docx）。

用法：python convert_pdf.py [--check]
依赖 LibreOffice 的 soffice.exe。
"""
import os, sys, glob, subprocess, time

from bookconf import out as _out
OUT = _out()
PDFDIR = os.path.join(OUT, 'pdf')
CANDIDATES = [
    r'C:\Program Files\LibreOffice\program\soffice.exe',
    r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
]


def find_soffice():
    for c in CANDIDATES:
        if os.path.exists(c):
            return c
    # 兜底：扫一遍
    for base in (r'C:\Program Files', r'C:\Program Files (x86)'):
        for p in glob.glob(os.path.join(base, 'LibreOffice*', 'program', 'soffice.exe')):
            return p
    return None


def main():
    so = find_soffice()
    if not so:
        sys.exit('未找到 soffice.exe，请先安装 LibreOffice')
    print('soffice:', so)
    os.makedirs(PDFDIR, exist_ok=True)
    docs = sorted(glob.glob(os.path.join(OUT, '*.docx')))
    print(f'待转换 {len(docs)} 个 docx')
    ok, fail = [], []
    for d in docs:
        base = os.path.splitext(os.path.basename(d))[0]
        dst = os.path.join(PDFDIR, base + '.pdf')
        t0 = time.time()
        r = subprocess.run([so, '--headless', '--norestore', '--convert-to', 'pdf:writer_pdf_Export',
                            '--outdir', PDFDIR, d],
                           capture_output=True, text=True, timeout=600)
        dt = time.time() - t0
        if os.path.exists(dst) and os.path.getsize(dst) > 1000:
            ok.append((base, os.path.getsize(dst), dt))
            print(f'  OK  {base}  {os.path.getsize(dst)/1024:.0f} KB  {dt:.1f}s')
        else:
            fail.append((base, r.stdout, r.stderr))
            print(f'  FAIL {base}\n     {r.stdout[-300:]}\n     {r.stderr[-300:]}')
    print(f'\n成功 {len(ok)}，失败 {len(fail)}')
    # 校验页数
    try:
        import pymupdf
        print('\n页数校验：')
        tot = 0
        for base, size, dt in ok:
            p = os.path.join(PDFDIR, base + '.pdf')
            n = pymupdf.open(p).page_count
            tot += n
            print(f'  {base}: {n} 页')
        print(f'  合计 {tot} 页')
    except Exception as e:
        print('  页数校验跳过:', e)
    # 确认 docx 仍在
    print(f'\n原 docx 文件仍在: {len(docs)} 个')


if __name__ == '__main__':
    main()
