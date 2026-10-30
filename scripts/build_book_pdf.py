# -*- coding: utf-8 -*-
"""把分章 docx 拼成整本，并出 PDF（保真做法）。

为什么不用「docx 合并后转 PDF」：
  docxcompose 能合 docx，但 LibreOffice 转 PDF 时会丢掉跨页表头（tblHeader），
  页眉也容易串。**逐份转 PDF 再 pymupdf.insert_pdf 拼接**保真得多，
  还能顺手写书签。

用法：
    python build_book_pdf.py [--pdf-only] [--docx-only]

顺序与页眉标签来自 docs.json（或 book.json 的 docs 键），自动排序：
    front → ch01..chN → apA, apB
"""
import json
import os
import subprocess
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import pymupdf

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
OUT = os.path.join(ROOT, 'out')
PDFDIR = os.path.join(OUT, 'pdf')
SOFFICE = os.environ.get(
    'SOFFICE', r'C:\Program Files\LibreOffice\program\soffice.exe')

def book_title():
    conf = os.path.join(ROOT, 'book.json')
    if os.path.exists(conf):
        return json.load(open(conf, encoding='utf-8')).get(
            'book_title', '中文版')
    return '中文版'
CN_HEAD = '微软雅黑'
EN_HEAD = 'Segoe UI'
LIGHT = (0.5, 0.5, 0.5)


def load_docs():
    p = os.path.join(ROOT, 'docs.json')
    if os.path.exists(p):
        return json.load(open(p, encoding='utf-8'))
    conf = os.path.join(ROOT, 'book.json')
    if os.path.exists(conf):
        cfg = json.load(open(conf, encoding='utf-8'))
        if cfg.get('docs'):
            return cfg['docs']
    sys.exit('缺少 docs.json（或在 book.json 里提供 docs 列表）')


def out_name(d):
    kind = d.get('kind', 'ch')
    if kind == 'front':
        return '00_' + d['title'], ''
    if kind == 'apx':
        return (f"{d['num']}_附录{d['num']}_{d['title']}",
                f"附录 {d['num']}　{d['title']}")
    num = int(d['num'])
    return (f'{num:02d}_第{num}章_{d["title"]}',
            f'第 {num} 章　{d["title"]}')


def sort_docs(docs):
    def key(d):
        k = d.get('kind', 'ch')
        if k == 'front':
            return (0, 0)
        if k == 'apx':
            return (2, ord(str(d['num'])[0]))
        return (1, int(d['num']))
    return sorted(docs, key=key)


def to_pdf(docx_name, retries=4):
    """转一份 PDF，失败重试（LibreOffice 偶尔会因残留进程失败）。"""
    import time
    src = os.path.join(OUT, docx_name)
    dst = os.path.join(PDFDIR, os.path.splitext(docx_name)[0] + '.pdf')
    last = None
    for attempt in range(retries):
        if os.path.exists(dst):
            os.remove(dst)
        r = subprocess.run([SOFFICE, '--headless', '--norestore',
                            '--convert-to', 'pdf:writer_pdf_Export',
                            '--outdir', PDFDIR, src], capture_output=True)
        if r.returncode == 0 and os.path.exists(dst):
            return dst
        last = r
        time.sleep(2 + attempt * 2)
    sys.exit('转 PDF 失败：%s (%s)' % (
        docx_name, (last.stderr or b'').decode('utf-8', 'replace')[:200]))


def main():
    only_pdf = '--pdf-only' in sys.argv
    only_docx = '--docx-only' in sys.argv
    os.makedirs(PDFDIR, exist_ok=True)

    docs = sort_docs(load_docs())
    plan = []
    for d in docs:
        name, label = out_name(d)
        src = os.path.join(OUT, name + '.docx')
        if not os.path.exists(src):
            sys.exit(f'缺文件：{src}')
        plan.append((name, label))

    # ---- 先合一份 docx（可选）----
    if not only_pdf:
        from docx import Document
        from docx.enum.section import WD_SECTION
        from docx.oxml.ns import qn
        from docxcompose.composer import Composer
        import merge_book  # 同目录下的页眉重写工具

        master = Document(os.path.join(OUT, plan[0][0] + '.docx'))
        merge_book.set_header(master.sections[0], plan[0][1])
        comp = Composer(master)
        for name, label in plan[1:]:
            sub = Document(os.path.join(OUT, name + '.docx'))
            sec = comp.doc.add_section(WD_SECTION.NEW_PAGE)
            sec.header.is_linked_to_previous = False
            sec.footer.is_linked_to_previous = False
            comp.append(sub)
            merge_book.set_header(comp.doc.sections[-1], label)
            print('已并入', name)
        for sec in comp.doc.sections:
            for el in sec._sectPr.findall(qn('w:pgNumType')):
                sec._sectPr.remove(el)
        docx_out = os.path.join(OUT, book_title() + '.docx')
        comp.save(docx_out)
        print('已生成', docx_out, '%.1f MB' % (os.path.getsize(docx_out) / 1048576))

    if only_docx:
        return

    # ---- 逐份转 PDF 再拼接（保真）----
    book = pymupdf.open()
    toc, start = [], 0
    for name, label in plan:
        p = to_pdf(name + '.docx')
        with pymupdf.open(p) as sub:
            n = sub.page_count
            book.insert_pdf(sub)
        toc.append([1, label or name, start + 1])
        start += n
        print('并入', name, f'（{n} 页）')

    # 页码连续：盖掉各子 PDF 自带的页脚，重写成全书页码
    for i in range(book.page_count):
        pg = book[i]
        r = pg.rect
        shape = pg.new_shape()
        shape.draw_rect(pymupdf.Rect(0, r.height - 70, r.width, r.height))
        shape.finish(color=None, fill=(1, 1, 1))
        shape.commit()
        txt = str(i + 1)
        tw = pymupdf.get_text_length(txt, fontname='helv', fontsize=9)
        pg.insert_text((r.width / 2 - tw / 2, r.height - 30), txt,
                       fontname='helv', fontsize=9, color=LIGHT)

    book.set_toc([])          # 清掉子文档带过来的细碎书签
    book.set_toc(toc)
    target = os.path.join(PDFDIR, book_title() + '.pdf')
    book.save(target, garbage=4, deflate=True)
    print('已生成', target, '共', book.page_count, '页，书签', len(toc))


if __name__ == '__main__':
    main()
