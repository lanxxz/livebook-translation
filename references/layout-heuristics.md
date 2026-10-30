# 版式解析判据

> parse_layout.py 的核心规则。换一本书时需要调的通常是「字体名」和「版心宽度」。
>
> 两类书差别很大，先判断类型再调参：
> - **手绘示意图书**（Grokking）：难点在图内标签排版，正文结构相对简单。
> - **两色排版书**（Manning）：难点在特殊块（侧栏/边注/清单条/代码截图）的识别与归属。

## 0. 两色/多色排版书：用颜色当主判据

Manning 这类书把「块类型」直接编码成**固定填充色**，比几何判据可靠得多：

```python
# 实测值（Manning 2024 版式）
COLOR_SIDEBAR = (0.969, 0.961, 0.910)   # 侧栏底色，米黄
COLOR_LISTING = (0.438, 0.652, 0.801)   # 清单标题条，蓝
COLOR_THEAD   = (0.277, 0.418, 0.523)   # 表头填充，深蓝
```

做法：`page.get_drawings()` 里取 `fill` 颜色，与上表比对（容差 0.01），
命中即得到该矩形是「侧栏块 / 清单条 / 表头」。

**但颜色只能定位矩形，不能判定文字归属。** 侧栏里的文字还必须叠一层字体特征：

```python
in_sidebar = 行中心点落在侧栏矩形内 \
             and 任一字体名以 ('FranklinGothic', 'Wingdings') 开头
```

只靠几何（缩进/颜色）判侧栏，在两色书上会炸——实测一页 5 个块的侧栏被切成 49 段，
因为满页都是缩进文本（pitfalls K4）。

## 1. 字体分类

PDF 里每段文字都带字体名。先摸清这本书用了哪几种，再把它们归到四类：

```python
BODY_FONTS = {'Minion-Regular', 'Minion-Italic', 'Minion-Bold'}   # 正文字体
CODE_FONTS = {'CourierNewPSMT', 'CourierNewPS-BoldMT'}            # 等宽字体
# 其余（Swister、MyriadPro、OpenSans 等）默认判为图内文字或标题
```

Manning 书的实测字体名（换书时按同位置替换）：

```python
BODY   = 'NewBaskerville'      # 正文衬线 10pt
CODE   = 'JetBrainsMonoNL'     # 代码等宽 8pt（MONO_CW 需实测，约 4.79）
HEAD   = 'FranklinGothic'      # 标题（-Demi / -Book / -Heavy 各有语义）
FIGTXT = 'ArialMT'             # 图内文字
SIDEBAR_BODY = 'FranklinGothic-Book'   # 侧栏正文 9.5pt（不是正文字体！）
BULLET = 'Wingdings2'          # 侧栏项目符号 8.5pt
```

判定一行的类型（按字符占比，不按 span 个数）：

```python
if code_ch / total > 0.75 and not 单个标识符:
    kind = 'code'
elif body_ch / total > 0.4:      # 正文行里行内代码可能占一半，阈值不要取 0.5
    kind = 'body'
elif 字体是标题字体 and size >= 11:
    kind = 'head'
else:
    kind = 'figtext'
```

**怎么摸字体**：抽 3 页，打印每行文字 + 字体统计，一眼就能看出正文、代码、图注分别是什么字体。

## 2. 图区聚类

drawings（矢量图形）+ 非正文文字行 → 聚成图块：

1. 收集所有 drawings 的 rect（宽或高 <0.8 的先外扩 0.6pt，否则直线/边框会被漏掉）
2. 按 bbox 距离聚类（gap 取 **9pt**，不要 20pt，否则会把表格和便签并成一块）
3. 用图内文字行二次生长边界（图里文字可能溢出线条范围）
4. 交叠 >5.5% 的两块合并（同一段注释被拆开会导致中文化后错位）

## 3. 行归属（最容易改坏的地方）

```python
# 唯一规则：行的中心点落在图 bbox 内 → 归图
cx = (x0 + x2) / 2; cy = (y0 + y2) / 2
for f in figs:
    r = f['bbox']
    if r[0]-2 <= cx <= r[2]+2 and r[1]-2 <= cy <= r[3]+2:
        owner = f; break
```

两个例外（都是实测必要，不算"聪明规则"）：

- **18pt 以上的标题不归图**：章标题跨两行时，第二行常被图 bbox 带进去，导致标题只剩半句。
- **图内孤立的 figtext**：中心不在任何图内时，按最近距离（<60pt）归入。

**反面教材**：试过"宽度 >250pt 的正文行不归图"和"用纯图元范围判断"——前者把 9 行的图内长注释误判成正文，后者让游离文字的兜底归属变化、把一张图裂成两张。都回滚了。

## 4. 段落合并

按阅读顺序逐行处理，判断是否并进上一段：

```python
if prev.type == 'para' and y0 - prev.y1 < 4.5:
    indent = x0 - base_x            # base_x = 本页正文左边距众数
    if 6 < indent < 40:             # 真缩进（12pt 左右）→ 新段
        新段
    else:                           # 0（续行）或 139（环绕排版的窄栏）→ 合并
        合并
```

- 软连字符 `\u00ad` 结尾 → 直接拼（不加空格）
- 硬连字符 `-` 结尾 → 直接拼（保留连字符语义）
- 其余 → 加一个空格再拼

**跨页续接**：上页末块不以 `。！？：；.!?:;"”)）` 结尾、下页首块同为 para → 合并；同为 code → 合并。

### 4.1 续行的三种特殊情形（长书必备）

两色书正文密集，跨页/跨图表折断极常见，且**不能只靠"前段未收句"一条**：

```python
def continues(prev, nxt):
    """判断 nxt 是否 prev 的续行（不是新段落）。"""
    if prev.endswith(('-', '—')):      # 连字符折断
        return True
    if not nxt[:1].isupper():          # 小写开头 → 极可能是续行
        return True
    return False
```

三种必须处理的情形：

1. **段落续行被图内标题挡住**：下页首块可能是图内伪标题（如 `Factors driving ...`），
   真正的续行在其后。做法：**在页首 4 块内向前找第一个满足 `continues()` 的 para**，
   找到就接回列表末项（pitfalls K1）。
2. **列表项跨页折断**：列表末项未收句，下一页顶部有续行 → 接回该列表的最后一项，
   **不是新建一个列表**。
3. **列表被图/表打断**：列表末项未收句，中间隔着 figure/table/caption/heading，
   后面还有续行 → 跳过图表块接回。允许跳过 **≤5 块**；超过就说明确实是新内容。

### 4.2 边注（DEFINITION / NOTE）聚合

Manning 用小号大写标题引出边注，边注正文常缩进在框内、逐行独立成段：

```python
# 判据：全大写短标题（3 < len < 30）+ 紧随 ≥2 个连续 para
if heading.type == 'heading' and text.isupper() and 3 < len(text) < 30:
    paras = 紧随其后的连续 para
    if len(paras) >= 2:
        # 若「标题之前那段」未收句，把它的尾巴并进来（半句在框外）
        note = {'type': 'note', 'head': 标题, 'text': 合并后的正文}
```

不聚合的话，一条边注会被切成 8 个碎片，正文完全读不通（pitfalls K2）。
聚合后全书 note 块从 14 涨到 24，para 从 1626 降到 1321 —— 结构更接近原书真实意图。

## 5. 标题

- 用字体 + 字号双判据（MyriadPro-Bold + 14pt 是 H2、11pt+MyriadPro 是 H3）
- 同级别标题跨行：`y0 - prev.y1 < size*0.8` 则合并
- 章首页版式独立解析（章号 40pt+、标题 18pt Semibold、引语用特殊字体）

## 6. 表格

只认**横竖线网格**：

- 有 ≥2 条水平线和 ≥2 条垂直线
- 单元格文字填充率 ≥70%

满足才当表格，否则当普通图。还原时按网格切 cell，逐格取文字，合并成 `data[rows][cols]`。

## 7. 代码

- 按字符占比 >75% 判 code（不要按 span 个数）
- 单行只是一个标识符（`count`、`fraud`）→ 当正文
- 相邻 code 行的 y 间隙 >4.5 → 插空行（保留原书的空行）
- 同一段落的 code 若被图打断，图内那部分会缺行，需要人工按图注重建

## 8. 图内文字的旋转与竖排

`line['dir']` 不是 `(1,0)` 就是旋转文字。判据：

```python
vertical = b['rotated'] and bh > bw * 1.6 and '\n' not in译文
```

纵轴标签、侧边注释属于这类。**中文必须竖排**（每字一行），否则会被压成 2–4pt。

## 9. 调参顺序（换新书时）

1. 先摸字体名 → 改 BODY_FONTS / CODE_FONTS
2. 量版心宽度（正文左边距/右边距）→ 改 `ORIG_TEXT_W_PT`
3. 跑 3 页看 dump，重点看：标题层级对不对、段落有没有被拆碎、图块数是否等于肉眼数
4. 只在这三步不够时才动 gap / 阈值，且每次改完**回头跑前几章**确认没回归

## 10. 代码截图类插图（Manning 特有）

Manning 会把清单里的代码**放大截图**，配箭头 + 旁注当"图"用。特征：

- figure 块内文字只有 1–2 段，且都是长英文旁注（`Generates binary predictions ...`）
- 紧随其后必然是一个 `code` 块（就是被放大的那段代码）
- 图内还有一行残缺文字（如 `the best score.`），是截图边缘被切掉的部分

处理：**整张略去**。内容已被清单代码 + 旁注完全覆盖，保留只会让代码出现两遍。

```python
# render_figs.py：不叠中文，原样导出
if key in SKIP_KEYS:
    copy_figure(page, fig, out); continue

# build_docx.py：整块跳过
if blk.get('key') in SKIP_FIGS:
    continue
```

两处都要改。只改渲染器，图还会进 docx（pitfalls I1/I2）。
判定名单手工建一次即可（一本书通常 3–5 张），写在 `work/fig_skip.json`。

## 11. 结构性颜色速查（Manning 2024 版式）

| 用途 | RGB 实测值 | 备注 |
|---|---|---|
| 侧栏底色 | (0.969, 0.961, 0.910) | 米黄，整块填充 |
| 清单标题条 | (0.438, 0.652, 0.801) | 蓝，条状 |
| 表头填充 | (0.277, 0.418, 0.523) | 深蓝 |
| 正文强调 | (0, 0, 0) 之外的单色 span | 用 `color != 0` 判强调 |

页面尺寸 531×632pt，正文块宽 372pt，左右页边距镜像（奇 93.2 / 偶 102.2）。
代码等宽字符宽 `MONO_CW ≈ 4.794`（JetBrainsMonoNL 8pt），换书必须重测。

---

## 12. Manning 2025 单色版（《How Large Language Models Work》实测）

上面第 0 节讲的「三色结构色」在这版书里**只剩两种**（没有深蓝表头，表头是浅蓝
`(0.4128, 0.6920, 0.8091)`）。判据要重测，不能照抄 2024 版。

### 12.1 字体与语义（实测字符串量占比）

| 用途 | 字体名 | 字号 | 判据 |
|---|---|---|---|
| 正文 | `NewBaskervilleW01-Roman` | 9.9~10.1 | 占全书 45% |
| 正文强调 | `NewBaskervilleW01-Italic` / `-BoldIt` | 9.9~10.1 | 只换字形不换字号 |
| H2 | `ITCFranklinGothicStd-Demi` | 12.5 | 蓝 `4746374` |
| H3 | `ITCFranklinGothicStd-Demi` | 10.5 | 蓝 `4746374` |
| 章首页 TOC 项 | `ITCFranklinGothicStd-Boo` | 10.0 | 蓝，**不给项目符号字形**（符号是矢量小方块） |
| 代码 | `CourierStd` / `CourierStd-Bold` | 8.0 | 行内代码也用同一族 |
| 题注 | `FranklinGothicFS-Demi` | 8.0 | 灰 `7171697` |
| NOTE/WARNING 标签 | `FranklinGothicFS-Demi` | 9.0 | 蓝 `4746374`，**与正文同基线** |
| 侧栏标题 | `FranklinGothicFS-Demi` | 11.0 | 蓝 |
| 清单条文字 | `FranklinGothicFS-Demi` | 10.0 | 白 `16777215` |
| 图内文字 | `ArialMT` / `Arial-BoldMT` / `HumanistMann521-BoldCond` / `txsys`（数学） | 6~9.6 | 颜色 `197636` |

关键：**同一个字体 `FranklinGothicFS-Demi` 承担了题注/NOTE 标签/侧栏标题/清单条四种角色**，
只能靠「字号 + 颜色 + 是否落在色块内」三者组合区分：

```python
if font.startswith('FranklinGothicFS-Demi'):
    if size <= 8.4 and color == 7171697:      'caption'   # 题注
    elif size >= 8.6 and color == 4746374:    'note_label'# NOTE/WARNING
    elif size >= 10.6:                        'side_head' # 侧栏标题（落在米色底内）
    elif color == 16777215:                   'listing'   # 清单条（落在蓝条内）
```

### 12.2 结构色（这版只有两种 + 一种符号色）

| 用途 | fill 实测 | 容差 | 形态 |
|---|---|---|---|
| 侧栏底 | `(0.969, 0.961, 0.910)` | 0.02 | 大矩形，宽 >150、高 >40 |
| 清单条 | `(0.438, 0.652, 0.801)` | 0.08 | 扁条，8 < 高 < 30、宽 >180 |
| 表头 | `(0.4128, 0.6920, 0.8091)` | — | **与清单条不同色**，别混用 |
| 项目符号 | `(0.798, 0.650, 0.353)` | 0.14 | **3×3pt 实心小方块**，不是字形 |

侧栏的边框是**同色描边**（`type='s'`，fill=None），直接按 fill 判会漏掉边框、
把边框当成图形区划进图块——**侧栏边框必须单独跳过**：

```python
if color_close(fill, SIDE) or color_close(drawing.get('color'), SIDE):
    continue          # 侧栏边框线，不算图形区
```

### 12.3 版心与尺寸

- 页面 531.36×666pt（**不是 632**，2024 那版的高度在这里不适用）
- 正文左边距 103.7pt，右边距 462.4pt，**版心宽 358.7pt**（`ORIG_TEXT_W_PT` 用 358）
- NOTE 框正文缩进 115.7pt（比正文多 12pt）
- 页眉带 y < 40；页脚带 y > 594（页码在 599.8）
- 代码等宽字符宽约 **4.78pt**（CourierStd 8pt），换书必须重测

### 12.4 表格识别：竖线会被拆成多段

这版书的表格竖线**按单元格分段存储**，一条 10 行的表会有 40+ 条竖线段，
长度都只有 10pt 左右。原来「`height > 18` 才算竖线」的条件会一条都取不到，
表格全部退化成 figure。

正确做法：**按 x 坐标分组，合并相邻线段，再看合并后的总跨度是否覆盖表高**：

```python
vseg = collections.defaultdict(list)
for dr in page.get_drawings():
    rr = dr['rect']
    if rr.width < 1.3:                       # 竖线
        vseg[round(rr.x0)].append((rr.y0, rr.y1))

vs = []
span = hs[-1] - hs[0]                        # 横线总跨度＝表高
for x, segs in sorted(vseg.items()):
    segs.sort()
    merged = [list(segs[0])]
    for a, b in segs[1:]:
        if a <= merged[-1][1] + 1.5:         # 相邻/重叠 → 合并
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    if max(b - a for a, b in merged) >= span * 0.6:
        vs.append(x)
```

同时**横线要跨满表宽**（`width >= 表宽 × 0.7`），否则示意图里的网格会被误判成表格。

### 12.5 表头行会被「清单条」抢走

表头是**浅蓝底 + 白字**，与清单条几乎同款。必须让 bbox 落在表格内的行优先归表格，
不能被 `bar_of` 抢走：

```python
# 表格识别完之后
if _inside_fig(fig_objs, cx, cy):
    bar_of.pop(id(ln), None)
    side_of.pop(id(ln), None)
```

并且**表格内的所有文字（含表头）都要并进 table 的 lines**，否则表头会变成表格上方
一行孤零零的白字（pitfalls P4）。

### 12.6 章首页的「This chapter covers」列表（换书时必须核对字体判据）

项目符号是**矢量小方块**（3×3pt），不在文字层。所以 TOC 项在 `get_text()` 里是
连续的行，没有 `•` 可作分组锚点。必须**按方块 y 坐标分组**：

```python
bullets = sorted(b[1] for b in bullet_rects if b[1] > 80)   # 章号区下方才有
for k, by in enumerate(bullets):
    hi = bullets[k + 1] - 2 if k + 1 < len(bullets) else 1e9
    seg = [t['text'] for t in toc_lines if by - 4 <= t['bbox'][1] < hi]
    items.append(clean(' '.join(seg)))
```

而且 TOC 项本身常被折成两行（`What Generative Pretrained Transformers` +
`and large language models are`），**必须在同一个方块分组内用空格拼接**，
译文也要合并成一条（不能译成两条）。

**踩坑提醒**：`parse_layout.py` 里 TOC 行的分类还挂在旧版式的字体名上
（`any(f.startswith('MyriadPro') for f in fonts)`）。换到 2025 版书时这句
一条都匹配不上，`toc_lines` 为空 → 章首页的 `toc_items` 全是 0。
**换书第一步就要把这里改成新书的章首页 TOC 字体**（本书是
`ITCFranklinGothicStd-Boo` 10pt 蓝色），否则章首页会丢整块「本章内容」。

```python
# 换书时按 dump 里实际出现的字体改这一行
elif any(f.startswith(('MyriadPro', 'ITCFranklinGothicStd-Boo')) for f in fonts) \
        and size < 13:
    toc_lines.append((bb[1], bb[0], text))
```

同理，`BODY_FONTS` / `CODE_FONTS` 也要一起换成新书的字体名（见第 12.1 节表）。

