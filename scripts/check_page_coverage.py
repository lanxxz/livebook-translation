# -*- coding: utf-8 -*-
"""审计原书页范围：找出 docs.json 没有覆盖、但实际有正文的页。

用法：
    python check_page_coverage.py <book.pdf> [docs.json]

为什么需要它：check_cov.py / check_zh.py 的“覆盖率 100%”只表示
**已解析的 layout 内部**块齐全，完全无法发现 docs.json 的 from/to 本身漏了一页。
本项目实测漏掉原书第 108 页（整页小结），两份闸门仍然全绿。

退出码：0 = 无缺口；1 = 有正文页未覆盖；2 = 用法/文件错误。
"""
import json
import os
import re
import sys

try:
    import pymupdf
except ImportError:
    sys.exit('需要 PyMuPDF: pip install pymupdf')


def load_docs(path):
    data = json.load(open(path, encoding='utf-8'))
    if isinstance(data, dict):
        data = data.get('docs') or []
    return data


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pdf_path = sys.argv[1]
    docs_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(pdf_path))), 'docs.json')
    if not os.path.exists(pdf_path) or not os.path.exists(docs_path):
        sys.exit(2)

    docs = load_docs(docs_path)
    covered = set()
    source_ranges = []
    for d in docs:
        # 只统计真正从原书取文的文档。术语索引/封面/译者说明是新建页，
        # 不能拿来“覆盖”原书正文页。
        if d.get('kind') in ('index', 'cover'):
            continue
        a, z = d.get('from') or 0, d.get('to') or 0
        if a and z and z >= a:
            covered.update(range(int(a), int(z) + 1))
            source_ranges.append((int(a), int(z)))

    doc = pymupdf.open(pdf_path)
    # 只审计正文范围。前置封面/目录、后置索引/广告通常被重建或有意省略，
    # 不应因未覆盖而报错。
    body_first = min((a for a, z in source_ranges), default=1)
    body_last = max((z for a, z in source_ranges), default=doc.page_count)
    missing = []
    outside = 0
    for i, page in enumerate(doc, 1):
        if i in covered:
            continue
        text = re.sub(r'\s+', ' ', page.get_text('text')).strip()
        if len(text) < 30:
            continue
        if not (body_first <= i <= body_last):
            outside += 1
            continue
        missing.append((i, len(text), text[:120]))

    print('原书页数 %d，docs.json 覆盖 %d 页，正文审计范围 p%d–p%d'
          % (doc.page_count, len(covered), body_first, body_last))
    if outside:
        print('范围外前置/后置有正文页 %d 页（封面/目录/索引/广告，可重建或省略）' % outside)
    if not missing:
        print('✓ 正文范围内未发现“有正文但未纳入范围”的页')
        return 0

    print('✗ 发现 %d 页有正文但未覆盖：' % len(missing))
    for pno, n, head in missing:
        print('  p%-4d %4d字  %s' % (pno, n, head))
    print('\n处理原则：')
    print('  · 正文页：补进对应 docs 条目的 from/to，再解析、翻译、重建。')
    print('  · 部分扉页：可作为 kind=part 的独立 1 页文档补入。')
    print('  · 原书索引：原页码已失效，建议改成中英术语索引，不要照搬。')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
