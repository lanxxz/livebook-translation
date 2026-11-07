---
name: livebook-translation
description: 把带插图的技术书（PDF）整本翻译成中文 Word/PDF——图内文字就地中文化、代码提取为可复制块、表格还原成真表格、逐块校验与原书对齐。覆盖文字层矢量图（Grokking 手绘、Manning 两色版）、**栅格图（截图/彩色示意图，OCR 擦像素重写）**、**分散图元矢量图（544 页 Manning 商业书，按图注间版面窗口裁图）** 与长代码重书；含骨架文本流水线、分片翻译、解析变更后译文重映射、封面重建与整书合订、参考文献与中英对照索引。当用户要求翻译一本技术书/电子书（尤其 Manning、O'Reilly 类）、或要把 PDF 书籍做成中文版 Word/PDF 时使用。
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

### 第一步永远是：图内文字在哪一层？

**这两种书要走两套完全不同的流程，混用必翻车。** 别急着写解析器，先跑十秒判定：

```python
page.get_text('dict')     # 在图的 bbox 里能取到 span → 文字层书
page.get_image_info()     # 图区域 get_text 为空、只有一坨大 PNG → 栅格书
```

| | 文字层书（Manning 两色版等） | 栅格书（截图 / 手绘 / 彩色示意图） |
|---|---|---|
| 图内文字 | 矢量 span，可取坐标 | **像素**，只能 OCR |
| 中文化方式 | 按坐标重绘 | OCR → 擦像素 → 写中文 |
| 用哪个脚本 | `render_figs.py`（本技能自带） | 自写，见「栅格图内文字流程」 |
| 字号可控性 | 精确（有原始字号） | 只能从字高反推，误差 ±20% |
| 主要风险 | 断行、溢出 | **擦除伤到图形**（见 pitfalls T1） |

实测一本 374 页的书：80 张插图**全是嵌入式 PNG**，`get_text()` 在图里拿不到一个字，
`get_drawings()` 也只有外框。这类书 `render_figs.py` 一行都用不上。

**第三种：混合型书（233 页 Manning 2025 实测，见 X1）。** 同一本书里，
矢量流程图的标签是 `ArialMT` span（可取坐标），而 ChatGPT / Colab / Cohere /
Hugging Face 界面截图是嵌入式 PNG（字在像素里）。判定要**按页统计**
`get_image_info()` 与 `get_drawings()`，别只跑一页就下结论。做法是分流：
矢量图走 `render_figs.py` 重绘，栅格截图整图保留 + 中文图注，在交付说明列出
页码与原因；不要为「图上零英文」对密集界面截图做 OCR 擦除。

另有一个假象：探查脚本若写了 `if s['text'].strip()` 过滤纯空格 span，
会把正常英文显示成 `importopenai`、`careertoexploiting...` 这种粘连文本，
差点误判「文字层损坏」。**先算全书空格率（正常英文约 0.15）**，
正常就说明是自己的 span 拼接逻辑丢了空格（X2）。

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

**7. 校验脚本本身也会骗人，闸门要两条。** 实测踩过两次：
`convert.py` 只在块数**少于** layout 时报警，多写的块头被静默丢弃，块号整体错位一格，
而它的输出看起来完全正常；`check_cov.py` 的块号正则曾要求块号独占一行，
而实际块头是 `@@B 12 p   # p45`，于是一个块都没识别到却报「多余 0 / 缺 0」。

所以**覆盖率闸门至少两条，判据不同**：
`check_cov.py` 看块号集合（快，边写边查），`check_zh.py` 还核**块类型**、
**块数严格相等**、**空块**（慢，交付前必过）。两条都绿才算这一份做完。
一条校验报「多余 0 且缺 0 且总数 0」时，先怀疑解析器，不要高兴得太早。

## 三条流程，按书的形态选一条

| | 短书 / 图重（Grokking 类） | 长书 / 代码重（Manning 464 页） | **中等 / 文档多（12–20 份）** | **栅格图多（截图 / 彩色示意图）** | **超长全书（544 页 / 195 图 / 245 清单）** |
|---|---|---|---|---|---|
| 规模 | 11 章 336 页 | 14 章 + 附录 464 页 | 12 份文档 248 页 / 18 章 296 页 | 10 章 374 页 / 80 张 PNG 图 | 15 章 + 3 附录 544 页 |
| 难点 | 图内文字排版（346 图） | 块结构归属 + 超长工作量 | 文档切分、块号对齐、逐份流水线 | **擦像素不伤图形** + OCR 质量 | **分散图元图区判定** + 代码清单合并 + 合订耗时 |
| 流程 | 「五步流程」 | 五步 + 「长书分片流程」 | **「骨架文本流水线」** | 骨架流水线 + **「栅格图内文字流程」** | 骨架流水线 + **「版面窗口裁图 + SDK 管线」** |
| 译文存放 | `chN_trans.json` 手写 | `tx_<包>.py` 分片→固化 | `work/<doc>_zh.txt` 纯文本逐块 | 同左（`_zh.txt` + `_figzh.txt`） | `work/<ch>/zh_tpl.md` + `{{CODE:x}}` 占位符 |
| 校验闸门 | `audit.py` | `cov.py`（多余键 0） | **`check_cov.py` + `check_zh.py` 双闸门** | 双闸门 + **渲染报告 MISSING/OVERFLOW/KEEP** | **四数一零**：图片数/代码框数/表格数/合并数=0 |
| 适合谁 | 图特别多 | 一本厚书一口气做完 | 章多、想并行、想分次交付 | 图内文字在像素里 | 500 页以上商业出版书 |

**怎么选：**

- 先判「图内文字在哪一层」（见上一节）。**这一步决定后面所有图相关工具的选择。**
- 图多、章少、文字层 → 五步流程，重点在图内排版
- 一本书 400+ 页、代码密集 → 长书分片流程，重点在键号纪律
- **12 份以上独立文档、想逐份交付/并行/中断可续 → 骨架文本流水线**（下面第四节）
- **80+ 张栅格图 → 骨架流水线 + 栅格图内文字流程**（图内文字部分单独做，见第五节）
- **500 页以上、插图是分散图元、代码清单上百 → 骨架流水线 + 「超长全书管线」**（见第六节）

第三种流程是前两种的简化版：不写 Python 分片文件，直接写「带块号的纯文本」，
由 `convert.py` 解析成 JSON。优点是**人和代理都能直接编辑**、出错只影响一份文档、
可以用 `build_doc.py <doc>` 单份重跑。

**第四种不是新流程，是第三种 + 一套替换掉的图内环节。** 正文部分完全一样；
只有「图内文字 → 渲染」这一段要换成 OCR 路线，且它是整本书最大的返工来源
（实测图内擦除逻辑重写了 9 次，见 pitfalls T1）。

**第五种：超长全书 + 分散图元 + 编辑器 SDK 管线。** 544 页 / 158k 词 / 195 图 / 245 个
代码清单这一量级，与前四种的差别在三个地方（详见 pitfalls U 组）：

1. **图区判定用「图注间版面窗口」而非图元聚类**。商业出版书的插图常由几十个分散图元
   构成（方框、箭头、圆间距超 16pt），聚类法要么把图切碎、要么把相邻图并进来。
2. **Word 生成走编辑器 SDK 的 Markdown 通道**。与 python-docx 逐段拼是两套坑：
   图片块必须独占批次（否则静默丢失）、代码块后必须补段分隔符、keepNext 有插入时机要求。
3. **合订本由分册同源重建**，构建耗时以半小时计，所以分册先行交付。

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
- `check_page_coverage.py <pdf> [docs.json]` — **原书页覆盖审计**：找出有正文但未进入
  docs 范围的页（本项目漏掉第 108 页的教训，见 V1）
- `check_merged_images.py <docx>` — **合订图片关系审计**：inline_shapes / 唯一 rId /
  media 三数必须相等，抓同页多图共用 key 的静默重复（见 V2）
- `layout_check.py <pdf>` — **排版体检**：页码连续性、页眉逐章、留白、孤立碎片、行距
  （audit 查内容，它查呈现；两套都要过）

**骨架文本流水线专用（第三种流程）**

- `slice_layout.py` — 按 docs.json 把整本 layout 切成每份文档的 layout/dump/figtexts
- `mk_skeleton.py <doc>…` — 生成 `_skel.txt` / `_figskel.txt` 待译骨架
- `convert.py <doc>` — 把 `_zh.txt` / `_figzh.txt` 解析成 `_trans.json` / `_figtrans.json`
- `build_doc.py <doc>…` — 单份文档一条龙：convert → 渲染图 → 出 docx → audit
- `build_book_pdf.py [--pdf-only|--docx-only]` — 合 docx + **逐份转 PDF 拼接** + 书签
  （保真做法；`--pdf-only` 时只出 PDF）
- `check_zh.py [<doc>…|--all] [-v]` — **第二道闸门**：块数严格相等 + 块类型逐块比对
  + 空块 + 图内缺译。`check_cov.py` 抓不到的错位靠它抓（见 pitfalls S1）
- `realign_zh.py <doc> --dry` — **块号错位后的译文抢救**。先诊断（类型/重复/缺号），
  再 `--rebuild [--by-position] [--fill f.json]` 按骨架重建，或
  `--by-signature` 按「类型+正文首 24 字」把旧译文匹配到新块号（解析规则变更后用，
  见 pitfalls S3）

**规模化补强（X 组，混合型书 / 并行交付 / 内容 QA）**

- `gen_figzh_map.py [--map m.json] [--keep k.json]` — 全书唯一 EN 短语一次生成
  各分册 `_figzh.txt`，KEEP 写英文原文（X9）
- `add_pdf_outline.py [合订PDF]` — 章 + 小节两级书签，必须接进重建链（X11）
- `qa_translation.py [--out 报告.md]` — 译文内容 10 类量化自查，**命中多为误报，
  逐条判读**（X13）

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
| `work/<doc>_zh.txt` | `@@B <块号> <类型>` 开头，后面直接写中文；块号与类型都必须与 `_skel.txt` 一致 |
| `work/<doc>_figzh.txt` | `@@FIG <key>` / `@@T <id>` / `ZH <中文>`（也可以直接写 `_figtrans.json`） |

各类型写法（`convert.py` 就是按这个解析的）：

```
@@B 0 chapter_open
TITLE: 中文标题
NUM: 3
TOC: 本章内容一
INTRO: 导言

@@B 1 h2
3.1 小节标题

@@B 2 p
整段中文，支持 **粗体** 与 `行内代码`

@@B 3 list
- 列表项一
- 列表项二

@@B 5 table
ENCAP: 表 3.1　表题
HDR: 列一 | 列二 | 列三
ROW: 值 | 值 | 值

@@B 6 panel
[h] 小标题
[p] 段落
[code] 原样代码

@@B 7 figure
ENCAP: 图 3.1　图注

@@B 8 code
（code 块留空，代码从原版面直接取）
```

**写块头必须照抄骨架的类型**。最常错的一处：`figure` 与紧随其后的 `p` 是两个独立块，
凭语义把它们并成一个，后面所有块号平移一格（pitfalls S1）。

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

### 这套流程的四条纪律

1. **块号与类型只信 `_skel.txt`**。写完立刻跑 `check_zh.py <doc>`：块数不等、
   类型不符、空块，都会指名到块号。`build_doc.py` 报"块序列不一致"时已经晚了
   ——那时 `_trans.json` 已经生成，只是内容串位。
2. **一次只重跑一份**。`build_doc.py <doc>` 是幂等的，坏了只影响那一份。
3. **code 块留空**。代码从原版面按坐标重建，手打会丢缩进。
4. **解析器一旦开工就冻结**。改一条合并规则会让全书块号平移，
   已译的内容要用 `realign_zh.py` 抢救（pitfalls S4）。

脚本放哪都行：`slice_layout.py` / `build_doc.py` / `check_zh.py` / `realign_zh.py` /
`merge_book.py` / `build_book_pdf.py` 会**向上找含 `book.json` 或 `docs.json` 的目录**
当项目根，所以既可以放在项目根，也可以放在 `<项目>/scripts/`。

## 同版式复用与整书合订（W 组，450 页 / 25 份分册实战）

工作区里若有同出版社、同页面尺寸的已完成项目，**先整套复用脚本再改判据**，
能省掉解析器调试的大头。但字体族名、页眉阈值、章首页判据、项目符号字符
这四类常量**必须按新书实测重设**（见 pitfalls W1–W5：字体差 `Std` 后缀就让正文全被判成图内文字；
页眉阈值 60 会吞掉 y≈51 的代码首行）。

### 三条合订硬约束（都是"生成成功但结果是错的"）

1. **前置页尺寸必须等于分册**。`docxcompose` 以 master 的节设置为准，
   自建前置页误设 16×23cm 会让所有 A4 分册按小页面重排，400 页膨胀成 628 页。
   合订前读任一分册 `sections[0]` 的宽高与边距，复制给前置页并断言一致（W14）。
2. **目录页码别用文本定位**。目录页自身印着全部章名，按标题搜索会把所有章
   误定位到第 2–4 页。逐份拼接时改用 `前置页页数 + Σ各分册 PDF 页数` 累加回填，
   并验证 `总页 == F + Σ分册 + 索引页`（本次 406 == 4 + 400 + 2）。
   两轮校准照做，只是把「定位」换成「累加」；目录文字直接用页眉 label，别重复拼标题（W15）。
3. **BLAS 线程要限死**。`render_figs.py` 偶发 `OpenBLAS error: Memory allocation
   still failed...` 会静默退出、整章插图消失，而 `build_doc.py` 仍产出缺图 docx 且
   `audit.py` 只报块序列一致。在 `build_doc.py` 的 `run()` 子进程 env 固化
   `OPENBLAS_NUM_THREADS=1` / `OMP_NUM_THREADS=1`，并用 `check_merged_images.py`
   核对图片数（W13）。

### 图注是"一组行"，裁完还要在 Word 里补回来

Manning 图注常由 `Figure 编号` + 同行长描述（y0 更小）+ 两行续文（字体换成 Mono Bold）
组成。只按 Figure 行裁会留英文残影；按**整组**裁剪并把英文全文存进 figure 块的
`caption`，再在 `build_docx.py` 的 figure 分支补中文图注段落 + 图片段 `keepNext`
（否则中文版没图注，或图在页底、图注翻页）。详见 W6/W7。
数据表按列排版导致网格错乱时，能重建就改真表格，不能重建就改原表图 + 中文表题，
**并记得在 `book_figtexts.json` 补一个 `blocks: []` 的 key**，否则渲染器不产图（W9）。

### 规模化逐章推进的两个省力做法

- **图内译文用唯一短语映射表**：`Counter` 导出唯一 EN，写「精确映射 + 长句前缀兜底 +
  默认写英文原文(KEEP)」的小脚本。ch04 84→129 条、ch10 125→180 条，比逐条手写快数倍；
  KEEP 分层（类名/网址/许可证/示例查询/数据表留英文，流程标签与叙述注释中文化），
  按章记录 OK/KEEP 比例写进交付说明（W11/W12）。
- **紧凑原文**：从 `_skel.txt` 导出 `@@B n type` + EN，code 块只写 `[CODE nL]`；
  每份固定动作「评估规模/空块 → 紧凑原文 → 双闸门 → build_doc → 转 PDF →
  图片三数 → 目视一张 → 更新 PROGRESS/日志」。跨会话续做靠 `PROGRESS.md` +
  每日日志，进度以磁盘产物为准（W17）。
- `check_cov.py` 的「图内多 N（提示）」不必清零，那是给免译符号块也写了译文；
  必须清零的只有「多余块号」（W16）。

交付说明固定写 7 类已知限制：栅格截图、数据表、KEEP 标识符、编译性中文图注、
原书笔误、索引改造、版权性质。术语表开工就建，收尾时自动解析生成中英索引（W19）。

## 混合型书与规模化交付（X 组，233 页 / 14 份分册实战）

《Data Analysis with LLMs》10 章 3 部分、43 图 / 157 图内文字块 / 225 代码块，
9 章由并行子代理同时翻译。这一节补 W/V 组没覆盖的三件事：**混合图处置、
并行翻译的组织、以及工程闸门全绿之后的内容级自查**。细节见 `pitfalls.md` X 组。

### 1. 解析器：章首页与清单是两类高频误判

- **章首页下半页还有正文**。`main()` 里 `is_chapter_open` 为真就只输出一个
  `chapter_open` 块，会把 1.1 标题、正文和诗句全吞掉。让 `parse_chapter_open`
  返回 `_rest_y`（第一个 heading 的 y−3），再
  `page_blocks(page, pno, skip_y0=rest_y)` 补出下半页；`skip_y0>0` 时把
  `graphic_regions` 置空，避免装饰章号被聚成假图。导言多段要让 `convert.py`
  把 `INTRO` 收成列表，`build_docx.py` 按 `\n` 拆段（X3）。
- **清单 / 便签被聚成图**。Manning 清单 = `Listing X.Y` 标题 + `CourierStd`
  代码行 + 圈码旁注，聚类会整块吸成 figure，代码就不可复制。图形区后处理加
  「含 Listing / ≥2 行代码 / TIP-WARNING / 圈码字体 → 整块回收（旁注行剔除）」，
  以及「宽 >240 且 ≥2 行正文 → 回收」两条规则（X4）。
- **侧置图注裁不掉时只擦不写**。图注与图上文字混成一行会让 `CAP_RE.match`
  失效，整段英文留在图里与中文图注重复。在 `render_figs.py` 的块循环里，
  KEEP 判定之前加 `caption-erased`：长图注采底色擦除、不写字（X5）。

### 2. 并行子代理逐章翻译：prompt 六要素 + 分段追加

9 章并行全部一次通过双闸门，关键是**自包含 prompt**：① 项目根 + 骨架路径 +
块数；② 必读 `TRANSLATION_GUIDE.md`、本章 `_skel.txt`、已完成样板 `ch01_zh.txt`；
③ 格式摘要（code 留空、figure 只写 `CAP:`、清单标题全角空格、`■` 逐行）；
④ 块号纪律（只信骨架、不合并 figure 与紧随的 p）；⑤ 保留英文的类别；
⑥ 自检命令（`check_cov.py` + `check_zh.py`）+ 禁止写 `_figzh.txt`（由统一映射表生成）。

150+ 块的长文件必须允许分段追加：先 `Write` 前 40~50 块，之后
`open(p,'a',encoding='utf-8')` 追加，**禁止第二次 Write 覆盖全文**。
代理自检只当第一道过滤，收尾由主流程统一跑双闸门与漏译复核（X8）。

### 3. 图内译文：一个通用脚本生成全部分册

不要每章写一个 `gen_figzh_chNN.py`。用 `scripts/gen_figzh_map.py`：
导出全书唯一 EN 短语 → 「精确映射 + KEEP 正则 + 默认写英文原文」一次生成
14 份 `_figzh.txt`（本书 100 条中文化 / 57 条 KEEP）。三个易错点：

- `render_figs.py` 判 KEEP 是 `cn == en`，所以 **KEEP 要写英文原文**，不是字面
  `SAME`（后者只有 `fig_raster.py` 认）；写纯空白会被判 `MISSING`。
- 映射键要 `unicodedata.normalize('NFKC', en)`，否则 `ﬁ` 这类连字命中不了。
- 分层 KEEP：界面按钮 / 数据表字段 / 示例查询 / 工具名 / 极窄标签保留英文，
  流程标签与叙述注释中文化；OK/KEEP 比例写进交付说明。

### 4. 合订三修：页眉页脚、两级书签、下游一致性

- **docxcompose 合并后页眉页脚会全丢**：master（前置页）没有页眉，
  `append()` 之后所有节都套用空页眉，`layout_check.py` 报「页眉样式数 1」。
  修法只能是「分节 → append → 逐节 `set_section_chrome`（页眉文字 + PAGE 域）」，
  再清各节 `w:pgNumType` 让页码连续；封面页码在 PDF 层 redact 擦掉（X10）。
- **两级书签**：`scripts/add_pdf_outline.py` 从各分册 `_trans.json` 的 h2/h3
  标题，在该分册的合订页区间内定位，写「章 + 小节」书签（本书 15+185 条），
  校验页码回跳 0 / 越界 0。**必须接进重建链**，否则下次重建又退回 15 条（X11）。
- **改任一分册都要刷新整条下游链**，手工逐步跑容易留下旧 PDF 与旧书签：

```text
14 份分册 docx → 逐份转 PDF → 删旧合订 PDF → build_final_book.py
→ 擦封面页码 → add_pdf_outline.py → 目录页码 5 条抽查
```

`build_final_book.py` 的目录两轮校准依赖各分册 PDF 的实际页数，
**分册 PDF 不刷新，目录页码就是错的**（X12）。

还有两类「生成成功但结果是错的」的数据残留：清防伪追踪码时
`re.sub(r'\s*[A-Z]{2}\s+\d{3}\s+\d{4}\s*', ' ', t)` 的首尾 `\s*` 会**跨行吞掉
`@@B` 块头**，必须做 layout / slice / skeleton / 译文四处同步删块与重编号（X6）；
PDF 提取的 NULL 字节藏在 JSON 的 `\u0000` 转义里，`json.dumps()` 检测会漏，
要递归遍历字符串对象清 C0/C1/代理项（X7）。

### 5. 工程全绿 ≠ 译文没问题：内容级自查单独做一层

用户问「翻译有没有问题」时，再跑一遍双闸门没有意义。用
`scripts/qa_translation.py` 逐块对齐 `*_layout.json` 与 `*_trans.json`，做
10 类扫描（长度比 / 数字 / URL / 圈码 / 编号格式 / 相邻重复 / 术语变体 /
无中文块分类 / 否定 / 比较），再每章抽 1 段人工逐句细读。

**量化命中几乎全是误报，必须逐条写清原因才可信**：`1,000`→「一千多」、
`680,000`→「68 万」是正确换算；URL 未匹配多是正则吞了句末点或 PDF 断字被修复；
双重否定 `does not do anything that you cannot do via the web interface` 译成
「这段代码能做的事，用 Web 界面也都能做」是地道处理；`as well as` 会被比较级
正则误判。96 处「整块不含中文」也要分类（模型输出 / SQL / 产品名标题 / 参考文献），
不是漏译。把「为什么这些不是问题」写进 `译文自查报告.md`，与工程层的
`质检报告.md` 分开（X13）。

术语的**语境变体要写进规范**：如 `token` 在计费公式与 API 参数里保留英文、
一般叙述写「词元（token）」，这是有意选择，别强行全书替换 200 处（X14）。

## 全书范围审计与新增页（V 组，交付前最后一道门）

来自 368 页 / 119 图 / 6 表 Manning 两色版的实战。**这一组解决的是“所有闸门都绿，
但书仍然是残的”**——块号、图片数、空白页全通过，仍可能整页漏译或图文串行。

### V1. “覆盖率 100%”只覆盖已解析的页，不覆盖 docs.json 的页范围

本项目 `check_cov.py` / `check_zh.py` 16 份文档全绿、PDF 无空白页，但原书第 108 页
**整页未进入任何 docs 条目**：第 4 章结尾断在“每个部门”，整节小结消失。
根因不是解析或翻译，而是 `docs.json` 的 `from/to` 边界错了。

交付前必须单独跑一次**原书页覆盖审计**：

```bash
$PY $S/check_page_coverage.py 原书.pdf docs.json
```

判读：

- 输出「有正文但未覆盖」的页 → 逐个归类为：正文页 / Part 扉页 / 原书索引 / 广告页。
- 正文页：补进对应文档的 `from/to`，必要时给 layout 追加块。
- Part 扉页：单独做 `kind=part` 的一页文档，不要硬塞进相邻章。
- 原书索引：页码已失效，改成中英术语索引（见 V7），不要照搬。
- 空白页（字符数 <30）可以忽略，不能因此把整段范围跳过不查。

**另一条人工判据：每章末页必须出现“小结/Summary”，或下一页就是下一章。**
只有块号对齐、没有这条例行检查，就会漏掉整章总结。

### V2. 同页多图必须按页内序号分配 key

`convert.py` 若用 `p{page}_f{b.get('figi', 0)}`，而 layout 的 figure 块没有 `figi`，
**同一页两张图会共用 `p121_f0`**。症状极具欺骗性：

- `inline_shapes` 数 = 图块数（119），页数、文件大小都正常；
- 实际唯一 `rId` 只有 98，同一张图被重复插入两三次；
- 报告不报错，目视只看第一张也发现不了。

修正：解析/转换时维护 `figi_by_page`，**figure 与 table 都自增页内计数**：

```python
_pg = b['page']; _fi = figi_by_page.get(_pg, 0)
figi_by_page[_pg] = _fi + 1
key = f'p{_pg}_f{_fi}'
```

交付前跑：

```bash
$PY $S/check_merged_images.py 全书.docx
```

判据必须是三个数同时相等：`inline_shapes == 唯一 r:embed == word/media 文件数`。
只数 inline_shapes 等于没查。

### V3. 裁图边界不要固定外扩，图注要按文本块并集扩高

两个方向的裁切错误都很隐蔽：

1. **左右固定扩 26pt**：原书窄图右侧排版时，左边相邻正文会被裁进图片，
   成品出现一列文字残片（`st/ss/e/c-`）。应按图块与图内文本 bbox 的并集裁，
   左右只留 1–2pt 安全边。
2. **图注最后一行超出 fig bbox**：图片底部出现半行英文残影，或被下一节标题压住。
   图注可能由多个文本块组成，最后一个块甚至不在 figtexts 里。
   裁图下边界要取 **fig bbox 与全部图内文本 bbox 的最大 y1**，并额外留 5–8pt；
   图注译文必须与英文全文逐句核对，不能只译前 3 行。

### V4. 正文与图注串行的识别与修复

原书右侧窄图 + 图注跨栏时，提取器会把图注的尾部并进上一段正文，得到：

```
……确保表的演进仍然高效。 每个文件的记录数，从而把 图 10.5 展示了一种更理想的元数据
元数据遍历和数据文件 I/O 的成本降到最低。 布局。
```

扫描所有 `p` 块，命中「中文句号后紧跟 ` 图 X.Y` 或 `Figure X.Y`」的，一律人工核对。
修复不是改语序，而是**把混入的图注文字移回 figure 的 caption 块**，正文只保留
完整句子。重建后必须翻到该页目视确认图注最后一行完整。

### V5. 新增页会重排全书：目录必须“两轮回填”

补译者说明、Part 扉页、术语索引后，原目录页码全部失效。可靠顺序：

```
① 用占位页码生成封面/目录（行数=最终行数）
② 合并 → 转 PDF → 按标题文本定位每章真实起始页
③ 回填 front_meta.json → 重生成封面 → 再合并 → 再转 PDF
④ 页数稳定后写 PDF 分级书签
```

本项目新增 1 页说明 + 3 页 Part + 2 页索引，总页数 368 → 375。
**不要用旧 `chapter_pages.json` 硬编码**；每加/删一页都重跑第 ② 步。

结构建议：

- Part 页用 `kind=part`，排序键插在对应章前（1.5 / 3.5 / 9.5），不要并进章节 docx。
- 译者说明放 `kind=front`，排在封面后、前言前。
- 原书索引不要照译；用 `kind=index` 生成「英文术语｜中文｜主要章节」三列表，
  2 页可容纳 70–80 条，比保留失效页码有用得多。
- PDF 书签可用页内标题批量生成（本项目 362 条，含 339 个小节），
  Word 目录仍是静态页码，这一点要在译者说明里写明。

### V6. 辅助页生成：`Pt(1.55)` 不是 1.55 倍行距

python-docx 里 `paragraph_format.line_spacing = Pt(1.55)` 表示 **1.55 磅固定行距**，
不是 1.55 倍。自写的 `pf(..., line=...)` 若内部统一 `Pt(line)`，传 1.55 会让整页
文字压成一条黑线，表格行高缩到 5pt——而报告不会报错。

规则：

- 固定行距时明确写点数：正文 10.5pt → `line=17`，标题 24pt → `line=30`；
- 需要倍数时用 `line_spacing = 1.55`（不经过 `Pt`）；
- 目录/索引表格每行设 `WD_ROW_HEIGHT_RULE.AT_LEAST`（如 0.42cm），
  否则 70+ 行会被 LibreOffice 压进一页；
- 新建页生成后必须**单独转 PDF 看首图**，不要直接并入合订本。

### V7. 原书索引不做逐条页码翻译，改术语索引

原书索引按英文版印刷页码编制；中文版重排后旧页码全部失效。**只译条目、保留旧页码
是最差折中**。本项目的处理是：

- 不照搬 397–409 页索引，改为 `kind=index` 的“术语索引”；
- 三列：English / 中文 / 主要章节；章节号由译文 heading 自动提取；
- 76 个术语约 2 页，表格行设最小高度，表头跨页重复；
- 在译者说明里明确“原索引不照搬，改用章节定位”。

这比“全书完成”但检索入口全错要诚实，也真正可用。

### V8. 目标 docx 被预览/Word 占用时，输出修订副本

合订时若 `PermissionError: ... .docx`，说明文件正被 Word/预览锁定。
不要强行覆盖，也不要删原文件。给 `merge_book.py` 加环境变量：

```bash
BOOK_OUT_NAME="书名（修订版）.docx" $PY $S/merge_book.py
```

产出并列修订版，旧版保留。交付时明确说明两版关系，避免用户以为改动丢失。

### V9. 语义级 QA 不能省：三个扫描 + 一次目视

块级闸门看不出“整页没进来”“句子串行”“图注少一行”。收尾至少做：

```text
① 页覆盖扫描：check_page_coverage.py
② 段落扫描：p 块中是否有“图 X.Y”混入；结尾是否停在“每个部门/Each department”这类半句
③ 图片扫描：check_merged_images.py + 每章抽 1 张多图页、1 张表格页
```

并且**逐章看最后一页**：章末是否真有小节，而不是一条孤立 bullet。
本项目两次最严重问题（p108 漏页、图 10.5 串行）都不是自动闸门发现的。

### V10. 交付清单（V 组）

| 检查 | 判据 |
|---|---|
| 原书页覆盖 | 无“有正文但未覆盖”的页；每章末有小结或下一章起始 |
| 多图 key | inline_shapes == 唯一 rId == media 数 |
| 图注 | 最后一行完整、无英文残影、未被下一节标题压住 |
| 辅助页 | 行距按 pt 明确；索引表格跨页表头重复、字号 ≥8pt |
| 目录 | 新增页后重算；目录页码 == PDF 实际起始页 |
| 书签 | 章节 + 小节分级；数量与标题数一致 |
| 锁定文件 | 输出修订副本，不覆盖打开中的 docx |

## 栅格图内文字流程（图是 PNG，字在像素里）

正文部分沿用骨架流水线，**只把「图内文字 → 渲染」这一段整体替换**。
这一节是本次 374 页 / 80 张 PNG 图实战的全部有效做法；细节踩坑见 pitfalls T 组。

### 四个环节，缺一不可

```
① OCR 提取 → ② 擦除原英文 → ③ 写中文 → ④ 报告与目视
   ocr_figs.py    erase_labels    px_draw      report + 看图
```

**技能自带两个脚本，直接可用：**

```bash
# ① 提取：裁图 → OCR → 过滤 → 按基线聚合 → 双套坐标，结果按图缓存
$PY $S/ocr_figs.py 书.pdf work/book_figtexts.json --dpi 300 --pages 1-374

# ②③ 擦除 + 写中文（内部已实现两阶段、彩块判定、结构保护）
$PY - <<'EOF'
import sys; sys.path.insert(0, r'<技能 scripts>')
from fig_raster import process_figure
import json
ft = json.load(open('work/book_figtexts.json', encoding='utf-8'))
rep = {'rendered': [], 'kept': [], 'MISSING': [], 'OVERFLOW': [], 'SMALL': []}
for key, v in ft.items():
    tr = json.load(open(f'work/{key}_figtrans.json', encoding='utf-8'))
    process_figure(f'work/ocr_cache/{key}.png', v['blocks'], tr, rep,
                   scale=v['scale'], out_path=f'figs/{key}.png')
print({k: len(x) for k, x in rep.items()})
EOF
```

`fig_raster.py` 里每一条判据都标注了它对应的失败编号（T1–T5），改之前先读注释。
`PROTECTED` 是术语保护表，按书的领域填；留空只是断行不够聪明，不会出错。

### ① OCR 提取：产出「块 + 像素坐标 + pt 坐标」

```python
DPI = 300; SCALE = DPI / 72.0        # 4.1667 px per pt
# 裁图 → easyocr → 过滤 → 按基线聚合 → 坐标换算
blocks.append({
    'px_bbox': [...],                 # 像素坐标（擦除用）
    'bbox':    [...],                 # pt 坐标（写进 figtexts，与正文同坐标系）
    'h_pt':    round(g['h'] / SCALE, 2),   # 字高（定字号用）
    'en': ' '.join(parts),
})
```

**必须同时存两套坐标。** 只存一套时，会在「字号用 pt、几何用 px」之间反复出错
（pitfalls T4）。

OCR 质量实测（easyocr，80 张图 1229 块）：

- 速度约 3 秒/图，300dpi 裁图；**结果按图缓存成 `*.ocr.json`**，
  重跑渲染不必重新识别（总耗时从 5 分钟降到秒级）。
- 代码/标识符识别常有错（`VrLS`、`0S ._`、`bvte`）——**这不影响交付**，
  因为这些块本来就 `ZH SAME`，不重绘。
- 真正需要中文化的是注释文字块，占比不到一半。

### ② 擦除：判据是「墨 − 结构」，填充是「本地底色」

这是唯一稳定成立的组合。**九次失败换来的**（完整失败清单见 pitfalls T1）：

```python
ink   = lum > med + 40 if fg_is_light(sub) else lum < paper - 45   # 分彩块/白纸
guard = binary_opening(ink, (1, kx)) | binary_opening(ink, (kx, 1)) \
      | binary_opening(ink, (kk, kk))                              # 长横线/长竖线/厚块
kill  = ink & ~guard
bg    = median(sub[~dilate(kill)])                                 # 本地底色，不是全图纸色
patch[kill] = bg
```

三条硬规矩：

1. **不要用 `cv2.inpaint`。** 文字压在灰条上、旁边紧贴黑边框时，重建出一团黑抹
   （实测 12 个灰标题栏全变黑块）。只要底色取准，「替换墨像素」就是无损的。
2. **不要用"行带内深色墨"当擦除掩膜。** 行带会带上紧邻的方框边线，擦完边框缺一段。
   必须让形态学结构保护兜住线。
3. **彩块要换阈值和前景色。** 橙 `#FF9800`、蓝 `#00ADD8` 上的白字，一律按
   "比纸暗"取墨时整块被涂白、白字也没了（pitfalls T2）。

### ③ 写中文：先擦完所有块，再统一画

**OCR 相邻框常纵向重叠**（实测两行重叠 20px）。边擦边画时，后一块的擦除窗口会把
前一块刚画上的中文擦掉一半，结果是中英文叠在一起看不清——这是用户最先指出的问题。

```python
# 阶段 1：全部擦（arr 原地更新，且每次都要 img.paste 同步回去）
for b, cn in plan:
    ok, drawn = render_block(img, arr, b, cn, report, glyph, erase_only=True)
    prepared.append(drawn)
# 阶段 2：统一绘制
for d in prepared:
    px_draw(d, img)
```

配套两条：

- **纵向避让带**：只与「横向范围有重叠」的邻块比，取中心到中点；**必须有下限**
  （不低于原字高的 80%），否则会把块压到 8px 高、字号退化到 1.4pt。
- **clamp 基于原始 bbox**，不能基于上一轮的 tight 框（会逐块自收缩）。

### ④ 报告三件套 + 必须看图

```python
report = {'rendered': [...], 'kept': [...], 'MISSING': [...],
          'OVERFLOW': [...], 'SMALL': [...]}
```

| 键 | 含义 | 交付闸门 |
|---|---|---|
| `MISSING` | 有原文、无译文 | 必须 0 |
| `OVERFLOW` | `over_h > 6%` | 必须 0 |
| `SMALL` | `fs_pt < 5` | 列出，交付说明交代 |
| `kept` | `ZH SAME` / 迷你框 / 短标识符 | 给出比例，不要求 0 |

**清零只说明"没有硬错误"，好看不好看必须看图。** 本次每一轮修完都把 PNG 调出来放大看，
发现的问题（方框缺口、灰块变黑、白块残留、字太小、中英重叠）**没有一个被报告抓到**。

### 一个自检断言，能省掉几小时

```python
assert not np.array_equal(np.array(before), np.array(after)), '输出与原图字节相同'
```

漏掉 `img.paste` 时的症状极具迷惑性：报告写 `rendered=51, OVERFLOW=0`，
但输出 PNG 与原图**字节完全相同**（pitfalls T5）。

### 交付说明里要诚实写出的三类

1. **对比度极低的残影**（浅绿底 `#E8F5E9` 上的深灰字）→ 列出页码，说明只能淡化。
2. **`ZH SAME` 保留英文的块数**（代码标识符 / 数字 / 索引）→ 给比例，
   如「1229 块中 967 块含字母，实际中文化 51/80 张图」。
3. **手绘图**（XKCD 漫画）→ 说明走了窄带兜底路径，中文用的是常规黑体，
   与原手写体风格不同。

## 超长全书管线（500 页以上 + 分散图元 + 上百代码清单）

来自 544 页 / 158k 词 / 195 图 / 46 表 / 245 个代码清单的实战，产出 22 个分册 docx
+ 593 页合订本。**正文翻译仍走骨架流水线的思路，换掉的是图区判定、代码处理和 Word 生成三段。**

### 6.1 图区判定：图注间版面窗口（分散图元书唯一可行解）

商业出版书的插图常由几十到上百个**分散图元**构成（方框/箭头/圆，间距常超 16pt），
且图内文字标签大量使用**正文字体**。按 `get_drawings()` 聚类定边界会得到两种结果：
容差 14pt → 图被切成 5~19 个碎片；容差 30pt → 相邻图的图元被并进来。

```python
# ① 本页图注按 y 排序；当前图的上边界 = 上一条图注底边（首页取版心顶 30pt）
lower = caps[i-1].y1 + 2 if i else 30.0
# ② 收集窗口内全部图元：drawings + 内嵌图片 bbox + 非正文字体的文本块
cand = [e for e in els if lower - 2 <= e.y0 <= capr.y1 + 16]
# ③ 图区 = 图元并集，横向拉到整栏（图内标签常溢出图元 bbox）
band.x0, band.x1 = content_left, content_right
band.y0, band.y1 = max(34, min(e.y0 for e in cand)-6), min(H-26, max(e.y1 for e in cand)+10)
```

三条配套规则（pitfalls U1）：

1. **横向必须拉到整栏**——图内标签用正文字体，被排除在图元之外，只按图元并集裁会切掉标签列。
2. **窗口内闯入的正文段要抹白**（判据：段宽 > 250pt 且行数 ≥ 2），否则正文被烙进图里。
3. **图注文字也要抹白**——侧置图注的图注落在图区纵向范围内，不涂掉就印进图里。

**图注必须先于交叠过滤判定**。图注本身落在图区矩形内，顺序写成「先判交叠再判图注」
会静默丢掉整章图注：

```python
is_cap = bool(re.match(r'^(Figure|Table|Listing)\s+([A-Z]\.\d+|\d+\.\d+)', raw0))
if not is_cap and any(bb.intersects(fb) for fb in figboxes): continue
```

### 6.2 页眉过滤：位置 + 高度，不要用 isupper

页眉形如 `5 1.1 Knowledge graphs`（混合大小写），`raw.isupper()` 抓不到。
实测判据：`bb.y0 < 44 and bb.height < 16`（单行页眉）+ `^\d+\s+CHAPTER\b` 正则。

### 6.3 代码清单：跨页合并 + 占位符注入

一个清单常被分页切成 3~4 个代码块。用「同一清单标题下的连续 code 块首尾相接」合并。
**译文里绝不手抄代码**——模板写 `{{CODE:7.15}}` 占位符，构建时从合并结果按编号注入：

```python
md = re.sub(r'\{\{CODE:([\w.]+)\}\}', lambda m: '```\n'+'\n'.join(books[m.group(1)]['code'])+'\n```', md)
```

两类必须手工恢复：代码行与旁注交错排版导致清单被拆空（回原页按 y 坐标逐行取）；
PDF 折行丢标点（`"2018-02-23}]->` 应为 `"2018-02-23"}]->`）。

### 6.4 Word 生成：编辑器 SDK 通道的五条铁律

与 python-docx 逐段拼是两套坑，全部实测过：

1. **图片块必须独占插入批次**。同一批次里既有正文又有图片行时，图片被**静默丢弃、不报错**
   （实测 13 张图只进 7 张，文件大小完全正常）。图片行也不能是批次的最后一块
   （只有图片行的 payload 同样被丢），所以图片行必须与紧随的图注合并为同一批。
2. **代码块/表格之后必须补段分隔符**。代码块是内联图形对象，紧邻的下一个块会挤进
   同一个 `<w:p>`（实测一章 25 处）。用本次插入回包的 `position`，不要用
   `last_edit_index - 1`（插入代码块后两者相等，减 1 就错位）。
3. **追加位置只信 `doc_get_last_operable_pos` 的 `position`**。在段落中间的位置插图，
   图片会被并进上一段，图注样式失效。
4. **图片归一化前必须判断 `a:blip`**。代码块/文本框也是 `w:drawing`，不判断会把代码框
   拉宽到版心宽度、全部变形。
5. **keepNext 必须在 set_ppr 之后插入，且插在 pPr 首位**。格式化函数的「移除既有属性」
   逻辑会清掉先写的 keepNext；OOXML 对 pPr 子元素有序要求。

### 6.5 显示尺寸：300 DPI 裁剪图必须归一化

编辑器按「像素尺寸 ÷ 300 DPI」折算物理尺寸，所以 300 DPI 裁出来的图显示出来正好是
原书印刷大小——在 A4（版心 15 cm）上明显偏小。**归一化到版心宽度是必做项**：

```python
TARGET_W, MAX_H = 5400000, 7200000      # 版心宽 15cm，超高按 20cm 限
ratio = min(TARGET_W / cx, MAX_H / cy)  # 保持比例；幂等，可反复重跑
```

### 6.6 超长文档：后台构建 + 进度日志

判据：**超过 3 万字符或 80 个块就后台跑**。143 块前台 2 分 21 秒后被 SIGTERM；
1137 块合订本后台跑了 35 分钟。每 20 块打一次进度，否则无法判断卡死还是在跑。

### 6.7 参考文献与索引（用户常指定的两种处理）

- **参考文献**：条目保留英文原文，只把「Chapter N」这类分组标题中文化。
  条目按 `[n]` 拆成独立段落（原书是连排的大段，不拆没法读）。
- **索引**：双栏页必须**按列裁剪两次**（左半→右半）再按「行尾是数字则闭合当前条目」
  合并续行，否则两栏交错乱序。页码是原书印刷页码，与 PDF 物理页有固定偏移——
  **用一条已知条目反推**（如「adjacency lists 443」对应附录 A.3 在 PDF 473 页 → 偏移 30），
  然后建「印刷页 → 章节」映射，用章节定位替代原书页码。

### 6.8 合订本与目录

分册与合订本**共用同一批源文件**（`zh_tpl.md` + `codebook.json` + `figs/`），
合订本只是按顺序拼接后重跑一次构建。任一册要改，改源文件重跑那一册即可。

目录用**两轮校准法**（Word TOC 域转 PDF 只有占位文字）：

```
① 插静态目录（页码全 0，行数 = 最终行数）
② 转 PDF → 按标题文本定位真实页 → 原地回填（只改 run 文本，不动段落数）
③ 再转一次 PDF
```

约 30% 标题因文本过短/重名搜不到，留空即可，**不要为它改标题文本**（一改分页又变）。

### 6.9 交付前「四数一零」

| 校验 | 判据 |
|---|---|
| 图片段数 | == 该章图注唯一编号数 |
| 代码框数 | == 该章清单数（含手工补的） |
| 表格数 | == 该章表注数（跨页拆分的会变多，需换算） |
| 段落合并数 | **必须 0**（代码框/表格与正文并段） |
| 空清单 | 列出并逐个人工补全 |

**「生成成功、文件大小正常」不能作为交付判据**——本次 6 张图丢失时文件大小完全正常。

## 图内文字排版（最容易翻车的地方）

这一节全是实测教训。**只适用于「图内文字在文字层」的书**（栅格图见上一节）。
图好不好看，80% 取决于这里的几条规则。

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

### 并排标签：一行 N 个独立标签，也别译

第四类要保留英文的，不是"框太小"，而是**结构不允许**：

```
System  Assistant Message  Message 1  Message 1  Message 2 …
```

这些标签在原 PDF 里是**同一行内的多个独立 span**，共享一根基线。中文比英文宽，
任何一个标签拉宽都会压住左右邻居；要做得干净只能重建整行、手工排每个标签的坐标。

**判据要严，放宽会吞掉正常段落**（实测踩过）：单行 + 大写开头词 ≥5 个
+ 平均词长 ≤7 + 短词（≤6 字母）占比 ≥60% + 无句末标点与逗号列举。
用这些条件能稳定命中真图例，而不会误判
`System instructions (trusted) You are an incident summary assistant…` 这类正文。

实测一本书 706 个文字组里，这类只有 9 组。**不要为了追求"图上零英文"
去重建整行** —— 收益远小于风险（见 pitfalls S5）。

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
- **图内标题可能不在图 bbox 里**。Manning 有些图把居中标题（`1. Prompt Template…`）
  画在图元上方 10–20pt，只按「中心点在 bbox 内」归属就会漏掉它，
  渲染出的图顶部缺字。做法：对**图内字体**（`ArialMT` 一类）的行，
  上下各放宽 24pt 并入图 bbox（pitfalls S7）。

## 交付前必查

**技术层（脚本能查）**

1. `audit.py`（逐章）— 块序列零差异、图片数一致、无 DPI 警告
2. `audit_book.py`（全书一次）— 块序列 / 漏译 / 代码含中文 / 图内溢出 / 图片数
3. 渲染报告 — `MISSING`、`OVERFLOW` 都必须为 0
4. `cov.py` 全章 — **多余键为 0**、缺项为 0
5. `find_blank.py` — 合并后无空白页
6. **`check_cov.py --all` + `check_zh.py --all` 双闸门** — 前者查块号集合与图内缺译，
   后者查块数严格相等 / 块类型逐块比对 / 空块。**两个都全绿才允许继续**；
   只有前者绿就出文档是本次最大的返工来源（pitfalls S1/S2）
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
13. **栅格图三查**（栅格图书必过）：
    - 渲染报告 `MISSING 0 / OVERFLOW 0`；`SMALL` 与 `kept` 有数就写进交付说明
    - `assert not np.array_equal(输入PNG, 输出PNG)` — 防「报告全绿但图没变」（T5）
    - **逐张看图**：方框线是否完整、灰条是否还是灰、彩块是否留白块、
      是否有中英文重叠、字号是否小到看不清（T1/T2/T3）
14. **合订 PDF 页码逐页核对** — 封面不计，正文从 1 连续；
    用页脚 clip 区域取文本，不要用「每页最后一行」（会误报，见上文）
15. **超长全书「四数一零」**（走第六节管线的必过，见 pitfalls U14）：
    图片段数 == 图注编号数、代码框数 == 清单数、表格数 == 表注数、
    **段落合并数必须 0**、空清单逐个人工补全。
    「生成成功 + 文件大小正常」**不是**交付判据——实测丢 6 张图时文件大小完全正常。
16. **图注没被静默吞掉** — 每章图注唯一编号数 == 文档内「图 X.Y」图注段数。
    图注落在图区矩形内，交叠过滤顺序写反会整章丢掉且不报错（pitfalls U2）
17. **原书页覆盖** — `check_page_coverage.py 原书.pdf docs.json` 无「有正文但未覆盖」；
    每章末页必须有小节，或下一页就是下一章。块级 100% 覆盖率**不检查这件事**（V1）
18. **语义级三扫** — `p` 块中混入 `图 X.Y` / 截断半句 / 章末孤立 bullet；至少每章
    抽看末页与一张多图页（V4/V8）
19. **合订图片三数相等** — `check_merged_images.py`：inline_shapes == 唯一 r:embed
    == media 文件数；只数 inline_shapes 会漏掉同页多图共用 key 的重复（V2）
20. **新增页** — 译者说明 / Part 页 / 索引若新增，目录必须两轮回填；辅助页行距用 pt
    明确（10.5pt → 17pt），索引表格行设最小高度（V5/V6）
21. **译文内容自查**（与工程体检分开做）— `qa_translation.py` 的量化命中逐条判读
    （大多是误报：中文数字换算、PDF 断字修复、规范保留英文、双重否定转肯定），
    每章抽 1 段人工细读；「整块不含中文」按类别归入规范允许。结论写进
    `译文自查报告.md`，**不要只报一句「检查通过」**（X13/X15）
22. **下游一致性** — 改任一分册后跑完「分册 PDF → 合订 → 封面页码 → 两级书签 →
    目录页码抽查」全链；分册 PDF 时间戳、书签条数、目录页码三者必须同时最新，
    否则目录页码基于旧分页（X11/X12）

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

| 特征 | Manning（两色排版） | Grokking（手绘示意） | **Go in Action 2e（栅格图版）** |
|---|---|---|---|
| 正文字体 | `NewBaskerville-*` 10pt 衬线 | 无衬线为主 | **`Verdana` 8.2pt** |
| 标题字体 | `FranklinGothic-*` | 手写体 | `FranklinGothic-Demi` 12.6/10.6 |
| 代码字体 | `JetBrainsMonoNL` 8pt | 视书而定 | **`Type3 (NNN 0 R)` 8pt（位图字形）** |
| 结构性颜色 | 侧栏 `(0.969,0.961,0.910)`、清单条 `(0.438,0.652,0.801)`、表头 `(0.277,0.418,0.523)` | 彩色填充块 | **只有三个值**：代码标题条 `(0,0,0.333)`、代码底 `(0.949,)³`、便签下划线 `(0.0039,0,0.263)` |
| 图内文字 | `ArialMT`，**在文字层**（栅格只有线稿） | 手写标注，部分在像素里 | **全部在嵌入式 PNG 里**，`get_text` 取不到 |
| 特殊块 | 侧栏（sidebar）、边注（DEFINITION/NOTE）、代码放大截图 | 对话气泡、流程箭头 | 代码框（深蓝条+灰底）、TIP/NOTE、矢量项目符号 |
| 版式陷阱 | 侧栏、边注、列表跨图表、脚注式小标题 | 图片碎片化、标签极窄 | 表头行矮（13.5pt）被竖线判据漏掉；列表无 `•` 字形；代码缩进靠 x 坐标 |

三条判断顺序（十秒出结论）：

1. **图内文字在文字层吗？** `get_text(clip=图bbox)` 有内容 → 文字层书；空 → 栅格书。
2. **代码字体是不是 Type3？** 是 → 代码只能原样取、不能重排。
3. **结构色有几个固定值？** 三个 → 用颜色分类块，比几何判据可靠得多。

两色书的关键判据：**结构性颜色是固定三个值**，用颜色就能区分侧栏/清单条/表头，
比几何判据可靠得多。详细参数见 `references/layout-heuristics.md` 第 11–13 节
（第 13 节是 Go in Action 2e 的完整实测表）。

**Manning 2025 正式版（《Knowledge Graphs and LLMs in Action》544 页实测）**，
与上表同一出版社但版式不同，单列一行：

| 项 | 实测值 |
|---|---|
| 正文 | `NewBaskerville-Roman/-Italic/-Bold` 10pt |
| 标题 / 图注 / 表注 | `FranklinGothic-Demi` / `-DemiItal` |
| 代码清单 | `CourierStd`（非 `JetBrainsMonoNL`） |
| 图内普通文字 | `ArialMT` / `Arial-BoldMT` |
| 图内注释文字 | `HumanistMann521-BoldCond`（**用正文字体粗细的注释会被误判为正文**） |
| 插图形态 | **矢量分散图元**（每图 10–200 个），图内只有小图标是位图 |
| 索引 / 参考文献 | 双栏，页码为原书印刷页码（与 PDF 物理页差 30） |

这一行的两个教训：① 图内注释用正文字体，**不能靠字体区分图内文字与正文**，
要靠「图注间版面窗口」（见第六节）；② 双栏索引必须按列裁剪两次再合并。

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

**封面是独立一份，不是 front 文档。** 用 kind: 'cover' 单列一项排在合并清单最前，
且必须在算目录页码**之前**就存在（封面页数会让正文整体后移，见 R3/R4）。
原书书名常是整幅栅格位图 + 金色标题 + 色块，无法无损中文化 → 按视觉骨架用文字重建
（w:shd 段落底色做色块 + 大字号标题），**封面页不挂页眉页脚、不插任何图片**。

- **出版社广告、相关书目、liveBook 推广页不译**：不是书的内容，译了只会让成品显得杂。
- **原书索引不直接照译**：索引页码绑定英文版排版，中文版重排后全部失效。要么不做，
  要么用中文版实际页码重建一份新索引；只译条目而保留旧页码是最糟的折中。
  **用户要求做索引时，正确做法是中英对照 + 章节定位**：条目保留英文原词、补中文译名、
  页码换算成中文版章节（印刷页码与 PDF 物理页的偏移用一条已知条目反推，见 pitfalls U11）。
  这是唯一既保留检索价值、又不被失效页码误导的方案。
- 交付时明确说明范围，不要用「全书完成」掩盖未做的索引/广告页。
- 同时给 **分章 docx + 全书合订 docx + 全书 PDF**：分章便于修订，合订本便于阅读。
  合订 docx 用 `docxcompose`；合订 PDF 用各章 PDF 顺序 `insert_pdf` 并 `set_toc()`
  写书签。页码、图表数要与分章合计核对，不能只信文件生成成功。

### 封面单独成档并排在最前（顺序会改页码）

封面**不是** front 文档的一部分，单列 `000_封面.docx`，且必须在算目录页码**之前**
就位——封面会让正文整体后移一页（pitfalls R3/R4）。

合订顺序：`封面 → 前言与目录 → 各章`。

### 合订 PDF 的页码必须逐页重写（三处都会错）

各章 PDF 的页脚都是从 1 起的，`insert_pdf` 之后**第 2 章又回到 1**。
docx 层的 `w:pgNumType` 在 `docxcompose` 合并后只剩 1 个 section，改不动分章页码
（实测 278 页里 277 页错位）。可靠做法是**在 PDF 层重写页脚数字**：

```python
for i in range(out.page_count):
    if i == 0:            # 封面不编号
        continue
    clip = pymupdf.Rect(w*0.30, h-46, w*0.70, h)      # 只认底部居中
    # 找纯数字行 → redact → insert_text(str(i))
```

三个坑，全都踩过：

1. **判据必须收窄到「底部 + 水平居中」**。放宽到整个页脚带，会把正文里含数字的行
   也擦掉（实测 6 页被误擦：`132`、`51234570`、`20250221112455165`）。
2. **封面跳过编号**，否则全书页码从 2 开始、整体偏一位。
3. **校验脚本自己也会误报**。用「取每页最后一行」判页码时，PDF 文本按列序返回，
   最后一行往往是正文；改用页脚 clip 区域取文本才算对。

### 前置页的「行」不能靠自动合并

版权页的五行元数据、简明目录的十来行章名，在 `convert.py` 里若按普通段落合并，
会**拼成一整行**（实测 `Version 9Copyright 2026 Manning…`）。

判据：块内有多行、且**过半以「数字＋空格」开头**，或**每行都很短** → 逐行保留
（输出时用 `\n` 连接，`build_docx` 侧用 `add_break()` 硬换行）。
另加一条：**含 `\n` 的块不参与「前段不以句号结尾就并段」的合并逻辑**，
否则第一行会吃掉下一块的开头。

### 封面重建的检查清单

| 检查 | 判据 |
|---|---|
| 不出现「第　章」 | `'第　章' not in page_text`（`num` 为空时会拼出这个） |
| 不插任何图片 | `len(page.get_images()) == 0` |
| 不挂页眉页脚 | `sec.different_first_page_header_footer = True` |
| 不占页码 | 重写页脚时 `if i == 0: continue` |

## 细节参考

- `references/pitfalls.md` — **踩坑清单**（A–F 图重书 / G–L 长书 /
  M 排版观感 / N 骨架流水线 / O 图内渲染真缺陷 / P 前置页 / Q 续译与交付边界 /
  R 合订本保真·封面重建·彩色图内文字 / S 块号错位与校验缺口 /
  **T 栅格图内文字** / **U 超长全书 + 分散图元 + SDK 管线** /
  **V 全书范围审计 + 同页多图 + 新增页** / **W 同版式复用与整书合订** /
  **X 混合型书 + 并行交付 + 内容级质检**），
  动手前先扫一遍，尤其 **A17 / F7 / F9 / G1 / G7 / H4 / I1 / J1 / M1 / M7 / M9 /
  N2 / N3 / O1 / O3 / O4 / P1 / P3 / P4 / P8 / P9 / Q1 / Q3 / Q7 /
  R1 / R2 / R3 / R4 / R5 / S1 / S2 / S3 / S4 / S5 / S7 /
  T1 / T2 / T3 / T4 / T5 / T6 / V1 / V2 / V3 / V4 / V5 / V6 / V7 / V8 / V9 /
  W1 / W2 / W3 / W4 / W6 / W7 / W9 / W11 / W12 / W13 / W14 / W15 / W16 / W17 / W19 /
  X1 / X2 / X3 / X4 / X5 / X6 / X7 / X8 / X9 / X10 / X11 / X12 / X13 / X14 / X15**

  **S 组是骨架流水线的必读**：S1（`convert.py` 静默吞掉多写的块头，导致整章串位）、
  S2（校验脚本正则自己漏掉全部块头，却报「多余 0 / 缺 0」）、
  S3（顺位取块 vs 按块号取块，用错就是串位）、S7（图内标题在图 bbox 之外被漏掉）。

  **T 组是栅格图书的必读**：T1（擦除判据的九次失败清单，一次看完全部弯路）、
  T2（彩块白字要换阈值）、T3（先擦完再统一画，否则中英文重叠）、
  T4（像素与 pt 两套坐标不能混用）、T5（改完 numpy 必须 paste 回 img）、
  T6（手绘漫画走窄带兜底）。

  **U 组是超长全书（500 页以上）的必读**：U1（分散图元用图注间版面窗口裁图，聚类必败）、
  U2（图注必须先于交叠过滤判定，否则整章图注静默丢失）、
  U4（图片块必须独占插入批次，混入正文会被静默丢弃）、
  U5（代码块后必须补段分隔符，否则后文被吸进同一段）、
  U6/U7（图片归一化先判 `a:blip`；300 DPI 裁剪图必须缩到版心宽）、
  U10（超 3 万字符必须后台构建）、U11（索引列感知抽取 + 页码偏移反推）、
  U12（目录两轮校准法）、U14（交付前「四数一零」，文件大小正常不算通过）。

  **V 组是整书交付前的必读**：V1（块级覆盖率 100% 不代表 docs 页范围没漏，
  必须单独跑 `check_page_coverage.py`）、V2（同页多图共用 key，inline_shapes 对但
  唯一 rId 少）、V3/V4（固定外扩裁进正文、图注最后一行被裁）、
  V5（新增页后目录两轮回填）、V6（`Pt(1.55)` 是 1.55 磅不是倍数）、
  V7（原书索引改章节定位的术语索引）、V8（文件被锁时输出修订副本）、
  V9（三个语义扫描 + 逐章看末页）。

  **W 组是跨会话整本翻译 + 合订的必读**：W1–W5（同版式项目复用，但字体/页眉阈值/
  章首页判据/私有区项目符号必须按新书实测）、W6/W7（图注整组裁剪 +
  figure 分支补中文图注 + keepNext）、W9（按列错乱的数据表改 figure 时要补
  `blocks: []` key）、W11/W12（唯一短语映射表批量图内译文 + KEEP 分层）、
  W13（**OpenBLAS 内存错误导致整章插图静默消失**）、W14（前置页尺寸不一致让
  400 页膨胀到 628 页）、W15（目录页码文本定位被目录页自己骗到，改用页数累加）、
  W17（紧凑原文 + 每份固定动作 + 磁盘进度）、W19（交付说明 7 类已知限制）。

  **X 组是混合型书 / 并行交付 / 内容级质检的必读**：X1（同一本书矢量图与栅格
  截图共存，按页分流而非二选一）、X2（纯空格 span 被过滤造成「文字层丢空格」
  假象）、X3（章首页下半页正文被 chapter_open 吞掉）、X4（清单与便签被聚成图）、
  X5（侧置图注 `caption-erased` 只擦不写）、X6（清防伪码的正则跨行吞掉 `@@B`
  块头，四处同步删块重编号）、X7（NULL 字节藏在 JSON `\u0000` 转义里）、
  X8（并行子代理 prompt 六要素 + 分段追加）、X9（KEEP 要写英文原文）、
  X10（docxcompose 合并后页眉页脚全丢）、X11（两级书签必须接进重建链）、
  X12（下游一致性刷新链）、X13（工程全绿 ≠ 译文没问题，量化命中多为误报）、
  X14（术语语境变体写进规范）、X15（交付前补两条检查）。
- `references/layout-heuristics.md` — 版式解析判据（字体分类、图区聚类、段落合并、
  中文竖排、**第 12 节 Manning 2025 单色版实测参数**：字体语义表、两种结构色、
  竖线分段合并的表格判定、章首页矢量项目符号分组）
- `scripts/ocr_figs.py` — **栅格图 OCR 提取**：裁图→识别→按基线聚合成块，
  输出同时含 `px_bbox`（擦除用）与 `bbox`/`h_pt`（排版用），结果按图缓存
- `scripts/fig_raster.py` — **栅格图擦除 + 中文化**：结构保护判据、彩块白字、
  本地底色填充、两阶段绘制、报告五键，全部按 T1–T5 的教训实现，可直接 import
- `scripts/gen_figzh_map.py` — **通用图内译文映射表**：导出全书唯一 EN 短语，
  「精确映射 + KEEP 正则 + 默认写英文原文」一次生成各分册 `_figzh.txt`；
  `--map` / `--keep` 可外部覆盖（X9）
- `scripts/add_pdf_outline.py` — **合订 PDF 两级书签**：从各分册 `_trans.json`
  的 h2/h3 标题在对应页区间定位，写「章 + 小节」书签并校验回跳/越界（X11）
- `scripts/qa_translation.py` — **译文内容量化自查**（只读）：原文 vs 译文逐块对齐，
  10 类扫描 + 否定/比较定向扫描 + 无中文块分类，可 `--out` 出报告（X13）
- `assets/book.json.example` — 配置模板
- `assets/trans.schema.json` — 译文 JSON 完整示例
