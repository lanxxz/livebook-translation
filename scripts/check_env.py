#!/usr/bin/env python3
"""环境自检：python scripts/check_env.py

检查技能脚本所需的 Python 库、LibreOffice 与中文字体，输出 PASS/WARN/FAIL。
FAIL = 核心流程跑不了；WARN = 只影响部分流程（见具体提示）。
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bookconf import detect_font  # noqa: E402  候选表单一来源，避免两处维护

fails = []
warns = []


def check_import(mod, pip_name, required=True, note=''):
    try:
        __import__(mod)
        print(f'[PASS] {pip_name}')
    except ImportError:
        tag = 'FAIL' if required else 'WARN'
        print(f'[{tag}] {pip_name} 未安装（pip install {pip_name}）{note}')
        (fails if required else warns).append(pip_name)


def find_soffice():
    p = shutil.which('soffice') or shutil.which('libreoffice')
    if p:
        return p
    if os.name == 'nt':
        for cand in (r'C:\Program Files\LibreOffice\program\soffice.exe',
                     r'C:\Program Files (x86)\LibreOffice\program\soffice.exe'):
            if os.path.exists(cand):
                return cand
    return None


def main():
    print(f'Python {sys.version.split()[0]}  ({sys.executable})')
    if sys.version_info < (3, 9):
        fails.append('python>=3.9')
        print('[FAIL] Python 版本过低，需要 >= 3.9')

    check_import('pymupdf', 'pymupdf')
    check_import('docx', 'python-docx')
    check_import('docxcompose', 'docxcompose')
    check_import('PIL', 'Pillow')
    check_import('numpy', 'numpy', required=False, note='# 栅格图流程需要')
    check_import('scipy', 'scipy', required=False, note='# 栅格图流程需要')
    check_import('easyocr', 'easyocr', required=False, note='# 栅格 OCR 需要；首次运行下载模型')
    check_import('jieba', 'jieba', required=False, note='# 缺省时图内断行退回按字切')

    soffice = find_soffice()
    if soffice:
        print(f'[PASS] LibreOffice: {soffice}')
    else:
        warns.append('libreoffice')
        print('[WARN] 未找到 LibreOffice（soffice）：convert_pdf.py 无法 docx→PDF')

    font = detect_font('font_cn') or detect_font('font_cn_bold')
    if font:
        print(f'[PASS] 中文字体: {os.path.basename(font)}')
    else:
        warns.append('cjk-font')
        print('[WARN] 未找到常见中文字体（微软雅黑 / 思源黑体 / Noto CJK）；'
              '此时必须在 book.json 配置 "font_cn" 指向可用字体文件，否则图内渲染会报错')

    # 若当前目录有 book.json，顺带核对显式配置的字体路径
    conf = os.path.join(os.getcwd(), 'book.json')
    if os.path.exists(conf):
        try:
            c = json.load(open(conf, encoding='utf-8-sig'))
        except Exception as e:
            warns.append('book.json')
            print(f'[WARN] book.json 解析失败: {e}')
            c = {}
        for k in ('font_cn', 'font_cn_bold', 'font_en', 'font_en_bold'):
            v = str(c.get(k) or '').strip()
            if not v:
                continue
            if os.path.exists(v):
                print(f'[PASS] book.json {k}: {v}')
            else:
                fails.append(k)
                print(f'[FAIL] book.json {k} 指向的文件不存在: {v}')

    print()
    if fails:
        print(f'结果: FAIL（{len(fails)} 项核心缺失: {", ".join(fails)}）')
        return 1
    if warns:
        print(f'结果: 核心就绪，{len(warns)} 项警告（{", ".join(warns)}）')
    else:
        print('结果: 全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
