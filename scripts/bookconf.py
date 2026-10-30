# -*- coding: utf-8 -*-
"""统一配置读取。

优先级：环境变量 > 当前目录 book.json > 默认值。

book.json 示例：
{
  "pdf": "D:/books/my-book.pdf",
  "root": "D:/work/mybook",
  "book_title": "图解流处理系统",
  "cn_body": "宋体",
  "cn_head": "微软雅黑",
  "cn_hand": "楷体",
  "en_body": "Times New Roman",
  "en_head": "Segoe UI",
  "body_pt": 10.5,
  "margin_cm": 2.4,
  "text_w_cm": 16.2
}
"""
import json
import os

_DEF = {
    'pdf': '',
    'root': os.getcwd(),
    'book_title': 'Book',
    'cn_body': '宋体',
    'cn_head': '微软雅黑',
    'cn_hand': '楷体',
    'en_body': 'Times New Roman',
    'en_head': 'Segoe UI',
    'body_pt': 10.5,
    'margin_cm': 2.4,
    'text_w_cm': 16.2,
    'dpi_cap': 230,        # 有效 DPI 上限
    'zoom': 4.1667,        # PDF pt → px（300 DPI）
    'max_h_cm': 17.5,      # 单图最大显示高度
}

_cache = None


def _load():
    global _cache
    if _cache is not None:
        return _cache
    c = dict(_DEF)
    for name in ('book.json', os.path.join(os.getcwd(), 'book.json')):
        if os.path.exists(name):
            try:
                c.update(json.load(open(name, encoding='utf-8')))
            except Exception:
                pass
            break
    m = {
        'pdf': 'BOOK_PDF', 'root': 'BOOK_ROOT', 'book_title': 'BOOK_TITLE',
    }
    for k, env in m.items():
        if os.environ.get(env):
            c[k] = os.environ[env]
    if not c['pdf'] or not os.path.exists(c['pdf']):
        raise SystemExit(
            '未找到 PDF。请在工作目录放 book.json（含 "pdf" 字段），'
            '或设置环境变量 BOOK_PDF。')
    _cache = c
    return c


def cfg(key):
    return _load()[key]


def work(*parts):
    """work 子目录路径（解析结果、译文 JSON）"""
    return os.path.join(cfg('root'), 'work', *parts)


def figs(*parts):
    """插图目录路径"""
    return os.path.join(cfg('root'), 'figs', *parts)


def out(*parts):
    """交付物目录路径"""
    return os.path.join(cfg('root'), 'out', *parts)


def ensure_dirs():
    for p in (work(), figs(), out()):
        os.makedirs(p, exist_ok=True)
