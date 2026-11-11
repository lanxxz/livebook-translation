# 流程细节（自 SKILL.md 移出的扩展阅读）

> SKILL.md 瘦身时把实战细节移到这里：SKILL.md 保留路由、流程骨架与闸门，
> 动手做对应工作时先读本文件对应章节。踩坑编号（W/X/V/T/U 组等）的完整案例在 `pitfalls.md`。

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

> 注：`build_final_book.py` 是项目专用脚本，**未随技能附带**。新项目用自带的
> `build_book_pdf.py`（逐份转 PDF + 拼接）+ `add_pdf_outline.py`（书签）+
> `chapter_pages.py`（目录页码）组成等价链。

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

### 6. 版式保真：工程闸门查不出「语义丢了」

用户把原书页与成品页并排一看，指出了前面五轮自查都没发现的问题：
对话没译、框内提问「消失」、线性段落不如原书好读、Part 扉页标题不醒目。
**这些都不是块错误**——块数、类型、图片数、页码、漏译复核全绿（X21）。

- **教学对话要译、要分轮**（X16/X17）。「模型输出保留英文」只适用于读者要复制的
  字面量；演示对话是读者要读懂的正文。PDF 会把 `User:` / `GPT:` 标签混进句子甚至
  断词中间，必须渲染原书页按目视重建轮次，译文用 `**用户：**` / `**GPT：**` 加粗标签，
  一块含两轮用 `■` 分行而不拆块。**带 style 的块绝不能被段落合并逻辑粘在一起**。
- **侧栏框 / 提示框按 fill 色从 PDF 提取**（X18）。本书 38 个米黄矩形里是
  DEFINITION / TIP 与提问式标题，文字译了但框没了，看起来就像内容消失。
  给落在框内的块打 `sidebar_head` / `sidebar_body`，呈现层用段落底纹 + 左边线还原，
  连续段段距设 0。
- **版式语义作为数据字段透传**（X19）：`book_layout.json` 加 `style` →
  `convert.py` 写进 `_trans.json` → `build_docx.py` 按 style 渲染。
  译文仍是纯中文，双闸门不受影响，换书只改打标规则。
- **Part 扉页单独渲染**（X20）：给第一个非 figure 块打 `part_title`，
  译文两行分别渲染成米黄底纹大标题与斜体引言，中间加分隔线。
- **交付前并排目视**（X21）：把原书 2–3 个代表页与成品对应页各导出 PNG 对照
  「标题层级 / 底色框 / 对话标签 / 缩进 / 留白」。`qa_translation.py` 顺带统计
  各类 style 块数，为 0 说明打标没生效。
- **成品被预览进程独占**（X22）：`open(p,'r+b')` 失败就换输出名
  （`BOOK_FINAL_NAME`），不要硬删、不要 `os.replace`、不要结束进程。

### 7. 加样式救不了碎片块：该改块序列时别只改呈现层（X23）

第一次修对话只给每个碎块加了 `dialog` 样式，用户**仍然不满意**。
根因不是「缺标签/底纹」，而是 PDF 把一轮 User+GPT 切成了 3–5 个块：
User 首行 / 续行、GPT 首行 / 续行、列表项、孤立的 `GPT :` 标签、
以及把英文落款和作者旁白混在一起的块。给每块各加一次缩进与底纹，
成品只会变成**一串分散小色块**，标签还插在编号 1 与 2 之间。

判据：**同一个语义单元被拆到多个块、块间有段落间距时，补样式只会放大碎片感**，
必须合并块。做法：

1. 按原书页面把碎块分成语义轮次（35 → 11 组），每组只保留首块，
   `type→para` / `style→dialog`，`text` 换成组内英文全文，其余删除；
2. 混入作者旁白的块排除出对话组、恢复普通段落；
3. 一个轮次块用 `■` 分行写 `**用户：** …` / `**GPT：** …`，
   编号列表让标签与第一项同行，断词续行重组成完整句；
4. **四处同步**：`book_layout.json` → `slice_layout.py` → `clean_front.py` →
   `mk_skeleton.py` → 按新骨架重写 `_zh.txt`
   （`clean_front.py` 为项目专用脚本，未随技能附带；新项目可手工清理
   `book_layout.json` 里的前置页块后重新切片）；
5. 重写 `_zh.txt` 时**必须从新 `_skel.txt` 回填块头类型**，
   一律写成 `p` 会让 `check_zh.py` 报整章类型不符；
6. 呈现层不必改：一个含 `\n` 的 `dialog` 块就是一个连续色块、行间无段距。

代价是块序列与原书 PDF 文本块不再一一对应，要在交付说明登记为编译性处理。


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


## 栅格图内文字流程细节：① OCR / ② 擦除 / ③ 写中文

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


## 超长全书管线细节（6.1–6.8）

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

> 注：下文 `freeze_tx.py` / `apply_fill.py` / `qa_pack.py` / `build_figtrans.py` /
> `render_chapter.py` / `do_chapter.py` / `check_all.py` 均为原 464 页项目的专用脚本，
> **未随技能附带**。新项目请用 SKILL.md「长书分片流程 → 等价做法」里的自带脚本动作
> （`check_cov.py` / `check_zh.py` / `convert.py` / `build_doc.py` / `audit_book.py`）。

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


## 附录：原长书分片流程（pack 流）

> 本节是 464 页 Manning 书项目使用的原始流程。**所引用的项目专用脚本未随技能附带**：
> `make_pack.py` / `cover.py` / `freeze_tx.py` / `apply_fill.py` / `build_figtrans.py` /
> `do_chapter.py` / `check_all.py` / `qa_pack.py` / `render_chapter.py`。
> 仅在接手已含这些脚本的旧项目时照此操作；新项目请用 SKILL.md「长书分片流程」里的骨架流水线等价做法。

### 原流程正文（pack 流，Manning 类 460 页以上）

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


## EPUB 源流程细节（Z 组配套，145k 词 Manning MEAP 实测）

145,740 词 / 10 章 / 75 图 / 2,873 块，产出 11 份分册 + 402 页合订本。
本节是 SKILL.md「EPUB 源」一节的扩写，动手前配合 pitfalls Z1–Z15 读。

### 8.0 完整命令链与槽位格式

```bash
PY=python; S=<本技能>/scripts        # 所有命令在项目根执行

# 1. XHTML → 块序列（递归容器、h1→章名、h5→图注、多 table 逐个产出）
$PY $S/epub_parse.py book.epub        # → work/book_layout.json + docs.json + <doc>_dump.txt

# 2. 生成骨架（点号 uid + 槽位）
$PY $S/epub_skel.py --all             # → work/<doc>_skel.txt / _slots.json

# 3. 写 work/<doc>_zh.txt（### <uid> [<type>] + 槽位行）
$PY $S/check_cov_slots.py --all       # 闸门：缺 0 / 多余 0 / 槽位合法

# 4. 回填 → trans.json
$PY $S/apply_zh.py --all

# 5. 图内中文化（三段流水线）
$PY $S/ocr_all.py                     # OCR 全部图（按图缓存）
$PY $S/fig_lines.py                   # 行内合并碎片（别跨行）
$PY $S/fig_kind.py --init --sheet     # 出草稿表与联系表，人工定三类
$PY $S/draw_figs.py                   # 示意图（读 work/fig_zh.json）
$PY $S/draw_charts.py                 # 统计图（读 work/chart_spec.json）

# 6. 出文档 + 合订
$PY $S/build_all.py                   # 每章 docx → PDF
$PY $S/build_front_epub.py            # 封面 + 目录
$PY $S/merge_book_epub.py             # 拼 PDF + redaction 重写页脚 + 两级书签
```

`_zh.txt` 的格式（**与骨架流水线的 `@@B` 块号格式不同**）：

```
### 12 [para]
text 错误会像背景噪音一样在 AI 项目里来回流窜。

### 43 [figure]
caption 图 1.1　氛围工程的循环……

### 63 [dialog:prompt]
speaker 提示词

### 63.0 [para]
text 生成一个 Python 函数……

### 63.1 [code]
caption Listing 5.1 预提交钩子示例
note:#A 把路径换成你本地的路径。

### 56 [table]
caption 表 9.1　模型之间的成本变化
cell[0][0] 任务类型
cell[0][1] Sonnet
```

槽位名只有这十个：`text` / `caption` / `speaker` / `title` / `label` / `intro` /
`toc[N]` / `item[N]` / `cell[R][C]` / `note:#X`。

**为什么用槽位而不是整块字符串**：一个 dialog 块的 `speaker` 与它内部的 `para`
是两个独立译文单元。写成嵌套 uid（`14` 与 `14.16`）能让「块头写错」和
「槽位写错」分别报错。代价是**槽位名写错会静默丢内容** —— 因为槽位名本身合法，
闸门查不出来（Z5 的实例）。

脚本分工：

| 脚本 | 职责 |
|---|---|
| `epub_parse.py` | 递归解析 XHTML → `book_layout.json` / `docs.json` / 每章 dump |
| `epub_skel.py` | 生成骨架与槽位表（`_skel.txt` / `_slots.json`） |
| `common.py` / `tree.py` | 项目根定位、块树扁平化、槽位枚举与回填 |
| `check_cov_slots.py` | 槽位版闸门（**与块号版 `check_cov.py` 并存**，别混用） |
| `apply_zh.py` | `_zh.txt` → `_trans.json` |
| `draw_figs.py` / `draw_charts.py` | 示意图 / 统计图两类渲染器 |
| `build_docx4.py` | EPUB 块类型全套渲染（dialog/callout/sidebar/equation/quote） |
| `merge_book_epub.py` | 合订（拼 PDF + redaction 重写页脚 + 两级书签） |

### 8.1 为什么 EPUB 比 PDF 省事

PDF 流程的成本集中在两处：**块边界靠聚类猜**、**图区归属靠 bbox 判**。
EPUB 里这两件事都是标签给的：

| 要判断的事 | PDF 做法 | EPUB 做法 |
|---|---|---|
| 两段该不该合并 | 行距 + 首行缩进 + 句末标点 | 两个 `<div class="readable-text">` 就是两块 |
| 这行文字属于图还是正文 | 中心点落在图元 bbox 内 | 它在 `<div class="figure-container">` 里就是图注 |
| 代码缩进多少空格 | `(行首x - 版心左边)/等宽字宽` | `<pre>` 里原样 |
| 这张图在哪 | `get_image_info()` 扫页 | `<img src="../Images/03__image012.png">` |
| 表格几行几列 | 判竖线横线交点 | `<tr><td>` 直接数 |

代价转移到三处：**嵌套容器的递归**（Z2）、**槽位名的纪律**（Z5）、
**OCR 拆词后的语义重建**（Z6）。图内文字仍在像素里，T/Y 组判据全部适用。

### 8.2 解析：递归 walk + 容器分类

顶层结构的实际分布（ch03 为例，255 块）：

```
div.readable-text                            × 87   普通容器（内有一个 p 或一个 h2）
div.readable-text.intended-text               ×134   同上，只是排版标记不同，无需区分
div.callout-container.sidebar-container
    .prompt-response-sidebar.prompt-sidebar    × 15   提示词对话
div.callout-container.sidebar-container
    .prompt-response-sidebar.response-sidebar  ×  2   模型回复
div.readable-text.sub-sub-section-heading     ×  5   四级标题容器
div.browsable-container.figure-container      × 14   插图
ul                                            ×  1   顶层列表
```

`walk(container, ctx)` 的骨架：

```python
def walk(container, ctx, depth=0):
    blocks = []
    for el in container.iterchildren():
        c = cls(el)
        if 'figure-container' in c:
            ctx['fig'] += 1
            blocks.append({'type': 'figure',
                           'key': '%s_f%02d' % (ctx['doc'], ctx['fig']),
                           'img': img_src(el), 'caption': cap_of(el)})
        elif 'listing-container' in c:
            blocks.append({'type': 'code', 'caption': cap_of(el),
                           'text': pre_text(el), 'notes': notes_of(el)})
        elif 'browsable-table-container' in c:
            for ti, tb in enumerate(el.cssselect('table')):
                blocks.append({'type': 'table',
                               'caption': cap_of(el) if ti == 0 else '',
                               'grid': grid_of_table(tb)})
        elif 'prompt-response-sidebar' in c:
            kind = 'prompt' if 'prompt-sidebar' in c else 'response'
            blocks.append({'type': 'dialog', 'kind': kind,
                           'speaker': speaker_of(el), 'initials': initials_of(el),
                           'parts': walk(el, ctx, depth + 1)})
        elif 'admonition-block' in c:
            blocks.append({'type': 'callout', 'label': cap_of(el).upper(),
                           'parts': walk(el, ctx, depth + 1)})
        elif 'sidebar-container' in c:
            blocks.append({'type': 'sidebar', 'title': cap_of(el),
                           'parts': walk(el, ctx, depth + 1)})
        elif el.tag == 'h1':
            continue                       # 章名已进 chapter_open（Z3）
        elif el.tag in ('h2', 'h3', 'h4', 'h5'):
            blocks.append({'type': 'heading', 'level': int(el.tag[1]),
                           'text': inline(el)})
        elif el.tag in ('ul', 'ol'):
            blocks.append({'type': 'list' if el.tag == 'ul' else 'numlist',
                           'items': [inline(li) for li in el.cssselect('li')]})
        elif el.tag == 'div':
            blocks.extend(walk(el, ctx, depth + 1))
    return blocks
```

三个必须注意的点：

1. **`browsable-table-container` 里可能有多个 `<table>`**。ch04 的 `p72`
   并排放了两张（`Use Case` 与 `Aspect`），只取 `[0]` 会静默丢一张。
2. **`h5` 是 caption 不是标题**。若统一处理，会产出 22 个无意义标题而图注反而丢了。
3. **`h1` 直接跳过**。它的文本已经进了 `chapter_open`，再产出 heading 会导致章名出现两遍。

### 8.3 验收：叶子文本包含检查

块数会骗人。第一版丢了两张表和三段代码，但块数一次都没变。

```python
def tight(s):
    return re.sub(r'\s+', '', re.sub(r'[*`]', '', s))

out = tight(' '.join(flatten(blocks)))
WHITE = {'这章涵盖', '所有笔记的代码都可以在'}     # 白名单：被渲染成固定标题的
for el in doc.body.iter():
    if el.tag in ('p', 'h2', 'h3', 'h4', 'li', 'td', 'th', 'pre', 'blockquote'):
        t = tight(el.text_content())
        if t and t not in out and t not in WHITE:
            print('MISSED', el.tag, t[:80])
```

**不要用 token 频次比对**。代码块被拆成单词后，`if`/`return`/`2` 的差额定会淹没真缺失
（实测 ch07 报 912 个"缺"、真正缺 0 个）。

### 8.4 图：OCR → 行内合并 → 三类分流 → 渲染

EPUB 的图不用裁（`z.read(src)` 就是整图），但图内文字仍是像素。四步：

**① OCR**（`ocr_all.py`）：easyocr 逐图识别，结果按图缓存成 `<key>.ocr.json`。
只保留 `conf >= 0.30` 且不是纯符号的块。

**② 行内合并**（`fig_lines.py`）：OCR 会把一行切成多块（`Word-of-the-` / `day` / `-`）。
合并判据：垂直重叠 > 70%、水平间隙 < 1.6 倍字高、字高相近（> 55% 彼此）。
**只做行内**——跨行合并会把不同卡片连成一整块（实测 35 块并成 2 块，结构全丢）。

**③ 分流**（`fig_kind.py`）：三类判据见 SKILL.md「图分三类」。
自动判据之后必须叠人工修正表，并且**做 contact sheet 复核**：

```python
COLS, TW, PER = 6, 300, 24            # 每张 300px 宽、每版 24 张
for si in range(0, len(keys), PER):
    rows = (len(chunk) + COLS - 1) // COLS
    sheet = Image.new('RGB', (COLS * TW, rows * CH), 'white')
    for i, k in enumerate(chunk):
        sheet.paste(thumb(k), ((i % COLS) * TW, (i // COLS) * CH + 20))
        ImageDraw.Draw(sheet).text(((i % COLS) * TW + 4, (i // COLS) * CH + 4), k, fill='red')
```

75 张图 4 版就能一眼看完，比逐张点开快一个数量级。

**④ 渲染**：示意图走 `draw_figs.py`（框内众数取底色、只保护长线、多行 `fit_multi`），
统计图走 `draw_charts.py`。

统计图的五条要点（都在实测中撞过）：

1. **轴刻度一律跳过** —— `re.match(r'^[\s\-+.,%$€£¥\d\^eE×xX/()]+$', en)` 命中的块不处理。
2. **竖排 Y 轴名一列一字**，`fs = min(bw*0.98, bhh/字数/1.06)` 再**封顶 14–15px**。
   超了会压到刻度数字上（Z9）。
3. **OCR 常整块漏检竖排轴名**（旋转 90° 的小字），`chart_spec.json` 要支持 `extra`：
   手工给 `px_bbox` + 译文，走竖排分支。
4. **横向标题可略超框宽**：`limit = max(bw+12, bw*1.6)`，
   否则 `Medicine Type` 这类短标签会被 OCR 窄框拆成两行。
5. **图例里的标识符保留英文**：`Haiku` / `Sonnet` / `hashMap` / `parallelStream` 是 API 名；
   只换 `concurrent→并发版`、`optimized→优化版` 这类描述词。

**效果不好就退回原图。** 实测 6 张试汉化后主动退回：双轴图例互相挤压、
x 轴标签被拆行、竖排轴名压刻度、表格状排版错位、中文填进错误框。
判据：**放大看过仍觉得比英文原图更难读，就退回**。退回后把人工表改回 `shot`、
删掉 `figs_zh` 里的产物，并在交付说明列出文件名与原因 ——
不要默默留一个半坏的中文图。

**合订前还要过一次图分类核对**：`figs_zh/` 里实际存在的文件集合，
必须与人工表里的 diagram/chart 集合逐张一致。实测这一步抓到过
「表里标 diagram 但产物没生成」和「产物存在但表里还是 shot」两类错位。

### 8.5 渲染器的四条硬规则（都是踩出来的）

| 规则 | 违反后的症状 |
|---|---|
| **底色取「框内颜色众数」**，不取外扩窗口中位数 | 标题条上下是白纸 → 判成白底黑字 → 蓝色标题条被当墨迹擦成白块 |
| **结构保护只保护长横线/长竖线**，不加"厚块" | 粗体大字被整片保下来 → 蓝条上的粗体白字擦不掉 |
| **擦除后必须 `img.paste(Image.fromarray(arr))`** | 报告 `rendered=51, OVERFLOW=0` 全绿，输出 PNG 与原图**字节相同** |
| **纵向扩张设硬上限**（≤0.3 倍行高） | 白字在深色条上会一路扩到白纸，整张图被吃掉（实测 114×18 → 516×163） |

多行译文的字号：`fit_multi` 按显式 `\n` 分段，`fs = min(h_ref*0.98, per_h*0.94)`，
每段独立求值再取最小。合并块一定要同时把 `h_pt` 设成**单行字高**而不是整块高，
否则字号被压到 8px 看不清。

### 8.6 合订：拼 PDF + redaction 重写页脚

合订 docx 与合订 PDF 分别做，PDF 是最终交付物：

```python
out = pymupdf.open()
for p in paths:                       # 封面 → 目录 → 前言 → 1..N 章
    src = pymupdf.open(p); out.insert_pdf(src); src.close()

for i, page in enumerate(out):
    r = page.rect
    foot = pymupdf.Rect(0, r.y1 - 72, r.x1, r.y1)
    page.add_redact_annot(foot, fill=(1, 1, 1))    # ← 必须 redaction
    page.apply_redactions()                        #    draw_rect 不删旧文字
    if i < 2:
        continue                                   # 封面与目录不编号
    txt = str(i - 1)                               # 页脚号：正文从 1
    w = pymupdf.get_text_length(txt, fontname='helv', fontsize=9.5)
    page.insert_text(((r.x1 - w) / 2, r.y1 - 36), txt, fontsize=9.5,
                     fontname='helv', color=(0.45, 0.45, 0.45))

out.set_toc(entries)                  # [level(1|2), title, page(1-based)]
out.save(tmp, deflate=True, garbage=3)
os.replace(tmp, final)
```

验收：`get_text(clip=页脚区)` 逐页比对 `str(i-1)`，必须 0 错位。

### 8.7 目录页码：基准只能选一个

目录里写**页脚号**还是**全书页号**，两者差「前置页数」（封面 1 + 目录 1 = 2）。
选页脚号：

```python
cur = 1                                # 正文首页的页脚号
for d in docs:
    print('%s …… %d' % (d['title'], cur))
    cur += pymupdf.open(pdf_of(d)).page_count
```

封面必须严格 1 页 —— 溢出到 2 页会让后面全部偏 1 页（实测 403 → 402 页之差就来自这里）。

### 8.8 交付前自审清单（本流程专属）

| 检查 | 方法 | 本次结果 |
|---|---|---|
| 块数与类型 | `layout` vs `trans` 逐块比 | 11/11 一致 |
| 叶子包含 | 见 8.3 | 只剩 1 条白名单 |
| 标签污染 | `speaker`/`label`/`title` 长度 > 40 | 5 处（最长 266 字） |
| 章名五处 | `docs.json`/文件名/页眉/目录/章首页 | 5 章不一致 |
| 图分类 | contact sheet 目视 | 12 张统计图误判为截图 |
| 图内叠加 | OCR 二次识别输出图 | 编号重复、拆词叠字 |
| 译文长度比 | 段落 `汉字/原文字符` 分布 | 中位 25.0、p90 28.2 |
| 页码/目录/书签/图片 | 见 8.6 | 0 错位 / 11:11 / 90 条 / 75 张 |

前四条都是**工程闸门查不出**的，必须单独做。

---

## 统一多级目录流程细节（AA 组配套，255 页 Manning MEAP 实战）

> 对应 pitfalls **AA1–AA14**。场景：用户要「章内小节目录合并到目录」，
> 成品是**一处统一多级目录**（章 / 小节 / 子小节三级）+ 每行可点击跳转，
> 章节正文不再有任何独立导览。本节只讲怎么做，踩过的坑看 pitfalls AA 组。
>
> 这套流程**已随技能附带**（配置驱动、跨平台，别的机器可直接跑）：
> `scripts/toc_common.py`（公共配置/解析/页码计算）、
> `scripts/toc_build.py`（两遍构建 + 合订 docx/PDF）、
> `scripts/toc_links.py`（挂链接 + fail-closed 校验）、
> `scripts/toc_verify.py`（三方核对 + 模拟点击验收），
> 配置模板 `assets/unified_toc.json.example`，用法见本节末尾「9. 配套脚本用法」。
> 下面给出算法骨架，便于按自己项目的目录结构调参。
> 技能原生 `scripts/build_front_pages.py` 已支持多级目录（4 元组 `level` 字段）。

### 1. 动笔前：三层盘点 + 方案确认

「目录样的东西」常常有三层，**只改自己加的那一层必然被用户退回**：

| 层 | 关键词 | 来源 | 默认处置 |
|---|---|---|---|
| 译者插页 | 本章小节目录 | 自己插的 | 删除，条目并入统一目录 |
| 章内导览 | 本章内容 / In this chapter | 原书 | **要用户拍板**（删正文 or 保留） |
| 简要目录 | 简要目录 / brief contents | 原书 welcome | 属原书正文，默认保留 |

盘点要同时扫 **PDF 全文**和 **docx 完整 XML**（页眉、文本框、表格都在 XML 里，
`Document.paragraphs` 看不到）。把命中位置列成编号清单给用户，
不要先改再解释。删原书内容是破坏性操作，必须先确认。

### 2. 条目收集：分册 PDF 书签是唯一真相来源

```
各分册 docx --(LibreOffice)--> 分册 PDF --get_toc()--> (级别, 标题, 局部页)
                                    |
                    +---------------+---------------+
                    |                               |
            统一目录条目/页码                合订 PDF 二级书签
```

LibreOffice 从 docx 的 `Heading 1/2/3` 样式生成 outline，带精确局部页，
比「在合订 PDF 里搜标题文字」可靠得多（换行标题、重复词会漏定位）：

```python
entries = []
for name in chapter_names:
    with pymupdf.open(os.path.join(PDFDIR, name + '.pdf')) as sub:
        for lvl, title, local_page in sub.get_toc():
            if not title.strip():
                continue
            entries.append({'num': ..., 'title': title.strip(),
                            'local_page': local_page,
                            'level': 0 if lvl == 1 else lvl - 1})
# 本次：10 章级 + 56 h2 + 101 h3 = 167 条
```

`front_meta.json` 的 `toc` 用四元组 `[编号, 标题, 页码, 层级]`，
章级为 0、小节 1、子小节 2。旧的三元组格式读时补默认值即可向后兼容。
合订书签定位复用同一份 outline：`final_page = 章起始页 + local_page - 1`。

### 3. 两遍构建：拆掉「目录页数 P ↔ 全书页码」的循环

关键性质：**P 只由条目数与排版决定**；页码右对齐，位数变化不影响换行。
所以可以先用占位页码量出 P，再按 P 算真正页码。

```
第 1 遍
  toc = [(num, title, '0', level) ...]          占位
  生成前置页 docx -> soffice 转 PDF -> P = 前置页数 - 2
  front = 2 + P   (封面 1 + 版权 1 + 目录 P)
  welcome = 2
  版面：front + welcome + sum(各分册页数) = 全书总页数
  每条最终页 = front + welcome + 前面分册页数累计 + local_page - 1

第 2 遍
  把最终页码写回 toc，重建前置页 docx/PDF
  断言：前置页数 == 2 + P 且 P 与第 1 遍相同；否则退出
```

```python
def compute_pages(entries, chapter_starts, P):
    front = 2 + P
    base = front + 2                     # welcome 占 2 页
    out = []
    for e in entries:
        out.append(base + chapter_starts[e['chapter']] - 1 + e['local_page'] - 1)
    return out
```

输出必须打印「第 2 遍：页数收敛 ✓」，`front_meta.json` 与
`chapter_pages.json` 一起落盘。**生成成功不等于收敛**。

### 4. 多级目录排版（python-docx）

| 层级 | 排版 | 字号 / 行距 |
|---|---|---|
| 章级 | 斜体章号（深蓝）+ 金色 ▪ + 章名，段前 6pt | 11pt / 19pt |
| 小节 | 左缩进 1.25cm，无装饰符 | 10pt / 14.5pt |
| 子小节 | 左缩进 2.3cm | 9pt / 12.5pt |

- 页码用**右对齐制表位**（`Cm(TEXT_W)`），不要用空格补
- 章级行的 `keep_with_next` 打开，避免章名与首个小节被分页拆开
- 前置页整页走 docx → LibreOffice，**不要用 pymupdf CJK 字体直接画**：
  `china-ss` 会把 `1.1` 拉成 `1 . 1`，金色 ▪ 还会丢字（AA9）

### 5. 链接挂载：先四方校验，再逐行挂两个 GOTO

目录行解析 = 左标题行 + 右页码行按 y 配对（阈值 8pt）。
**y 带下限放到 55**：p3 有「目录」大标题首行 y≈128，
但 p4 起的续页首行 y≈70，用 100 会静默吃掉每页顶部 2–3 行（AA5）。

挂链接前四项必须全对，否则 `return 1`，不产出「看起来对」的文件：

| 校验 | 判据 |
|---|---|
| 行数 | `len(rows) == len(front_meta.toc)` |
| 标题 | `norm(row_text) == display_key(entry)` |
| 印刷页码 | `printed_page == entry.page` |
| 书签页 | `bookmark_page == entry.page` |

```python
def display_key(ent):
    if ent['level'] == 0:
        return norm(ent['num'] + ent['title'])   # 印刷成「N ▪ 章名」
    return norm(ent['title'])                    # 小节标题自带编号，不能再拼 num

for bb in (title_bbox, page_bbox):             # 标题区 + 页码区双区域
    page.insert_link({'kind': pymupdf.LINK_GOTO,
                      'from': pymupdf.Rect(bb[0]-2, bb[1]-2, bb[2]+2, bb[3]+2),
                      'page': target - 1,
                      'to': pymupdf.Point(bb[0], title_y or 0)})
```

再加各章页眉「返回目录」链接形成双向导航。
保存到原文件要写临时文件再 `replace`（AA7）：

```python
if Path(dst).resolve() == src.resolve():
    tmp = Path(str(dst) + '.tmp')
    doc.save(tmp, garbage=4, deflate=True)
    doc.close()
    tmp.replace(dst)
```

### 6. 章内导览：渲染层开关，源数据不动

```python
# build_docx.py，chapter_open 分支
KEEP_CHAPTER_TOC = os.environ.get('KEEP_CHAPTER_TOC', '0') == '1'
...
if KEEP_CHAPTER_TOC and blk.get('toc'):
    # 「本章内容」标题 + List Bullet 要点（原逻辑）
```

`work/*_trans.json` 里的 `chapter_open.toc` 原样保留，
所以 `audit_book.py` 的「原文块序列 vs 译文块序列」继续全绿，
且 `KEEP_CHAPTER_TOC=1` 随时可重建对照版。改的是呈现，不是真相来源（AA2）。

### 7. 下游链：一条命令跑完，不许挑着跑

```
9 个分册 docx -> soffice 转分册 PDF
             -> toc_build.py --step rebuild   两遍构建前置页 + 页码
             -> toc_build.py --step merge     合订 docx + 合订 PDF + 两级书签
                                             (redaction 删子页脚 + 写连续页码)
             -> toc_links.py                 167 行 x 2 + 页眉返回目录
             -> toc_verify.py                三方核对 + 逐个模拟点击
             -> 项目自有 audit_book.py / final_check.py（内容级 / 排版层另跑）
```

即使某次改动后**各章页数和书签数完全没变**，也必须整条重跑：
合订 docx、合订 PDF、链接注解是三份独立产物，
只重跑其中一段会留下旧内容（本次删导览后合订 docx 仍有 9 个残留，AA10）。

### 8. 验收清单（断言层 + 目视层）

| # | 检查 | 判据 |
|---|---|---|
| 1 | 章内导览残留 | 全书检索「本章内容 / 本章小节目录 / 小节目录」命中 **0 页** |
| 2 | 三方页码核对 | 书签 / `front_meta` / PDF 印刷页，逐条一致（167/167） |
| 3 | 目录行数 | `front_meta` 条目数 == 解析行数 == 行链接数 / 2 |
| 4 | 链接端到端 | 逐个模拟点击：矩形有可见文字、目标页含对应标题、双区域落点一致 |
| 5 | 链接类型 | 全部 `LINK_GOTO`，无外链 |
| 6 | 页码连续 | 1..N 逐页 `get_text(clip=页脚区)` 比对 |
| 7 | 全书终检 | 空白页 / 页眉页脚 / 溢出 / 书签回跳越界 / 图数 / 表数 / 代码行数 |
| 8 | 内容级四比对 | 代码逐字符 / 表格逐格 / 数字等价 / 图内「该译未译」 |
| 9 | 目视 | 目录首页 + 续页 + 2~3 个章首页渲染 PNG：三级缩进、右对齐竖线、无空洞 |
| 10 | 交付说明 | 顶部写「当前状态 + 旧文件自检提示」，历史问题标注「已被 #N 取代」 |

第 9、10 条专治「脚本全绿但用户说没改」：前者查脚本查不出的观感，
后者避免用户拿旧副本或文档里的历史措辞当现状（AA11/AA14）。

### 9. 配套脚本用法（配置驱动，别的机器直接跑）

**四个脚本 + 一个配置模板**：

| 文件 | 职责 |
|---|---|
| `scripts/toc_common.py` | 配置加载 / 项目根定位 / 跨平台 soffice 探测 / norm / 目录行解析 / 条目收集 / 页码计算 |
| `scripts/toc_build.py` | `--step rebuild`（两遍构建前置页）/ `merge`（合订 docx+PDF+书签）/ `all`；`--check` 只复核书签 |
| `scripts/toc_links.py` | 目录行双区域 `LINK_GOTO` + 页眉返回目录；挂链接前四方 fail-closed 校验 |
| `scripts/toc_verify.py` | 三方页码核对 + 逐个模拟点击 + 章内导览残留 + 链接类型，任一不符退出码 1 |
| `assets/unified_toc.json.example` | 配置模板，逐字段带 `_note` 说明 |

**三步命令**（在项目根执行；`scripts/` 指技能目录，可换成绝对路径）：

```bash
cp <技能>/assets/unified_toc.json.example work/unified_toc.json
# 按项目改 docs.json 命名模板、book_title、front_fixed_pages、toc_rows 等
python <技能>/scripts/toc_build.py  --config work/unified_toc.json --step all
python <技能>/scripts/toc_links.py  --config work/unified_toc.json
python <技能>/scripts/toc_verify.py --config work/unified_toc.json
```

**最少输入**：`docs.json`（文档顺序）、`work/front_meta.json`（封面/版权文字 + `toc` 数组）、
各分册 docx 与 PDF（命名要能被 `name_template` 对上）。`root` 留 `null` 时
从配置文件所在目录向上找 `docs.json`/`book.json`，也可 `--root` 或 `BOOK_ROOT` 覆盖。

**跨平台要点**：

- 路径全部 `os.path.join`，无驱动器/用户名硬编码；配置里路径可相对 `root`。
- LibreOffice 探测顺序：`SOFFICE` 环境变量 / 配置 `soffice` 字段 → `PATH` →
  Windows / Linux / macOS 常见安装路径；找不到给出明确提示，不静默跳过。
- 书名、页眉文字、章号正则、命名模板、页脚安全区、目录 y 带全部来自配置，
  不假设中文书名或「第 N 章」写法（`bookmark_regex` 可改）。
- 只依赖 `pymupdf` / `python-docx` / `docxcompose`（`requirements.txt` 已列），
  不需要 `book.json`，也不需要技能里的其他脚本先跑过。
- `toc_verify.py` 是 fail-closed：把 `toc_rows.y_min` 误设成 100 时，
  `toc_links.py` 会打印「行数与 front_meta 不一致，中止」并退出 1，不产出坏文件（AA5）。

**回归实测**（用 255 页 Manning MEAP 项目在隔离目录跑完整链，与项目专版产物逐项比对）：

| 项 | 通用版 vs 项目专版 |
|---|---|
| 页数 | 255 / 255 ✓ |
| 书签（168 条） | 逐条一致 ✓ |
| 链接（345 个） | 落点与热区全一致 ✓ |
| 逐页文本 | 255/255 页一致 ✓ |
| 目录行（167 条） | 全一致 ✓ |
| `toc_verify.py` | 0 问题（三方 167/167、模拟点击 334、残留 0 页） |

回归时把分册 docx/PDF 复制到临时目录、配置 `root=null` 自动定位，
因此**不碰原项目产物**；交付前用 `toc_verify.py` 对最终文件再跑一次即可。
