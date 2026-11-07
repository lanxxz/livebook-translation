# -*- coding: utf-8 -*-
"""图块渲染 + 图内文字中文化。

用法：python render_figs.py <layout.json> <figtexts.json> <trans.json> <outdir>
trans.json 结构：{"p32_f0": {"0": "中文译文", "1": "中文\n第二行"}}

排版原则（都是实测踩坑得来的，改动前先读 references/pitfalls.md 的 F 组）：
1. 断行单位是"词"，不是"字"。中文按词切（jieba 可用则用），英文按空格；
   绝不做"按字均衡"——那会把「提示词」切成「提示/词」。
2. 字号从原文字号起、按需收缩；不强制放大到某个最小字号。
   原书图内字号常只有 6~7pt，硬推到 7.5pt 会把标签挤爆方框。
3. 溢出必须被检测：渲染后比对"最宽一行 vs 方框宽度"，超阈值标 OVERFLOW。
4. 竖排只在译文很短（≤2 字）且框明显窄高时使用。
"""
import json, sys, os, re
import pymupdf
from PIL import Image, ImageDraw, ImageFont

from bookconf import cfg, font_file
PDF = cfg('pdf')
# 字体文件路径：book.json 的 font_cn / font_cn_bold / font_en / font_en_bold
# 字段优先；未配置时 bookconf.font_file 自动探测 Win/Linux/macOS 常见路径。
FONT_CN = font_file('font_cn')
FONT_CN_B = font_file('font_cn_bold')
FONT_EN = font_file('font_en')
FONT_EN_B = font_file('font_en_bold')
DPI = 300
ZOOM = DPI / 72.0
INK = (34, 34, 34)

# 字号硬下限（pt）：只防"小到不可读"，不作为强制放大目标
MIN_PT_HARD = 4.6
# 译文最宽一行超过方框多少即判为溢出
OVERFLOW_TOL = 1.04


def measure(txt, font):
    return font.getlength(txt) if hasattr(font, 'getlength') else font.getbbox(txt)[2]


HEAD_FORBID = set('。，、；：！？）》」』”’%·…')

# ---------------------------------------------------------------- 词级断行

# 必须整体不拆的技术术语（图内标签里常见的复合词）。可按书扩充。
PROTECTED_TERMS = (
    '提示词模板', '提示词', '模型数据', '向量库', '会话记忆', '聊天历史',
    '检索增强生成', '模型上下文协议', '工具调用', '内容审核', '情感分析',
    '智能体', '评估器', '生成结果', '嵌入模型', '响应格式',
    '服务端', '客户端', '本地资源', '远程资源', '并行化', '聚合器',
)


def _protect_terms(txt):
    """把受保护的术语切成独立 token，避免被分词器拆开。"""
    terms = sorted(PROTECTED_TERMS, key=len, reverse=True)
    out = []
    i = 0
    while i < len(txt):
        hit = None
        for t in terms:
            if txt.startswith(t, i):
                hit = t
                break
        if hit:
            out.append(hit)
            i += len(hit)
        else:
            out.append(txt[i])
            i += 1
    return out


def _jieba_words(text):
    try:
        import jieba
        return [w for w in jieba.cut(text, cut_all=False) if w] or [text]
    except Exception:
        return [text]


def _tokenize_cn(para):
    """中文按词切：先保术语，余下交给 jieba。"""
    pieces = _protect_terms(para)
    out, run = [], ''
    for pc in pieces:
        if len(pc) > 1 and pc in PROTECTED_TERMS:
            if run:
                out.extend(_jieba_words(run))
                run = ''
            out.append(pc)
        elif len(pc) == 1 and ord(pc) > 127:
            run += pc
        else:
            if run:
                out.extend(_jieba_words(run))
                run = ''
            out.append(pc)
    if run:
        out.extend(_jieba_words(run))
    return out


def _split_term(tok):
    """超宽术语按子术语拆（提示词模板 → 提示词 / 模板）。"""
    if tok not in PROTECTED_TERMS:
        return [tok]
    terms = sorted(PROTECTED_TERMS, key=len, reverse=True)
    out, i = [], 0
    while i < len(tok):
        hit = None
        for t in terms:
            if len(t) > 1 and tok.startswith(t, i) and t != tok:
                hit = t
                break
        if hit:
            out.append(hit)
            i += len(hit)
        else:
            out.append(tok[i])
            i += 1
    merged = []
    for piece in out:
        if len(piece) == 1 and merged and len(merged[-1]) == 1:
            merged[-1] += piece
        else:
            merged.append(piece)
    return merged if len(merged) > 1 else [tok]


def _split_ascii(seg):
    return [t for t in re.split(r'(\s+)', seg) if t]


def _greedy(txt, font, maxw):
    """按词贪心断行；只在单词本身超宽时才拆字。"""
    out = []
    for para in txt.split('\n'):
        if not para.strip():
            out.append('')
            continue
        tokens = []
        for chunk in re.findall(r'[\x00-\x7f]+|[^\x00-\x7f]+', para):
            if all(ord(c) < 128 for c in chunk):
                tokens.extend(_split_ascii(chunk))
            else:
                tokens.extend(_tokenize_cn(chunk))
        cur = ''
        for tk in tokens:
            cand = cur + tk
            if measure(cand, font) <= maxw or not cur.strip():
                if not cur.strip() and measure(tk, font) > maxw:
                    subs = _split_term(tk)
                    if len(subs) > 1:
                        for sub in subs:
                            if cur and measure(cur + sub, font) > maxw:
                                out.append(cur)
                                cur = sub
                            else:
                                cur += sub
                    else:
                        for ch in tk:
                            if cur and measure(cur + ch, font) > maxw:
                                out.append(cur)
                                cur = ch
                            else:
                                cur += ch
                else:
                    cur = cand
            else:
                out.append(cur.rstrip())
                cur = tk.lstrip() if tk.strip() else ''
        out.append(cur.rstrip())
    return [l for l in out if l != ''] or ['']


def _fix_head_punct(lines):
    """避免标点出现在行首：把上一行末字挪下来。"""
    for i in range(1, len(lines)):
        while lines[i] and lines[i][0] in HEAD_FORBID and len(lines[i - 1]) > 1:
            lines[i] = lines[i - 1][-1] + lines[i]
            lines[i - 1] = lines[i - 1][:-1]
    return lines


def wrap_by_width(txt, font, maxw):
    """按词断行（不做按字均衡，避免把词切碎）。"""
    return _fix_head_punct(_greedy(txt, font, maxw))


def pick_font(txt, bold=False):
    ascii_only = all(ord(ch) < 128 for ch in txt)
    if ascii_only:
        return FONT_EN_B if bold else FONT_EN
    return FONT_CN_B if bold else FONT_CN


def fit_text(txt, bbox_w, bbox_h, size_cap_px, bold=False, max_lines=99,
             zoom=1.0, hard_w=None):
    """在 bbox 内选字号与断行方案。

    hard_w：文字必须落进的真实宽度（不含允许的外扩）。缺省等于 bbox_w。
    优先保证：最宽一行放得进 hard_w；其次行数不超过 max_lines。
    """
    if hard_w is None:
        hard_w = bbox_w
    path = pick_font(txt, bold)
    lo = int(MIN_PT_HARD * zoom)
    cap = max(size_cap_px, lo)
    limit = min(bbox_w, hard_w)

    def attempt(fs, maxh=None):
        f = ImageFont.truetype(path, fs)
        lines = wrap_by_width(txt, f, limit)
        widest = max((measure(l, f) for l in lines), default=0)
        ok = widest <= limit * 1.001 and len(lines) <= max_lines
        if maxh is not None and len(lines) * fs * 1.15 > maxh:
            ok = False                    # 高度也要放得下（中文比英文占高）
        return f, lines, widest, ok

    best = None
    one_line = txt.replace('\n', '')
    fs_max = int(round(cap))

    # 第一轮（原文本身是单行时）：整串落进一行
    if txt.count('\n') + 1 <= 1:
        for fs in range(fs_max, lo - 1, -1):
            f = ImageFont.truetype(path, fs)
            if measure(one_line, f) <= limit * 1.001:
                best = (fs, [one_line])
                break

    # 第二轮：允许按词换行
    if best is None:
        for fs in range(fs_max, lo - 1, -1):
            f, lines, widest, fits = attempt(fs, maxh=bbox_h)
            if fits:
                best = (fs, lines)
                break

    # 第三轮：仅轻微溢出时继续降字号把溢出消掉
    if best is not None:
        fs0, lines0 = best
        f0 = ImageFont.truetype(path, fs0)
        if max((measure(l, f0) for l in lines0), default=0) > limit * 1.02:
            for fs in range(fs0 - 1, lo - 1, -1):
                f = ImageFont.truetype(path, fs)
                lines = lines0 if len(lines0) > 1 else wrap_by_width(txt, f, limit)
                if max((measure(l, f) for l in lines), default=0) <= limit * 1.02 \
                        and len(lines) <= max_lines:
                    best = (fs, lines)
                    break

    if best is None:
        # 兜底：下限字号，允许行数超出，但保证不横向溢出
        fs = lo
        f = ImageFont.truetype(path, fs)
        lines = wrap_by_width(txt, f, max(limit, 1))
        if any(measure(l, f) > limit * 1.001 for l in lines):
            lines, cur = [], ''
            for ch in txt.replace('\n', ''):
                if cur and measure(cur + ch, f) > limit:
                    lines.append(cur)
                    cur = ch
                else:
                    cur += ch
            if cur:
                lines.append(cur)
        best = (fs, lines)
    return best


def _mode_color(px, w, h, skip_inner=None):
    """取像素众数；skip_inner=(x0,y0,x1,y1) 时跳过该矩形内部。"""
    cnt = {}
    sx0, sy0, sx1, sy1 = skip_inner if skip_inner else (-1, -1, -1, -1)
    for yy in range(h):
        for xx in range(w):
            if sx0 <= xx < sx1 and sy0 <= yy < sy1:
                continue
            c = px[xx, yy]
            if (c[0] * 299 + c[1] * 587 + c[2] * 114) / 1000 < 175:
                continue                       # 深色墨迹，跳过
            cnt.setdefault((c[0] // 8, c[1] // 8, c[2] // 8), []).append(c)
    if not cnt:
        return None
    best = max(cnt.values(), key=len)
    n = len(best)
    return (sum(c[0] for c in best) // n,
            sum(c[1] for c in best) // n,
            sum(c[2] for c in best) // n)


def sample_pad(img, box, pad=10):
    """取擦除用的底色。返回 (颜色, 该颜色覆盖的矩形)。

    三种候选，按优先级取第一个可用：
      1) 内圈（bbox 缩小 1px）：文字所在区域的底色 —— 高亮块里就是高亮色
      2) 外圈（bbox 外扩 pad、跳过 bbox 内部）：普通白底/深底
      3) 全 bbox 众数（兜底）

    为什么要分内外圈：图内常有黄色高亮条，它的范围**比文字框大**，
    只取外圈会拿到高亮块外面的白色，擦完在黄条上留一块白斑。
    反过来，普通白底文字的外圈可能压到旁边的线条，取内圈更安全。
    判据：内圈颜色「够不白也不够黑」（饱和度/偏离灰阶明显）→ 大概率是彩色底，用内圈。
    """
    x0, y0, x1, y1 = [int(v) for v in box]
    W, H = img.size
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(W, x1), min(H, y1)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None, (x0, y0, x1, y1)

    # 1) 内圈（剔除抗锯齿边缘）
    ix0, iy0 = x0 + 1, y0 + 1
    ix1, iy1 = x1 - 1, y1 - 1
    inner = None
    if ix1 - ix0 >= 3 and iy1 - iy0 >= 3:
        px = img.crop((ix0, iy0, ix1, iy1)).load()
        inner = _mode_color(px, ix1 - ix0, iy1 - iy0)

    # 2) 外圈
    ex0, ey0 = max(0, x0 - pad), max(0, y0 - pad)
    ex1, ey1 = min(W, x1 + pad), min(H, y1 + pad)
    px2 = img.crop((ex0, ey0, ex1, ey1)).load()
    outer = _mode_color(px2, ex1 - ex0, ey1 - ey0,
                        skip_inner=(x0 - ex0, y0 - ey0, x1 - ex0, y1 - ey0))

    def colored(c):
        """彩色底判据：偏离灰阶明显（R/G/B 之间差 >12）或明显偏黄/偏蓝。"""
        if c is None:
            return False
        return (max(c) - min(c)) > 12

    if colored(inner):
        return inner, (x0 - 3, y0 - 3, x1 + 3, y1 + 3)   # 高亮底：只擦 bbox 略外扩
    if outer is not None:
        return outer, (ex0, ey0, ex1, ey1)
    if inner is not None:
        return inner, (x0 - 3, y0 - 3, x1 + 3, y1 + 3)
    return None, (x0, y0, x1, y1)


def sample_bg(img, box):
    """取 bbox 内部像素的颜色众数作为背景色（文字是少数像素，背景是多数）。"""
    x0, y0, x1, y1 = [int(v) for v in box]
    W, H = img.size
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(W, x1), min(H, y1)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return (255, 255, 255)
    crop = img.crop((x0, y0, x1, y1))
    small = crop.resize((max(1, (x1 - x0) // 2), max(1, (y1 - y0) // 2)), Image.NEAREST)
    cnt = {}
    for c in small.getdata():
        k = (c[0] // 12, c[1] // 12, c[2] // 12)
        cnt.setdefault(k, []).append(c)
    best = max(cnt.values(), key=len)
    n = len(best)
    return (sum(c[0] for c in best) // n, sum(c[1] for c in best) // n,
            sum(c[2] for c in best) // n)


def ink_ratio(img, box):
    """bbox 内深色像素比例，用于判断原文是否真的可见。"""
    x0, y0, x1, y1 = box
    if x1 - x0 < 4 or y1 - y0 < 4:
        return 0.0
    dx, dy = (x1 - x0) * 0.25, (y1 - y0) * 0.25
    x0, y0, x1, y1 = int(x0 + dx), int(y0 + dy), int(x1 - dx), int(y1 - dy)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return 0.0
    crop = img.crop((x0, y0, x1, y1)).convert('L')
    h = crop.histogram()
    return sum(h[:110]) / max(1, sum(h))


def render_one(page, fig, texts, trans, out_path):
    # 左右多留 26pt：中文标签常比英文宽，居中后容易出框；下边留 5pt 但不切图注
    clip = pymupdf.Rect(fig['bbox'][0] - 26, fig['bbox'][1] - 3,
                        fig['bbox'][2] + 26, fig['bbox'][3] + 5)
    clip = clip & page.rect
    # 小图块提高倍率，保证等效像素密度
    dpi = DPI * 2 if (clip.width < 200 or clip.height < 200) else DPI
    pix = page.get_pixmap(clip=clip, dpi=dpi)
    img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    dr = ImageDraw.Draw(img)
    zoom = dpi / 72.0

    def to_px(r):
        return ((r[0] - clip.x0) * zoom, (r[1] - clip.y0) * zoom,
                (r[2] - clip.x0) * zoom, (r[3] - clip.y0) * zoom)

    report = []
    for b in texts['blocks']:
        cn = trans.get(str(b['id']))
        if cn is None or not str(cn).strip():
            report.append({'id': b['id'], 'status': 'MISSING', 'en': b['en'][:40]})
            continue
        cn = str(cn)
        x0, y0, x1, y1 = to_px(b['bbox'])
        vis = ink_ratio(img, (max(0, x0), max(0, y0),
                              min(img.size[0], x1), min(img.size[1], y1)))
        if cn.strip() == b['en'].strip() and vis > 0.012:
            report.append({'id': b['id'], 'status': 'KEEP', 'vis': round(vis, 3),
                           'en': b['en'][:40]})
            continue
        bw, bh = x1 - x0, y1 - y0
        # 底色：内圈判彩色底、外圈兜普通底；深底反白字
        bg, erase_box = sample_pad(img, (x0, y0, x1, y1), pad=10)
        if bg is None:
            bg = sample_bg(img, (x0, y0, x1, y1))
            erase_box = (x0 - 3, y0 - 3, x1 + 3, y1 + 3)
        _lum = (bg[0] * 299 + bg[1] * 587 + bg[2] * 114) / 1000
        ink = (255, 255, 255) if _lum < 110 else INK
        if vis >= 0.004:
            dr.rectangle(list(erase_box), fill=bg)

        cap = b['size'] * zoom * 1.15
        bold = b['en'].isupper() or b['en'].endswith('!')
        max_lines = max(len(b.get('line_bboxes') or []), cn.count('\n') + 1, 1)
        only_cn = all(ord(ch) > 127 or ch in ' \n' for ch in cn)

        # 极窄/极小框：中文放不进去，原样保留英文（交付说明里要列出来）
        #   1) 窄条（纵轴标签、图例一条）      bw < 60pt 且明显窄高
        #   2) 迷你框（坐标轴刻度、单位符号）  面积 < 12x12pt
        #   3) 高度连一个汉字都放不下          bh < 2.2 个汉字高
        _cjk_pt = 4.6                                     # 汉字最小可读字号
        _cnlen = len(cn.replace('\n', ''))
        # 可用宽度：只允许很小的外扩（框宽 6%，且不超过 0.9pt/侧）
        limit = max(6, bw + min(bw * 0.06, 0.9 * zoom) * 2)
        # 一行汉字最多能放几个（按最小可读字号估）
        _per_line = max(1, int(limit / (_cjk_pt * zoom)))
        # 单字框（纵轴刻度、单符号）：宽度连 2 个汉字都放不下
        tiny = (bw < 12 * zoom and bh < 12 * zoom)
        # 窄条：译文需要 3 行以上，而框又窄又高 → 硬排只会糊成一团
        narrow = (bw < 60 * zoom and bh > bw * 1.6
                  and _cnlen > _per_line * 2)
        # 太矮：可用高度放不下译文需要的行数
        _need_lines = -(-_cnlen // _per_line)              # 向上取整
        too_short = (bh < _cjk_pt * 1.15 * _need_lines * zoom)
        if narrow or tiny or too_short:
            report.append({'id': b['id'], 'status': 'KEEP',
                           'reason': ('narrow-box' if narrow else
                                      'tiny-box' if tiny else 'short-box'),
                           'en': b['en'][:40],
                           'bbox_pt': [round(bw / zoom, 1), round(bh / zoom, 1)]})
            continue

        # 竖排：仅当译文很短（≤2 字）且框明显窄高；多字竖排会被拉成长条
        vertical = ('\n' not in cn) and only_cn and len(cn) <= 2 \
            and bh > bw * 2.0 and bw < 22 * zoom

        if vertical:
            fs = int(min(cap, max(9, bw * 0.92)))
            lines = [c for c in cn if c.strip()]
            pitch = 1.22
        elif '\n' in cn:
            # 译者按原文分行给出：优先严格分行；某行超宽时，只把那一行再拆开
            explicit = [x.strip() for x in cn.split('\n') if x.strip()]
            fs = max(1, int(4.6 * zoom))
            for cand in range(int(round(cap)), int(4.6 * zoom), -1):
                f_try = ImageFont.truetype(pick_font(cn, bold), cand)
                widest = max((measure(x, f_try) for x in explicit), default=0)
                if widest <= limit * 1.001 and len(explicit) * cand * 1.12 <= bh * 1.4:
                    fs = cand
                    break
            lines = explicit
            # 到底还超宽 → 保字号，按宽度对超宽行二次换行（不破坏已给的语义分行）
            f_chk = ImageFont.truetype(pick_font(cn, bold), fs)
            if max((measure(x, f_chk) for x in lines), default=0) > limit * 1.001:
                rebuilt = []
                for seg in lines:
                    if measure(seg, f_chk) <= limit * 1.001:
                        rebuilt.append(seg)
                    else:
                        rebuilt.extend(wrap_by_width(seg, f_chk, limit))
                lines = rebuilt
            pitch = max(1.0, min(1.22, bh / max(1, len(lines) * fs)))
        else:
            if not only_cn and bh > bw * 2.0 and bw < 22 * zoom:
                max_lines = max(max_lines, 3)
            fs, lines = fit_text(cn, limit, max(6, bh), cap,
                                 zoom=zoom, bold=bold, max_lines=max_lines,
                                 hard_w=max(6, bw))
            # 总高必须落进 bbox：先压行距（下限 1.14，再低行会叠字），再缩字号
            PITCH_MIN = 1.14
            pitch = 1.22
            if len(lines) * fs * pitch > bh:
                pitch = max(PITCH_MIN, bh / max(1, len(lines) * fs))
            guard = 0
            while len(lines) * fs * pitch > bh + 0.5 and fs > 4.5 * zoom and guard < 60:
                fs -= 1
                f_try = ImageFont.truetype(pick_font(cn, bold), fs)
                lines = wrap_by_width(cn, f_try, limit)
                pitch = (1.22 if len(lines) * fs * 1.22 <= bh
                         else max(PITCH_MIN, bh / max(1, len(lines) * fs)))
                guard += 1

        f = ImageFont.truetype(pick_font(cn, bold), fs)
        total_h = len(lines) * fs * pitch
        ty = y0 + (bh - total_h) / 2 + fs * 0.10
        centered = len(cn.replace('\n', '')) <= 16 or bool(b.get('rotated'))
        for ln in lines:
            wpx = measure(ln, f)
            tx = x0 + (bw - wpx) / 2 if centered else x0
            tx = max(2.0, min(tx, img.size[0] - wpx - 2.0))   # 夹紧，避免贴边被切
            dr.text((tx, ty), ln, font=f, fill=ink)
            ty += fs * pitch

        widest = max((measure(l, f) for l in lines), default=0)
        over_w = (widest / bw - 1) * 100 if bw else 0
        over_h = (total_h / bh - 1) * 100 if bh else 0
        bad = over_w > (OVERFLOW_TOL - 1) * 100 or over_h > 6
        report.append({'id': b['id'],
                       'status': 'OVERFLOW' if bad else 'OK',
                       'fs_px': fs, 'fs_pt': round(fs / zoom, 1),
                       'lines': len(lines),
                       'over_w': round(over_w, 1), 'over_h': round(over_h, 1),
                       'bbox_pt': [round(bw / zoom, 1), round(bh / zoom, 1)]})

    img.save(out_path)
    from PIL import ImageChops
    tmp = img.convert('L')
    bbox = ImageChops.difference(tmp, Image.new('L', tmp.size, 255)).getbbox()
    if bbox:
        pad = 6
        img2 = img.crop((max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                         min(img.size[0], bbox[2] + pad),
                         min(img.size[1], bbox[3] + pad)))
        img2.save(out_path)
    return report


def main():
    layout_p, figtexts_p, trans_p, outdir = (sys.argv[1], sys.argv[2],
                                             sys.argv[3], sys.argv[4])
    layout = json.load(open(layout_p, encoding='utf-8'))['pages']
    figtexts = json.load(open(figtexts_p, encoding='utf-8'))
    trans = json.load(open(trans_p, encoding='utf-8'))
    os.makedirs(outdir, exist_ok=True)
    doc = pymupdf.open(PDF)

    figs_by_key = {}
    for pno, blks in layout.items():
        fi = 0
        for b in blks:
            if b['type'] in ('figure', 'table'):
                key = f'p{pno}_f{fi}'
                if b['type'] == 'figure':
                    figs_by_key[key] = (int(pno), b)
                fi += 1

    allrep = {}
    n_bad = 0
    for key, (pno, fig) in figs_by_key.items():
        texts = figtexts.get(key) or {'blocks': []}
        tr = trans.get(key, {})
        out = os.path.join(outdir, key + '.png')
        rep = render_one(doc[pno - 1], fig, texts, tr, out)
        allrep[key] = rep
        bad = [r for r in rep if r['status'] not in ('OK', 'KEEP')]
        n_bad += len(bad)
        fs_min = min([r.get('fs_pt', 99) for r in rep if 'fs_pt' in r], default=0)
        print(f'{key}: {len(rep)} 块, 最小字号 {fs_min}pt'
              + (f'  <<< {len(bad)} 处问题' if bad else ''))
        for r in bad:
            print('    ', r)
    json.dump(allrep, open(os.path.join(outdir, '_report.json'), 'w',
                           encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n合计问题 {n_bad} 处')
    if n_bad:
        print('OVERFLOW = 文字超出方框（改短译文或调字号）；'
              'MISSING = 缺译')


if __name__ == '__main__':
    main()
