# livebook-translation

> 把**带插图的英文技术书（PDF）**整本翻译成中文 Word / PDF：图内文字就地中文化、
> 代码还原成可复制块、表格还原成真表格、逐块校验与原书对齐。

这是一份 **Agent 无关的 Skill 操作规范**：deepseek harness、Claude Code、Codex、
WorkBuddy 等能读写文件并执行 Python 的 Agent 都可直接使用；它不是独立的命令行程序，
也不依赖任何特定厂商的 API 或插件。
`SKILL.md` 是给 Agent 的完整操作手册（约 1600 行），本文件是给人看的**导航与快速上手**。

---

## 它解决什么问题

普通机翻 / 截图搬运一本技术书会得到：图里全是英文而正文是中文、代码被箭头注释切断且复制出来跑不了、
画出来的表格线不是真表格、目录页码全是原书的、译文与原书块序对不上。

本技能的做法：

```
PDF 版面 → 结构化块序列 (标题/段落/列表/代码/图/表)
        → 逐块翻译（块号一一对应）
        → JSON 驱动 Word/PDF 生成
```

图不是「贴一张英文截图」：文字层书按坐标擦除英文、原位重写中文；栅格截图书走 OCR 擦像素重写。
代码缩进由 x 坐标反算，图注从图里裁出来改由正文以中文呈现。

## 适用 / 不适用

| 适用 | 不适用 |
|---|---|
| Manning / O'Reilly / Grokking 类带大量插图的技术书 | 纯文字小说、无插图文档 |
| 图里有英文标签、注释、对话气泡 | 扫描版 PDF（无文字层，需先 OCR 成文字层） |
| 需要按章交付 docx + 整本合订 docx/PDF | EPUB（需先转 PDF） |
| 需要保留原书版式感，而不是重排成纯文本 | 只想快速读个大概（直接用翻译工具更快） |

---

## 快速开始

### 1. 环境

Python 3.10+（实测 3.13），Windows / macOS / Linux 均可；脚本默认中文字体路径为 Windows，
其它平台要改 `render_figs.py` / `build_docx.py` 里的 `FONT_CN` 常量。

```bash
pip install pymupdf python-docx docxcompose Pillow numpy scipy
# 可选：栅格图 OCR 与中文按词断行
pip install easyocr jieba
```

转 PDF 需要 **LibreOffice**（`soffice --headless`）。合订 PDF 书签用 `pymupdf` 写入。

### 2. 建项目

在任意工作目录放两个文件（模板见 `assets/`）：

```jsonc
// book.json —— 至少填 pdf 与 root
{
  "pdf": "D:/books/your-book.pdf",
  "root": "D:/work/mybook",
  "book_title": "中文书名",
  "cn_body": "宋体", "cn_head": "微软雅黑", "cn_hand": "楷体",
  "en_body": "Times New Roman", "en_head": "Segoe UI",
  "body_pt": 10.5, "margin_cm": 2.4, "text_w_cm": 16.2,
  "dpi_cap": 230, "zoom": 4.1667, "max_h_cm": 17.5
}
```

```jsonc
// docs.json —— 按原书物理页切分文档
[
  {"id":"fm",   "title":"前言与导读", "num":"",  "kind":"front", "from":11, "to":18},
  {"id":"part1","title":"第一部分",   "num":"1", "kind":"part",  "after":0, "from":19, "to":19},
  {"id":"ch01", "title":"第一章标题", "num":"1", "kind":"ch",    "from":20, "to":34}
]
```

建议同时建 `work/ figs/ out/ out/pdf/ parts/ review/ tmp/`，并把本技能 `scripts/` 复制到项目
`scripts/`（同版式复用时按新书字体改 `parse_layout.py` 的字体表与章首页判据）。

### 3. 十秒判定：图内文字在哪一层

**这一步决定后面所有图相关工具的选择，别跳过。**

```python
import pymupdf
page = doc[图所在页]
page.get_text('dict')      # 图 bbox 内能取到 span → 文字层书
page.get_image_info()      # 图区 get_text 为空、只有一坨大 PNG → 栅格书
```

| | 文字层书 | 栅格书 | **混合型书** |
|---|---|---|---|
| 图内文字 | 矢量 span，可取坐标 | 像素，只能 OCR | 两类共存，要**按页统计**分流 |
| 中文化 | `render_figs.py` 按坐标重绘 | `ocr_figs.py` + `fig_raster.py` | 矢量图重绘 + 栅格截图保留英文界面 |
| 主要风险 | 断行、溢出 | 擦除伤到图形 | 误把整本书归成一类 |

### 4. 选流程

| 书的形态 | 走哪条 | 详见 `SKILL.md` |
|---|---|---|
| 图多章少（Grokking 类，300+ 页） | 五步流程 | 「五步流程」 |
| 400+ 页、代码密集 | 五步 + 长书分片流程 | 「长书分片流程」 |
| **12 份以上文档、想逐份交付 / 并行 / 可续做** | **骨架文本流水线**（最常用） | 「骨架文本流水线」 |
| 80+ 张栅格截图 | 骨架流水线 + 栅格图内文字流程 | 「栅格图内文字流程」 |
| 500 页以上、分散图元、上百代码清单 | 骨架流水线 + 版面窗口裁图 + SDK 管线 | 「超长全书管线」 |
| 矢量流程图 + 界面截图共存 | 骨架流水线 + 混合型分流 | 「混合型书与规模化交付（X 组）」 |

---

## 主流程速查（骨架文本流水线）

```bash
PY=python; S=<本技能>/scripts        # 所有命令在项目根执行

# 1. 全书解析 + 图内文字抽取（各一次）
$PY $S/parse_layout.py 11 226 work/book_layout.json
$PY $S/extract_fig_texts.py work/book_layout.json work/book_figtexts.json

# 2. 切片 + 生成待译骨架
$PY $S/slice_layout.py                       # 读 docs.json
$PY $S/mk_skeleton.py fm part1 ch01 ch02 …   # → work/<doc>_skel.txt / _figskel.txt

# 3. 翻译（逐块对应，块号只信 _skel.txt）
#    work/<doc>_zh.txt      : @@B n <type> + 中文；code 块留空；figure 写 `CAP: 图 X.Y　…`
#    work/<doc>_figzh.txt   : @@FIG key / @@T id / ZH 中文（KEEP 时写英文原文）
$PY $S/gen_figzh_map.py --root .             # 可选：全书唯一短语表批量生成 _figzh.txt
$PY $S/pairs.py ch01                         # 写译文前看「块号+原文」对照

# 4. 双闸门（两条判据不同，缺一不可）
$PY $S/check_cov.py --all                   # 块号集合 + 图内缺译
$PY $S/check_zh.py --all                    # 块数严格相等 + 类型逐块 + 空块

# 5. 逐份出文档（convert → 渲染图 → docx → audit，一条龙）
$PY $S/build_doc.py fm part1 ch01 ch02 …

# 6. 合订 + 交付前体检
$PY $S/build_front_pages.py out/_前置页.docx  # 封面/版权/目录（整页文字排版，不走图块）
$PY $S/merge_book.py                          # 分章 docx → 合订 docx（分节页眉 + 页码连续）
$PY $S/build_book_pdf.py --pdf-only           # 逐份转 PDF 再拼接（保真做法）+ 书签
$PY $S/add_pdf_outline.py out/pdf/全书.pdf    # 章 + 小节两级书签
$PY $S/layout_check.py out/pdf/全书.pdf      # 页码/页眉/留白/孤立行/行距
$PY $S/find_blank.py out/pdf/全书.pdf
$PY $S/check_merged_images.py out/全书.docx  # inline_shapes == 唯一 rId == media
$PY $S/check_page_coverage.py 原书.pdf docs.json
$PY $S/qa_translation.py --root . --out out/译文自查报告.md   # 内容级自查（非工程体检）
```

> 详细参数、每步的人工核对点、以及「结论：✓ 通过」的判读标准，见 `SKILL.md`。
> 接手已有项目时**先按磁盘产物盘点进度，不要重译**，见 `SKILL.md`「接手已有翻译项目」。

---

## 目录结构

```
livebook-translation/
├── SKILL.md                  # Agent 操作手册（必读）：核心认知 / 五条流程 / 交付前必查
├── README.md                 # 本文件
├── scripts/                  # 39 个可复用脚本（见下）
├── references/
│   ├── pitfalls.md           # 踩坑清单 A–X 组（约 1900 行，动手前先扫）
│   └── layout-heuristics.md  # 版式判据：字体分类 / 图区聚类 / 段落合并 / 各书实测参数
└── assets/
    ├── book.json.example     # 项目配置模板
    └── trans.schema.json     # 译文 JSON 的完整结构示例
```

### 脚本按阶段分组

| 阶段 | 脚本 |
|---|---|
| 解析 | `parse_layout.py` `dump_layout.py` `slice_layout.py` `extract_fig_texts.py` `block_tool.py` `remap_seq.py` |
| 待译骨架 | `mk_skeleton.py` `pairs.py` `export_pairs.py` `make_chapter.py` |
| 图内文字 | `render_figs.py`（文字层） · `ocr_figs.py` `fig_raster.py`（栅格） · `gen_figzh_map.py`（批量映射） |
| 译文转换 | `convert.py` `cov.py` `realign_zh.py` |
| 生成 | `build_doc.py` `build_docx.py` `build_front.py` `build_front_pages.py` `convert_pdf.py` `convert.py` |
| 合订 | `merge_book.py` `build_book_pdf.py` `add_pdf_outline.py` `chapter_pages.py` |
| 校验 | `check_cov.py` `check_zh.py` `audit.py` `audit_book.py` `check_blocks.py` `check_merged_images.py` `check_page_coverage.py` `find_blank.py` `layout_check.py` `verify_docx.py` `qa_translation.py` |
| 辅助 | `bookconf.py` `preview_html.py` `build_front.py` |

---

## 质量闸门（三条线，缺一不可）

1. **工程层**：`check_cov.py` + `check_zh.py` 双闸门 → `audit.py` 块序列一致 →
   图渲染报告 `MISSING 0 / OVERFLOW 0` → `check_merged_images.py` 三数相等。
2. **版式层**：`layout_check.py`（页码错位 0、页眉样式 >1、孤立单行页 0）、
   `find_blank.py`（空白页 0）、`check_page_coverage.py`（原书无漏页）、目录页码抽查。
3. **内容层**：`qa_translation.py` 做 10 类量化扫描 + 否定/比较定向扫描，
   每章抽段人工细读。**量化命中大多是误报**（中文数字换算、PDF 断字修复、
   规范保留英文、双重否定转肯定），必须逐条写清原因，不能只报「通过」。

工程全绿 ≠ 译文没问题；三层的结论分别写进 `质检报告.md` 与 `译文自查报告.md`。

---

## 文档导航

| 想找什么 | 去哪 |
|---|---|
| 完整操作流程、五条流程详解、交付前 22 条检查 | `SKILL.md` |
| 某个具体 bug 的症状与修法 | `references/pitfalls.md`（A–X 组，按书分类；目录在 `SKILL.md`「细节参考」） |
| 换一本新书怎么调字体表 / 页眉阈值 / 章首页判据 | `references/layout-heuristics.md` |
| 译文 JSON 长什么样 | `assets/trans.schema.json` |
| 图内文字在像素里怎么办 | `SKILL.md`「栅格图内文字流程」 + pitfalls **T 组** |
| 500 页以上 / 分散图元 | pitfalls **U 组** |
| 合订、封面、目录两轮校准 | pitfalls **R / W / X 组** |
| 并行翻译、术语表、内容级 QA | pitfalls **X 组** |

`pitfalls.md` 分组速记：**A–F** 图重书 · **G–L** 长书 · **M** 排版观感 · **N** 骨架流水线 ·
**O** 图内渲染真缺陷 · **P** 前置页 · **Q** 续译边界 · **R** 合订保真 · **S** 块号错位 ·
**T** 栅格 OCR · **U** 超长全书 · **V** 全书范围审计 · **W** 同版式复用与整书合订 ·
**X** 混合型书 + 并行交付 + 内容级质检。

---

## 实战记录

技能里的每条经验都来自真实整本翻译，不是推演：

| 书 | 规模 | 沉淀 |
|---|---|---|
| Grokking 类手绘书 | 336 页 / 346 图 | 五步流程、图内文字重绘 |
| Manning 代码密集书 | 464 页 / 13 万词 | 长书分片、键号纪律 |
| Manning 两色版 | 248 页 / 12 份文档 | 骨架流水线、双闸门（S/V 组） |
| 栅格图为主 | 374 页 / 80 张 PNG | OCR 擦像素流程（T 组） |
| 商业出版书 | 544 页 / 195 图 / 245 清单 | 版面窗口裁图 + SDK 管线（U 组） |
| Manning 2026 | 450 页 / 25 分册 / 406 页合订 | 同版式复用与整书合订（W 组） |
| Manning 2025 | 233 页 / 14 分册 / 43 图 | 混合型书 + 并行交付 + 内容级 QA（X 组） |

---

## 已知取舍（主动选择，不是遗漏）

- 栅格界面截图里的英文界面文字无法无损中文化，保留英文原图 + 中文图注，并在交付说明列页码。
- 图内极窄标签、类名、函数名、示例查询、数据表字段按 `KEEP` 保留英文。
- 原书索引页码在中文版失效，改为「英文术语｜中文」对照索引；封面/版权/目录按中文版重建。
- 原书笔误、断词、前后不一致按原样保留；中文版是学习用途的非官方译本。

完整交付说明模板见 `SKILL.md`「交付说明模板：7 类已知限制」。

---

## 版本与贡献

本目录是一个 git 仓库。每次沉淀一本新书的经验，按 `A–X` 组追加到 `references/pitfalls.md`、
在 `SKILL.md` 增补对应小节与新脚本，然后提交：

```bash
git add SKILL.md README.md references/ scripts/
git commit -m "新增 XXX 经验（Y 组）：NNN 页 XX 书实战沉淀"
```

新脚本请保持：可独立运行、有 docstring 与 `--help`、路径通过 `--root` 或项目根 `book.json` 解析、
不硬编码具体书名。提交前至少跑 `python -m py_compile` 与一次真实项目冒烟。
