# -*- coding: utf-8 -*-
"""把分章 docx 合并为整本书（每节独立页眉 + 页码连续）。

为什么不能直接用 docxcompose 一把拼：
  - append() 会把新内容并入「同一节」，页眉只有底板那一份，全书页眉都错。
  - 如果在 append 之后才 add_section，会多出一个空节 → 凭空多出空白页。
  - 每份子 docx 自带 <w:pgNumType start=1>，合并后每章页码都从 1 重排。

正确顺序只有一种：**先分节 → 再 append → 最后按 sections[-1] 设页眉**。

用法：
  python merge_book.py --order     # 只打印将要合并的清单与页眉标签
  python merge_book.py             # 合并

顺序与标签来自 docs.json（或 book.json 的 docs 键）：
  [{"id":"ch01","title":"本地 AI 入门","num":"1","kind":"ch","from":28,"to":46}, ...]
kind: front（前言，无页眉）/ ch（章）/ apx（附录）

输出：out/<book_title>.docx
"""
import json
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import docx
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from docxcompose.composer import Composer

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
CN_HEAD = '微软雅黑'
EN_HEAD = 'Segoe UI'
LIGHT = RGBColor(0x80, 0x80, 0x80)


def book_config():
    p = os.path.join(ROOT, 'book.json')
    if os.path.exists(p):
        return json.load(open(p, encoding='utf-8'))
    return {}


def load_docs(cfg):
    p = os.path.join(ROOT, 'docs.json')
    if os.path.exists(p):
        return json.load(open(p, encoding='utf-8'))
    if cfg.get('docs'):
        return cfg['docs']
    sys.exit('缺少 docs.json（或在 book.json 里提供 docs 列表）')


def out_name(d):
    kind = d.get('kind', 'ch')
    if kind == 'front':
        return '00_' + d['title']
    if kind == 'apx':
        return f"{d['num']}_附录{d['num']}_{d['title']}"
    num = int(d['num'])
    return f'{num:02d}_第{num}章_{d["title"]}'


def header_label(d):
    kind = d.get('kind', 'ch')
    if kind == 'front':
        return ''
    if kind == 'apx':
        return f"附录 {d['num']}　{d['title']}"
    return f"第 {int(d['num'])} 章　{d['title']}"


def sort_docs(docs):
    def key(d):
        k = d.get('kind', 'ch')
        if k == 'front':
            return (0, 0)
        if k == 'apx':
            return (2, ord(str(d['num'])[0]))
        return (1, int(d['num']))
    return sorted(docs, key=key)


def set_header(section, label, book_title=''):
    """给一节写入独立页眉（右侧小字 + 下细线）与居中 PAGE 页脚。"""
    section.header.is_linked_to_previous = False
    section.footer.is_linked_to_previous = False

    hp = section.header.paragraphs[0]
    for r in list(hp.runs):
        r._element.getparent().remove(r._element)
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if label:
        text = f'{book_title}　|　{label}' if book_title else label
        run = hp.add_run(text)
        run.font.size = Pt(8.5)
        run.font.name = EN_HEAD
        run.font.color.rgb = LIGHT
        rPr = run._element.get_or_add_rPr()
        rFonts = rPr.find(qn('w:rFonts'))
        if rFonts is None:
            rFonts = OxmlElement('w:rFonts')
            rPr.append(rFonts)
        rFonts.set(qn('w:eastAsia'), CN_HEAD)
        rFonts.set(qn('w:ascii'), EN_HEAD)
        rFonts.set(qn('w:hAnsi'), EN_HEAD)

        pPr = hp._p.get_or_add_pPr()
        for el in pPr.findall(qn('w:pBdr')):
            pPr.remove(el)
        pbdr = OxmlElement('w:pBdr')
        bottom = OxmlElement('w:bottom')
        bottom.set(qn('w:val'), 'single')
        bottom.set(qn('w:sz'), '4')
        bottom.set(qn('w:space'), '1')
        bottom.set(qn('w:color'), 'CCCCCC')
        pbdr.append(bottom)
        pPr.append(pbdr)

    fp = section.footer.paragraphs[0]
    for r in list(fp.runs):
        r._element.getparent().remove(r._element)
    for el in list(fp._p):
        if el.tag == qn('w:fldSimple'):
            fp._p.remove(el)
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fld = OxmlElement('w:fldSimple')
    fld.set(qn('w:instr'), 'PAGE')
    run = OxmlElement('w:r')
    rPr2 = OxmlElement('w:rPr')
    sz = OxmlElement('w:sz')
    sz.set(qn('w:val'), '18')
    rPr2.append(sz)
    run.append(rPr2)
    t = OxmlElement('w:t')
    t.text = '1'
    run.append(t)
    fld.append(run)
    fp._p.append(fld)


def main():
    cfg = book_config()
    book_title = cfg.get('book_title', '中文版')
    docs = sort_docs(load_docs(cfg))

    plan = []
    for d in docs:
        name = out_name(d)
        src = os.path.join(OUT, name + '.docx')
        if not os.path.exists(src):
            sys.exit(f'缺文件：{src}')
        plan.append((src, header_label(d)))

    if '--order' in sys.argv:
        for src, lab in plan:
            print('%-56s %s' % (os.path.basename(src), lab or '(无页眉)'))
        return

    base = docx.Document(plan[0][0])
    set_header(base.sections[0], plan[0][1], book_title)
    comp = Composer(base)
    for src, label in plan[1:]:
        sub = docx.Document(src)
        sec = comp.doc.add_section(WD_SECTION.NEW_PAGE)
        sec.header.is_linked_to_previous = False
        sec.footer.is_linked_to_previous = False
        comp.append(sub)
        # append 之后新节在末尾，此时才写页眉
        set_header(comp.doc.sections[-1], label, book_title)
        print('  +', os.path.basename(src), '→', label or '(无页眉)')

    # 页码连续：清掉各节自己的起始页码
    for sec in comp.doc.sections:
        for el in sec._sectPr.findall(qn('w:pgNumType')):
            sec._sectPr.remove(el)

    target = os.path.join(OUT, book_title + '.docx')
    comp.save(target)
    print('合并 %d 份 →' % len(plan), target,
          '%.1f MB' % (os.path.getsize(target) / 1048576))


if __name__ == '__main__':
    main()
