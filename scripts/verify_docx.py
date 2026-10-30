# -*- coding: utf-8 -*-
"""校验生成的 docx：大纲层级、图片数与顺序、表格、段落完整性。"""
import sys, re, zipfile
from docx import Document
from docx.oxml.ns import qn


def para_text(p):
    return re.sub(r'\s+', ' ', p.text).strip()


def has_pic(p):
    return bool(p._p.findall('.//' + qn('w:drawing')))


def main(path):
    doc = Document(path)
    z = zipfile.ZipFile(path)
    media = [n for n in z.namelist() if n.startswith('word/media/')]
    print(f'文件: {path}')
    print(f'段落数: {len(doc.paragraphs)}   表格数: {len(doc.tables)}   内嵌图片: {len(media)}')
    print('-' * 78)
    pics = 0
    for i, p in enumerate(doc.paragraphs):
        t = para_text(p)
        st = p.style.name
        tag = ''
        if has_pic(p):
            pics += 1
            tag = f'[IMG#{pics}]'
        if st.startswith('Heading'):
            print(f'{i:4d} {st:12s} {tag} {t[:60]}')
        elif tag:
            print(f'{i:4d} {"(pic)":12s} {tag}')
        elif t:
            print(f'{i:4d} {"":12s}     {t[:70]}')
    print('-' * 78)
    print('图片段落数:', pics)
    for ti, tb in enumerate(doc.tables):
        print(f'表{ti+1}: {len(tb.rows)} 行 x {len(tb.columns)} 列 | 表头: '
              + ' / '.join(c.text.strip()[:12] for c in tb.rows[0].cells))


if __name__ == '__main__':
    main(sys.argv[1])
