#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""原书 / 译本页面对比：把两个 PDF 的指定页并排渲染成一张 PNG，供目视回归。

用法：
  python compare_pages.py <原书.pdf> <译本.pdf> <原书页码> <译本页码> [--dpi 150] [--out cmp.png]

页码从 1 开始。用途：重排版 / 改版式参数后，抽查「原书第 N 页 ↔ 译本第 M 页」
的版面是否对应（图位置、段落数、留白）。输出同时打印两页的文本量与图片数，
差异过大时先怀疑页码对应错了。
"""
import argparse

import pymupdf
from PIL import Image


def render(pdf_p, page_no, dpi):
    doc = pymupdf.open(pdf_p)
    if page_no < 1 or page_no > len(doc):
        raise SystemExit(f'!! {pdf_p} 共 {len(doc)} 页，请求第 {page_no} 页')
    page = doc[page_no - 1]
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    n_text = len(page.get_text())
    n_imgs = len(page.get_image_info())
    doc.close()
    return img, n_text, n_imgs


def main():
    ap = argparse.ArgumentParser(description='两个 PDF 页面并排渲染对比')
    ap.add_argument('orig', help='原书 PDF')
    ap.add_argument('trans', help='译本 PDF（或任意对比对象）')
    ap.add_argument('orig_page', type=int, help='原书页码（1 起）')
    ap.add_argument('trans_page', type=int, help='译本页码（1 起）')
    ap.add_argument('--dpi', type=int, default=150)
    ap.add_argument('--out', default=None, help='输出 PNG 路径')
    args = ap.parse_args()

    img_a, ta, ia = render(args.orig, args.orig_page, args.dpi)
    img_b, tb, ib = render(args.trans, args.trans_page, args.dpi)

    gap = 24
    canvas = Image.new('RGB', (img_a.width + gap + img_b.width,
                               max(img_a.height, img_b.height)), (210, 210, 210))
    canvas.paste(img_a, (0, 0))
    canvas.paste(img_b, (img_a.width + gap, 0))
    out = args.out or f'cmp_p{args.orig_page}_p{args.trans_page}.png'
    canvas.save(out)

    print(f'原书 p{args.orig_page}: 文本 {ta} 字符 / 图 {ia} 张')
    print(f'译本 p{args.trans_page}: 文本 {tb} 字符 / 图 {ib} 张')
    if abs(ta - tb) > 0.5 * max(ta, tb, 1):
        print('!! 两页文本量相差一倍以上，先确认页码对应是否正确')
    print('saved', out)


if __name__ == '__main__':
    main()
