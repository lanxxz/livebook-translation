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
  "text_w_cm": 16.2,
  "font_cn": "",
  "font_cn_bold": "",
  "font_en": "",
  "font_en_bold": ""
}

font_* 为图内渲染用的字体**文件路径**（如 "C:/Windows/Fonts/msyh.ttc"）；
留空 = 按 font_file() 候选表自动探测（Windows / Linux / macOS 常见路径）。
"""
import json
import os
import sys

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
    # 图内渲染字体文件路径；空串 = 按 _FONT_CANDIDATES 自动探测
    'font_cn': '',
    'font_cn_bold': '',
    'font_en': '',
    'font_en_bold': '',
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
                # utf-8-sig：兼容 Windows 记事本保存的带 BOM 文件
                c.update(json.load(open(name, encoding='utf-8-sig')))
            except Exception as e:
                print(f'!! book.json 读取失败，按默认值继续: {e}', file=sys.stderr)
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


_FONT_CANDIDATES = {
    'font_cn': (
        r'C:\Windows\Fonts\simkai.ttf',
        r'C:\Windows\Fonts\msyh.ttc',
        r'C:\Windows\Fonts\simsun.ttc',
        r'C:\Windows\Fonts\SourceHanSansSC-Regular.otf',
        r'C:\Windows\Fonts\NotoSansCJKsc-Regular.otf',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        '/System/Library/Fonts/PingFang.ttc',
    ),
    'font_cn_bold': (
        r'C:\Windows\Fonts\simhei.ttf',
        r'C:\Windows\Fonts\msyhbd.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
        '/System/Library/Fonts/PingFang.ttc',
    ),
    'font_en': (
        r'C:\Windows\Fonts\arial.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
    ),
    'font_en_bold': (
        r'C:\Windows\Fonts\arialbd.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
    ),
}


def _scan_font_dirs():
    """字体目录兜底扫描（带 ~/.fonts 等自定义安装位置）。"""
    keys = ('YaHei', 'NotoSansCJK', 'SourceHanSans', 'WenQuanYi', 'uming', 'ukai')
    for d in ('/usr/share/fonts', '/usr/local/share/fonts',
              '/System/Library/Fonts',
              os.path.expanduser('~/.fonts'),
              os.path.expanduser('~/.local/share/fonts')):
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                if any(k in f for k in keys):
                    return os.path.join(root, f)
    return None


def detect_font(key):
    """只按候选表探测字体，**不读 book.json**。

    供 check_env.py 等轻量场景复用，避免候选表在两处各维护一份。
    返回路径或 None。
    """
    for cand in _FONT_CANDIDATES.get(key, ()):
        if os.path.exists(cand):
            return cand
    if key.startswith('font_cn'):
        return _scan_font_dirs()
    return None


def font_file(key):
    """字体文件路径。book.json 里对应 key 非空则优先，否则按候选表探测。

    可用 key：font_cn / font_cn_bold / font_en / font_en_bold。
    配置了但路径不存在时报错退出（不静默回退，避免渲染用错字体）。
    """
    p = str(_load().get(key) or '').strip()
    if p:
        if not os.path.exists(p):
            raise SystemExit(f'book.json 配置的字体路径 {key}={p} 不存在')
        return p
    hit = detect_font(key)
    if hit:
        return hit
    raise SystemExit(
        f'未找到 {key} 字体文件。请在 book.json 配置 "{key}" 字段，'
        f'例如 "font_cn": "C:/Windows/Fonts/msyh.ttc"')


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
