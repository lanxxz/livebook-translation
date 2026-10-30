# -*- coding: utf-8 -*-
"""扫描成品 PDF 的空白页 / 近空白页，用于验证合并没有产生多余页。

判据：该页可提取正文字符 < 120，且不含位图。
（只留页码和页眉的页会命中；整页插图页因为含位图不会误报。）

用法：python find_blank.py out/pdf/全书.pdf
输出：总页数 + 每张可疑页的字符数与图形数
"""
import sys

import pymupdf


def main():
    path = sys.argv[1]
    doc = pymupdf.open(path)
    blanks = []
    for i, page in enumerate(doc, 1):
        txt = (page.get_text() or '').strip()
        imgs = len(page.get_images(full=True))
        if len(txt) < 120 and imgs == 0:
            blanks.append((i, len(txt), len(page.get_drawings())))
    print('总页数 %d，疑似空白/近空白页 %d 张' % (len(doc), len(blanks)))
    for i, n, d in blanks[:80]:
        print('   p%-4d 字符 %-4d 图形 %d' % (i, n, d))
    if not blanks:
        print('（无空白页，合并正常）')


if __name__ == '__main__':
    main()
