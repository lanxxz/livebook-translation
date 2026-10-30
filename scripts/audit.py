# -*- coding: utf-8 -*-
"""交付前体检：译文块 vs 原版面块的一致性、图片显示尺寸与有效 DPI。"""
import json, sys, re, zipfile
from docx import Document
from docx.oxml.ns import qn
from PIL import Image

EMU_PER_CM = 360000


def check_blocks(layout_p, trans_p):
    layout = json.load(open(layout_p, encoding='utf-8'))['pages']
    trans = json.load(open(trans_p, encoding='utf-8'))

    seq = []
    for pno in sorted(layout, key=int):
        for b in layout[pno]:
            t = b['type']
            if t == 'chapter_open':
                seq.append('chapter_open')
            elif t == 'heading':
                seq.append('h%d' % b['level'])
            elif t in ('list', 'numlist'):
                if seq and seq[-1] == t:
                    continue
                seq.append(t)
            else:
                seq.append(t)
    tseq = [('para' if b['type'] == 'p' else b['type']) for b in trans]
    # 合并连续同类（译文里一个 list 块对应原文多个 list 块）
    def collapse(s):
        out = []
        for x in s:
            if out and out[-1] == x and x in ('list', 'numlist', 'p'):
                # 连续 p 不合并（原文每段独立）
                if x != 'p':
                    continue
            out.append(x)
        return out
    t2 = collapse(tseq)
    print(f'原文块序列长度 {len(collapse(seq))}，译文块序列长度 {len(t2)}')
    if collapse(seq) == t2:
        print('✓ 块序列完全一致')
        return True
    # 打印差异
    a, b = collapse(seq), t2
    for i in range(max(len(a), len(b))):
        x = a[i] if i < len(a) else '-'
        y = b[i] if i < len(b) else '-'
        mark = '' if x == y else '   <<< 不一致'
        print(f'  {i:3d} 原文={x:12s} 译文={y:12s}{mark}')
    return False


def check_images(docx_p, figdir, trans_p):
    doc = Document(docx_p)
    z = zipfile.ZipFile(docx_p)
    media = sorted([n for n in z.namelist() if n.startswith('word/media/')])
    print(f'\n内嵌图片 {len(media)} 张')
    # 显示尺寸
    from docx.shared import Emu
    idx = 0
    for p in doc.paragraphs:
        for dr in p._p.findall('.//' + qn('w:drawing')):
            for ext in dr.findall('.//' + qn('wp:extent')):
                cx, cy = int(ext.get('cx')), int(ext.get('cy'))
                idx += 1
                print(f'  图{idx}: 显示 {cx/EMU_PER_CM:.2f} x {cy/EMU_PER_CM:.2f} cm'
                      f'{"  ⚠ 超版心" if cx/EMU_PER_CM > 16.3 else ""}')
    # 原始像素与有效 DPI
    print('\n图片清晰度（有效 DPI = 像素宽 / 显示宽度英寸）')
    trans = json.load(open(sys.argv[2], encoding='utf-8'))
    files = [b['key'] + '.png' for b in trans if b['type'] == 'figure']
    i = 0
    for p in doc.paragraphs:
        for dr in p._p.findall('.//' + qn('w:drawing')):
            if i >= len(files):
                break
            for ext in dr.findall('.//' + qn('wp:extent')):
                cx = int(ext.get('cx'))
                fp = __import__('os').path.join(figdir, files[i])
                with Image.open(fp) as im:
                    w, h = im.size
                dpi_eff = w / (cx / EMU_PER_CM / 2.54)
                flag = '  ⚠ 偏低' if dpi_eff < 150 else ''
                print(f'  {files[i]:14s} {w}x{h}px  → {dpi_eff:.0f} dpi{flag}')
                i += 1


if __name__ == '__main__':
    ok = check_blocks(sys.argv[1], sys.argv[2])
    check_images(sys.argv[3], sys.argv[4], sys.argv[2])
