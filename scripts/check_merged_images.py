# -*- coding: utf-8 -*-
"""检查合订 docx 的图片关系是否撞车 / 丢图。

用法：
    python check_merged_images.py <book.docx>

判据：
    inline_shapes 数 == 唯一 r:embed 数 == word/media 文件数

为什么需要它：图片数“看起来对”不代表每张图都对。本项目曾因同页多图共用
p{page}_f0 键，合订本 119 个 inline shape 只指向 98 个关系，同一张图重复三次，
而文件大小、页数、块序列全部正常。只数 inline_shapes 抓不到这种错。

退出码：0 = 通过；1 = rId 撞车/图片丢失；2 = 用法错误。
"""
import hashlib
import sys
import zipfile
from collections import Counter

from docx import Document
from docx.oxml.ns import qn


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]

    doc = Document(path)
    ids = []
    for p in doc.paragraphs:
        for blip in p._p.findall('.//' + qn('a:blip')):
            rid = blip.get(qn('r:embed'))
            if rid:
                ids.append(rid)
    # 图片也可能在表格单元格里
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for blip in p._p.findall('.//' + qn('a:blip')):
                        rid = blip.get(qn('r:embed'))
                        if rid:
                            ids.append(rid)

    z = zipfile.ZipFile(path)
    media = [n for n in z.namelist() if n.startswith('word/media/')]
    hashes = [hashlib.md5(z.read(n)).hexdigest() for n in media]
    dup = [(rid, n) for rid, n in Counter(ids).items() if n > 1]

    print('inline 图片引用: %d' % len(ids))
    print('唯一 r:embed  : %d' % len(set(ids)))
    print('media 文件     : %d（唯一内容 %d）' % (len(media), len(set(hashes))))
    if dup:
        print('✗ 有 %d 个 rId 被多张图共用：%s' % (len(dup), dup[:8]))
    if len(ids) != len(set(ids)):
        print('判读：rId 撞车。通常是同一页多张图共用了 p{page}_f0 键。')
        return 1
    if len(ids) != len(media):
        print('判读：图片引用数与 media 文件数不一致，检查是否有图片丢失。')
        return 1
    if len(media) != len(set(hashes)):
        print('提示：存在内容相同的 media 文件（可能原书重复图，需目视确认）。')
    print('✓ 图片引用与 media 文件一一对应')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
