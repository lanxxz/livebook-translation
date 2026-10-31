---
name: livebook-translation
description: 把带矢量插图的技术书（PDF）整本翻译成中文 Word/PDF——图内文字就地中文化、代码提取为可复制块、矢量表格还原成真表格、逐块校验与原书对齐。覆盖短图重书（Grokking 类）与长代码重书（Manning 类，含分片翻译、解析变更后译文重映射、整书合并）。当用户要求翻译一本技术书/电子书（尤其带大量手绘示意图的 Manning、O'Reilly 类书籍）、或要把 PDF 书籍做成中文版 Word/PDF 时使用。
---

# 技术书整本翻译（图内文字中文化）

## 这个技能解决什么问题

普通翻译工具处理不了这类书，因为**图里的文字是排版的一部分，不是像素**。直接机翻或截图搬运会得到：图里全是英文而正文是中文，读者要来回对照；代码被箭头注释切断，复制出来跑不了；表格是画出来的线条，不是真表格。

本技能的做法：**把 PDF 版面拆成结构化块序列 → 逐块翻译成 JSON → 用 JSON 驱动 Word 生成**。图不是抄图片，而是按矢量指令重新渲染，图内英文擦掉、原位重写中文。这样图文一致、可复制、可校验。

## 什么时候用

- 用户给一本 PDF 技术书，要求出中文版（按章 docx 或整本）
- 书里有大量插图，且图里有英文标签/注释/对话气泡
- 需要保留原书版式感（不是重新排版成纯文本）

不适用：纯文字小说、无插图的文档、扫描版 PDF（无文字层）、EPUB（需先转 PDF）。

## 核心认知（先理解这六条，再动手）

**1. 块序列是唯一的真相来源。** 原书每页被拆成「标题/段落/列表/代码/图/表格」的序列，译文 JSON 必须**逐块一一对应**。少一个图、多一个段落，后面全部错位。每章跑 `audit.py`，不一致不许交付。

**2. 图内文字必须就地重绘，不能贴白块。** 擦除用「背景色采样」——取该文字 bbox 内像素颜色的众数填回去，黑底白字、圆筒内部、渐变背景都不留疤。字号按可用空间求解；中文**按词断行**（禁标点行首、禁单字成行），绝不按字切。

**3. 归属判断保持最简。** 判断某行文字属于图还是正文，只用一条规则：**行的中心点落在图元 bbox 内就归图**。不要加"宽行保护""纯图元范围"之类的聪明规则——实测每加一条都会引发连锁回归（见 pitfalls A17）。

**4. 代码缩进是版面坐标，不是文本。** PDF 里代码的缩进靠 x 坐标排版，提取出的行文本被 strip 后缩进就没了。必须按 `(行首 x − 版心左边界) / 等宽字符宽` 反算空格数。等宽字符宽度用全书代码行自动测量（不同书字体不同，不能写死），版心边界要**逐页**取（左右页常镜像）。另外 Word 会折叠连续半角空格，写回 docx 时前导缩进要用 U+00A0。

**5. 有些东西不该走图块流程。** 封面 / 版权页 / 目录整页是**文字排版**，
原书里的 logo、竖排章号、金色方块都是矢量装饰；当图处理只会得到白底白图或被拉扁的数字。
判断标准：**这一页的信息能不能只用文字和段落表达？** 能，就别画图。
同理，图里那些窄到放不下一个汉字的框（图例条、坐标轴刻度），保留英文比硬塞中文好。

**6. 长书必须分片，分片必须核对键号。** 一本 Manning 书 13 万词、460 页，不可能一口气译完。分片引入的主要风险不是"翻得不好"，而是**键号写错导致整片作废**。铁律两条：① 写译文前必须先 `export_pairs.py` 导出「块号+字段+原文」对照，照抄左边；② 每片写完立刻 `cov.py`，**多余键必须为 0**（缺可以为非 0，表示还没写完）。

## 三条流程，按书的形态选一条

| | 短书 / 图重（Grokking 类） | 长书 / 代码重（Manning 464 页） | **中等 / 文档多（20+ 份）** |
|---|---|---|---|
| 规模 | 11 章 336 页 | 14 章 + 附录 464 页 | 18 章 + 2 附录 + 前言 296 页 |
| 难点 | 图内文字排版（346 图） | 块结构归属 + 超长工作量 | 文档切分与逐份流水线 |
| 流程 | 「五步流程」 | 五步 + 「长书分片流程」 | **「骨架文本流水线」** |
| 译文存放 | `chN_trans.json` 手写 | `tx_<包>.py` 分片→固化 | `work/<doc>_zh.txt` 纯文本逐块 |
| 适合谁 | 图特别多 | 一本厚书一口气做完 | 章多、想并行、想分次交付 |

**怎么选：**

- 图多、章少 → 五步流程，重点在图内排版
- 一本书 400+ 页、代码密集 → 长书分片流程，重点在键号纪律
- **20 份以上独立文档、想逐份交付/并行/中断可续 → 骨架文本流水线**（下面第四节）

第三种流程是前两种的简化版：不写 Python 分片文件，直接写「带块号的纯文本」，
由 `convert.py` 解析成 JSON。优点是**人和代理都能直接编辑**、出错只影响一份文档、
可以用 `build_doc.py <doc>` 单份重跑。

## 接手已有翻译项目（续译，不要重做）

**进度以磁盘产物为准，不以笔记、README 或会话总结为准。** 实测遇到过记忆里写着
「已交付 1–13 章」，实际 `out/` 只有 1–3 章的情况；按错误进度续做会重译或漏译。

续译前先做一次产物盘点：

```bash
ls out/*.docx | sort          # 真正可交付的分章
ls work/*_trans.json | sort   # 已固化的译文
ls work/*_layout.json | sort  # 已解析的版面
# 对每个“看似完成”的章跑一次 check，而不是只看文件存在
$PY run.py check 13
```

判定一章完成至少要同时满足：`layout + trans + docx` 存在，且 `audit.py` 块序列一致、
图片数一致、无 DPI 警告。只有 `trans` 没有 `docx` 的是半成品；只有 `docx` 没有
`trans` 的是旧版产物，改动前先确认来源。

**优先复用项目自己的 runner**（如 `run.py prep|figs|build|check`），不要另起一套脚本。
很多项目的 `build` 已经把「渲染图 → 出 docx → audit」串好，单独重跑其中一步容易留下旧 PNG。

**轻量补丁式项目**常用 `work/chN_tr.py`，以 `PS` / `LS` **按文字块、列表块的出现顺序**
给译文，`apply_tr.py` 用断言把顺序映射到块下标。这是 10–15 章项目最省心的写法：

```python
PS = ["第 4.1 节标题", "第一段…", "第二段…"]   # 只含 p/h2/h3/caption/note/callout
LS = [["列表项 1", "列表项 2"], …]               # 只含 list/numlist
```

数量对不上时**不要猜下标**：先打印骨架中各类块的数量与顺序，定位是解析多了一块、
译文少了一项，还是某个图注被并进了正文。`PS`/`LS` 数量必须精确相等，断言失败就停。

**调用项目脚本要固定工作目录。** 这些脚本常通过当前目录找 `book.json`；在任意目录
直接调用会报缺配置。用项目 runner，或在命令里显式设置 `BOOK_ROOT` / `BOOK_PDF`；
只设这两个变量仍可能缺 `orig_text_w` 等字段，最稳的是让脚本在项目根目录运行。

**不要为了修一章去改公共渲染器。** 先确认改动是否影响所有章节；改完必须至少重建
「当前章 + 一个旧章」并比对块序列与图片数，确认无回归再继续。

## 五步流程

前置：项目根目录放 `book.json`（模板见 assets/book.json.example），至少填 `pdf` 与 `root`。

```bash
PY=<python>; S=<本技能 scripts 目录>

# 1. 解析版面（一次一章，给页码区间）
$PY $S/parse_layout.py 79 106 work/ch3_layout.json
$PY $S/dump_layout.py work/ch3_layout.json > work/ch3_dump.txt
#    → 人工核对 dump：标题层级、段落有没有被拆碎/误并、列表项数、
#      图块数、代码块完整度、有无重复文本。这 5 分钟能省 2 小时。

# 2. 提取图内文字，导出待译清单
$PY $S/extract_fig_texts.py work/ch3_layout.json work/ch3_figtexts.json
#    → 翻译成 work/ch3_figtrans.json：{"p103_f0": {"0": "中文", "1": "中文\n第二行"}}

# 3. 渲染图块（把中文写回图里）
$PY $S/render_figs.py work/ch3_layout.json work/ch3_figtexts.json work/ch3_figtrans.json figs/ch03
#    → 盯三件事：MISSING（缺译）、OVERFLOW（溢出方框）、fs_pt 过小
#    渲染器已内置溢出检测：字宽超过方框 4% 即标 OVERFLOW，必须清零再交付

# 4. 写正文译文 work/ch3_trans.json（按 dump 的块序列逐块对应）、跑校验

# 5. 生成 + 体检
$PY $S/build_docx.py work/ch3_trans.json work/ch3_figtexts.json work/ch3_figtrans.json \
    figs/ch03 "out/03_第3章_标题.docx" "第 3 章　标题"
$PY $S/audit.py work/ch3_layout.json work/ch3_trans.json "out/03_第3章_标题.docx" figs/ch03
#    必须：块序列一致、图片数 == 图块数、无 ⚠ 偏低 DPI

# 6. 全书一次性体检（12 章批量）
$PY $S/audit_book.py work/chapters.json
#    chapters.json 是 [{ch,layout,trans,docx,figs}, ...]
#    一次输出：块序列 / 漏译 / 代码含中文 / 图内溢出与字号 / 图片表格数
```

辅助脚本：
- `make_chapter.py prep|build <N> <起> <止>` — 把 1/3/5 步串成一条命令
- `verify_docx.py <docx>` — 打印段落大纲（标题层级 / 图位置 / 前 70 字）
- `preview_html.py` — 无 Office 时用 HTML + Chrome 截图自查排版
- `convert_pdf.py` — docx 批量转 PDF（LibreOffice headless，保留 docx）
- `build_front.py` — 生成前言/附录（致谢、术语表三列表格这类**内容页**）
- `build_front_pages.py` — **前置页专用**（封面 / 版权 / 目录），整页文字排版、不产生图片；目录页码自动取 `chapter_pages.json`
- `audit_book.py` — 全书批量体检（块序列/漏译/代码/图内溢出/图片数）
- `chapter_pages.py` — **算各章在中文版里的起始页**，写 `work/chapter_pages.json`（目录页码必须用它，不能照抄原书页码；**算的集合要含封面**，见 R4）
- `merge_book.py` 的**保真要点**（实战必读）：搬运 XML 前必须逐张 `relate_to` 重建
  `r:embed`（否则 rId 撞车、63 张图挤成 8 个关系），保存后按字节补 `xmlns:a`/
  `xmlns:pic`（否则 LibreOffice 打不开）。**最终 PDF 走「拼接分册 + 逐页重写页脚数字」**，
  不用合订 docx 再转（见 pitfalls R1/R2）
- `pairs.py <doc> [out]` — 把版面块导出成「块号+原文」对照，**写 `_zh.txt` 前必看**
- `check_cov.py <doc>… | --all` — 骨架流水线的覆盖率闸门：块号多余/缺失 + 图内缺译
- `export_pairs.py <包> <起> <止>` — **写译文前必跑**：导出「块号+字段+原文」对照
- `cov.py <包> [tx分片.py ...]` — 合并分片并核对覆盖率，**多余键必须为 0**
- `block_tool.py dump|peek|pages <包>` — 看某块有哪些键 / 是否被折断 / 图在哪些页
- `remap_seq.py <包> --dry` — 解析规则变更后，按块签名重对齐旧译文
- `merge_book.py` — 分章 docx 合成整本（每节独立页眉 + 页码连续，顺序敏感）
- `find_blank.py <pdf>` — 扫合并后是否产生空白页
- `layout_check.py <pdf>` — **排版体检**：页码连续性、页眉逐章、留白、孤立碎片、行距
  （audit 查内容，它查呈现；两套都要过）

**骨架文本流水线专用（第三种流程）**

- `slice_layout.py` — 按 docs.json 把整本 layout 切成每份文档的 layout/dump/figtexts
- `mk_skeleton.py <doc>…` — 生成 `_skel.txt` / `_figskel.txt` 待译骨架
- `convert.py <doc>` — 把 `_zh.txt` / `_figzh.txt` 解析成 `_trans.json` / `_figtrans.json`
- `build_doc.py <doc>…` — 单份文档一条龙：convert → 渲染图 → 出 docx → audit
- `build_book_pdf.py [--pdf-only|--docx-only]` — 合 docx + **逐份转 PDF 拼接** + 书签
  （保真做法；`--pdf-only` 时只出 PDF）

## 长书分片流程（Manning 类，460 页以上）

核心原则：**手写 `tx_<包>.py` 分片 → 合并核对 → 固化 → 应用 → 出文档**。
`*_fill.json` 是中间产物，**永远不要拿它当编辑对象**。

```bash
# 0. 全书解析 + 打包骨架（一次做完）
$PY $S/parse_layout.py 1 464 work/all_layout.json
$PY $S/extract_fig_texts.py work/all_layout.json work/all_figtexts.json
$PY $S/make_pack.py work/all_layout.json work/chapters.json work/pack
#    → 每章得到 <包>_skel.json（骨架）+ _src.txt（英文原文）+ _fill.json（待填模板）

# 1. 看某章规模，决定分几片
$PY $S/block_tool.py pages ch7        # 页数 + 图分布
$PY $S/cover.py ch7                   # 或直接 cov.py 看「模板 N 键」

# 2. 导出对照表 —— 分片翻译的唯一合法依据
$PY $S/export_pairs.py ch7 0 60 90
#    → 照左边的 "#8 list / item0" 抄键名，绝不凭记忆写 "12|text"

# 3. 手写分片译文 work/tx_ch7a.py（FILL_A = {...}），每片 40~80 项
#    超过 80 项一片，键号写错的返工成本会指数上升

# 4. 每写完一片立刻核对
$PY $S/cov.py ch7 work/tx_ch7a.py work/tx_ch7b.py
#    判读：多余必须 0；缺可以为非 0（尚未写完）
#    多余 > 0 → 键号写错了，回头对照 export_pairs 修正

# 5. 全部填满后固化并应用
$PY $S/freeze_tx.py ch7                          # fill.json → tx_ch7.py（唯一真源）
$PY $S/apply_fill.py work/pack/ch7_skel.json work/pack/ch7_fill.json work/ch7_trans.json
#    → 必须打印「缺 0 项」，这是完整性闸门

# 6. 出图 + 出文档 + 全书体检
$PY $S/build_figtrans.py ch7                     # fig_ch7.py → ch7_figtrans.json
$PY $S/do_chapter.py ch7                         # 应用+QA+渲染+docx 一条龙
$PY $S/check_all.py                              # 全书一张表，全 OK 才继续
```

### 解析规则改动后的译文抢救

改 `parse_layout.py` 里任何一条合并规则，全书块号都会平移，旧译文全部指错块。
**不要人工对**，按这个顺序：

```bash
$PY $S/parse_layout.py 1 464 work/all_layout.json   # 重新解析
$PY $S/make_pack.py ... work/pack                   # 重新打包（保留已填值）
$PY $S/remap_seq.py ch4 --dry                       # 先看对齐率
#   「对齐 205/205 块，缺 0 项」→ 完美
#   「对齐 157/157 块，缺 83 项」→ 缺的是空旁注续行，也算过
#   「对齐 180/205 块」          → 有关键块没对上，必须人工干预
$PY $S/remap_seq.py ch4                             # 落地
$PY $S/freeze_tx.py ch4                             # 立刻固化，保住成果
$PY $S/check_all.py                                 # 全章复检
```

纪律：**一次只加一条解析规则**，加完立刻全书重解析 + `check_all.py`。多条一起加，
出问题就定位不到是哪条引起的（pitfalls H4）。

### 整书合并

```bash
$PY $S/merge_book.py --order        # 先确认合并清单与页眉标签
$PY $S/merge_book.py                # 合并
$PY $S/convert_pdf.py               # 转 PDF
$PY $S/find_blank.py out/pdf/全书.pdf   # 必须「无空白页」
```

合并顺序铁律：**分节 → append → 设页眉**。顺序反了要么页眉全错，要么多出一堆空白页
（pitfalls J1/J2）。

## 骨架文本流水线（20+ 份文档，逐份交付）

核心思路：**不写 JSON、不写 Python 分片，写带块号的纯文本**。
`convert.py` 负责把它翻成 `build_docx.py` 要的 JSON。
好处：人和代理都能直接改、一份文档出错不影响别的、可以随时中断续做。

### 一次性准备

```bash
# 0. 全书解析一次（不切章）
$PY $S/parse_layout.py 1 296 work/book_layout.json
$PY $S/extract_fig_texts.py work/book_layout.json work/book_figtexts.json

# 1. 按 docs.json 把整本切成每份文档
#    docs.json: [{"id":"ch01","title":"…","num":"1","kind":"ch","from":28,"to":46}, …]
$PY $S/slice_layout.py
#    → work/<doc>_layout.json / _dump.txt / _figtexts.json

# 2. 给每份文档生成"待译骨架"
$PY $S/mk_skeleton.py ch01 ch02 …
#    → work/<doc>_skel.txt     逐块 @@BLOCK n type，%%ZH 之间留空
#    → work/<doc>_figskel.txt  图内待译 @@FIG/@T
```

### 逐份翻译

先导出对照表，再动笔 —— 块号必须照抄左边，不要凭顺序数：

```bash
$PY $S/pairs.py ch03 work/ch03_pairs.txt     # 或 --all 一次导出全部
$PY $S/check_cov.py --all                    # 动手前先看基线（应报「缺 N」）
```

读 `<doc>_dump.txt`（英文版面）→ 写两个纯文本文件：

| 文件 | 内容 |
|---|---|
| `work/<doc>_zh.txt` | `@@B <块号>` 开头，后面直接写中文；块号必须与 `_skel.txt` 一致 |
| `work/<doc>_figzh.txt` | `@@FIG <key>` / `@@T <id>` / `ZH <中文>` |

各类型写法（`convert.py` 就是按这个解析的）：

```
@@B 0
TITLE: 中文标题
APPENDIX: no
NUM: 3
TOC: 本章内容一
INTRO: 导言

@@B 1
3.1 小节标题

@@B 2
整段中文，支持 **粗体** 与 `行内代码`

@@B 3
- 列表项一
- 列表项二

@@B 5
CAP: 表 3.1　表题
HDR: 列一 | 列二 | 列三
ROW: 值 | 值 | 值

@@B 8
（code 块留空，代码从原版面直接取）
```

### 一条命令出一份文档

```bash
$PY $S/check_cov.py ch03      # 先过闸门：块号多余必须 0、图内缺译必须 0
$PY $S/build_doc.py ch03
# convert → 渲染图 → 出 docx → audit，一次跑完
# 末尾必须是「结论：✓ 通过」
```

`check_cov.py` 比 `build_doc.py` 更早发现问题：它只看文本，不渲染、不出 docx，
块号写错立刻报「多余块号」；而 `build_doc.py` 要到 audit 阶段才提示块序列不一致。

### 全书收尾

```bash
$PY $S/merge_book.py --order          # 确认顺序与页眉
$PY $S/merge_book.py                  # 合 docx
$PY $S/build_book_pdf.py              # 逐份转 PDF + 拼接 + 书签（保真）
$PY $S/layout_check.py out/pdf/全书.pdf   # 排版体检
```

`build_book_pdf.py` 会把 docx 合并和 PDF 拼接一起做掉，也可以
`--pdf-only` / `--docx-only` 单独跑。

### 这套流程的三条纪律

1. **块号只信 `_skel.txt`**。写完立刻 `build_doc.py`，它报"块序列不一致"就是
   少/多了块，看首个差异的块号回去补。
2. **一次只重跑一份**。`build_doc.py <doc>` 是幂等的，坏了只影响那一份。
3. **code 块留空**。代码从原版面按坐标重建，手打会丢缩进。

脚本放哪都行：`slice_layout.py` / `build_doc.py` / `merge_book.py` /
`build_book_pdf.py` 会**向上找含 `book.json` 或 `docs.json` 的目录**当项目根，
所以既可以放在项目根，也可以放在 `<项目>/scripts/`。

## 图内文字排版（最容易翻车的地方）

这一节全是实测教训。图好不好看，80% 取决于这里的几条规则。

### 断行：单位是词，不是字

- 中文必须先分词再断行（`jieba` 可用则用；没有就按 2~4 字滑窗近似）。
- **坚决不要"按字均衡分行"**。早期实现为了让每行等宽，会按字符累积宽度重新切分，结果「提示词」被切成「提示/词」、「提示词模板」被切成「提示/词模板」。词级贪心已经是想要的效果。
- 加**术语保护表**：把 `提示词模板`、`模型数据`、`检索增强生成` 这类复合词整体当 token，避免分词器切错。术语放不下时按子术语拆（提示词 / 模板），而不是拆成单字。

### 字号：跟着方框走，不设强制下限

- 原书图内字号常常只有 6~7pt，这是正常排版值。
- **不要**把"最小 7.5pt"当硬目标：中文比英文占宽，硬推字号会让 3 个汉字塞进 2 字宽的框，只能断行并溢出。
- 正确顺序：从原文字号起 → 若放不下就逐档收缩 → 到 4.6pt 左右为止。宁可字略小，不要溢出。
- **宽度和高度都要检测**。只查宽度会漏掉最难看的一类问题：译文行数不变但每行更高，
  总高超出方框，上下各溢出一半、字被裁掉。实测这一条占了全部返工的一半。

```python
# 正确顺序：先压行距（下限 1.14），再缩字号
PITCH_MIN = 1.14
pitch = 1.22
if len(lines) * fs * pitch > bh:
    pitch = max(PITCH_MIN, bh / max(1, len(lines) * fs))
while len(lines) * fs * pitch > bh + 0.5 and fs > 4.5 * zoom:
    fs -= 1
    lines = wrap_by_width(cn, ImageFont.truetype(path, fs), limit)
    pitch = (1.22 if len(lines) * fs * 1.22 <= bh
             else max(PITCH_MIN, bh / max(1, len(lines) * fs)))
```

报告里 `over_w`（宽度超出%）和 `over_h`（高度超出%）都 >0 才算合格；
`over_h > 6%` 报 `OVERFLOW`。

### 有些框就是放不下：`KEEP` 比硬塞好

三类必须原样保留英文（渲染器标 `KEEP`，交付说明里列出）：

| 类型 | 判据 | 原因 |
|---|---|---|
| 窄条 | `bw < 60pt` 且明显窄高，译文需 3 行以上 | 纵轴标签、图例一条，中文换行就糊成一团 |
| 迷你框 | `bw < 12pt && bh < 12pt` | 坐标轴刻度、单位符号，连一个汉字都放不下 |
| 太矮 | `bh < 4.6pt × 1.15 × 需要行数` | 高度决定性地不够，缩字号到 4.6 仍然溢出 |

实测一本 109 图的书，`KEEP` 有 109 个块（约 19%），全部是图例条和刻度；
硬塞中文的那些在目视检查里全是糊的。**宁可留英文，也不要糊。**

### 外扩要克制

给"允许轻微外扩"设上限：**取框宽的 6%，且不超过 0.9pt/侧**。固定加宽 1.6pt 对 11pt 的窄框相当于放宽 28%，会出现"以为放得下、实际溢出"。

### 竖排只在必要时用

只有当译文 ≤2 字、且方框明显窄高（高 > 2 倍宽）时才竖排。多字竖排会变成一根长条，把图形关系搞乱。

### 每张图渲染后都看一眼

`OVERFLOW` / `MISSING` 清零只说明"没有硬错误"，排版丑不丑还得眼睛看。重点抽查：多行标签、极窄框、连线旁的小注释。

## 呈现层：让成品"看着专业"（不是"能读"）

内容对了不等于好看。这一节处理的全部是**版面观感**问题，它们不会让 audit 报错，
但用户一眼就能看出不对劲。踩坑细节见 `references/pitfalls.md` M 组。

### 三条铁律

**1. 章节必另起一页，但别用空段落。**
```python
if not first_block:
    p.paragraph_format.page_break_before = True   # 挂在章标题段落上
```
用「空段落 + `<w:br type=page>`」会多出一整页空白。

**2. 正文密度：行距 1.5、段后 6pt。**
10.5pt 正文配 1.62 行距会显得松散空洞。1.5 是中文技术书的舒适区。

**3. 原书没有的元素，默认不加。**
"图内文字对照""代码逐行注释""术语小贴士"这类加料，一旦覆盖几十页，
每页底部都拖一条小字，整本书的阅读节奏就断了。真要做，做成 `SHOW_XXX = False`
的开关，默认关。

### 分章生成 → 合并：四件事必须做

| 要做 | 不做的后果 | 做法 |
|---|---|---|
| 清掉各节 `w:pgNumType` | 每章页码从 1 重排，和物理页错位 | 合并后遍历 `doc.sections` 删除该元素 |
| 每节重写页眉 | 全书都印第一章页眉 | `is_linked_to_previous=False` + **append 之后**按 `sections[-1]` 写 |
| 表头 `tblHeader` 放在 `cantSplit` 之后 | LibreOffice 不认，跨页无表头 | 先 `keep_row_together` 再 `repeat_header` |
| **逐份转 PDF 再拼接**，而不是 docx 合并后转 | 表头/页眉在 PDF 里丢失 | `pymupdf.insert_pdf` + `set_toc()` 生成书签 |

最后一条特别值得强调：**docxcompose 适合交付 docx，但交付 PDF 应该走"逐份转 → 拼接"**。
每份按自己正确的排版渲染，保真度明显更好，还能顺手生成 PDF 书签目录。

**表格只给表头加 `tblHeader` 不够，每条数据行也要 `w:cantSplit`。** 否则一行刚好跨页时，
下一页只剩公式或说明的续行，指标名和阶段列全是空白，读者会以为表格坏了；`audit.py`
不会报这种问题。正确做法是建表时给所有数据行加 `cantSplit`，表头再单独加 `tblHeader`。
目视抽查不要只看表题所在页，还要看**下一页**是否出现无主语的续行。

### 整块的东西必须不可分页

侧栏（sidebars）、便签（callout/note）、表题+表、图+图注，都属于**一个整体**。
被分页从中间切开，读者会看到两个残框——这是用户最先指出来的问题，比字号不合
更显眼。实测一本 520 页的书有 100+ 处。

**三条要点**（细节见 pitfalls P9）：

1. 框内**每段** `keepLines`，除末段外全部 `keepNext`，整串才连贯。
2. **`python-docx` 的 `keep_together` 不落地** —— 实测 `pPr` 里没有
   `<w:keepLines>`，`<w:keepNext>` 还被写成 `val="0"`。必须直接写 OOXML，
   并**回读 XML 验证**。
3. 框的范围用 `start_idx = len(doc.paragraphs)` 精确记录；
   收尾时不要用 `reversed(doc.paragraphs)` 找最后一个非空段，那会越过框边界。

```python
def xml_keep(p, lines=True, nxt=False):
    pPr = p._p.get_or_add_pPr()
    def _set(tag, want):
        el = pPr.find(qn(tag))
        if want:
            if el is None:
                el = OxmlElement(tag); pPr.append(el)
            el.set(qn('w:val'), '1')
        elif el is not None:
            pPr.remove(el)
    _set('w:keepLines', lines); _set('w:keepNext', nxt)
```

**检测被切开的框，判据不能写错**：不能用「矩形贴顶/贴底」——正常开始的框也贴顶。
要判「本页底部有底色矩形 + 下一页顶部有**同色且宽度相近（±12px）**的矩形」，
才是同一个框跨页。交付闸门：`0 处`。

### 修 bug 时的分层原则

拿到一个排版 bug，先问：**修它会不会改变块的数量或顺序？**

- **不会**（孤立碎片、多余空行、字号、间距）→ 在 `build_docx.py` 呈现层修
- **会**（块分类、合并规则）→ 极度谨慎。块数一变，全书块号平移，
  所有译文 JSON 全部错位，要重映射（见 `remap_seq.py`）

实战教训：为一个孤立代码尾巴去改 `parse_layout.py` 的块分类，
导致 10 份文档的表格译文错位，回滚四轮才恢复。正确做法是在 `build_docx.py`
的 code 分支里判断"这是不是行内代码的孤立尾巴"，是就 `add_run` 并进上一段。

## 前置页：封面 / 版权页 / 目录（别走图块流程）

这几页在原书里大量使用**矢量装饰元素**，走通用图块流程必出事故：

| 现象 | 原因 | 处理 |
|---|---|---|
| 封面出版社 logo 位置一片空白 | logo 是白色填充路径（`fill=(1,1,1)`），靠白压白显形；裁剪渲染成白底白图 | 整页改文字排版 |
| 简目左侧横着几个巨大数字、章名被盖住 | 竖排章号是图形，按原始像素宽度插入 | 同上 |
| 目录页码全错 | 照抄了原书页码 | 用 `chapter_pages.py` 算中文版实际页 |
| 版权页糊成一坨 | 10 段连排无留白 | 按语义分三块 |

**封面还必须单独检查两件事**（pitfalls P8）：

- **不得出现「第　章」**。`front_open` 若复用章节页渲染函数，会无条件拼
  `第 {num} 章`；封面没有 `num`，就印出「第　章」。封面要单独走
  `add_cover()`，前置内页走 `add_front_head()`（只出标题+副标题+分隔线，
  不带任何编号）。
- **不得插入任何图片**。原书封面的 logo 是白色填充的矢量装饰，走图块流程会采到
  黑色轮廓，插进去就是两块大黑方块。交付前断言
  `len(page.get_image_info()) == 0`。

**结论：前置页整页交给专门的排版函数，不产生任何图片。**

```bash
$PY $S/chapter_pages.py                     # 先算出各章实际起始页
$PY $S/build_front_pages.py out/00_封面与版权.docx --meta=work/front_meta.json
```

`build_front_pages.py` 三个页各是一个函数（`cover` / `copyright_page` / `toc_page`），
可以只调其中一个；也可以 `import` 进项目自己的构建脚本：

```python
import sys; sys.path.insert(0, '<技能 scripts 目录>')
from build_front_pages import front_pages
front_pages('out/00_封面与版权.docx', {
    'book_title': '大语言模型如何工作',
    'en_title':  'How Large Language Models Work',
    'authors':   ['Edward Raff', 'Drew Farris', 'Stella Biderman'],
    'press': 'MANNING', 'press_sub': 'SHELTER ISLAND',
    'copyright': ['段落1', '', '段落2', ...],   # 空字符串 = 分块
    'toc_title': '内容提要',
    'toc': [['1', '全景图：大语言模型是什么', ''], ...],   # 页码留空 = 自动填
})
```

`toc` 的页码留空字符串时，自动从 `work/chapter_pages.json` 读取实际页码；
写死原书页码是最常见的错误来源。

### 目录页码的正确顺序（顺序错了页码就是错的）

```
各章 docx → 逐份转 PDF → chapter_pages.py → build_front_pages.py → 合并 → 出整本 PDF
```

页码依赖各章 PDF 的实际页数，所以**必须先转 PDF 才能算准**。改完任何一章都要重跑这段。

### 排版要点

- **封面**：右对齐骨架 —— 中文大标题（30pt 加粗蓝）→ 英文斜体副标题 → 细分隔线
  → 作者（字距 `w:spacing=12`）→ 右下角出版社（字距 100）
- **留白用空段落 + 固定 `line=14pt`**，比 `space_before` 好控
- **目录行用制表位**（`Cm(1.35)` 左对齐章名 + `Cm(TEXT_W)` 右对齐页码），
  不要用空格补，否则 9 个页码落不到同一条竖线
- **版权页分块**：联系信息 / 法律声明 / 出版信息，块间 `before=14`
- 前置页也要挂**页眉页脚**，否则 `layout_check.py` 会报页眉样式不连续

## 译文 JSON 结构

```json
[
 {"type":"chapter_open","num":"3","title":"中文章名","orig_title":"English Title",
  "toc":["…"],"quote":"中文引语","quote_by":"——作者（英文名）","intro":"导言"},
 {"type":"h2","text":"…"}, {"type":"h3","text":"…"},
 {"type":"p","text":"支持 **粗体** 与 `行内代码`"},
 {"type":"list","items":["…"]}, {"type":"numlist","items":["…"]},
 {"type":"figure","key":"p103_f0"},
 {"type":"table","head":["…"],"rows":[["…"]]},
 {"type":"code","text":"多行代码用 \\n 分隔","notes":[["// 英文注释","中文"]]}
]
```

连续的 list/numlist 在 layout 里可能是多块，译文合并成一块即可（校验会折叠）。

## 翻译约定

- **术语统一**：同一英文术语全书一个译法，首次出现给「中文（English）」，之后只用中文。开工就建术语表，最后放附录。
- **代码不译**：标识符、API 名、类名保留英文（`applyOperator()`、`StatefulSource`、`instance`）。
- **图内标签要短**：`Van` → 「货车」而不是「厢式货车」，否则字号会被压到不可读。
- **图内标签按词断行**：中文按词切（jieba + 术语保护表），绝不按字切。宁可缩字号，也不要把「提示词模板」拆成「提示/词模/板」。
- **英文标识符不译**：图里的模板变量（`{game}`、`{question}`）、API 名、`LLM`、`Spring AI` 保持英文。
- **极窄框可换短说法**：框宽 <18pt（约 2 个汉字）时用同义短式（门控→门、输出→出），并在交付说明里列出来让用户复核。
- **保留原语气**：口语化原书（Grokking 系列）别改成教科书腔。
- **原书笔误按原样保留**。包括作者故意展示的模型坏输出：`<think>` / `<reasoning>`
  标签、公式、错算、重复啰嗦的「过度思考」都要照译，不要替模型改对。
- **长输出示例要整段译完**。模型原始回答常被解析成几十个段落、列表和 callout，
  逐块翻译时保持标签与分段；只有标点的碎片块（如 `。`）应并回上一语义片段，
  不能单独输出一个标点，否则覆盖率检查会把它判成未翻译。
- **表格误判不换块类型**。流程图被解析成表格时，可在 `table` 块内按语义重建列与行；
  不要改成 `figure`，块类型一变，块序列校验和后续译文索引都会失配。

## 交付前必查

**技术层（脚本能查）**

1. `audit.py`（逐章）— 块序列零差异、图片数一致、无 DPI 警告
2. `audit_book.py`（全书一次）— 块序列 / 漏译 / 代码含中文 / 图内溢出 / 图片数
3. 渲染报告 — `MISSING`、`OVERFLOW` 都必须为 0
4. `cov.py` 全章 — **多余键为 0**、缺项为 0
5. `find_blank.py` — 合并后无空白页
6. `check_cov.py --all` — 每份文档「多余 0 / 缺 0 / 图内缺 0」
7. 漏译扫描 — 找「整段不含中文」的块（排除代码、专有名词、URL、引号字面量）
8. **整块完整性** — 侧栏/便签没有被分页切开：
   「本页底部有底色矩形 + 下一页顶部有同色同宽矩形」= 0 处
9. **前置页无编号** — 全书 `'第　章' not in page_text`；
   封面 len(page.get_image_info()) == 0、封面页无页码
10. **合订本图片没丢** — 合订 docx 的 inline_shapes 数 == 图块总数，
    且 len(set(md5(part.blob))) 与之相同（rId 撞车会让 63 张图挤在 8 个关系上）；
    合订 PDF 的 sum(len(p.get_images())) 也要等于图块总数（见 R1/R2）
11. **目录页码与实际一致** — 抽查 5 条，目录写的页 == 该书签的实际页；
    算页码的集合必须含封面（见 R4）
12. **图内彩色底无白块** — 彩色圆/色块上的中文标签周围不得有白色方框
    或英文残影（见 R5）

**排版层（`layout_check.py` 一次跑完，必跑）**

7. `layout_check.py out/pdf/全书.pdf` — 五项指标：
   - 页码错位页数 **必须 0**
   - 页眉样式数 **必须 >1**（说明分组页眉生效）
   - 空白过半页数（章末页允许，正文中部出现就是问题）
   - 整页只有一行的页数 **必须 0**（孤立碎片代码）
   - 基线比 1.05~1.28（换算 Word 行距 1.4~1.6）

> 这一层专治 **"audit 全绿但用户说排版差"**。内容校验查不出页码重置、
> 页眉吞掉、多余的一行行小字、大片留白。详见 pitfalls M 组。

**目视层（脚本查不出，必须看）**

8. **代码缩进**：挑 2~3 个有嵌套的代码块，确认层级看得出来（不是全顶格）
9. **代码换行**：必须是真 `<w:br/>`，不是被压成一行
10. 章首页是否**另起一页**（用 `page_break_before`，不要用空段落+分页符）
11. 表格跨页后**续页有表头**（`<w:tblHeader>` 必须在 `cantSplit` 之后）
12. **每个侧栏/便签框**是否完整落在一页内（抽 3–5 个，尤其页尾那几个）
13. 有没有"自己加戏"加出来的东西（图内中英对照行、重复的代码清单）——
    原书没有的元素默认不加

**交付说明必须诚实列出的三类"做不到"**

13. 图内文字若被画进**栅格像素**（matplotlib 标题）→ 无法无损中文化，列出具体页码
13b. **`KEEP` 的图内文字**（窄条 / 迷你框 / 太矮，见上文）→ 列出页码与块数，
   说明这些位置保留英文原样，并解释原因（典型：图例条过窄、坐标轴刻度）
14. **代码放大截图**类插图 → 已整图略去（避免与清单代码重复），说明处理方式
15. 原书笔误、前后不一致 → 按原样保留，不擅自"修正"

## 出版社排版特征速查（判断书属于哪一类）

拿到 PDF 先跑 `page.get_text('dict')`，看一页的字体与颜色分布，十秒判断类型：

| 特征 | Manning（两色排版） | Grokking（手绘示意） |
|---|---|---|
| 正文字体 | `NewBaskerville-*` 10pt 衬线 | 无衬线为主 |
| 标题字体 | `FranklinGothic-*` | 手写体 |
| 代码字体 | `JetBrainsMonoNL` 8pt | 视书而定 |
| 结构性颜色 | 侧栏 `(0.969,0.961,0.910)`、清单条 `(0.438,0.652,0.801)`、表头 `(0.277,0.418,0.523)` | 彩色填充块 |
| 图内文字 | `ArialMT`，**在文字层**（栅格只有线稿） | 手写标注，部分在像素里 |
| 特殊块 | 侧栏（sidebar）、边注（DEFINITION/NOTE）、代码放大截图 | 对话气泡、流程箭头 |
| 版式陷阱 | 侧栏、边注、列表跨图表、脚注式小标题 | 图片碎片化、标签极窄 |

两色书的关键判据：**结构性颜色是固定三个值**，用颜色就能区分侧栏/清单条/表头，
比几何判据可靠得多。

## 长书进度管理（14 章 + 附录的老实做法）

一本 Manning 书的实际节奏，供估算：

| 阶段 | 耗时占比 | 说明 |
|---|---|---|
| 摸版式 + 调解析器 | 25% | 最值得投入。这里省 1 小时，后面返工 5 小时 |
| 逐章翻译 | 55% | 真正的体力活，一章 150–450 个字段 |
| 图内中文化 | 10% | 图少，但每张都要看溢出 |
| 合并 + 体检 | 10% | 收尾，容易被忽略但必须做完 |

**每章的固定动作（不要跳步）**

```
export_pairs → 分片写 tx_<包>.py → cov.py（多余必须 0）
→ freeze_tx.py → apply_fill.py（缺 0）→ qa_pack.py（问题 0）
→ build_figtrans.py → render_chapter.py（异常 0）→ do_chapter.py
```

这 8 步跑完一章才算完。中间任何一步报错就停下修，不要"先攒着以后一起修"——
攒到后面会分不清是哪一章引入的问题。

**全书收尾**

```
check_all.py        全章一张表，必须全 OK
merge_book.py --order  先确认清单
merge_book.py       合并（分节→append→设页眉）
convert_pdf.py      转 PDF
find_blank.py       必须「无空白页」
+ 目视抽查 3–5 页    页眉、页码、代码缩进、图注
```

**什么情况下可以停下来问用户**

- 图内文字被画进栅格像素（无法无损中文化）→ 列出页码，说明只能重绘图
- 原书内容自相矛盾或明显笔误 → 按原样保留，交付时说明
- 参考文献这类专有名词密集区 → 说明只译说明段落、条目保留原文

除此之外不打断，直接做完。

## 交付范围与合订本

默认范围：**前置部分（封面/序言/前言/致谢/关于本书）+ 正文所有章节**。

**封面是独立一份，不是 ront 文档。** 用 kind: 'cover' 单列一项排在合并清单最前，
且必须在算目录页码**之前**就存在（封面页数会让正文整体后移，见 R3/R4）。
原书书名常是整幅栅格位图 + 金色标题 + 色块，无法无损中文化 → 按视觉骨架用文字重建
（w:shd 段落底色做色块 + 大字号标题），**封面页不挂页眉页脚、不插任何图片**。

- **出版社广告、相关书目、liveBook 推广页不译**：不是书的内容，译了只会让成品显得杂。
- **原书索引不直接照译**：索引页码绑定英文版排版，中文版重排后全部失效。要么不做，
  要么用中文版实际页码重建一份新索引；只译条目而保留旧页码是最糟的折中。
- 交付时明确说明范围，不要用「全书完成」掩盖未做的索引/广告页。
- 同时给 **分章 docx + 全书合订 docx + 全书 PDF**：分章便于修订，合订本便于阅读。
  合订 docx 用 `docxcompose`；合订 PDF 用各章 PDF 顺序 `insert_pdf` 并 `set_toc()`
  写书签。页码、图表数要与分章合计核对，不能只信文件生成成功。

## 细节参考

- `references/pitfalls.md` — **踩坑清单**（A–F 图重书 / G–L 长书 /
  M 排版观感 / N 骨架流水线 / O 图内渲染真缺陷 / P 前置页 / Q 续译与交付边界 /
  **R 合订本保真·封面重建·彩色图内文字**），
  动手前先扫一遍，尤其 **A17 / F7 / F9 / G1 / G7 / H4 / I1 / J1 / M1 / M7 / M9 /
  N2 / N3 / O1 / O3 / O4 / P1 / P3 / P4 / P8 / P9 / Q1 / Q3 / Q7 /
  R1 / R2 / R3 / R4 / R5**
- `references/layout-heuristics.md` — 版式解析判据（字体分类、图区聚类、段落合并、
  中文竖排、**第 12 节 Manning 2025 单色版实测参数**：字体语义表、两种结构色、
  竖线分段合并的表格判定、章首页矢量项目符号分组）
- `assets/book.json.example` — 配置模板
- `assets/trans.schema.json` — 译文 JSON 完整示例
