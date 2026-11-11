# 踩坑清单（273 条）

> A–F 来自《Grokking Streaming Systems》中文版实战（11 章 / 336 页 / 346 图 / 1918 段）。
> G–J 来自《Financial AI in Practice》（Manning，14 章 + 附录 / 464 页 / 113 图）实战。
> AA 组来自《Rearchitecting LLMs》MEAP V07（9 章 / 255 页合订 / 167 条统一目录 / 345 链接）实战。
> 每条格式：**症状 → 原因 → 做法**。动手前扫一遍，能省掉大半返工。
>
> 两本书的差异本身也是一条经验：**Grokking 是手绘示意图 + 短标签；Manning 是两色排版 + 长正文 + 代码密集 + 多作者前后不一致**。前者难在图内文字排版，后者难在块结构归属与超长工作量。

## 目录（26 组 / 273 条；E 组已并入其他组，编号保留空缺）

| 组 | 主题 | 条目 |
|---|---|---|
| A | 版面解析（parse_layout.py） | A1–A21 |
| B | 图内中文化（render_figs.py） | B1–B12 |
| C | docx 生成（build_docx.py） | C1–C10 |
| D | 流程与协作 | D1–D5 |
| F | 代码缩进与图内排版 | F1–F13 |
| G | 长书分片翻译（Manning 级体量） | G1–G8 |
| H | 解析规则变更后的译文重映射 | H1–H4 |
| I | 代码截图类插图 | I1–I3 |
| J | 整书合并与交付 | J1–J5 |
| K | 书稿本身的坑（内容层） | K1–K5 |
| L | 交付前的"看着像对、其实不对" | L1–L4 |
| M | 排版"能过校验但不好看" | M1–M10 |
| N | 骨架文本流水线专有坑 | N1–N6 |
| O | 图内文字渲染六个真缺陷 | O1–O6 |
| P | 前置页（封面 / 版权 / 目录） | P1–P9 |
| Q | 续译与交付边界 | Q1–Q8 |
| R | 合订本保真、封面重建与彩色图内文字 | R1–R11 |
| S | 块号错位与校验缺口 | S1–S7 |
| T | 栅格图内的文字 | T0–T10 |
| U | 超长全书 + 分散图元 + 编辑器 SDK 管线 | U1–U14 |
| V | 全书范围、同页多图与新增页 | V1–V9 |
| W | 450 页 Manning 2026 整本翻译 | W1–W19 |
| X | 混合型书 + 并行交付 + 内容级质检 | X1–X23 |
| Y | 彩色图内文字与两遍渲染 | Y1–Y21 |
| Z | EPUB 源 + 锚点槽位 + 统计图 | Z1–Z15 |
| AA | 统一多级目录与章内导览合并 | AA1–AA14 |

---

## A. 版面解析（parse_layout.py）

| # | 症状 | 原因 | 做法 |
|---|---|---|---|
| A1 | 整张对比表漏检 | drawings 的 rect 宽或高为 0（直线、表格边框）被 `width>0.5` 过滤掉 | 宽/高 <0.8 时各外扩 0.6pt 后再判断 |
| A2 | 表格和图注便签被并成一块 | 图形区二次生长的 gap 取 20pt 太大 | 取 **9pt**；图块再按"交叠 >5.5% 合并"单独处理 |
| A3 | 同一段注释被拆到两个图里，中文化后前后错位 | 图块交叠未合并 | 交叠 >5.5% 必合并 |
| A4 | `Notethat`、`restarted` 这种黏连 | span 拼接丢空格 | `join_spans` 按 x 间隙 >0.8 补空格 |
| A5 | `continu ous` | 软连字符 `\u00ad` 删除后仍加空格 | 末尾是 `\u00ad` 时**直接拼接**；硬连字符 `-` 保留（`temperature-sensitive`） |
| A6 | 段落缩进判断失效 | 用"上一段首行 x0"当基准，多段都缩进时就错 | 用**本页正文左边距众数**作基准 |
| A7 | 列表项出现重复文字 | 原书有视觉重叠的双层文本（`• More flexible` 与 `More flexible—…` 重叠） | `dedupe_lines`：bbox 重叠 + 文本互为子串 → 留长行，bullet 标记转移 |
| A8 | 段落被拆碎 | 同一视觉行被拆成多个 line（行内代码前后） | `merge_same_row`：y 中心差 <3.2 且 x 间隙 <15 合并 |
| A9 | 整行被判成 code，段落碎成多段 | 单个标识符（`count`）用 Courier 排 | 匹配 `^[A-Za-z_][A-Za-z0-9_.]{0,24}$` 的行按正文处理 |
| A10 | 含 `getData()` 的整段正文判成 code | 按 span 个数判代码 | 按**字符占比** >75% 判 code；正文行里行内代码可占一半，body 阈值取 >0.4 |
| A11 | 列表项被错误合并 | 用 gap 判据（相邻项 gap 也能为 0） | 用 "y0 差 < size×1.55" + "行首自带 `•`/`n.` 一定是新项" |
| A12 | 图内注释被当正文，或正文末行被图吞 | 图内注释用正文字体排，落在图外 | 块级后处理：<30 字符的独立 para、中心在图 bbox 内或垂直相距 <22pt → 并入图。**不要用行级规则**（会吞正文段落末行） |
| A13 | 代码块丢空行 | 行距信息未利用 | 按行距 gap >4.5 插空行 |
| A14 | 排序 KeyError | code 块没记 y0/y1 | `flush_code` 里补 y0/y1/x0 |
| A15 | 章首页解析不出来 | 章首页版式独立（40pt+ 章号 / 18pt Semibold 标题 / 引语） | `parse_chapter_open` 单独解析；toc 用"独立项目符号行"作锚点分组 |
| A16 | 圆筒+方框被判成表格 | 无网格线的多列文字 | 表格只认**横竖线网格**且单元格填充率 ≥70% |
| A17 | 改一次归属规则，别处就崩 | **给归属判断加"聪明"规则**（宽行保护 / 纯图元范围） | **不要加**。归属判定只用"行中心点是否在图 bbox 内"。加过的两种规则都引发了连锁回归（p55/p73 便签长注释被拆成正文、p55 两图不再合并） |
| A18 | 一句话被拆成 5 个段落 | 文字环绕图排版，窄栏 x0 远大于版心（229 vs 90） | 首行缩进判据用 `6 < indent < 40`，不要用 `indent > 6` |
| A19 | docx 缺图 | 无文字的纯结构图在 figtexts 里没有条目 → 不渲染 | extract 时对无文字的图也输出条目（blocks 为空）；render 用 `figtexts.get(key) or {'blocks':[]}` |
| A20 | 标题只剩半句 | 18pt 的第二行被图 bbox 吞掉 | 归属判断与 extract 都加：`size >= 16 且 head 类型 → 不归图` |
| A21 | 段落/代码跨页断开 | 页末句子没写完，下页是 H2 | main 里加"跨页续接"：上页末块不以句末标点结尾、下页首块同为 para（或同为 code）则合并 |

---

## B. 图内中文化（render_figs.py）

| # | 症状 | 原因 | 做法 |
|---|---|---|---|
| B1 | 方框被涂黑 | 背景采样取外圈，把图形边框当背景 | 取 **bbox 内像素颜色众数** |
| B2 | 原文被图形遮住却判为可见 | 可见性判据太宽 | 用 bbox **中心 50%** 区域深色像素比；<0.004 则不擦除、只绘制 |
| B3 | 英文标识符被楷体撑宽拆行（`E`/`xecutor`） | 译文==原文却重绘 | 译文==原文且原文可见 → **完全跳过**；纯 ASCII 译文用 Arial |
| B4 | `3. 返回并等 / 待 / 下一个请求。` | 中文分行不均衡 | **按词断行**（见 F1），禁标点行首、禁单字行。⚠ 不要用"按字宽度均匀切分"——那会把「提示词」切成「提示/词」 |
| B5 | 字号退化到 1.9pt | 手动 `\n` 分行后行数超过原块行数，fit_text 全失败 | `max_lines = max(原行数, 译文行数+1)`；fallback 字号下限 10px |
| B6 | `Source.getEvents()` 被拆成两行 | token 正则不含 `()` | 正则为 `[A-Za-z0-9_\-\.\'\(\)]+\s*` |
| B7 | `Van` 的 16×15pt 空间塞 4 个中文 | 原图标签空间极小 | 译文必须精简（「货车」而非「厢式货车」）；盯渲染报告 `fs_pt < 7.5` |
| B8 | 擦除后留残影 | 外扩不足 | 外扩 **3px**（原文不可见时不擦） |
| B9 | DPI 体检全错、图序与文件名错位 | 渲染目录残留合并前的旧 PNG | 每次 re-render 前清理不在 figtexts 里的 png |
| B10 | 表格型图的标签列被打乱（9 行 `card no:` 折成 5 行） | 译文写成一长串，被自动换行 | 这类**多行对齐的标签必须用 `\n` 显式逐行拆分**，让每行对应表格的一行 |
| B11 | 纵轴标签被压成 2.2pt，几乎不可读 | 原文字是竖排（旋转 + 高远大于宽），中文按横排塞进 10pt 宽的框 | **中文竖排渲染**：`rotated and bh > bw*1.6 and 无\n` 时每字一行，`fs = min(cap, bw*0.92)` |
| B12 | 矮框里的长旁注只有 5pt | 原书旁注 1 行英文（bbox 高约 13pt），中文要 2 行 | 放宽**行数**上限（`max_lines`），让文字往下排；外扩要克制（≤框宽 6%，≤0.9pt/侧），别靠加宽撑字号 |

---

## C. docx 生成（build_docx.py）

| # | 症状 | 原因 | 做法 |
|---|---|---|---|
| C1 | 小图被放大到 7cm，62dpi 糊 | 图宽只按下限约束 | 加 DPI 上限 `像素宽×2.54/230`，下限 3.8cm |
| C2 | `__init__` 被 Markdown 吃成粗体 | 正文里写了双下划线 | 一律写 `` `__init__` ``；`add_rich` 支持 `**粗体**` 与 `` `行内代码` `` |
| C3 | 列表渲染坏掉 | 列表项前置了 `>` | 列表前不加 `>` |
| C4 | 图注对照太长占篇幅 | 未去重 | 去重 + 跳过未译项（en==cn） |
| C5 | 章首页空段落 | intro 为空 | `if blk.get('intro')` |
| C6 | DPI 体检结果全错 | audit 按文件名排序取图，`p100` 会排在 `p80` 前 | **按译文里 figure 的出现顺序取图** |
| C7 | 段落仍是碎的 | 块级碎片未合并 | 渲染层预处理：相邻 p 块，前块不以句末标点结尾 → 与后块直接拼接（中文不加空格） |
| C8 | 代码块的英文注释没人看得懂 | 代码不能改（要能直接跑） | code 块支持 `notes` 字段：`[["// 原文","中文"]]`，渲染成代码块下方 8pt 灰字 |
| C9 | 27 张图占了大半页，文字被挤成留白 | 单图高度 16–20.7cm，A4 正文区才 25.3cm | 加 `MAX_H_CM=17.5`，超出按比例缩窄宽度 |
| C10 | 页眉只有「书名 ｜」，章名丢失 | 主程序 `build(*args[:5])` 把第 6 个参数切掉了 | `build(*args[:6])`；改完用 `Document(f).sections[0].header.paragraphs[0].text` 验一下 |

---

## D. 流程与协作

| # | 症状 | 原因 | 做法 |
|---|---|---|---|
| D1 | 整份译文 JSON 被删空 | 脚本用 `d[None:134]` 切片，因为 `i0` 没匹配到 | **改译文 JSON 必须先 assert 定位索引**，改完立刻跑块序列校验；损坏就整文件重写，别叠补丁 |
| D2 | 图位置反复放错 | 凭"图大概在这段后面"的语感 | figure 的插入位置必须**数 layout 的下标**（有时是 `hi+3` 而不是 `hi+2`） |
| D3 | 校验通过但内容错 | 只校验了块序列 | 交付前另做：漏译扫描、术语混用统计、图内字号统计 |
| D4 | 文件名带全角冒号，命令行传参出错 | `11_第11章_收尾：xxx.docx` | 文件名避免全角标点 |
| D5 | 一条命令改代码 + 渲染，结果没生效 | 两个命令用 `&&` 串联时中间的 heredoc 可能异常 | 改完代码单独跑一次验证（`grep` 确认写入） |

---

## F. 代码缩进与图内排版（实测教训）

这两组问题是"看起来通过了、读者一眼就看出来"的典型，务必当成交付红线。

### F1–F3：图内文字断行

| # | 症状 | 原因 | 做法 |
|---|---|---|---|
| F1 | 「提示词」被断成「提示 / 词」，「提示词模板」断成「提示 / 词模板」 | 断行 token 是**单个汉字**；另有"按字宽度均衡分行"逻辑会二次打散 | 断行单位改成**词**：中文分词（jieba）+ 术语保护表 + 英文按空格。**删掉按字均衡** |
| F2 | 技术复合词被分词器切错（`提示词模板` → `提示/词/模板`） | 通用分词词典不认识领域复合词 | 维护 `PROTECTED_TERMS`（提示词模板、模型数据、检索增强生成…），长词优先整体保留；确实放不下才按**子术语**拆 |
| F3 | 单字成行、标点跑行首 | 只按宽度切 | 断行后做一次修正：标点行首则把上一行末字挪下来；避免单字行 |

### F4–F6：图内文字字号与溢出

| # | 症状 | 原因 | 做法 |
|---|---|---|---|
| F4 | 中文溢出方框、压在图形边线上 | 强行把字号抬到 7.5pt（中文比英文占宽，3 个汉字塞进 2 字宽的框） | **取消强制下限**：从原文字号起、放不下就收缩，下限约 4.6pt。原书图内 6~7pt 是正常值 |
| F5 | 渲染报告"全部 OK"，实际却溢出 | 没有任何溢出检测 | 渲染后比对**最宽一行 vs 方框宽度**，超 4% 标 `OVERFLOW`；`fit_text` 要接收"真实框宽"（`hard_w`），不能用含外扩的宽度自我判定 |
| F6 | 固定加宽 1.6pt 导致窄框误判 | 外扩量没按框宽比例 | 外扩 = `min(框宽×6%, 0.9pt)`；`11pt` 宽的框固定加 3.2pt 等于放宽 28% |

### F7–F10：代码块

| # | 症状 | 原因 | 做法 |
|---|---|---|---|
| F7 | **所有代码块缩进全丢**，全顶格 | PDF 缩进是 **x 坐标**、不在文本里；行文本被 strip | 按 `(行首 x − 版心左边界) / 等宽字符宽` 反算空格数 |
| F8 | 缩进算错、时有时无 | 等宽字符宽度写死；版心边界用了整页最小值 | 宽度用**全书代码行自动测量**（取 `宽/字符数` 中位数）；版心边界**逐页**取（左右页常镜像，差 9pt） |
| F9 | DOCX 里明明是 2 空格，PDF 里看不出来 | Word 段落会**折叠连续半角空格** | 前导缩进改用 **U+00A0（不换行空格）**，等宽字体下同宽且不折叠。验证要看渲染后的像素位置，别只看 docx 文本 |
| F10 | 长代码行被拆成两行（`int time) {` 单独一行） | PDF 折行，解析时当成新行 | 判定续行：上一行顶到版心右边界 + 本行紧贴其下 + 本行不是新语句开头；`\|\|` 结尾强制合并；连字符折断按词表决定是否保留（`tile-placement` 保留、`generative` 接回） |
| F11 | 代码块里每行之间都多空行 | 空行阈值用了固定 4.5pt | 用**本块内出现最多的行距（众数）**做基准，超过 `1.5×基准 + 1pt` 才算空行 |

### F12–F13：图块合并与信息丢失

| # | 症状 | 原因 | 做法 |
|---|---|---|---|
| F12 | 一张图被渲染成 4 个碎片，每个都带同一个图注 | 原书一张图被拆成多个 figure 区块（图元不连通的聚类） | 同页**纵向重叠 >50%** 的 figure 合并为一块，bbox 取并集、texts 取合并 |
| F13 | 图上残留英文（`Local resource` 只剩 `resource`） | 两行对不齐的行没归成一段，只翻到第一行；或该行被图注的"续行吸收"误吞 | 归组放宽：**中心点接近**也算同段；图注续行吸收要限制"候选必须落在图注水平范围内" |

---

## G. 长书分片翻译（Manning 级体量）

一本书 464 页、13 万词，**不能一次翻完**。分片是必须的，但分片会引入一整类新错误。

| # | 症状 | 原因 | 做法 |
|---|---|---|---|
| G1 | 分片译文键号整体偏移，`多余键` 一堆、`缺失` 一堆 | 凭"第几个块"手写 `"12\|text"`，但真实块号因合并规则与预期不同 | **不许凭记忆写块号**。先 `export_pairs.py <包> <起> <止>` 导出「块号+字段+英文原文」对照，照抄左边那列 |
| G2 | 写完 200 项，一查发现 40 项对不上 | 靠人眼数列表项 | 每写完一个分片立刻跑 `cov.py <包> tx_a.py tx_b.py`，看 `多余` 是否为 0。**多余必须为 0，缺可以为非 0**（分片尚未写完） |
| G3 | 列表块 `item0..item15`（16 项），以为解析错了 | 原书把「设备取证」等子项缩进排成同级 list | 不是 bug。逐项翻译；`show_src.py <包> <块> <块>` 看真实项数 |
| G4 | 表格块键名是 `r0c0..r6c3`，用 `text` 写不进去 | 表格按单元格扁平化 | 键名就是 `head0..headN` / `r{行}c{列}`；先 `dump_block.py <包> <块号>` 看清有哪些键 |
| G5 | 填了 `caption` 却报"无此键" | 该表格在原书把 caption 排成表上方的**独立段落**，被并入前一段正文，块本身没有 caption 字段 | 接受现状（表头即说明），或按 D-类做法在渲染层给表格补默认标题 |
| G6 | 只想改一个字段，结果整份 fill 被覆盖清空 | `make_pack.py` 重新生成骨架时把已填值冲掉 | 打包脚本必须**保留已有 fill 值**（merge-and-keep）；另留 `restore_fill.py` 兜底 |
| G7 | 译文源文件被脚本改坏 | 直接编辑 `*_fill.json` 做增量补丁 | **唯一真源是 `tx_<包>.py`**：手写 dict，`cov.py` 合并 → `freeze_tx.py` 固化。永远不要拿 fill.json 当编辑对象 |
| G8 | PowerShell 里 `python -c "@'...'@"` 反复报 `SyntaxError` / `NameError: name 'work' is not defined` | 引号、反斜杠、`$` 在 here-string 里被吃掉 | **一律写 `.py` 文件再执行**，永不内联多行 Python |

## H. 解析规则变更后的译文重映射

改一条合并规则，全书块号会平移。这时**译文不能丢，也不能靠人工对**。

| # | 症状 | 原因 | 做法 |
|---|---|---|---|
| H1 | 加了"边注聚合"规则后，ch2–ch6 全部报 `缺 N` | 块号整体前移，旧译文键全部错位 | 跑 `remap_seq.py <包> --dry` 先看对齐率；`对齐 N/N 块，缺 0 项` 才落地 |
| H2 | 重映射后译文张冠李戴 | 只按序号平移 | 用**块签名**（字段名集合 + 个数 + 正文首尾指纹）做 LCS 对齐，序号只作兜底 |
| H3 | 重映射报"缺 83 项"，以为丢内容 | 那 83 项原本就是**有意的空旁注续行**（`note12: ""`） | 完整性校验必须**跳过 `\|note` 续行键**，否则永远报缺 |
| H4 | 结构越改越碎，越改越不敢改 | 每加一条聪明规则都引发连锁回归 | 改解析规则的纪律：**一次只加一条**，加完立刻全书重解析 + 跑 `check_all.py`，`缺 0` 才算过 |

## I. 代码截图类插图

Manning 会把代码片段**放大截图**配箭头旁注当"图"用。这类图必须整张略去。

| # | 症状 | 原因 | 做法 |
|---|---|---|---|
| I1 | 代码页顶出现一大片英文代码，与下方清单重复 | 那是"代码放大图"，figtexts 里只有 1–2 段旁注 | 建 `fig_skip.json` 名单，**渲染时保留原图、构建时整图跳过**。判定：图内文字块 ≤2 且是长英文旁注、紧随其后就是 code 块 |
| I2 | 跳过渲染后图仍在 docx 里 | 只改了渲染器，没改构建器 | 两处都要改：`render_figs.py`（不叠中文）+ `build_docx.py`（`SKIP_FIGS` 集合直接 `continue`） |
| I3 | 图表标题仍是英文（`target class Overview`） | matplotlib 把标题画进了**栅格像素**，不在文字层 | 无解，除非重绘整图。**交付说明里明确列出**，不要假装全中文化 |

## J. 整书合并与交付

分章 docx 拼成一本时，`docxcompose` 会吃掉分节，页眉只剩第一章的。

| # | 症状 | 原因 | 做法 |
|---|---|---|---|
| J1 | 全书页眉全是"版权信息"，第 30 页标着 front_copyright | `append()` 并入同一节，页眉沿用底板 | **先 `add_section(NEW_PAGE)` 再 `append`**，然后给新节单独写页眉（`header.is_linked_to_previous = False`） |
| J2 | 合并后凭空多出 30 多张空白页 | 在 `append` **之后**才 `add_section`，多出一个空节 | 顺序必须是：分节 → append → 设页眉 |
| J3 | 全书 376 页，怀疑有内容重复 | 各章页数相加本来就是这个量级 | 用 `find_blank.py` 扫空白页（字符 <120 且无图）验证，`0 张` 即可放心 |
| J4 | 目录页码对不上 | 目录是静态生成的，PDF 页码在合并后才确定 | 目录先只列章节名，页码留到合并后二次回填；或直接不做页码 |
| J5 | 交付物散在 `out/` 里，用户不知道哪个是最终版 | 分章 docx 与全书 docx 混在一起 | 最终交付只用 `present` 给两份：`全书.docx` + `全书.pdf`；分章件仅作过程产物 |

## K. 书稿本身的坑（内容层，非代码）

| # | 症状 | 原因 | 做法 |
|---|---|---|---|
| K1 | 章节正文同一段话出现两次，一次完整、一次只剩尾巴 | 原书排版把跨页续行单独成段，解析后一段变两段 | 段落续接只看「前段是否收句 + 后段是否小写开头」，不做长度阈值 |
| K2 | 边注（DEFINITION / NOTE）被切成 8 个碎片，正文读不通 | 边注框内每行都是独立 para，且前面半句被切在框外 | 把「全大写小标题 + 紧随的连续 para」聚成一个 note；若标题前那段未收句，把尾巴并进来 |
| K3 | 参考文献 90 多条，全译会毁掉可检索性 | 文献条目是专有名词堆 | **只译说明性段落，条目原文保留**；用 `keep_refs.py` 把 list 条目从 src 原样搬进 fill |
| K4 | 侧栏（sidebar）在一个 5 块页面上炸成 49 段 | 判据用了"缩进 + 颜色"，两色书里满页都是缩进 | 侧栏判定必须**叠字体特征**（本页特有的 FranklinGothic / Wingdings），不能只看几何 |
| K5 | 英文图内注释残留半句 | 图注续行吸收了图内的旁注行 | 续行吸收限定「候选必须落在图注水平范围内」 |

## L. 交付前的"看着像对、其实不对"

| # | 症状 | 原因 | 做法 |
|---|---|---|---|
| L1 | `check_all.py` 全 OK，读者一眼看出代码没缩进 | 完整性校验只查"填没填" | 必查项分离：① 覆盖率 `缺 0`；② 目视抽查 2–3 个嵌套代码块 |
| L2 | 页眉章名正确但页码从 1 重新开始 | 分节后未链接页码域 | 合并后抽查 3 个不同章节的首末页页码连续性 |
| L3 | 图注中文对了，英文原名也照搬但太长占版面 | 图注同时保留中英 | 中文主标题 + 8.5pt 灰字英文原名，超长按句截断 |
| L4 | 表格是真表格但列宽挤成一团 | 未设列宽/字号 | 表格统一 9pt，首列给足宽度，长文本列自动换行 |

---

## M. 排版"能过校验但不好看"（第三本书实战：Mac 本地 AI 应用，21 份文档 / 274 页）

> 来源：《Build Applications with Local AI Models on a Mac》中文版。
> 这一组坑的共同点：**`audit.py` 全绿，用户却说排版不满意**。它们全部出在
> `build_docx.py` / `merge_book.py` 的呈现层，不在解析层与翻译层。

### M1. 只查"有没有"，不查"好不好看"——这是最大的盲区

| # | 症状 | 原因 | 做法 |
|---|---|---|---|
| M1 | 21 章 audit 全过，交付后用户说排版差 | audit 只验块序列/漏译/溢出/图片数，**没有一条验留白、页码、页眉重复** | audit 之外加一轮**版面体检**（见下方 `layout_check.py`），把"空白过半页数""页码错位页数""页眉是否逐章变化"作为硬指标 |
| M2 | 正文页大片空白 | 只在章首页做美化，正文块后 `after` 间距过大（8pt）+ 行距 1.62 | 正文 `after=6`、行距 **1.5**；1.62 在 10.5pt 下视觉已偏松 |
| M3 | 每章都从新页开始，但上一章末尾空掉半页 | 用「空段落 + `<w:br type=page>`」分页 | 改用 **`paragraph_format.page_break_before = True`**（挂在章标题段落上）。空段落分页会额外产生一页空白 |

### M2. 我自己"加戏"加出来的排版问题

原书没有的东西不要加。加之前先问：读者需要它吗？它会占多少版面？

| # | 症状 | 原因 | 做法 |
|---|---|---|---|
| M4 | 74 / 274 页底部拖着一行小字"图内文字对照 …"，页面挤 | 为了让读者对照中英，给每张图追加了一行中英标签对照 | **默认关闭**（`SHOW_FIG_NOTES = False`）。图已经就地中文化了，再列一遍是冗余。真需要时做成可选开关 |
| M5 | 代码截图类插图下面又整段重复代码 | 图本身是代码，再列"图内文字对照"等于抄两遍 | 按 `code_like` 占比 ≥50% 判定，这类图**跳过对照行** |
| M6 | 目录里"1""2""3"独占一行且是大号标题字 | 原书目录的章节号是独立文本块，被判成 heading | 只含 `^\d{1,2}$` 的 heading **直接丢弃**（条目文本里已含编号）；`appendix A` 这类保留但降为正文小字 |

### M3. 分章生成 → 合并，必然遇到的四件事

| # | 症状 | 原因 | 做法 |
|---|---|---|---|
| M7 | 全书页码每章从 1 重来（274 页里 256 页错位） | 每份 docx 都是独立文档，各自有 `<w:pgNumType start=1>`；`docxcompose` 合并后各节保留自己的起始页码 | 合并**之后**统一清掉所有节的 `w:pgNumType`：`for sec in doc.sections: for el in sec._sectPr.findall(qn('w:pgNumType')): sec._sectPr.remove(el)` |
| M8 | 全书页眉都印第一章 | `docxcompose` **不会带过子文档的页眉**，新节默认继承上一节 | 每加一节：`sec.header.is_linked_to_previous = False`，然后**在 append 之后**按 `doc.sections[-1]` 重写页眉文字（顺序：分节 → append → 设页眉） |
| M9 | 表格跨页后，续页没有表头 | `<w:tblHeader>` 加了但 LibreOffice 不认 | **元素顺序错了**。`trPr` 里 `cantSplit` 必须在 `tblHeader` 之前：先 `keep_row_together` 再 `repeat_header`，且 `tblHeader` 用 `cantSplit.addnext()` 插入 |
| M10 | docx 里表格正常，转 PDF 后表头丢了 | 用 docxcompose 合并后再转 PDF | 改用 **逐份转 PDF 再 `pymupdf.insert_pdf` 拼接**：每份按自己正确的排版渲染，表头/页眉/页码都保真，还能顺手 `set_toc()` 生成书签 |

### M4. 排版体检脚本（交付前必跑）

```python
# layout_check.py —— 三分钟跑完，专治"看着不对劲"
import pymupdf, re
d = pymupdf.open('out/pdf/全书.pdf')

# 1) 页码错位：页脚数字 != 物理页号
bad = []
for i in range(d.page_count):
    r = d[i].rect
    t = d[i].get_text('text', clip=pymupdf.Rect(0, r.height-60, r.width, r.height)).strip()
    m = re.fullmatch(r'\d+', t)
    if m and int(m.group()) != i+1:
        bad.append((i+1, int(m.group())))
print('页码错位页数', len(bad))          # 必须 0

# 2) 留白过多：正文块最低点 / 版心高度 < 0.5
semi = []
for i in range(d.page_count):
    r = d[i].rect
    body = pymupdf.Rect(r.x0, 60, r.x1, r.height-60)
    bl = [b for b in d[i].get_text('blocks', clip=body) if b[4].strip()]
    if not bl:
        semi.append((i+1, 'EMPTY')); continue
    used = (max(b[3] for b in bl) - 60) / (r.height - 120)
    if used < 0.5:
        semi.append((i+1, round(used, 2)))
print('空白过半', len(semi), semi[:10])  # 章末页允许；正文中部出现就是问题

# 3) 页眉逐章：抽查若干页，确认章名不同
for i in (21, 41, 100, 200):
    r = d[i].rect
    print(i+1, d[i].get_text('text', clip=pymupdf.Rect(0, 0, r.width, 52)).strip())

# 4) 行距与字号体检：行距众数应 ≈ 字号 × 1.4~1.6
```

### M5. 判断"排版不满意"的具体来源（优先级排序）

用户说"排版不满意"时，按这个顺序查，命中率从高到低：

1. **页码/页眉**（M7、M8）——翻两页就能发现，最刺眼
2. **多余的一行行小字**（M4、M5）——占版面、打断阅读节奏，且是自己加的
3. **大片留白**（M2、M3）——像"没排完"
4. **章首页没另起一页**（M3）——专业书的基本要求
5. 表格跨页无表头（M9）——查资料时很烦
6. 行距过松（M2）——"看着累"但说不清

**改完必须重新出 PDF 并逐页抽查**，不要只看 docx。docx 与 PDF 的呈现差异（尤其表头、分页）会让问题在 docx 里看不出来。

### M6. 一个反直觉的教训

这轮我为了修一个"孤立代码尾巴"（`homebrew/bin/.` 单独成块），去改 `parse_layout.py` 的
块分类，结果**全书块号平移，10 份文档的表格译文全部错位**，花了四轮才回滚干净。

**正确做法是改呈现层，不是改解析层**：

```python
# build_docx.py 里，code 分支入口判断"是不是行内代码的孤立尾巴"
_ct = (blk.get('text') or '').strip().replace('\xa0', ' ')
_frag = (len(_ct) <= 40
         and re.fullmatch(r'[`\w./~@\-]+[.`]?', _ct) is not None
         and len(blk['text'].split('\n')) == 1)
if _frag:
    _last = next(p for p in reversed(doc.paragraphs) if p.text.strip())
    _last.add_run(' ' + _ct.strip('`').rstrip('.`'))
    continue          # 不生成独立代码框
```

判断依据：**修这个 bug 会不会改变块的数量/顺序？** 会 → 千万别在解析层改，
在呈现层用"合并到上一段"的方式解决。解析层的任何块数变化都意味着全部译文要重映射。

---

## N. 骨架文本流水线（第三种流程）专有坑

> 来源：20+ 份文档的书（18 章 + 2 附录 + 前言）。改用"块号纯文本"而非 JSON，
> 主要风险从"键号写错"变成"**块号整体平移**"。

| # | 症状 | 原因 | 做法 |
|---|---|---|---|
| N1 | `build_doc.py` 报"块序列不一致"，首个差异在中间某块 | 少写/多写了一个 `@@B` | 打开 `_skel.txt` 数块号，不要数 `_zh.txt`（后者是你写的，错的就是它） |
| N2 | 表格内容跑到列表项里，页面上出现 `4. CAP: 表 1.1…` | `@@B` 块号写错，把表格内容写进了列表块 | 表格块号必须从 `_dump.txt` 的 `[TABLE]` 行确认，**不要凭顺序猜**；改完重跑 `build_doc.py` 并扫一遍 docx 里有没有 `CAP:`/`HDR:`/`ROW:` 残留 |
| N3 | 改一处解析规则后，全部文档译文错位 | 改的是 `parse_layout.py`（解析层），块数变了 | 见 M6：**先问"会不会改变块数"**。会，就别在解析层修 |
| N4 | `slice_layout.py` 报"缺少 docs.json" | 脚本在 `scripts/` 下，`ROOT` 算成了 `scripts/` | 用向上找 `book.json`/`docs.json` 的 `project_root()`，不要直接 `dirname(__file__)` |
| N5 | 生成的 docx 文件名/页眉标签不对 | 文件名规则散落在多个脚本里 | 统一一个 `out_name(d)`：front → `00_标题`；ch → `NN_第N章_标题`；apx → `A_附录A_标题` |
| N6 | 单份重跑后整本书没更新 | 只跑了 `build_doc.py`，没重新合并 | 单份 → `build_doc.py <doc>`；全书 → `merge_book.py` + `build_book_pdf.py` |

---

## O. 图内文字渲染：实测出的六个真缺陷

> 来源：Manning 2025 单色书，109 张图、603 个文字块。下面每一条都是「渲染报告全绿
> 但人眼一看就不对」的类型——`OVERFLOW`/`MISSING` 检测不到。

| # | 症状 | 原因 | 修法 |
|---|---|---|---|
| O1 | 黄色高亮底上的文字擦除后留一圈黄边 | 背景色取 bbox **内部**众数，取到的就是高亮色本身，等于没擦 | 取 bbox **外扩 pad 后、剔除深色墨迹**的颜色众数（见下） |
| O2 | 彩色填充块里的白字变成黑字 | 只判「亮度 < 110 → 用白字」，浅色底（米黄/浅蓝）走了黑字分支 | 用取到的**背景亮度**决定墨色，不要用固定色 |
| O3 | 长注释中文被底边裁掉半行 | 译文字数比原文多，行数不变但总高变大，仍按 bbox 居中 → 上下各溢出一半 | 总高必须落进 bbox：**先压行距（下限 1.14），再缩字号** |
| O4 | 同一段文字被拆成 3 行、把图例挤成一团 | 一句长英文（`Transistors (thousands) Single-thread performance…`）被当单行整体重排 | 极窄框（宽 < 60pt）**保留英文原样**，不要硬塞中文 |

### O1. 背景色采样：先外扩，再剔除墨迹

原实现「取 bbox 内部像素众数」在三种底色上全错：

```python
# 错：bbox 内部＝文字本身所在的彩色底，取到的是高亮色
def sample_bg(img, box):
    crop = img.crop(box); cnt = Counter(crop.getdata())
    return cnt.most_common(1)[0][0]
```

正确写法——**外扩 pad、跳过 bbox 内部、剔除深色墨迹**，三步合一：

```python
def sample_pad(img, box, pad=10):
    """外扩 pad 后，剔除深色墨迹像素，取剩余颜色的众数。

    白底得到白、黄底得到黄、深底得到深色 —— 三种情况都能正确擦除。
    """
    x0, y0, x1, y1 = [int(v) for v in box]
    W, H = img.size
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(W, x1 + pad), min(H, y1 + pad)
    px = img.crop((x0, y0, x1, y1)).load()
    cnt = {}
    for yy in range(y1 - y0):
        for xx in range(x1 - x0):
            c = px[xx, yy]
            if (c[0]*299 + c[1]*587 + c[2]*114) / 1000 < 175:
                continue                       # 深色墨迹，跳过
            cnt.setdefault((c[0]//10, c[1]//10, c[2]//10), []).append(c)
    best = max(cnt.values(), key=len)
    n = len(best)
    return (sum(c[0] for c in best)//n,
            sum(c[1] for c in best)//n,
            sum(c[2] for c in best)//n), pad
```

**擦除时 pad 要随底色变**：浅底 3px 够，彩色高亮底要给到 11px，否则边缘留一圈彩色残边。

### O2. 墨色跟着背景走

```python
lum = (bg[0]*299 + bg[1]*587 + bg[2]*114) / 1000
ink = (255, 255, 255) if lum < 110 else (34, 34, 34)
```

米黄底 `(247,242,232)` 亮度 242 → 黑字；深蓝底 `(72,108,134)` 亮度 105 → 白字。
判据只能是**实测背景**，不能是「这块看起来应该是浅色」。

### O3. 总高必须落进 bbox（这是最容易被忽略的一条）

`fit_text()` 只保证**宽度**放得下，不管高度。中文比英文占高，一行译文常常比
原文一行高 15~30%，3 行就超框。而 `OVERFLOW` 检测只比宽度，所以报告全绿、图上却缺半行。

正确顺序（**先压行距，再缩字号**）：

```python
PITCH_MIN = 1.14                      # 再低行会叠字，这个下限不能破
pitch = 1.22
if len(lines) * fs * pitch > bh:
    pitch = max(PITCH_MIN, bh / max(1, len(lines) * fs))

guard = 0
while len(lines) * fs * pitch > bh + 0.5 and fs > 4.5 * zoom and guard < 60:
    fs -= 1
    f_try = ImageFont.truetype(path, fs)
    lines = wrap_by_width(cn, f_try, limit)
    pitch = (1.22 if len(lines) * fs * 1.22 <= bh
             else max(PITCH_MIN, bh / max(1, len(lines) * fs)))
    guard += 1
```

同时 `fit_text()` 的 `attempt()` 也要带高度约束，否则选出来的字号本身就过高：

```python
def attempt(fs, maxh=None):
    f = ImageFont.truetype(path, fs)
    lines = wrap_by_width(txt, f, limit)
    widest = max((measure(l, f) for l in lines), default=0)
    ok = widest <= limit * 1.001 and len(lines) <= max_lines
    if maxh is not None and len(lines) * fs * 1.15 > maxh:
        ok = False                     # 高度也要放得下
    return f, lines, widest, ok
```

**渲染报告的判据也要补高度**，否则永远发现不了这类问题：

```python
report.append({'fs_pt': round(fs / zoom, 1),
               'lines': len(lines),
               'over_w': round((widest / bw - 1) * 100, 1),
               'over_h': round((len(lines) * fs * pitch / bh - 1) * 100, 1)})
# over_h > 4% 同样报 OVERFLOW
```

### O4. 放不下的框：`KEEP` 比硬塞好（三类判据）

硬塞的结果是「渲染报告全绿、图上一片糊」。判据要**按容量算**，不要只按尺寸：

```python
_cjk_pt = 4.6                                     # 汉字最小可读字号
_cnlen = len(cn.replace('\n', ''))
limit = max(6, bw + min(bw * 0.06, 0.9 * zoom) * 2)   # 必须在判据之前算好！
_per_line = max(1, int(limit / (_cjk_pt * zoom)))
_need_lines = -(-_cnlen // _per_line)             # 向上取整

tiny   = (bw < 12 * zoom and bh < 12 * zoom)                       # 刻度、单符号
narrow = (bw < 60 * zoom and bh > bw * 1.6 and _cnlen > _per_line * 2)  # 图例条
short  = (bh < _cjk_pt * 1.15 * _need_lines * zoom)                # 高度根本不够
if narrow or tiny or short:
    report.append({'id': b['id'], 'status': 'KEEP'})
    continue                                       # 不叠中文，原图像素不动
```

**踩过的坑（务必注意顺序）**：`limit` 最初定义在判据**之后**，导致判据里用的是
上一轮循环残留的值，`narrow` 判断全错、两条真溢出漏网。
凡是"判据要用到的变量"，一定要在判据之前算。

实测收益：109 张图的书里 `KEEP` 命中 109 个块（约 19%），全是图例条与坐标轴刻度；
之前硬塞中文的那些在目视检查里全是糊的。**这类"做不到"要在交付说明里列出来**。

### O5. 显式换行 `\n` 要严格分行（但超宽的那一行还要再拆）

译者按原文分行给出 `ZH 第一行\n第二行` 时，不能被自动换行逻辑重排——否则
原本 3 行的图例会被重新断成 5 行，行数和位置全乱：

```python
if '\n' in cn:
    explicit = [x.strip() for x in cn.split('\n') if x.strip()]
    # ① 在「每行都放得下」的字号里挑最大的
    fs = max(1, int(4.6 * zoom))
    for cand in range(int(round(cap)), int(4.6 * zoom), -1):
        f_try = ImageFont.truetype(path, cand)
        widest = max(measure(x, f_try) for x in explicit)
        if widest <= limit * 1.001 and len(explicit) * cand * 1.12 <= bh * 1.4:
            fs = cand
            break
    lines = explicit
    # ② 字号到底仍超宽 → 只拆超宽的那一行，别动已给的语义分行
    f_chk = ImageFont.truetype(path, fs)
    if max(measure(x, f_chk) for x in lines) > limit * 1.001:
        rebuilt = []
        for seg in lines:
            rebuilt.extend([seg] if measure(seg, f_chk) <= limit * 1.001
                           else wrap_by_width(seg, f_chk, limit))
        lines = rebuilt
```

**为什么不能整体 `wrap_by_width`**：译者给的分行是按原文语义切的（图例一条一行、
坐标轴一个标签一行），整体重排会把 3 行变成 5 行，位置和视觉对应全乱。

### O6. 图块裁剪：左右多留 26pt

中文标签比英文宽，居中后容易出框；裁剪时左右各留 26pt，
下边留 3~5pt（留太多会把下方图注切进来）：

```python
clip = pymupdf.Rect(fig['bbox'][0] - 26, fig['bbox'][1] - 3,
                    fig['bbox'][2] + 26, fig['bbox'][3] + 5)
clip = clip & page.rect
```

渲染后还要**夹紧水平位置**，避免长行贴到图片边缘被切：

```python
tx = max(2.0, min(tx, img.size[0] - wpx - 2.0))
```


---

## P. 前置页（封面 / 版权页 / 目录）：别让矢量图形走图块流程

> 来源：同一本 Manning 2025 书。用户反馈「封面排版不好看，内容提要生成的有些问题」，
> 追下去发现是**两类东西被当成"图"处理了**。

### P1. 封面出版社 logo 被渲染成空白图

`MANNING` logo 在 PDF 里是**白色填充路径**（`fill=(1.0,1.0,1.0)`，靠白色压在底上
才显形）。走图块流程 → 裁剪区渲染成白底 + 白色路径 → 得到一张纯白 PNG。

症状：docx 里那位置是一片空白，audit 不报错（图数对得上）。

**判据**：凡是 `drawings` 里 `fill == (1,1,1)` 或接近纯白的整块路径，
都是"反向留白"的装饰元素，**不能当图**。

### P2. 简目的竖排数字条被拉成巨图

原书 brief contents 左侧有一串竖排的 `1`…`9`（每章一个），是矢量文字或图形。
走图块流程后按原始宽度插入，一张 172×1200px 的图横在页面左边，
**把章名全盖住了**。

症状：页面上半是几个巨大数字 + 被截断的文字（`Big`、`Tok`、`Tra`…）。

### P3. 正确做法：前置页整页交给专门的排版函数

前置页（封面/版权/目录）本来就该用**文字 + 段落**排，不该有图。
把它们从通用图块流程里摘出来，写一个独立 builder：

```python
def build_front(zh, pages):
    # ---- 封面：右对齐版式 ----
    for _ in range(5): blank_line(14)                  # 顶部留白
    para(zh[0], size=30, bold=True, color=NAVY,
         align=RIGHT, spacing=4)                        # 中文大标题
    para('How Large Language Models Work',
         size=12, italic=True, color=LIGHT, align=RIGHT)  # 英文副标题
    hr(color=NAVY, sz=6)

    for _ in range(9): blank_line(14)
    for name in (zh[3], zh[4], zh[5]):
        para(name, size=13, align=RIGHT, spacing=12)   # 作者，字距拉开

    for _ in range(11): blank_line(14)
    para('MANNING', size=14, align=RIGHT, spacing=100)  # 字距 100（1/20pt）
    para('SHELTER ISLAND', size=9, align=RIGHT, spacing=45)
```

要点：
- **留白用空段落，每段固定 line=14pt**，比 `space_before` 好控
- 字距用 `w:spacing`（单位 1/20pt），`MANNING` 给 100 才有原书那种疏朗感
- 标题右对齐 + 细分隔线，是 Manning 封面的固定骨架

### P4. 目录页码必须换成中文版实际页码

原书目录写的是英文版页码（1/14/29/46…），中文版因为字号行距不同，
实际落在 9/19/30/44/60/79/96/109/121/137。**照抄原书页码等于全错**。

做法：合并前先算一遍各章起始页，写进一个 json，目录生成时读取：

```python
# chapter_pages.py —— 按 docs.json 顺序累加各份 PDF 页数
pages, cur = {}, 0
for d in sorted(docs, key=sort_key):
    n = pymupdf.open(f'out/pdf/{out_name(d)}.pdf').page_count
    if d['kind'] == 'ch':
        pages['ch%02d' % int(d['num'])] = cur + 1
    elif d['kind'] == 'apx':
        pages['ap%s' % d['num']] = cur + 1
    cur += n
```

**顺序铁律**：`merge_book` → `chapter_pages.py` → `build_front` → 再合并一次。
页码依赖各章 PDF，所以必须先转 PDF 才能算准。

### P5. 目录行用制表位，不要用空格对齐

```python
p.paragraph_format.tab_stops.add_tab_stop(Cm(1.35), WD_TAB_ALIGNMENT.LEFT)  # 章名起点
p.paragraph_format.tab_stops.add_tab_stop(Cm(TEXT_W_CM), WD_TAB_ALIGNMENT.RIGHT)  # 页码贴右
add_run(f'{num}'); add_run('\u2002\u25AA  '); add_run(title); add_run('\t'); add_run(page)
```

用空格补到页码会让每行长短不一，制表位才能让 9 个页码严格落在同一条竖线上。

### P6. 版权页分块，不要一坨

10 个段落连排会糊成一片。按语义分三块，块间留白：

```python
groups = [[7, 8, 9],        # 联系信息
          [10, 11, 12, 13, 14],   # 法律声明
          [15, 16]]         # 出版信息
for gi, g in enumerate(groups):
    for k in g:
        para(zh[k], before=14 if k in (10, 15) else (0 if k == 7 else 4),
             line=13.6, align=JUSTIFY)
```

同时检查**原文块本身有没有重复**：原书 PDF 把「更多信息请联系」抽成了独立一块，
上一块结尾又写了同一句，直接照译会出现两遍（本项目的实际踩点）。

### P7. 前置页也要有页眉页脚

封面 / 版权页 / 目录三页同样要挂页眉和页码，否则合并后这三页是"裸页"
（`layout_check.py` 会报页眉样式数不连续）。



### P8. 封面印出「第　章」、还混进两个黑方块

症状：封面顶部一行小字是「第　章」（章号空白），中间出现两块黑色斜面矩形，
文字散落、大量留白，整页明显不对。

原因有两个，都属同一类错误——**把封面当章节页处理**：

1. 渲染器里 `front_open` 走的是 `add_chapter_open`，该函数无条件拼
   `f'第 {blk["num"]} 章'`；封面块没有 `num` 字段，于是拼出「第　章」。
2. 原书封面的 logo 是**矢量装饰**（白色填充路径压白底显形），
   走图块流程后 `get_image_info()` 采到的是黑色轮廓，按原始像素宽度插入
   就成了两块巨大的黑方块。

**做法**：

- 封面单独走 `add_cover()`，**整页文字排版，不放任何图片**；
  交付前断言 `len(page.get_image_info()) == 0`。
- `front_open` 分两路：有 `cover` 元数据 → 封面；否则 → `add_front_head()`
  （只出中文标题 + 英文斜体副标题 + 分隔线，**不带任何编号**）。
- 前置内页（版权/赞誉/献词/前言）一律不得出现「第 X 章」；
  全书扫描断言 `'第　章' not in page_text`。

字段约定（`_trans.json` 的首块）：

```json
{"type":"front_open","title":"Elasticsearch 实战","orig_title":"…",
 "cover":{"title":"…","orig_title":"…","edition":"第 2 版",
          "authors":["Madhusudhan Konda　著"],"foreword":"Shay Banon　作序",
          "press":"MANNING","press_sub":"SHELTER ISLAND","site":"www.manning.com"}}
```

版次只出现一次（放 `edition`），标题里不要再重复「第 2 版」。

### P9. 侧栏/便签被分页从中间切开

症状：蓝色框（sidebars）或米色便签（callout）上半截在页尾、下半截在下一页，
读者看到两个残框。用户会直接指出「这一块最好在同一页显示全」。

这是**系统性**问题，不是个别页：实测一本 520 页的书有 100+ 处。

原因三层，逐层排除：

1. **只设了 `keep_with_next`**。框是一串段落，必须**每段** `keepLines`
   （段中不分页）+ 除末段外全部 `keepNext`，整串才连贯。
2. **`python-docx` 的 `keep_together` 不落地**。实测
   `paragraph_format.keep_together = True` 之后，`pPr` 里根本没有
   `<w:keepLines>`，`<w:keepNext>` 还会被写成 `val="0"`。必须直接写 OOXML：

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

   改完**必须回读 XML 验证**（`pPr.find(qn('w:keepLines'))` 不为 None），
   否则会以为改好了其实没生效。
3. **框的范围算错**。收尾若用 `reversed(doc.paragraphs)` 找「最后一个非空段」，
   会越过框边界把**框外段落**也粘进来，真正的框反而不连续。
   必须在框开始时记 `start_idx = len(doc.paragraphs)`，收尾用精确区间。

**判据要写对**。不能用「矩形贴顶/贴底」判断被切断——正常开始的框也贴顶。
正确判据：第 N 页底部有底色矩形，且第 N+1 页顶部有**同色、宽度相近（±12px）**
的矩形，才是同一个框被切开：

```python
if r.y1 >= 795: bot[i+1].append(round(r.width))
if r.y0 <= 62:  top[i+1].append(round(r.width))
# 宽度相近才配对
```

交付闸门：`确认被分页切开的侧栏/便签：0 处`。

**超长框怎么办**：框本身超过一页时无法整框保持，此时退化为逐段
`keepLines`（每段自身不跨页），并在交付说明里列出这类长框，
不要为了「整框同页」把字号压到不可读。

---

## Q. 续译与交付边界（15 章 Manning 书续做实测）

> 来源：接手一个已翻译大半的 `ds-slm` 项目，补完第 14、15 章并合订全本。
> 这一组坑都不涉及解析算法，而是**“以为已经完成”造成的返工**。

### Q1. 进度笔记说完成了，磁盘上并没有

症状：交接记录写「已交付 1–13 章」，实际 `out/` 只有 1–3 章，`work/` 也缺多章译文。
如果照着笔记从第 14 章开始，中间 10 章会被永久跳过；反过来若不信任何记录从第 1 章重做，
又会覆盖已经合格的产物。

**做法**：以三件套为准逐个核对，不看总结——

```bash
for n in $(seq 1 15); do
  test -f work/ch${n}_trans.json && test -f out/$(printf '%02d' $n)_*.docx \
    && echo "ch$n 可能是完成态" || echo "ch$n 未完成"
done
```

再对“可能是完成态”的章跑 `audit.py`。`trans` 存在但 `docx` 缺失 = 半成品；
`docx` 存在但 `trans` 缺失 = 旧版产物，改动前先确认来源，别直接覆盖。

### Q2. `PS`/`LS` 按顺序写译文时，数量断言失败就猜下标

症状：`apply_tr.py` 报 `PS 98 != 99 个文字块`，于是手工把译文往后挪一位，
结果后面整章错位。

原因通常是解析层多出/少了一个**碎片块**（图注后的短句、被拆开的列表续行、
只有一个标点的 callout），而不是译者漏了一大段。

**做法**：断言失败先打印骨架的类型序列和已有译文键，找到第一个差异块。轻量项目里
用 `PS`/`LS` 顺序写法就是为了避免下标；一旦数量不等，**回到骨架定位，不要靠猜**。
只有标点的块（`。`、`，`）要并回上一句译文，不能单独留一个标点——CJK 检测会把它
判成未翻译，且读者会看到一个孤立的句号段落。

### Q3. 表头重复了，数据行却在跨页处被拆开

症状：表 14.1 跨页后，下一页顶部有完整表头，但第一行只有右列的一截公式，
「指标」「RAG 阶段」两格全空。`audit.py` 全绿，因为块数、图数、DPI 都没问题。

原因：只给表头加了 `w:tblHeader`，没给数据行加 `w:cantSplit`。Word 允许单行跨页，
一行较高时就会从中间劈开。

**做法**：建表时给**每一条数据行**加 `w:cantSplit`，表头再单独加 `w:tblHeader`。
目视检查表格时，必须同时看表题页和下一页；只看表题页会漏掉这种“无主语续行”。

### Q4. 流程图被解析成表格：不要改块类型

症状：GraphRAG 流程图被解析成一个 22×3 的 `table`，单元格顺序完全打乱，直接渲染是
一堆竖排单词。

**做法**：保留 `table` 类型，按图的语义重建表头与行（例如「索引阶段 / 中间产物 /
查询阶段」），块数不变。**不要改成 `figure`**：块类型一变，`audit.py` 的块序列校验
立刻失配，后续所有译文索引也要重排。宁可表格不是原图的视觉复刻，也要保证结构可读、
块序列稳定。

### Q5. 图内字号 6–7pt：先缩短译名，不要先接受小字

症状：`Agentic AI` 译成「智能体式 AI」后字号被压到 6.2pt；`Does the database have info?`
译成两行后 7.0pt。渲染报告只标 `fs_pt < 7.5`，不算硬错误，但印出来几乎看不清。

**做法**：按「语义缩写 → 单行化 → 再渲染」的顺序处理：

- `Agentic AI` → 「智能体」（图内上下文已足够）
- `Does the database have info?` → 「找到信息？」
- `Gets appropriate prompt for the category` → 「获取类别提示」

缩完重渲染，字号通常回到 7.7–8pt，且不丢语义。只有缩写后仍放不下时，才按 `KEEP`
保留英文；不要为了保住完整译名把字号压到 6pt。

### Q6. 在错误的工作目录调用项目脚本，配置读不到

症状：`build_front.py` 报 `未找到 PDF`，或只设 `BOOK_ROOT`/`BOOK_PDF` 后报
`KeyError: 'orig_text_w'`。脚本本身没错，是 `bookconf` 按**当前目录**找 `book.json`，
而命令是在工作区根目录执行的。

**做法**：优先用项目 runner（它 `cwd=项目根`）。必须单独调用时，让 Python 在项目根
运行，而不是只注入两个环境变量——`book.json` 里还有版心宽度、字体、DPI 等字段，
缺一个就可能在 import 阶段炸掉。

### Q7. 把模型的“坏输出”翻译成“正确答案”

症状：第 15 章展示 AutoThink 的失败案例，原文模型把 750 颗算成 3250、把 1350 分钟
加成 1353 分钟 6 秒，还反复自我怀疑。译者“好心”改成正确算式，读者就看不懂作者为什么
说这次评估失败。

**做法**：`<think>` / `<reasoning>` 内的错算、重复、跑题、格式错误全部照译；标签、
公式定界符、数字、`<|im_end|>` 保留。译文只负责让中文读者看懂“模型当时是怎么错的”，
不负责修正模型。原书用这些例子讲过度思考与评估失败，改对等于抽掉论据。

### Q8. “全书完成”却漏了前置和索引，或把广告也译了

症状：15 章正文都交付了，但没有封面/序言/前言，读者拿到的是“从第 1 章开始”的裸文档；
或者反过来，把出版社广告、相关书目、liveBook 推广页也逐字翻译，成品显得杂乱。

**做法**：交付前先定义范围——**前置部分 + 正文**是默认范围；出版社广告与相关书目不译；
原书索引不照译（页码绑定英文版排版，中文重排后全部失效），要做就用中文版实际页码重建。
合订本交付时说明范围，别用“全书完成”掩盖缺口。

## R. 合订本保真、封面重建与彩色图内文字（297 页 Manning 实战）

这一组来自一本 297 页、22 份独立文档、63 张矢量图的书。骨架流水线本身跑得很顺，
**全部返工都发生在“合订”和“图内彩色底”这两处**。

### R1. 合订本 docx 用 `lxml` 搬 XML → 图全丢 + LibreOffice 打不开

症状三连（按出现顺序）：

1. 合订后 `inline_shapes` 有 63 个，但 `uniq(rId)` 只有 8 个 —— 63 张图挤在 8 个关系上；
2. LibreOffice 报 `source file could not be loaded`，合订 PDF 转不出来；
3. 勉强转出来的 PDF 里 `get_images()` 为 0，整本书一张图都没有。

两个独立成因，必须一起修：

**成因一：rId 撞车。** `deepcopy(child)` 搬过来的是源文档的 `r:embed="rId12"`，
而合订本自己也有 `rId12`。关系表按 rId 索引，于是所有图都指向合订本自己的那几张。

**成因二：`xmlns:a` / `xmlns:pic` 丢失。** 源文档把 DrawingML 命名空间声明在**局部元素**上，
深拷贝搬走后声明留在原地；合订本根节点又没有这两个前缀 → XML 不合法 → LibreOffice 拒绝加载。

**正确做法：**

```python
def _rehome_media(master, src, root):
    """搬运前把每个 r:embed/r:link/r:id 重新建立成合订本的关系。"""
    from docx.oxml.ns import nsmap
    R_NS = nsmap['r']
    for el in root.iter():
        for attr in (f'{{{R_NS}}}embed', f'{{{R_NS}}}link', f'{{{R_NS}}}id'):
            rid = el.get(attr)
            if not rid:
                continue
            rel = src.part.rels.get(rid)
            if rel is None:
                continue
            if rel.is_external:
                new = master.part.relate_to(rel.target_ref, rel.reltype,
                                            is_external=True)
            else:
                new = master.part.relate_to(rel.target_part, rel.reltype)
                new = getattr(new, 'rId', new)
            el.set(attr, new)
```

命名空间**不要**试图 `el.set('xmlns:a', ...)` —— `lxml` 直接抛
`ValueError: Invalid attribute name 'xmlns:a'`。改成**保存后按字节修补根标签**：

```python
x = zin.read('word/document.xml').decode('utf-8')
m = re.search(r'<(w:document|document)\b[^>]*>', x)
extra = ''.join(f' xmlns:{p}="{u}"' for p, u in NS_DECL.items()
                if f'xmlns:{p}=' not in m.group(0))
x = x[:m.start()] + m.group(0)[:-1] + extra + '>' + x[m.end():]
```

**验收断言**（缺一不可）：

```python
assert len(set(md5(part.blob) for each inline_shape)) == 图块总数
assert 'xmlns:a=' in document.xml 根标签
assert len(pymupdf.open(merged_pdf)[0].get_images()) > 0
```

### R2. 合订 docx 再转 PDF 不稳，最终 PDF 走“拼接 + 重写页码”

即便修好 R1，2MB 的 `document.xml` 让 LibreOffice 加载仍然很慢、偶发失败。
**可靠做法：拼接各分册 PDF，然后逐页把页脚数字涂掉重写。**

```python
doc = pymupdf.open()
for d, path in items:
    doc.insert_pdf(pymupdf.open(per_doc_pdf))

for pno in range(doc.page_count):
    page = doc[pno]
    foot = pymupdf.Rect(0, page.rect.height - 60, page.rect.width, page.rect.height)
    hits = [(pymupdf.Rect(l['bbox']), l['spans'][0]['size'])
            for b in page.get_text('dict', clip=foot)['blocks'] if b['type'] == 0
            for l in b['lines']
            if ''.join(s['text'] for s in l['spans']).strip().isdigit()]
    for rect, _ in hits:
        page.add_redact_annot(rect, fill=(1, 1, 1))
    if hits:
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
        page.insert_text((hits[0][0].x0 - 2, hits[0][0].y1 - 2),
                         str(pno + 1), fontname='helv', fontsize=hits[0][1])
```

关键：`PDF_REDACT_IMAGE_NONE`，否则涂页码会连带清掉同页的插图。

这样得到的 PDF：页码连续（`layout_check` 的“页码错位 0”才成立）、图片齐全、
还能用各分册的 `get_toc()` 拼出全书书签。**合订 docx 仍然交付**（便于修订），
但它不再是 PDF 的来源。

### R3. 封面别用 `front` 文档冒充，要独立的 `cover` kind

症状：交付后用户第一句就是“缺少封面”。原因是 `docs.json` 第一项是 `front`
（前言/致谢），骨架流水线把它当普通文档渲染，于是全书从“前言”开始。

新增一个 `kind: 'cover'`，并且：

- **排在合并清单最前**，且必须**先有它再算目录页码**（封面 3 页会让正文整体后移）；
- **不能复用 `front_open` 渲染**，否则没有 `num` 时会印出「第　章」（见 P8）；
- **封面不插入任何图片** —— 原书书名与插画是整幅栅格位图，抠出来就是白底白图。

原书封面是**栅格大图 + 金色标题 + 橄榄色块**，无法无损中文化；按视觉骨架用文字重建：

```python
def cover(doc, meta):
    blank(doc, 3)
    for _ in range(2):                       # 橄榄色装饰条（原版左侧色块）
        p = pf(doc.add_paragraph(), line=10)
        shade(p, '5A553A')                   # w:shd 段落底色
    # 英文原书名（浅灰）→ 金色分隔线 → 中文主标题（34pt 金色加粗）
    # → 作者 → 序者 → MANNING / SHELTER ISLAND（字距 100）
```

**封面页不挂页眉页脚**：`cover()` 写在第一节，版权页/简目用
`doc.add_section(WD_SECTION.NEW_PAGE)` 另起一节，并对新节设
`sec.header.is_linked_to_previous = False` 后才写页眉。否则封面会印上页码「1」，
比没有封面更显眼。

### R4. 目录页码必须“先算后建”，且算的集合要含封面

正确的依赖顺序（错一步页码就全错）：

```
封面 docx → 封面 PDF → chapter_pages.py（含封面，正文从第 4 页起）
→ build_cover.py 用新页码重出封面 → 封面 PDF 重转 → merge_book.py
```

实测踩过：先建封面（目录写 `前言 1`），再插入封面 3 页，正文实际从第 4 页开始，
目录全错。`chapter_pages.py` 必须把 `cover` 作为第一行参与累加。

**部扉页不要占用章号列。** 简目里「第 1 部分」和「第 1 章」都印 `1`，读者会以为重复。
部扉页的章号列留空，标题写成 `第 1 部分　拓展基础`。

### R5. 图内文字擦除：`_mode_color` 滤掉深色会误伤彩色底

症状：南美洲地图的紫/红/绿色圆上，中文标签周围留一圈**白色方块**，
还叠着原来英文的白字残影。

根因在取底色的众数函数里有一行“跳过深色墨迹”：

```python
if lum < 175:  continue     # ← 紫色 (118,61,151) 的 lum≈94，被当成墨迹丢掉
```

于是内圈众数只剩白字 → 底色判成白色 → 在白底上擦、在白底上写，彩色圆上就出现白块。

**修法：只跳过“深色且不彩”的像素**：

```python
lum = (c[0]*299 + c[1]*587 + c[2]*114) / 1000
sat = max(c) - min(c)
if lum < 175 and sat <= 12:      # 黑字跳过；深紫/深红保留
    continue
```

**再加一层保险**：优先用 **bbox 外 6px 环带**（完全不含文字）的颜色，
只要它与内圈亮度差 > 40，就以环带为准。这样黑字块、白字块都正确。

```python
if colored(ring):                                  # 环带是彩色 → 最可信
    return ring, (x0-3, y0-3, x1+3, y1+3)
if colored(inner):
    return inner, (x0-3, y0-3, x1+3, y1+3)
if abs(luma(inner) - luma(ring)) > 40:
    return ring, (x0-4, y0-4, x1+4, y1+4)
```

### R6. 有些图内标签注定做不干净：接受“保留原文”

地图上直接压在多色区块的国名（`Brazil`、`Argentina`…），标签框**横跨两个以上色块**，
单色擦除必然留斑；改成“中文标签 + 引线重排”需要手工给每个标签指定新坐标，无法自动化。

判断标准：**擦除框内是否只有一种底色**。不是，就整块 `KEEP` 保留英文原像素，
并在交付说明里列出这些位置。这比在图上留白斑或白字残影好得多——
读者能接受英文地名，不能接受一块块白补丁。

### R7. 小图别拉伸到满栏

`w_cm = orig_w / ORIG_TEXT_W * TEXT_W` 会把 237pt 宽的小图放大到 16cm 满栏，
文字边缘立刻发虚。加一条上限：

```python
w_cm = min(TEXT_W_CM,
           orig_w / ORIG_TEXT_W_PT * TEXT_W_CM,
           orig_w * 1.15 * 2.54 / 72)      # 最多放大到原版面的 1.15 倍
```

配套把小图的采样密度提到 450dpi（`if clip.width < 300 or clip.height < 240`）。
像素够、尺寸不放大，缩到 10cm 时仍有 240dpi 以上。

### R8. 摘要列表的最后一项会单独占一页

`layout_check` 报「整页只有一行的页数：1」，`find_blank` 报「近空白页」。查下来是
某章“小结”列表的最后一条刚好溢出到新页——上一页已排满，这属于自然分页，
**不要为了凑页去硬改正文**，也不要加 `keepNext` 把整页内容往前拽（会引发新溢出）。

可以做的只有两件：

1. 该条译文明显啰嗦（中日韩文字比英文省空间）→ 压一句，往往就回填了；
2. 压了仍在下一页 → 判定为正常章末页，在交付说明里写明。

判定“是否章末页”不要靠肉眼：

```python
nxt = [p for p, t in chapters if p > pn]
is_last = bool(nxt) and pn == nxt[0] - 1
```

### R9. 封面必须排在合并清单第一位，否则页码整体偏一

封面单独成档 `000_封面.docx`，合并顺序 `封面 → 前言与目录 → 各章`。
**它必须在算目录页码之前就位**——封面占 1 页，正文整体后移（本书 278 → 281 页）。

合订 PDF 的页码要**逐页重写**，三处都会错：

```python
for i in range(out.page_count):
    if i == 0:                                    # ① 封面不编号
        continue
    clip = pymupdf.Rect(w*0.30, h-46, w*0.70, h)  # ② 判据收窄到「底部居中」
    # 找纯数字行 → redact → insert_text(str(i))
```

| 坑 | 后果 |
|---|---|
| 判据放宽到整个页脚带 | 正文里含数字的行被误擦（实测 6 页：`132`、`51234570`、`20250221112455165`） |
| 封面也编号 | 全书从 2 开始，整体偏一 |
| 只在 docx 层改 `w:pgNumType` | `docxcompose` 合并后只剩 1 个 section，改不动分章页码；278 页里 277 页错位 |
| 校验用「每页最后一行」 | PDF 文本按列序返回，最后一行多是正文 → 全部误报 |

### R10. 前置页的「行」不能交给自动合并

版权页五行元数据、简明目录十来行章名，若按普通段落合并，会拼成一整行：
`Version 9Copyright 2026 Manning PublicationsFor more information…`

两条一起加才有效：

1. `convert.py` 里判「多行且过半以数字开头 / 每行都短」→ 逐行保留（`\n` 连接）；
2. `build_docx.py` 里**含 `\n` 的块不参与「前段不以句号结尾就并段」**，
   否则第一行会吃掉下一块的开头。

另外：目录型块（≥6 行）行距要收到 1.15 并加 `page_break_before`，
否则十来行会溢出到下一页，目录被拆成两半。

### R11. 图注要按图的实际内容译，不要照抄 caption

实测原书两处图注有问题：

- **图 6.5 的英文 caption 与图 6.4 完全相同**（`Generic Linked List Implementation`），
  但图 6.5 画的是 `Map[K comparable, V any] → HashMap → HashMap[string, int]`。
  → 把图调出来看内容，译为「泛型映射的实现」，并在交付说明里写明「原书笔误」。
- **图 6.2 的 caption 被 PDF 折成两块**（`figure` 块 + 紧随的 `p` 块），
  只译前半句会留一段残句挂在图注下。
  → 合并进 caption；原 `p` 块改写为解释图内容的正常段落。

判据：**图注与图不符时以图为准。** 只译文字不看图，会产出读起来通顺、
但指着错误位置的图注。

## S. 块号错位与校验缺口（248 页 Manning 两色版实战）

这一组来自一本 248 页、12 份文档、2084 块、39 张矢量图的书。图内排版与合订都顺利，
**全部返工都发生在「块号错位」和「校验脚本自己骗自己」这两处**。

### S1. `convert.py` 对「多写的块头」静默忽略，docx 才暴露

症状：`convert.py` 输出 `ch02: 156 blocks -> ch02_trans.json`，看起来正常；
出 docx 后发现段落与标题整体串位——某个 `panel` 里装着图注，某个 `h3` 里装着正文。

根因：`convert.py` 按 `@@B` 出现顺序取块内容，但**只在块数少于 layout 时报警**。
`_zh.txt` 有 156 个块头、layout 只有 155 块时，多出的第 156 个被丢掉，
而 0..155 的对应关系已经错了一位。触发源是**把一个 `figure` 块当成正文 `p` 写**：
`figure` 与紧随其后的 `p` 是两个独立块，凭语义写极易并成一个。

**修法：加第二道闸门 `check_zh.py`**——块数必须严格相等（多也要报）、
每块类型必须落在 layout 类型的允许集合里（`heading` 允许 `h2`/`h3`）、
非 code 块不得为空。三道一起过才允许出 docx。

```python
TYPE_MAP = {'heading': ('h2', 'h3'), 'para': ('p',), 'figure': ('figure',),
            'panel': ('panel',), 'sidebar_head': ('sidebar_head', 'sidebar'), ...}
if len(zh) != len(seq):            problems.append('块数 %d≠%d' % (len(zh), len(seq)))
for i, (pn, lt) in enumerate(seq):
    if zh[i][0] not in TYPE_MAP.get(lt, (lt,)): mismatched.append(i)
```

### S2. 校验脚本的块号正则把「自带类型的块头」全漏掉了

症状：`check_cov.py` 报「多余 0 / 缺 0」但 `图内 0 条`，看着像一切正常；实际上
`_zh.txt` 一个块都没被识别到，因为块头长这样：

```
@@B 12 p   # p45
```

而旧正则要求块号独占一行（`^@@B\s+(\d+)\s*$`），一条都匹配不到。
`多余 0` 与 `缺 0` 同时成立是个可疑信号——**总数也算 0 时，先怀疑解析器而不是内容**。

**修法**：`^@@B\s+(\d+)\b`，块号后允许任意尾随（类型、`role=`、`# p45` 注释）。

### S3. 「顺位取块」与「按块号取块」是两种错位，混用就是串位

`realign_zh.py --rebuild` 早期用「先按块号、取不到再按位置」，看起来稳，实测更糟：
漏写块 73 时，块 73 取不到，于是拿位置 73 的内容（其实是块 74 的正文）填进去，
**表面 0 处类型不匹配，实际从 73 起全部串位**。

两种错位必须分开：

| 错位形态 | 特征 | 取块方式 |
|---|---|---|
| 有块没写 | 块号连续，中间缺号 | **按块号**取，缺的留空再补 |
| 块号本身错了 | 块号重复 / 整体平移 | **按位置**取（`--by-position`） |

判据：`--rebuild` 完跑一次 `check_zh.py`，若「空块」出现本该有内容的块，
说明块号本身错了，换 `--by-position` 重试。

### S4. 改解析规则前先问：这次改动会不会让块号平移

实测把「章内小标题」从 `panel_head` 改成 `head`，heading 从 197 涨到 307，
**全书 12 份文档块号全部平移**。当时 ch02 已译完 155 块，只能诊断 + 重建。

纪律：**解析器一旦开始翻译就冻结**。发现解析缺陷时，先在「呈现层」找补
（`build_doc.py` 里改渲染），只有在块序列确实错了时才动解析器，并预留
「全书重解析 → `realign_zh.py` → `check_zh.py` 复核」这一轮成本。

### S5. 并排图例的判定不能放宽，一放宽就吞掉正常段落

`render_figs.py` 里为了不把「一行 N 个短标签」的图例译成一团重叠，
加了「含 4 个以上大写词就保留英文」。结果把这两个也判成了图例、整段不译：

- `System instructions (trusted) You are an incident summary assistant…`
- `RELIABLE, REUSABLE PROMPT TEMPLATE Consistent structure + clear language…`

**收紧后的判据**（单行 + 平均词长 ≤7 + 词数 ≥5 + 短词占比 ≥60% + 无句末标点），
只命中真正的图例行（`System Assistant Message Message 1 Message 1…`）。

教训：**「跳过」类规则必须给出「为什么必须跳过」的最小充分条件**，
用宽泛特征（大写词个数、宽度）当判据，一定会误伤正常内容，而且误伤是静默的
（那一段就是不译，不报错）。

### S6. 交付说明必须区分「不能译」与「不该译」

三类要分开写，混在一起用户没法复核：

1. **不能无损中文化**：文字被画进矢量路径或栅格（图内标题在 `get_drawings` 里，
   不在 `get_text` 里）；列出页码。
2. **不该译（并排标签）**：同一行多个独立标签共享基线，译一个就压住邻居；
   列出页码与原文，说明保留理由。
3. **不该译（纯符号/纯代码）**：`1`、`</>`、``` ```` 、整组 diff；不必列全，
   说明规则即可。

实测一本 248 页的书：706 组中 9 组属第 2 类、13 组属第 3 类、0 组属第 1 类。
给出比例比给出形容词有用。

### S7. 图内居中标题画在图 bbox 之外，会被漏掉

症状：图渲染出来顶部缺一行字（1. Prompt Template (with Input Variables)），
而 MISSING 是 0——渲染器压根不知道有这一行。

原因：归属规则是「行中心点落在图 bbox 内就归图」，但那行标题在 y=52.9，
图 bbox 从 y=63.9 起，中心点在框外 → 判定为正文 → 既没进图、也没进正文
（被后续的「图内重叠」过滤吞掉）。

**修法（两遍扫描，不要边迭代边改列表）**：

1. 先把**紧贴图上下沿**的图内字体行（ArialMT 一类，kind == 'figtext'）
   并入图 bbox：水平落在 f[0]-14 … f[2]+14，垂直落在 f[1]-24 … f[1]+2
   或 f[3]-2 … f[3]+18；
2. 再按扩过的 bbox 做归属分配。

放宽只对**图内字体**生效，正文衬线字体不放宽，否则会把正文段落吸进图里。

---

## T. 栅格图内的文字（字体在像素里，不在文字层）

前面 A–S 组处理的都是「图内文字在 PDF 文字层」的书。这一组来自一本 374 页、
10 章、80 张插图的书，**插图全是嵌入式栅格 PNG**——`page.get_text()` 拿不到图内
任何文字，`get_drawings()` 也只有外框。整套流程从「按坐标重绘矢量文字」换成
「OCR → 擦像素 → 写中文」。

这是本项目最大的一块返工来源：**图内擦除逻辑重写了 9 次**。下面是每次失败的真实原因，
按重要性排序，前三条能省掉 90% 的时间。

### T0. 先判断图内文字在哪一层，再选流程

```python
page.get_text('dict')          # 图内文字在文字层 → 走 render_figs.py（矢量重绘）
page.get_image_info()          # 有大图 + 该区域 get_text 无内容 → 栅格图，走 OCR
```

判据：把图的 bbox 拿去 `get_text(clip=bbox)`，若返回空或只有图注，就是栅格图。
两本书的 `render_figs.py` 完全不能混用。

### T1. 擦除的正确解法是「bbox 内深色墨 − 长线/厚块」，不是连通域也不是涂底色

这一条是整组里最贵的教训。**九次失败**，每次都是"换个思路"而不是"修 bug"，实际是因为
判据选错了维度。按失败顺序记录：

| # | 做法 | 失败后果 |
|---|---|---|
| 1 | 按 bbox 矩形涂底色 | 紧贴文字的**方框边线被抹掉**（p13 方框一圈缺口） |
| 2 | 取 bbox 内**众数色**填充 | 粗体字时众数色就是字形色，留下深色块 |
| 3 | 取 bbox 内**中位色**填充 | 文字占多数像素时同上 |
| 4 | 先涂底色，再用「结构掩膜」回填线 | 圆角与斜线不符合横/竖开运算，回填不全（p11 圆角被咬掉） |
| 5 | 只删「与线不连通的连通域」 | 整词字母常连成一个连通域（"Sender" 六字母连成 112px），**一个字都擦不掉** |
| 6 | 按连通域尺寸过滤（长边 ≤ 62px 算字形） | 手绘漫画字高 69px → 全被判成结构物，只擦掉 **29%** 笔画 |
| 7 | 改成相对阈值（≤ 2.2×字高） | 覆盖率到 97%，但擦除范围蔓延到相邻图形 |
| 8 | 用 `cv2.inpaint` 填回背景 | **灰条紧贴黑边框时重建出一团黑抹**（p16 所有灰标题栏变黑块） |
| 9 | bbox 内深色墨 − 长线/厚块保护 + **填本地底色** | ✅ 通过 |

**最终做法**（`erase_labels`）：

```python
# 1. 窗口 = bbox 外扩（横向多给，补 OCR 漏的尾字符；纵向只给一点）
rx0, rx1 = x0 - int(bh*0.35), x1 + int(bh*0.35)
ry0, ry1 = y0 - max(2, int(bh*0.12)), y1 + max(2, int(bh*0.12))

# 2. 取墨：分两种情况（见 T2）
ink = lum < paper - 45          # 白纸黑字
ink = lum > med + 40            # 彩块白字

# 3. 结构保护：开运算识别长线/厚块，从墨里剔除
kx = max(9, int(bh * 1.5))
horiz = ndimage.binary_opening(ink, np.ones((1, kx)))
vert  = ndimage.binary_opening(ink, np.ones((kx, 1)))
thick = ndimage.binary_opening(ink, np.ones((kx//3, kx//3)))
guard = ndimage.binary_dilation(horiz | vert | thick, np.ones((3, 3)))
kill  = ink & ~guard

# 4. 填「本地底色」：掩膜以外像素的中位色（灰条取到 #B0B0B0，白纸取到 #FFFFFF）
bgmask = ~ndimage.binary_dilation(kill, np.ones((5, 5)))
bg = np.median(sub[bgmask], axis=0)
patch[kill] = bg
```

关键认识：**"什么该保留"用形态学判据（长线/厚块），"填什么"用本地统计量。**
一旦把这两件事混起来（用连通域同时表达"保留"和"填充"），必然顾此失彼。

### T2. 彩块上的白字必须换一套阈值与前景色

图上常有橙色 `#FF9800`、蓝色 `#00ADD8` 的色块，上面压白字。一律按"比纸暗"取墨时，
**整块彩色被当墨涂成白方块，白字也被擦掉**（实测 ch09 橙色 URL 块与蓝色 Worker 圆
整片变白）。

```python
def fg_is_light(arr):
    """底色偏深且存在明显更亮的像素 → 图上写的是浅色字"""
    lum = arr[:, :, :3].astype(float).mean(2)
    med = float(np.median(lum))
    if med > 170:                  # 白纸，不触发
        return False
    return float(np.percentile(lum, 95)) - med > 60

# 墨与前景色都要跟着切
ink = lum > med + 40 if fg_is_light(sub) else lum < paper - 45
fg  = (255, 255, 255) if fg_is_light(sub) else fg_color(sub, bg)
```

`#FF9800` 中位亮度 ≈152、`#00ADD8` ≈121，判据稳定；白纸 ≈255 不会误触发。

### T3. 必须先擦完所有块，再统一画中文

**这一条单独导致过一次"中英文叠在一起看不清"**（用户直接指出的问题）。

原因：OCR 的相邻文字框常**纵向重叠**。实测图 1.1 前两行是 `72–171` 与 `152–241`，
重叠近 20px。若按「擦一块 → 画一块」的循环，后一块的擦除窗口会覆盖前一块刚画上的
中文，把它擦掉一半，于是中英文互相压着。

```python
# 阶段 1：全部擦除（arr 原地更新）
for b, cn in plan:
    ok, drawn = render_block(img, arr, b, cn, report, glyph, erase_only=True)
    prepared.append(drawn)
# 阶段 2：统一绘制
for d in prepared:
    px_draw(d, img)
```

配套：给每块算**纵向避让带**（与"横向范围有重叠"的邻块比，取中心到中点），
且避让带**必须有下限**——早期没下限，把某些块压到 8px 高，字号退化到 1.4pt，
整片标签变成看不清的小字（p13 退化过一次）。

### T4. 字号与几何必须在同一坐标系里

像素图里 `px_bbox` 是像素、`h_pt` 是 pt。混用会让字号差 4 倍：

```python
scale = px_per_pt                      # 300dpi 时 = 4.1667
base_fs = h_pt * scale * 0.92          # 像素字号，不是 pt
```

早期直接拿 `h_pt`（7.2）当像素字号，7pt 的框里塞 7px 的字，**全部渲染过小**。
另一个反向事故：`tight` 框被当成下一轮的输入再次收窄，逐块自收缩到 8×10px、
字号掉到 1.4pt。**clamp 必须基于原始 `bbox`，不能基于上一轮的 tight 框。**

### T5. 擦除与绘制必须同步回同一个图像对象

```python
arr[ry0:ry1, rx0:rx1, :3] = patch      # 改了 numpy 视图
img.paste(Image.fromarray(arr))        # ← 这一行漏了，输出就是原图
```

漏掉 `paste` 时的现象极具迷惑性：**渲染报告的覆盖率是 97%、`rendered=51`、
`OVERFLOW=0`，但输出的 PNG 与原图字节完全相同**。用
`np.array_equal(输入, 输出)` 做一次断言就能一眼看穿。

同理，`erase_labels` 里用 `img = Image.fromarray(...)` 重新绑定局部变量是无效的——
只改了函数内的名字，调用方拿到的还是旧对象。

### T6. 手绘漫画（XKCD 类）要走"窄带兜底"路径

手绘图的笔画、对话框轮廓与文字**连成一个连通域**，字形掩膜里几乎没有该块的墨
（实测覆盖率 0.26~0.29）。这时按连通域判定会一个字都擦不掉，可它又确实需要中文化。

兜底判据：当 `glyph & band` 不足 6 像素时，改用**紧贴 bbox 的窄带**取深色墨
（±8% 高、±2% 宽），而不是宽行带——宽行带会把相邻方框边线卷进来，擦出缺口。

### T7. OCR 的框会漏字：按"整行墨"而不是"按框"擦

OCR 常只框住一个词的头几个字母（"Goroutine 1" 只框到 "Goroutine"，末尾的 `1`
留在原地形成残字）。擦除窗口横向外扩 0.35~2.2 倍字高可覆盖，但**外扩必须靠
结构保护兜住**，否则会吃到相邻图形。这是 T1 里"深度墨 + 长线保护"能成立的前提。

### T8. 浅色底上的低对比字要补第二遍

浅绿 `#E8F5E9` 上的深灰字，与底色的差只有 30~50，第一遍阈值抓不到，留下英文残影。
补一轮：`|像素 − 底色| > 60` 且经 2×2 开运算去噪，再与结构保护求交。
实测能清掉大部分，但**对比度极低的残影无法完全消除**——这类要写进交付说明，
不要假装干净。

### T9. 图内译文用 `ZH SAME` 显式标记"保留原样"

栅格图的文字块里大量是**代码标识符、数字、索引**（`int`、`ptr`、`len`、`cap`、
`[0]`、`main`、`addOneToAll`）。让译者写 `ZH SAME` 而不是留空，好处是：
缺译（真空）与故意保留（SAME）在闸门里可区分，`MISSING` 只统计真空的。

### T10. 图注继承原书笔误：按图的实际内容改，并在交付说明里指出

实测原书两个图注有问题：

- 图 6.5 的英文 caption 与图 6.4 **完全相同**（`Generic Linked List Implementation`），
  但图 6.5 画的是 `Map[K comparable, V any] → HashMap → HashMap[string,int]`。
  → 把图调出来看内容，译为「泛型映射的实现」，并记录「原书笔误」。
- 图 6.2 的 caption 被 PDF 折成两块（`figure` 块 + 紧随的 `p` 块），只译前半句会
  留一段残句挂在图注下。→ 合并进 caption，原 `p` 块改写为解释图内容的正常段落。

判据：**不要照抄 caption 文字，要看图里画的是什么。** 图注与图不符时以图为准。

## U. 超长全书 + 分散图元 + 编辑器 SDK 管线（544 页 Manning 实战）

这一组来自《Knowledge Graphs and LLMs in Action》：544 页 / 158k 词 / 15 章 + 3 附录 +
195 图 / 46 表 / 245 个代码清单，最终 22 个分册 docx + 593 页合订本。
它与前面所有组别的差别有两个：**插图是分散图元构成的矢量图**（聚类法必败），
以及**Word 生成走的是编辑器 SDK 的 Markdown 通道**而不是 python-docx 逐段拼。

### U1. 图区判定：分散图元的书必须用「图注间版面窗口」，不能聚类

原书每张图由几十到上百个**分散图元**构成（方框、箭头、圆，间距常超 16pt），
且图内文字标签大量使用**正文字体**。按 `get_drawings()` 聚类定边界会得到两种结果：

- 聚类容差 14pt → 图被切成 5~19 个碎片，每片都是一个小方框；
- 容差放到 30pt → 相邻图的图元被并进来，两张图粘成一张。

**正确做法是按「图注之间的版面窗口」定图区**：

```python
# ① 本页所有图注按 y 排序；当前图的上边界 = 上一条图注的底边（首页取版心顶）
lower = caps[i-1].y1 + 2 if i else 30.0
# ② 收集 [lower, 本图注底边] 窗口内的全部图元（drawings + 内嵌图 + 非正文字体文本块）
cand = [e for e in els if lower - 2 <= e.y0 <= capr.y1 + 16]
# ③ 图区 = 这些图元的并集，横向拉到整栏（图内标签常溢出图元 bbox）
band.x0, band.x1 = content_left, content_right
```

三条配套规则，缺一条就翻车：

1. **横向必须拉到整栏**。图内文字标签用正文字体（`NewBaskerville`），被排除在图元之外，
   只按图元并集裁会把椭圆图右侧的标签整列切掉（实测图 1.5 右侧被裁 1/3）。
2. **窗口内闯入的正文段必须抹白**。正文段落与图共享纵向区间时（图文混排），
   渲染前把该段矩形涂白，否则正文被烙进图里。判据用「段宽 > 250pt 且行数 ≥ 2」。
3. **图注文字也要抹白**。图注若落在图区纵向范围内（侧置图注常见），不涂掉就会印进图里。

### U2. 图注必须先于「交叠过滤」判定，否则整章图注全丢

判断文本块是否属于图内文字时，图注本身就落在图区矩形内。顺序写成「先判交叠、再判图注」，
6 个图注会被当成图内文字全部过滤掉，而且**不报错**——只是图注凭空消失。

```python
is_cap = bool(re.match(r'^(Figure|Table|Listing)\s+([A-Z]\.\d+|\d+\.\d+)', raw0))
if not is_cap and any(bb.intersects(fb) ... for fb in figboxes):
    continue          # 只有非图注块才允许被图区吞掉
```

### U3. 页眉过滤：混合大小写的 running head 骗过 isupper

页眉形如 `5 1.1 Knowledge graphs` 与 `4 CHAPTER 1 Knowledge graphs and LLMs...`。
用 `raw.isupper()` 只能抓到后者。**实测有效的判据是位置 + 高度**：

```python
if bb.y0 < 44 and bb.height < 16: continue          # 单行页眉
if re.match(r'^\d+\s+CHAPTER\b', raw0) or 'CHAPTER ' in raw0[:20]: continue
```

### U4. 图片块必须独占插入批次，否则被静默丢弃

`doc_insert_markdown` 的单次负载里**既有正文又有图片行时，图片会被静默丢掉、不报错**。
实测第 2 章 13 张图只进 7 张，图片数校验之外的一切都显示「正常」。

```python
def pack(blocks, limit=700):
    for b in blocks:
        if b.lstrip().startswith('!['):
            if cur: out.append(cur); cur = ''
            out.append(b)          # 图片块（含紧随的图注）单独一批
            continue
        ...
```

配套：图片行**不能是批次的最后一块**（只有图片行的 payload 同样会被丢），
所以图片行必须和紧随的图注合并为同一批。

### U5. 代码块 / 表格之后必须补段分隔符

代码块在 docx 里是**内联图形对象**（`w:txbxContent`），紧邻的下一个块会挤进同一个 `<w:p>`。
实测第 3 章出现 25 处，症状是 `H3 标题` 与代码块文本并成一段、标题层级失效。

```python
if b.lstrip().startswith(('```', '|')):
    doc_insert_paragraph_with_text(idx=<本次回包的 position>, text="")   # 补空段分隔
```

注意 idx 要用**本次插入回包的 `position`**，不要用 `last_edit_index - 1`
（插入代码块后 `position == last_edit_index`，减 1 就错位）。

### U6. 图片归一化前必须判断 `a:blip`

把插图统一缩放到版心宽度时，代码块/文本框也是 `w:drawing`，会被一起拉宽到 15 cm、
代码框全部变形。判据：**只处理含 `a:blip`（位图引用）的 drawing**。

```python
for dr in body.iter(qn('w:drawing')):
    if dr.find('.//' + qn('a:blip')) is None:
        continue                      # 代码块形状不是图片
    ext = dr.find('.//' + qn('wp:extent'))
    ratio = min(TARGET_W / cx, MAX_H / cy)      # 版心宽 15cm，超高按 20cm 限
```

### U7. 300 DPI 裁剪图的显示尺寸 = 原书版面尺寸

编辑器按**像素尺寸 ÷ 300 DPI** 折算物理尺寸，所以 300 DPI 裁出来的图显示出来正好是
原书印刷大小——在 A4（版心 15 cm）上明显偏小。**归一化到版心宽度是必做项，不是可选项**，
且幂等（第二次 ratio = 1），可以反复重跑。

### U8. keepNext 必须在 set_ppr 之后插入，且在 pPr 首位

格式化函数先写 spacing/ind/jc、后加 keepNext 的顺序下，`set_ppr` 的「移除既有属性」逻辑
会把 keepNext 清掉。另外 OOXML 对 pPr 子元素有顺序要求，`keepNext` 要插在**首位**：

```python
set_ppr(p, ...)                                  # 先格式化
if is_cap or has_pic:
    pPr3.insert(0, el('w:keepNext'))             # 后插、插最前
```

### U9. 代码清单跨页断裂要合并，注释串位的要手工补

一个清单常被分页切成 3~4 个代码块（PDF 按版面断行）。合并规则：**同一清单标题下的
连续 code 块首尾相接**。另有两类必须手工恢复：

- 代码行与旁注（annotation）交错排版时，旁注用图内字体、代码用等宽字体，
  按块抽取会把清单拆空——要回原页按 y 坐标逐行取。
- PDF 把长行折行后丢掉标点（`"2018-02-23}]->` 应是 `"2018-02-23"}]->`），按语义补回。

### U10. 超长文档必须后台构建，且要打进度日志

143 个内容块前台构建 2 分 21 秒后被 SIGTERM；1137 块的合订本后台跑了 **35 分钟**。
判据：**超过 3 万字符或 80 个块就后台跑**，并且每 20 块打一次进度，
否则无法判断是卡死还是在跑。

### U11. 索引列感知抽取 + 页码偏移反推

双栏索引页用普通 `get_text()` 会得到两栏交错的乱序文本。必须**按列裁剪两次**
（左半 → 右半），再按「行尾是数字则闭合当前条目」的规则合并续行。

页码是原书印刷页码，与 PDF 物理页有固定偏移。**不要猜，用一条已知条目反推**：
本例 `adjacency lists and matrices 443` 对应附录 A.3（PDF 473 页）→ 偏移 = 30。
反推后建「印刷页 → 章节」映射表，索引用章节定位而不是原书页码
（原书页码对中文版毫无意义，这是用户明确要求的）。

### U12. 目录两轮校准法

Word 的 TOC 域不更新字段时，转出的 PDF 只有一句「按 F9 生成目录」。
两轮法可拿到带页码的静态目录：

```
① 插静态目录（页码全 0，行数 = 最终行数）
② 转 PDF → 按标题文本在 PDF 里定位真实页
③ 原地回填页码（只改 run 文本，不动段落数 → 分页不变）
④ 再转一次 PDF
```

已知残留：约 30% 的标题因文本过短/重名在 PDF 里搜不到，留空处理即可，
不影响其余条目。**不要为了这 30% 去改标题文本**——一改分页又变。

### U13. 分册交付 + 合订本重建，走同一条构建链

22 个分册与合订本**共用同一批 `seg`/`codebook`/`figs` 源文件**，合订本只是按顺序拼接后
重跑一次构建。好处是任一册要改，只需改源文件后重跑那一册，合订本随时可重建。
代价是合订本构建耗时（35 分钟），所以**分册要先行交付**，不要等合订本。

### U14. 校验清单：四个数字 + 一个零

每章交付前必核（本次三个静默缺陷全靠它抓出来）：

| 校验 | 判据 |
|---|---|
| 图片段数 | == 该章图注唯一编号数 |
| 代码框数 | == 该章清单数（含手工补的） |
| 表格数 | == 该章表注数（跨页拆分的会变多，需换算） |
| 段落合并数 | **必须 0**（代码框/表格与正文并段） |
| 空清单 | 列出并逐个人工补全 |

「生成成功、文件大小正常」**不能**作为交付判据——本次 6 张图丢失时文件大小完全正常。

## V. 全书范围、同页多图与新增页（368 页 Manning 两色版修订实战）

这一组记录的是「所有既有闸门都绿，但书仍然是残的」的失败。项目：368 页、119 图、
6 表、11 章 + 3 附录；`check_cov.py` / `check_zh.py` 16 份全 OK、PDF 无空白页，
仍漏掉原书整页、出现图注重影、同页多图串成一张。

### V1. 覆盖率 100% 只覆盖已解析的页，不覆盖 docs.json 的页范围

**症状**：译稿第 4 章末尾停在「每个部门」。原书第 108 页（第 4 章续句、过渡段、6 条
小结）完全没有进入任何 `docs.json` 条目。`check_cov` 与 `check_zh` 都报「100%」，
因为 layout 里根本没有那一页。

**根因**：边界用 `ch04 from=81 to=107`，第 108 页被下一章起点截断；而后续校验只比
「layout 块数 == 译文块数」，两边都没有第 108 页，自然全绿。

**修法**：

1. 交付前跑 `check_page_coverage.py 原书.pdf docs.json`，列出所有有正文但未覆盖的页；
2. 每章末页人工确认有「小结/Summary」，或下一页就是下一章；
3. 正文章节从 `to` 补页后，要重新 parse（或手工追加 layout 块），再翻译、重建；
4. Part 扉页是 `kind=part` 的一页，不要硬塞进相邻章；
5. 原书索引页不进入正文覆盖范围，单独按 V7 处理。

### V2. 同页多图共用 `p{page}_f0`，图片数正确但内容重复

**症状**：合订 docx 有 119 个 inline shape，但只有 98 个唯一 `r:embed`；原书同一页的
两张不同插图（图 5.8 / 图 5.9）在成品里变成同一张图重复两次。文件大小 19MB、页数、
块序列、图片总数全部正常。

**根因**：`convert.py` 的 key 写成 `p{page}_f{b.get('figi', 0)}`，而 layout 的 figure
块没有 `figi` 字段；同一页所有图都得到 `p121_f0`，指向同一张 PNG。

**修法**：

```python
_pg = b['page']
_fi = figi_by_page.get(_pg, 0)
figi_by_page[_pg] = _fi + 1
key = f'p{_pg}_f{_fi}'
```

figure 与 table 都要占页内序号（table 也自增，避免后续 figure 错位）。
交付前跑 `check_merged_images.py 全书.docx`，三数必须相等：
`inline_shapes == 唯一 r:embed == word/media 文件数`。

### V3. 固定 26pt 外扩把相邻正文裁进图片

**症状**：窄图右侧排版时，图片左边出现一列正文文字残片（`st / ss / e / c- / d`），
看起来像排版错位，其实是 PNG 里烙进了相邻正文。

**根因**：为了让中文标签有空间，`render_figs.py` 固定 `bbox x0-26, x1+26`。
窄图与正文只隔几 pt 时，26pt 足够把整列正文裁进图。

**修法**：左右各留 1–2pt，下边按图注文本块并集扩到 5–8pt。图内标签的宽度问题应由
字号/断行处理，不靠固定外扩掩盖。

### V4. 图注最后一行被裁：英文残影 + 下一节标题压字

**症状**：图 10.5 的图注显示到「每个文件包含的记录数更多」，下面一条英文
`minimizing the cost of metadata traversal and data file...` 被切掉，紧接着是下一节标题。
同一处正文还残留「每个文件的记录数，从而把 图 10.5 展示了一种更理想的元数据…布局。」
的串行乱句。

**根因**：图注被拆成多个文本块，最后一块不在 figtexts；bbox 只覆盖前几行。
正文块又把图注尾部并进来。

**修法**：

1. 图注 bbox 取「fig bbox ∪ 全部图内文本 bbox」的最大 y1，再 +5~8pt；
2. 图注译文与英文全文逐句对齐，不能只译前几行；
3. 扫所有 `p` 块，命中「句号 + 空格 + 图 X.Y」的移回 caption；
4. 重建后翻到该页，确认最后一行完整且不被下一节标题压住。

### V5. 新增页使全书重排：目录必须两轮回填

**症状**：补 1 页译者说明、3 页 Part 扉页、2 页术语索引后，原目录页码整体失效。
只改 cover 不重算，会导致目录差 1–6 页。

**可靠顺序**：

```
① 用占位页码生成封面/目录（行数 = 最终行数）
② 合并 → 转 PDF → 按标题文本定位每章真实起始页
③ 回填 front_meta.json → 重生成封面 → 再合并 → 再转
④ 页数稳定后写 PDF 分级书签
```

新增页前先算它对后续页面的位移：front note +1、Part1 +1、Part2 +1、Part3 +1。
每次增删页都重跑 ②，不要复用旧 `chapter_pages.json`。

### V6. `Pt(1.55)` 是 1.55 磅，不是 1.55 倍行距

**症状**：自写的说明页六个小节全部叠成一行；术语索引 76 行被压进一页、字小到不可读。
表格每行只有 5pt 高，但报告和 `layout_check` 都不报错。

**根因**：辅助页的 `pf(..., line=...)` 内部是 `paragraph_format.line_spacing = Pt(line)`；
传 1.55 就是 1.55pt 固定行距。表格单元格同样传 1.05，行高被压到 1pt 级。

**修法**：

- 固定行距写点数：正文 10.5pt → `line=17`，标题 24pt → `line=30`；
- 需要倍数时直接 `line_spacing = 1.55`，不要包 `Pt()`；
- 索引表格每行设 `WD_ROW_HEIGHT_RULE.AT_LEAST`（如 0.42cm），否则 70+ 行会被压成一页；
- 新增页单独转 PDF 看首页，再并入合订本。

### V7. 原书索引不做逐条页码翻译，改术语索引

**背景**：原书索引 397–409 页按英文版页码编制，中文版重排后页码全部失效。
只译条目保留旧页码是最差折中。

**可行替代**：`kind=index` 的 2 页三列表——英文术语 / 中文 / 主要章节。
章节定位由译文 heading 的编号得出，比页码稳定；本项目 76 个术语约 2 页。
在译者说明里明确写出“原索引不照搬”。

### V8. 目标 docx 被预览/Word 锁定时输出修订副本

**症状**：`merge_book.py` 保存时报
`PermissionError: [Errno 13] ... 书名.docx`。

**处理**：不要覆盖、不要删旧文件。给合订脚本加输出名环境变量：

```bash
BOOK_OUT_NAME="书名（修订版）.docx" $PY $S/merge_book.py
```

生成并列修订版，旧版保留；交付时说明两版关系。

### V9. 语义级 QA：三个扫描 + 一次目视

自动闸门只保证「已解析的块都在」，不保证「该解析的页都进来了」「句子没串」。
收尾至少做：

1. `check_page_coverage.py`：原书页覆盖；
2. `p` 块扫描：图注混入、半句结尾（`每个部门` / `Each department`）；
3. `check_merged_images.py` + 每章抽 1 张多图页、1 张表格页；
4. 逐章看最后一页：小结是否真的存在，而不是一条孤立 bullet。

本项目两次最严重缺陷（整页漏译、图注串行）都不是自动闸门发现的。

---

## W. 450 页 Manning 2026 整本翻译（25 份分册 / 406 页合订实战）

项目：《AI Agents and Applications: With LangChain, LangGraph, and MCP》（Roberto Infante, Manning 2026, 450 页）。
图内文字在文字层，走骨架流水线；产出 25 份分册 + 整书合订 docx/PDF，约 3,780 块译文、约 2,000 条图内文字译文。
**本组专收「跨会话逐章推进 + 整书合订」这一段的新坑**，与 V 组（范围审计）互补。

### W1. 同版式项目可整套复用，但常量不能照抄

工作区里已有同出版社、同页面尺寸（531×636pt）的两色版项目，直接复制 39 个脚本，
只重建字体表与判据，省掉解析器调试的大头。**但以下四类必须按新书实测重设**：
字体族名、页眉阈值、章首页判据、项目符号字符。照抄旧常量是 W2–W5 的共同根因。

### W2. 页眉阈值把代码清单首行吞了

`if bb[3] < 60: continue` 在旧书成立，本书页眉 y≈27 但**代码清单从 y≈51 起**，
首行被当页眉丢弃。改为 44 后恢复。判据前置动作：dump 一页的 y 分布，
分别标出页眉底、正文首行、代码首行，再定阈值。

### W3. 字体族名差一个后缀，正文全被判成图内文字

旧书 `NewBaskervilleStd-*` / `ITCFranklinGothicStd-Dem`，本书是
`NewBaskerville-Roman`（无 `Std`）/ `FranklinGothic-DemiItal` / `JetBrainsMonoNL`。
`BODY_FONTS` / `CODE_FONTS` / `HEAD_FONTS` 三张表都要按 `page.get_text('dict')`
的实测值重建；只改其中一张时，症状是「大段正文消失、图里多出陌生文字」。

### W4. Wingdings 私有区项目符号 + 缩格续行

本书列表符号是 `\uf0a1`（私有区 `\uf000-\uf0ff`），不在 `[•·▪¡]` 中，
导致 bullet 列表被并进普通段落。三处要一起改：

- 列表识别正则含 `\uf000-\uf0ff`；
- **缩格续行判据**：续行 `x0 > 版心左边界 + 4pt` 才并回上一项，
  否则「列表后的新段落」会被整个吞进最后一项；
- 连续项目符号项合并到**同一个** list 块（每项独立成块会让骨架与译文错位）。

### W5. 章首页没有装饰性大章号

旧判据「size>=40 的孤立数字」在本书失效：章首页只有 30pt 斜体章题 +
`This chapter covers` 列表 + 下半页导言。改为按「含 `This chapter covers`
且有 30pt `NewBaskerville-Italic` 章题」判定，章号用
`{物理页: 章号}` 映射表（本书物理页 = 印刷页 + 28）。
附录首页是 `appendix A` + 标题（也是 30pt 斜体），要识别成 heading，
否则标题落进 figtext 被当图内文字。

### W6. 图注是「一组行」，不是一行 —— 裁不干净就留英文残影

Manning 图注常由三段组成：`Figure 编号` + **同一视觉行的长描述（y0 更小）**
+ 下面两行续文（字体甚至换成 `JetBrainsMonoNL,Bold` 7.5pt）。
只按 Figure 行 y0 裁剪，会在图底留下半行英文残影（V3 的加强版）。
可靠做法：

```python
cap_y = min(ln.bbox[1] for ln in lines if CAP_RE.match(ln.text))
grp = [ln for ln in lines
       if cap_y - 12 <= ln.bbox[1] <= cap_y + 40
       and ln.size <= 9.5
       and (CAP_RE.match(ln.text) or 图注字体族命中)]
fig.lines = [ln for ln in fig.lines if id(ln) not in {id(x) for x in grp}]
fig.bbox = (x0, y0, x1, min(fig.bbox[3], min(g.bbox[1] for g in grp) - 2))
fig.caption = ' '.join(g.text for g in sorted(grp))   # 英文全文存下
```

`CAP_RE` 要同时匹配 `Figure` 与 `Table`；排序时把 Figure 行放最前。
图注英文全文保留在 figure 块里，译者在 `CAP:` 行写中文，不丢信息。

### W7. 裁出图注后，figure 分支必须自己输出图注并 keepNext

旧生成器的 figure 分支**只插图、不写 caption**（因为旧项目把图注留在图里）。
裁图注后若不补，中文版会出现「有图没图注」；补了还要给图片段设
`keep_with_next`，否则图在页底、图注被推到下一页。
两处一起改，改完目视一页含图页确认「图 + 图注同页」。

### W8. 空列表块与孤立页码要在冻结解析器之前清掉

PDF 折行会留下 `items=['']` 的空 list 块、`xxvi` 这类孤立页码，
`check_zh.py` 会判空块。删块会**重排块号**，所以必须在生成骨架前
扫描并删除、然后重跑 `slice_layout.py` + `mk_skeleton.py`。
本次共清 17 个空块 + 1 个页码，涉及 ch03/04/07/08/11 等。

### W9. 数据表「按列排版」把整列塞进一个单元格

表 C.1 被解析成 2 行 4 列、每格 10 个数字；表 E.2 是 5×5、每格 10 个分数。
这类表按列排版，通用网格提取必错。两种处理按难度选：

- 能重建（行列关系清楚）→ `fix_tables_<doc>.py` 把 figure 改成真 table，
  手写 `grid.data`（表 2.1/2.2 成功还原为 7×2 / 6×2）；
- 不能重建（数据密集、模型名/许可证/网址多）→ 改成 figure 原表图 +
  中文表题，保留英文数据，与「数据表 KEEP」策略一致。

**改成 figure 时必须在 `book_figtexts.json` 补一个 `{'blocks': []}` 的同名 key**
（如 `p409_f0`），否则 `render_figs.py` 不产图、docx 静默缺图。key 名要与
`convert.py` 的 `p{page}_f{页内序号}` 一致；改完跑 `check_merged_images.py`。

### W10. Part 扉页漏页：`after` 排序键

`check_page_coverage.py` 抓出 5 页 Part 扉页（每页 1000–1800 字导语）未进 docs。
补成 `kind=part` 的独立 1 页文档，并给 `out_name()` / `sort_docs()` 支持
`after` 字段（part1 `after=0` → 排序键 0.5，插在 ch01 的 1 之前）。
**不要并进相邻章**：那会平移该章全部块号，已写译文全部作废。

### W11. 图内译文用「唯一短语映射表」批量生成

图多、重复标签多时（ch04 84 个唯一短语→129 条、ch10 125→180、
ch08 114→144），逐条手写既慢又易漏。做法是每章一个小脚本：

```python
c = Counter(b['en'] for v in figtexts.values() for b in v['blocks'])  # 先看唯一数
M = {'User question': '用户问题', ...}          # 精确映射
PREFIX = [('In the standard Retrieve-and-Read', '中文长句'), ...]  # 长句前缀兜底
zh = M.get(en) or next((t for p, t in PREFIX if en.startswith(p)), en)  # 默认 KEEP
```

PDF 提取的长叙述句常被截断/拼接，精确键匹配不上，所以**前缀规则是必需兜底**。
默认写英文原文会让渲染器标 `KEEP`，完全合法。生成后统计 OK/KEEP 写进交付说明。

### W12. KEEP 要分层，并按章记比例

保留英文：类名、函数名、代码残片、网址、许可证名、示例查询、
`Q1/C1/HD1` 这类标识符、`thread_id`、SQL 关键字、数据表数值。
中文化：流程标签、步骤说明、叙述性注释、云朵/便签里的解释文字。
栅格截图（LangSmith 追踪、终端、MCP Inspector）**只给中文图注**，界面英文原样留。
本次记录：ch01 OK92/KEEP73、ch07 OK60/KEEP99、ch10 OK88/KEEP92、
appE OK37/KEEP105。比例随内容变化，不必追求「图上零英文」。

### W13. OpenBLAS 内存错误会让整章插图静默消失 ★

`render_figs.py` 偶发：

```
OpenBLAS error: Memory allocation still failed after 10 retries, giving up.
```

进程直接退出，`figs/<doc>/` 为空；而 `build_doc.py` 仍会生成缺图 docx，
`audit.py` 只报「块序列完全一致」，看不出异常。**根因是 BLAS 多线程内存分配**。
修复：在 `build_doc.py` 的 `run()` 里固化子进程环境

```python
env = dict(os.environ, PYTHONIOENCODING='utf-8',
           OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
```

并在交付前跑 `check_merged_images.py`：inline 图片数 == 唯一 rId == media 数 == 图块数。
发现某章图片数不对，先查 `figs/<doc>/_report.json` 是否存在。

### W14. 合订前置页尺寸必须等于分册，否则全书重排膨胀 ★

本次前置页自建为 16×23cm，而分册是 A4（21×29.7cm / 边距 2.4, 2.2）。
`docxcompose` 以 master 的节设置为准，合并后**所有分册被按小页面重排**，
分册合计 400 页膨胀成 628 页（不是空白页，是文字密度变了）。
改回 A4 后恢复 406 页。

```python
ref = Document(plan[0]['path']).sections[0]
assert abs(front.section.page_width - ref.page_width) < 1000, '前置页尺寸与分册不一致'
```

**合订前读任一分册 `sections[0]` 的 page_width/height/margins 并复制到前置页**。

### W15. 目录页码用文本定位会被目录页自己骗到 ★

V5 建议「按标题文本在合订 PDF 里定位真实起始页」。本次 25 条**全部被误定位成 2/3/4**——
因为目录页本身就印着全部章名，第一次命中必然在目录页。
当合订是「逐份 PDF 拼接 / 分册页数不变」时，改用**页数累加法**更可靠：

```python
F = 前置页单独转 PDF 的页数                  # 本次 4
acc, pages = F, {}
for item in plan:
    pages[item.id] = acc + 1
    acc += pymupdf.open(item.pdf).page_count
# 校验：总页 == F + Σ分册页数 + 索引页数   # 406 == 4 + 400 + 2
```

两轮校准照做（占位目录 → 合订 → 累加回填 → 重新合订），只是把「定位」换成「累加」。
目录条目文字直接用页眉 label（`第 N 章　标题` 已含标题），不要再拼一次 title，
否则出现「第 1 章　AI 智能体与应用导论　AI 智能体与应用导论」。

### W16. 「图内多 N（提示）」不是错误，不要清零

`check_cov.py` 的 `need` 只统计需要翻译的图内块；给免译符号块、纯数字编号
也写了译文时会报「图内多 N（提示）」，脚本明确**不算失败**，渲染器照常采用。
真正必须清零的只有「多余块号」。为消除提示去删译文是白费功夫。

### W17. 跨会话逐章推进：紧凑原文 + 固定动作 + 磁盘进度

一章一交付、每轮 1–2 份时，先把 `_skel.txt` 转成「紧凑原文」：
`@@B n type` + EN，**code 块只写 `[CODE nL]`**（本章 43k 字符里代码占一半）。
每份固定动作：评估规模/空块 → 紧凑原文 → 双闸门 → `build_doc.py` →
转 PDF → 图片三数 → 目视一张多块图 → 更新 `PROGRESS.md` 与当日日志。
进度以磁盘产物为准；`PROGRESS.md` 放状态表、质检记录、续做命令、收尾说明。

### W18. 编译性处理要集中登记

原书没有独立图注的「代码清单标题图」、被 PDF 拆成两块的插图
（图 1.8 / 5.1 / 9.1 / 14.1）、跨两页的表格图，中文版各配一条描述性中文图注。
这是编译性加注，不是原文；必须在 `PROGRESS.md` 收尾说明与交付说明里统一列明。

### W19. 交付说明模板：7 类已知限制 + 术语索引自动生成

本书交付说明固定写 7 类：① 栅格截图保留英文（列页码/比例）② 数据表保留英文数据
③ KEEP 标识符 ④ 编译性中文图注 ⑤ 原书笔误与断句处理 ⑥ 原书索引改为术语索引
⑦ 版权性质（AI 辅助翻译、非官方授权译本）。
术语表**开工就建**，收尾时从术语表 Markdown 自动解析生成中英索引（本次 64 条），
不要到最后一章才临时凑。

---

## X. 混合型书 + 并行交付 + 内容级质检（233 页 Manning 2025 实战）

《Data Analysis with LLMs》233 页 / 10 章 / 14 份分册 / 43 图 / 157 图内文字块 /
225 代码块。这一组是**前面各组都没覆盖的新场景**：同一本书里矢量图和栅格截图共存、
9 章由并行子代理同时翻译、以及「所有工程闸门都绿之后还要单独查译文内容」。

### X1. 第三种形态：混合型书（矢量图 + 栅格截图共存）

技能开头说「文字层书 / 栅格书混用必翻车」，但实测存在**同一本书两种都有**：
流程图/示意图的标签是 `ArialMT` 矢量 span（可取坐标），而 ChatGPT / Colab /
Cohere / Hugging Face 的界面截图是嵌入式 PNG（字在像素里）。

十秒判定不要只跑一页，**按页统计 `get_image_info()` 与 `get_drawings()`**：

```python
# 有图的页：图区 get_text(clip=bbox) 有字 → 文字层；空 → 栅格
# 本书 74 张可视图里约 20 页是界面截图，其余是矢量流程图
```

正确分流：**矢量图走 `render_figs.py` 重绘，栅格截图整图保留 + 中文图注**，
在交付说明里列出保留英文界面的页码与原因。不要为了「图上零英文」对栅格截图做
OCR 擦除——界面文字密集、相邻框重叠，收益远小于返工（见 T 组）。

### X2. 「文字层丢空格」多半是探查脚本自己的锅

初判时看到 `careertoexploitingtheamazingcapabilities...`、`importopenai` 这种
粘连文本，差点判定为「PDF 文字层损坏、不能译」。根因是探查脚本写了
`[s for s in line['spans'] if s['text'].strip()]`，**把纯空格 span 过滤掉了**。

判据：先算全书空格率（正常英文约 0.15）。正常就说明文字层完好，
是自己的 span 拼接逻辑丢了空格。写解析器时 `join_spans` 不要过滤空 span。

### X3. 章首页下半页有正文：`chapter_open` 会吞掉整页

`main()` 里若 `is_chapter_open(page)` 为真就只输出一个 `chapter_open` 块，
在「章首页只有标题+本章内容+导言」的书里没问题；但本书 p20 还有
`1.1` 标题、导言后的正文段落和四行诗，全被吞掉。

做法：给 `parse_chapter_open` 额外返回 `_rest_y`（第一个 heading 的 y − 3），
`main()` 里 `blocks = [co] + page_blocks(page, pno, skip_y0=rest_y)`；
`page_blocks` 收行时跳过 `bb[1] < skip_y0`，并在 `skip_y0 > 0` 时把
`graphic_regions` 置空（章首页的装饰章号是文字不是图元，聚类会造假图块）。
导言常有多段，让 `convert.py` 的 `kv()` 把 `INTRO` 收成列表再 `'\n'.join`，
`build_docx.py` 的 chapter_open 分支按 `\n` 拆成独立段落。

### X4. 代码清单 / 便签被聚成图：整块回收，旁注剔除

Manning 清单由「`Listing X.Y` 标题 + `CourierStd` 代码行 + `CombiNumeralsLtd`
圈码旁注」构成，矢量框聚类会把整块吸成一个 figure，代码就不可复制了。

图形区后处理加三条回收规则（顺序在 `ok_grid` 判定之前）：

```python
has_listing = any(LIST_RE.match(ln['text'].strip()) for ln in f['lines'])
code_lines  = [ln for ln in f['lines'] if ln['kind'] == 'code']
has_note    = re.match(r'^(TIP|WARNING|NOTE|DEFINITION)\b', _all_txt)
has_ann     = any(ann_font in ff for ln in f['lines'] for ff in ln['fonts'])
if has_note or has_ann or has_listing or len(code_lines) >= 2:
    # 旁注行剔除（否则一份清单被切成多个孤立代码块），其余回收为正文
    reclaimed.extend([ln for ln in f['lines'] if not is_pure_ann(ln)])
    continue
# 宽幅多行正文被误吸（含圈码的 13.4pt 正文行尤易发生）
if w > 240 and len(body_lines) >= 2 and body_chars > 120:
    reclaimed.extend(f['lines']); continue
```

同时把 `Listing X.Y` 标题行判为 `body`（普通段落），中文版写
`清单 3.1　……`（编号后全角空格）。空底色条 / 矮装饰框（无文字且 h<80）丢弃。

### X5. 侧置图注被裁进图区：`caption-erased` 只擦不写

图注整组裁剪（W6）依赖「行首匹配 `Figure|Table X.Y`」。本书侧置图注与图上文字
混排时被合成一行，`text` 变成 `Multimodal prompt con- Figure 6.1 taining an image...`，
`CAP_RE.match` 失败，整段英文图注留在图里，与 Word 正文的中文图注重复。

兜底放在 `render_figs.py` 的块循环里，**在 KEEP 判定之前**：

```python
if len(b['en']) > 55 and re.search(r'\b(Figure|Table)\s+\d+\.\d+', b['en']):
    bg, box = sample_pad(img, bbox_px, pad=10)   # 采底色
    dr.rectangle(box, fill=bg)                   # 只擦，不写字
    report.append({'status': 'KEEP', 'reason': 'caption-erased'}); continue
```

中文图注已由 Word 正文 `CAP:` 呈现，图里留白比留一段英文干净。
另外：骨架里 `CAP:` 为空的 figure 块，要从原书该页的
`FranklinGothicFS-Demi` 8pt 行恢复完整英文图注再译，别自己编。

### X6. 清理 PDF 残留时，一次性正则会吞掉块头

Manning 电子版每本带随机防伪追踪码（形如 `XK 470 3686`、`TL 445 6808`），
不是正文。用 `re.sub(r'\s*[A-Z]{2}\s+\d{3}\s+\d{4}\s*', ' ', t)` 清理时，
首尾的 `\s*` **会跨行**，把下一行的 `@@B 123 code` 拼到上一块末尾：

```
@@B 122 p @@B 123 code     ← 块头不再独占一行，check_cov 报「缺 123」
```

症状具有欺骗性：块数少 1、类型错 N 处、空块 1 处，且**从某处开始整体错位一格**。

正确做法是结构化同步清理，**四处同时改**（`fix_noise.py` / `drop_orphan_caption.py`）：

1. 记下每份文档里「整块是噪声」的**旧块号**；
2. 修复所有被拼到行内的 `@@B`（`re.sub(r'[ \t]+(@@B\s+\d+)', r'\n\n\1', t)`）；
3. 从 `book_layout.json` 删整块、其余段落只去串不删块 → 重跑
   `slice_layout.py` → `clean_front.py`（前置页清洗会被 slice 覆盖，必须重跑）
   → `mk_skeleton.py` → `gen_figzh.py`；
4. 对译文删对应块并**按出现顺序重编号 0..N-1**；
5. 双闸门 + 重建该分册 + 重跑合订（页数可能变，目录要两轮校准）。

同一套流程也适用于「原书图注断词残留的孤立英文尾巴」
（本书 `lized tool, generating a query result.`，中文图注已完整覆盖其含义）。

### X7. NULL 字节藏在 JSON 的 `\u0000` 转义里

`build_docx.py` 报 `ValueError: All strings must be XML compatible`，
只有一章失败。直接扫 `_zh.txt` 没有控制字符；`json.dumps(obj)` 也扫不到——
因为 `\x00` 在 JSON 文件里是**字面 6 字符** `\u0000`，`dumps` 又把它转义回去。

必须递归遍历解析后的字符串对象，且覆盖 C0、C1、代理项、FFFE/FFFF：

```python
ILL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\u007f-\u009f\ud800-\udfff\ufffe\uffff]')
def clean(o):
    if isinstance(o, str): return ILL.sub('', o)
    if isinstance(o, list): return [clean(x) for x in o]
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    return o
# 对 work/*.json 全部无条件重写，不要用 dumps 做存在性判断
```

### X8. 并行子代理逐章翻译：prompt 六要素 + 分段追加

9 章由 9 个子代理并行完成，全部一次通过双闸门。关键是 **prompt 自包含**：

1. 项目根绝对路径 + 本章骨架路径 + 块数；
2. 必读三件：`TRANSLATION_GUIDE.md`、`work/<doc>_skel.txt`、已完成的样板
   `work/ch01_zh.txt`（让代理照格式，不要靠描述猜）；
3. 格式规范摘要（`code` 留空、`figure` 只写 `CAP:`、清单标题全角空格、
   `INTRO` 多行、`■` 逐行）；
4. **块号纪律**：只信骨架、不合并 figure 与紧随的 p 块、不新增块；
5. 保留英文的类别（模型输出/提示词字面量/SQL/参考文献/产品名）；
6. 自检命令（`check_cov.py <doc>` + `check_zh.py <doc>`）与「不许写 `_figzh.txt`」
   （图内译文由统一映射表生成，避免代理各写一套）。

长文件（150+ 块）必须允许分段追加：先 `Write` 写前 40~50 块，之后用
`open(p, 'a', encoding='utf-8').write(...)` 追加，**禁止第二次 Write 覆盖全文**。
收尾统一由主流程跑双闸门 + 漏译扫描复核，代理的自检只当第一道过滤。

### X9. 图内译文映射表通用化：KEEP 写英文原文

W11 的做法在项目里常写成每章一个 `gen_figzh_chNN.py`。本次用**一个通用脚本**
（技能 `scripts/gen_figzh_map.py`）从 `book_figtexts.json` 导出全书唯一 EN 短语，
「精确映射 + KEEP 模式 + 默认写英文原文」，一次生成全部 14 份 `_figzh.txt`
（100 条中文化 / 57 条 KEEP）。

两个易错点：

- `render_figs.py` 判 KEEP 的条件是 `cn.strip() == b['en'].strip() and vis > 0.012`，
  所以 **KEEP 要写英文原文**，不是字面 `SAME`（`SAME` 只被 `fig_raster.py` 认）。
  写纯空白会被判 `MISSING`。
- 连字 `ﬁ` 等要用 `unicodedata.normalize('NFKC', en)` 做映射键，否则命中不了。
- 建表时按类别分层：界面按钮 / 数据表字段 / 示例查询 / 工具名 / 极窄标签 KEEP，
  流程标签与叙述注释中文化；把 OK/KEEP 比例写进交付说明。

### X10. docxcompose 合并后页眉页脚全丢

`build_final_book.py` 以「无页眉页脚的前置页」为 master，
`Composer.append()` 之后**所有节都套用 master 的空页眉**：
`layout_check.py` 报「页眉样式数 1」，合订 PDF 页脚一个数字都没有，
而分册 PDF 的页眉页码都正常。技能「呈现层」讲了顺序，但没讲这个症状。

修法在 `merge()` 内，顺序只能是「分节 → append → 逐节写」：

```python
set_section_chrome(comp.doc.sections[0], labels[0])
for f, lab in zip(files[1:], labels[1:]):
    sec = comp.doc.add_section(WD_SECTION.NEW_PAGE)
    sec.header.is_linked_to_previous = False
    sec.footer.is_linked_to_previous = False
    comp.append(Document(f))
    set_section_chrome(comp.doc.sections[-1], lab)   # append 之后才写
for sec in comp.doc.sections:                        # 清 pgNumType，页码连续
    for el in sec._sectPr.findall(qn('w:pgNumType')): sec._sectPr.remove(el)
```

`set_section_chrome` 重写页眉文字 + 下边框，并重建页脚 `w:fldSimple instr="PAGE"`。
重建后 `layout_check.py` 页眉样式数从 1 变 9；封面页码在 PDF 层用
redact 擦掉（不加数字）。

### X11. 两级书签要接进重建链，否则一重建就退化

从各分册 `_trans.json` 的 `h2`/`h3` 中文标题，在该分册于合订本中的页区间内
按「去空格后前 14 字」定位，可生成 15 条章级 + 185 条小节级书签。
`pymupdf.set_toc()` 后检查**页码回跳 0、越界 0**。

关键纪律：**把这一步接进 `finalize.py`**。`build_final_book.py` 每次重建只写
章节级书签，若二级书签是手工跑的，下一次重建就悄悄退回 15 条。

### X12. 下游一致性：改任一分册都要一条命令刷新

改译文 / 删块 / 改封面后，手工逐步重跑容易留下旧 PDF 与旧书签。
`finalize.py` 把下游串成一条链：

```
14 份分册 docx → 逐份转 PDF → 删旧合订 PDF → build_final_book.py
→ 擦封面页码 → add_pdf_outline.py → 目录页码 5 条抽查
```

只排除 `_前置页.docx`、`_术语索引.docx`、合订本自身，其余 `out/*.docx` 全部重转。
`build_final_book.py` 的目录两轮校准依赖各分册 PDF 的实际页数，
**分册 PDF 不刷新，目录页码就是错的**。

### X13. 工程全绿 ≠ 译文没问题：内容级自查要单独做一层

用户问「翻译有没有问题」时，再把双闸门跑一遍没有意义。本次新增
`scripts/qa_translation.py`，逐块对齐 `*_layout.json` 与 `*_trans.json`，做 8 类
量化扫描：长度比、数字、URL、圈码、编号格式、术语变体、相邻重复、图注/清单编号；
再对机翻高发的**否定与比较结构**做定向扫描；最后每章抽 1 段人工逐句细读。

实测结果很反直觉：**量化命中几乎全是误报**，必须逐条写清原因才可信：

| 命中 | 真实原因 |
|---|---|
| 长度比异常 2 块 | 评审人名表（只译连接词）、中文更凝练 |
| 数字未原样出现 3 块 | `1,000`→「一千多」、`680,000`→「68 万」、`365 million`→「3.65 亿」 |
| URL 未匹配 24 块 | 正则吞了句末 `.`/`;`，以及 PDF 断字被正确修复 |
| 否定结构 8 块 | 5 块是规范保留英文的模型输出；双重否定被正确转成肯定 |
| 比较结构 47 块 | 多为 `as well as` / `as long as` 被正则误判 |
| 专有名词小写变体 | `import openai`、`sqlite3`、`serpapi.com` 等合法字面量 |

**96 处「整块不含中文」也要分类**（模型输出/提示词 64、SQL/代码/数据字段 23、
产品名标题 5、参考文献 4），而不是当成漏译。本次 10 段抽样细读 0 处误译，
最后只修了 3 处一致性与措辞项。把「为什么这些不是问题」写进
`译文自查报告.md`，比只报一句「检查通过」有说服力得多。

### X14. 术语「语境变体」要写进规范，别靠全书强行统一

`token` 在本书出现 204 次、「词元」14 次，看似不一致，实际是：
ch03 是 API 参数（`max_tokens`）、ch09 是计费公式，保留英文是**有意的语境选择**；
ch04/ch07/ch10 的一般叙述用「词元」。

规范里要写死口径，否则每次自查都会把它当问题：

> 术语定义/一般叙述写「词元（token）」并后续用「词元」；API 参数名、计费公式、
> 模型 ID、代码与命令行中的字面量一律保留 `token`。

强行替换 200 处会破坏参数名、公式与可读性。同样，「数据集」38 次 vs
「数据集合」1 次才是真变体，改 1 处即可。

### X15. 交付前必查清单补两条（在 V/W 组之外）

- **内容级自查**：`qa_translation.py` + 每章抽样细读 + `译文自查报告.md`；
  量化命中逐条判读，不允许只报「通过」。
- **下游一致性**：`finalize.py` 跑完后，分册 PDF 时间戳、合订本、
  两级书签数、目录页码抽查四者必须同时是最新的。

### X16. 「模型输出保留英文」有边界：教学对话不是字面量

翻译规范里「模型输出、提示词示例、代码、SQL 保留英文」容易被过度套用。
本次把整章 User/GPT 逐轮对话（约 60 块）全保留英文，读者根本读不懂书在讲什么，
用户反馈「没有翻译，并柔和在一起，缺乏阅读感」。

判据不是「这段是不是模型生成的」，而是：

- **读者要读懂的内容**（演示对话、示例评论、模型回答的叙述部分）→ 译中文；
- **读者要复制或核对的字面量**（SQL、代码、`Personal computers.` 这类输出标签、
  英文落款、API 名、URL）→ 保留英文。

`audit_book.py` 会把这些块报成「漏译」，别为了清零去改规范；但反过来，
**「漏译复核 0 处」也不能证明对话可读**。要单独抽一页对话目视。

### X17. PDF 把说话人标签混进正文行，轮次必须从页面重建

Manning 对话排版是「`User:` / `GPT:` 斜体标签在左 + 正文缩进」。
PDF 提取把标签并进首行，甚至插到句子中间：

```
B29  'Have a look at the following product review: User :'
B31  'Based on the review, the BananaBook is a product that the reviewer pur-GPT :'
B50  'refer to? Answer concisely: Electronics. GPT :'      ← 一轮 User + 一轮 GPT 挤在一块
B72  '... producing Banana-User : Book! ... GPT :'          ← 标签插在断词中间
```

不能靠 `text.startswith('User')` 判断轮次。做法：

1. 渲染原书对应页，**按页面目视重建每一轮**；
2. 译文里用 `**用户：**` / `**GPT：**` 加粗标签（`add_rich` 会自动渲染粗体）；
3. 一块含两轮时用 `■` 分行（`convert.py` 转硬换行），**不要拆块**——拆块要
   layout/skeleton/译文四处同步重编号，代价远大于收益；
4. 被断词劈开的续行（如 `pur-` / `chased`）按语义重组到前一块，别留悬空半句；
5. 给这些块打 `dialog` 样式：左缩进 0.75cm + 左侧细线 + 小段距。

**特别坑**：`build_docx.py` 里「前块不以句末标点结尾就与后块拼接」的
文字环绕图修复逻辑，会把「用户续行」和「GPT 首行」粘成一段，说话人标签又挤在一起。
合并判据必须加 `not prev.get('style') and not cur.get('style')`——
**带版式语义的块一律不合并**。

### X18. 侧栏框 / 提示框是内容，不是装饰

原书有 38 个米黄色矩形（`fill ≈ (0.97, 0.96, 0.91)`，`w>200`、`h>25`），
里面是 DEFINITION / TIP / 提问式侧栏：
`Which model should I choose?`、`What are hallucinations?`、
`Why am I getting different output?`、`What is the .csv format?`、
`How to deal with multiline queries` ……
用户反馈「有一些提问是在特定方块内，翻译后也没有了」——文字其实译了，
但**框没了、标题压成普通正文，看起来就像内容消失**。

做法（只加字段、不动块序）：

```python
# 1. 按 fill 色从 PDF drawings 提取框 bbox（排除章首页「本章内容」框）
f, r = dr.get('fill'), dr.get('rect')
if f and r and r.width > 200 and r.height > 25 \
   and abs(f[0]-0.97)<0.03 and abs(f[1]-0.96)<0.03: boxes[pno].append(r)

# 2. 落在框内（重叠 >35%）的块打 style；与框内第一行标题匹配的打 sidebar_head
# 3. WARNING / TIP / NOTE 开头的块打 warning / tip
# 4. 呈现层给段落加 w:shd 底纹 + w:pBdr 左边线，连续段段距设 0 才不留白缝
```

`sidebar_head` 用深蓝粗体，`warning` 暖橙底，`tip` 浅蓝底。
章首页的「This chapter covers」框由 `chapter_open` 自己渲染，别重复打框。

### X19. 版式语义要作为数据字段透传，别写进译文文本

```
book_layout.json  加 style 字段（不改块数/顺序/type）
   ↓ slice_layout.py
<doc>_layout.json
   ↓ convert.py: blocks[-1]['style'] = b.get('style')
<doc>_trans.json
   ↓ build_docx.py 按 style 选底纹/缩进/字号
docx
```

这样 `_zh.txt` 仍是纯中文可编辑文本，`check_cov.py` / `check_zh.py`
只比 type 与块数，**双闸门完全不受影响**；换一本书只要改打标规则，
渲染层不动。反面做法是把 `::USER::` 之类标记写进译文，既污染正文又容易漏渲染。

### X20. Part / 部分扉页要单独渲染

原书扉页 = 米黄底纹块里的 `Part 1` + 大号蓝色斜体部分标题 + 大号引言 +
各章介绍 + 下半页留白。中文版若用普通段落，用户一眼就看出「部分标题没特别处理」。

给该页**第一个非 figure 块**打 `part_title`（第一块常是被 `slice_layout.py`
过滤掉的装饰图，直接取 `blks[0]` 会打空），译文用 `■` 分成两行：
第一行 `第 1 部分　认识语言模型` 渲染成 23pt 带米黄底纹的大标题，
第二行渲染成 13pt 斜体引言，中间加 `hr_rule()` 分隔线。
`docs.json` 的 `kind: part` + `after` 已保证它在合订顺序里排在章前。

### X21. 双闸门全绿 ≠ 排版还原：必须并排目视

本次 5 类问题（对话、框内提问、版式压平、部分扉页、阅读节奏）
**没有任何一条会被现有校验脚本发现**：块数对、类型对、图片三数对、
页码对、漏译复核 0 处。是用户把原书页和成品页并排看才发现的。

交付前固定加一步：把原书 2–3 个代表性页面与成品对应页各渲染成 PNG，
逐项对照「标题层级 / 底色框 / 对话标签 / 缩进 / 留白」。
`qa_translation.py` 可以顺带统计各类 `style` 的块数（对话 35、侧栏 56、
提示 12、扉页 3），数量为 0 就说明打标没生效。

### X22. 目标 PDF 被预览面板独占时，别硬删硬覆盖

展示过的成品 PDF 可能被外部进程独占：可读、`os.access(W_OK)=True`，
但 `open(p,'r+b')` 与 `pymupdf.saveIncr()` 都报 `Permission denied`，
`os.remove` 被 safe-delete 拦截，`os.replace` 也 `WinError 5`。
整条合订链会在最后写书签时中断。

做法：`finalize.py` 先试 `open(target,'r+b')`，失败就把输出名改为
`BOOK_FINAL_NAME`（如加「·修订版」）并 `os.environ` 传给下游所有脚本；
`build_final_book.py` / `add_pdf_outline.py` 的输出名都从该环境变量读。
分册 docx 过滤条件要用 `'全本' in basename` 而不是精确匹配新名，
否则会把合订 docx 误当分册再转一次 PDF。**不要**为了覆盖去删文件或结束进程。

### X23. 加样式救不了碎片块：对话区必须重组成轮次块

X17 用「给每个碎块加 `dialog` 样式」修过一次对话，用户看完成品**仍然不满意**。
原因是根因判断错了：问题不在「没有标签/底纹」，而在**块序列本身就是碎的**。

原书一轮对话（User 一句 + GPT 一句）被 PDF 提取切成 3–5 块：

```
B29 User 首行 + 标签    B30 User 评论续行
B31 GPT 首行 + 标签     B32 GPT 回答续行
B55 User 提问           B56 User 续行
B57 numlist 第 1 项     B58 孤立的 'GPT :' 标签     B59 numlist 第 2–4 项
B74 英文落款 + 作者旁白（混在一个块里）
```

给每个块各加一次左缩进 + 底纹，成品就是**一串分散的小色块**：
「用户：」和「（手机、个人电脑、游戏机）」分两段、`**GPT：**` 插在编号 1 与 2
之间、作者旁白被当对话渲染。样式越明显，碎片感越强。

**判据**：当「同一个语义单元」被拆到多个块、且块间有段落间距时，
补样式只会让碎片更显眼，必须**改块序列**，把碎块合并成一个完整块。

六步做法（本次 35 碎块 → 11 轮次块，ch02 163 → 141 块）：

1. 渲染原书页，按**语义轮次**把碎块分组，而不是按 PDF 块边界；
2. 每组只保留首块：`type→para`、`style→dialog`，`text` 换成本组英文全文
   （供骨架 `%%EN` 对照），其余块删除；
3. 混入作者旁白的块（英文含 `Pretty good!` / `Okay, that works!` 等）
   **排除出对话组**，去掉 style 恢复普通段落，否则旁白会被渲染成对话；
4. 一个轮次块的译文用 `■` 分行写 `**用户：** …` / `**GPT：** …`，
   编号列表让标签与第一项同行（`■ **GPT：** 1. 屏幕出色`），
   断词续行按语义重组成完整句，模型输出字面量保留英文；
5. **四处同步**：`book_layout.json` → `slice_layout.py` → `clean_front.py` →
   `mk_skeleton.py`，然后按新骨架重写 `_zh.txt`（块号 0..N-1 重新编号）；
6. 双闸门 → 重建分册 → 合订（目录两轮校准会自动处理页数变化）→ 目视。

**重映射必踩坑**：重写 `_zh.txt` 时如果图省事把块头全写成 `@@B n p`，
`check_zh.py` 会报整章「类型/缺 N 处」（`chapter_open`、`h2`、`figure`、
`numlist` 全变成 `p`）。正确做法是**从新 `_skel.txt` 读 `@@BLOCK n type` 回填块头类型**。

**渲染层反而不必改**：合并后的一个 `dialog` 块含 `\n`，`add_rich` 会渲染成硬换行，
一个段落就是一个连续色块、行间无段距，阅读感接近原书「标签 + 缩进 + 连续块」。
也就是说：**数据在 layout 层修好，呈现层保持简单**。

代价与登记：块序列与原书 PDF 文本块不再一一对应，属于编译性处理，
必须在交付说明「已知限制」里写明「未增删信息，但对话区合并为轮次块」。




---

## Y. 彩色图内文字与两遍渲染（233 页 Manning 2025 RAG 书实测）

这一组是 **O 组 / T 组 / W13 的后续**：书里大量文字不是近黑色，而是橙色
（`#F16A4B`，亮度 142）、灰色（`#717374`，115）、蓝色（`#0A509C`），
还有深条/橙条上的白字。旧 `render_figs.py` 的 `ink_ratio()` 只统计
L 直方图 `<110` 的像素，这些字**全被判成「没有墨迹」→ 跳过擦除**，
中文直接压在英文上，成品出现「J裁判模型el」「Th阈值old」「F融合n」。
三个独立子代理在不同章各自报出同一现象，说明是系统缺陷而非单章个例。

**Y1｜墨迹判据要相对底色，不能只看亮度。**
`sample_bg/mode color` 取 bbox 内像素众数（用 numpy，`arr >> 4` 量化求簇），
再算「与底色逐通道差 >56」的像素比例。白底黑字、白底橙字、黑底白字一次全成立。
顺带修掉 `_mode_color()` 里「亮度 <175 一律跳过」的老逻辑：深色底一个像素都不剩，
众数返回 `None`，擦除色退化成白色，深条上就留一块白斑、两端还剩黑段。

**Y2｜底色的选取只看「谁在这个框里占的面儿最大」。**
文字永远比背景少，所以内圈众数占比 ≥0.42 时内圈就是底色
（白底 / 黑条 / 橙条 / 黄色高亮四种全对）；只有占比过低才退到外圈。
不要再按「彩色底 vs 非彩色底」分流，也不要擦外扩 10px 的整个外圈矩形——
会啃到邻居的线条。擦除矩形改成 bbox ±1px 即可盖住抗锯齿边。

**Y3｜先擦全部、再统一写（T3 在文字层书同样成立）。**
一遍到底会出现「后一个块的底色把前一个块刚写好的字擦掉一半」：
图内文本框常有 1–3pt 互相重叠（如 `Context` 标签与紧随的正文块），
实测把「上下文」写成「卜下文」。做法：`eraseq` / `drawq` 两个队列，
循环里只算不画，循环结束后先填所有底色、再写所有中文。

**Y4｜按原始每一行擦，不要按整块 bbox 擦。**
一块里常把框外标签（`Step 4`）和框内正文并在一起，标签在框上方。
按整块 bbox 填底色会把标签与正文之间那条框线一起擦掉，
成品四个说明框全是开口的。用 `line_bboxes` 逐行各擦各的（±1px），框线完好。

**Y5｜「放不下就 KEEP」的判定必须排在擦除之前。**
旧版先填底色再判 `narrow/tiny/short` 并 `continue`，英文被擦掉、中文又没写，
图上留一块空白（一句话竖排注释就这么消失）。判定前置即可。
另外 `narrow` 用「译文总字数 > 每行字数×2」会把 6 行、每行 4 字的表格列
误判成窄条而整块保留英文；改成 **最长一行** 与 `每行字数×2` 比。

**Y6｜「原文是否可见」用墨迹像素个数，不用比例。**
短文字放在大框里时比例天然很低（47×34pt 框里两个短词，比例 0.00256），
固定阈值 0.004 会判「无墨迹」不擦，中文叠在英文上。
改成 `vis * bbox面积 >= 20` 个像素才擦。

**Y7｜图区裁剪要按图注上沿回收。**
图注间版面窗口偶尔越界到图注、甚至图注下面那句正文
（p167 的 Figure 7.1，bbox 一直伸到 579pt），裁进图片后正文与图注各出现两次。
做法：渲染时回页面文字层找 `^(Figure|Table)\s+\d+\.\d+` 行的 y，
图注位于图区下半部时把裁图下沿卡在它上沿；同时按「图内最后一块文字 + 10pt」
再收一次，给边框线留余量。落在裁图边界外的块标 `out-of-crop`、不擦不写。
注意：图注行在解析阶段已从 `figtexts` 里剔掉了，**必须回 `page.get_text('dict')` 找**。

**Y8｜图内字体用无衬线。**
原书图内是 ArialMT / Arial-BoldMT；6–7pt 小字用楷体/宋体会发灰发糊。
换 `msyh.ttc` / `msyhbd.ttc` 后与图中保留的英文标签字重、观感一致。
另：`•`(U+2022) / `▪`(U+25AA) 在 simkai/simhei 里缺字形会渲染成空心方框，
图内项目符号用 `·`(U+00B7)。

**Y9｜渲染器一旦修好，必须回头重译「被迫保留英文」的旧章。**
早期为了躲叠字，译者把本该译的名词短语、说明框句子、示例问句都写成了英文原文
（等价于 KEEP）。修复渲染器后这些残留不会自动消失，要专门派一轮「图内补译」：
只改 `_figzh.txt`、不动正文、逐图目视。本项目补译 136 块，
第 2 章图内英文残留从 32 块降到 0。**改公共渲染器后至少重建当前章 + 一个旧章**
并比对块序列与图片数，确认无回归再继续。

**Y10｜页码脚本要按 Part 的 `after` 排序，封面参数形式别写错。**
`chapter_pages.py` 的 `sk()` 若漏 `part` 分支，Part 会按自己的 `num` 排到
同号章前面（第 3 部分被排到第 3 章前），后面所有章节页码全偏 1–2 页，
而目录表面看不出问题。修复后要跑**两轮**：合订 → 重算页码 → 重建封面目录 → 再合订。
`build_front_pages.py` 只认 `--meta=xxx.json`；写成 `--meta xxx.json` 会静默
丢掉整份 meta，产物只剩一个空封面 + 一个空目录页（2 页而非 3 页）。
修复后应支持两种写法，并在交付前**把目录页文本打出来看一眼**。

**Y11｜非骨架生成的文档不要进双闸门 `--all`。**
封面/版权/目录由 `build_front_pages.py` 生成，术语索引由独立脚本生成，
都没有 `_layout.json` / `_skel.txt`；`check_cov.py --all` / `check_zh.py --all`
按 `docs.json` 全量枚举会把它们报成「未通过」。
枚举时按「同时存在 `_layout.json` 和 `_skel.txt`」过滤。

**Y12｜原书页码索引改成章节定位的术语索引。**
中文版重新排版后原索引页码全部失效，照搬只会把读者指到错页。
从翻译规范里的术语表生成「英文术语 ｜ 中文译名 ｜ 首次出现章节」三列，
按各章 `trans.json` 扫首次出现位置（中文主体 + 英文整词 + 少量同义别名），
既保住查词功能又不会指错。本项目 101 条全部定位到章节，未定位 0。

**Y13｜二级书签别用「页码单调递增」硬约束，按命中页排序。**
章首页的「本章内容」目录条目常被解析成 `h3`（如「关键层」「小结」「生产最佳实践」），
它们命中章首页、却排在 `_trans.json` 里正常小节标题之后。
`add_pdf_outline.py` 旧逻辑 `if hit and hit >= last_page` 会把它们以及后续
所有标题一起丢掉 —— 实测某章 11 个标题只定位 5 个，看起来像「30 条书签丢失」，
其实是约束写错了。改成收集 `(命中页, 标题)` → 按页排序 → 去重 → 全部写入。
另外 `key = norm(标题)[:14]` 之后别用 `len(key) < 4` 过滤：
「小结」「总结」这类 2 字标题是合法小节，会被静默丢掉；放到 `< 2` 即可。
本项目修完后 158 个小节标题 **100% 定位**（16 一级 + 162 二级 = 178 条书签）。

**Y14｜表格说明列能不能中文化，取决于块是不是「跨行合并块」。**
两种情形要分开判：
- **每行是独立块**（表 6.1）：把译文按原文 `line_bboxes` 的行数**显式分行**
  （`@@T` 首行 `ZH` 后直接续行，每行 4–8 字），渲染器会把字号从 4.6pt 拉回
  9.1pt、`over_h=0`、段首与左侧行名偏差 ≤1 行。35 块全部成功中文化。
- **10 个单元格并成一个 490pt 跨行大块**（表 7.1）：显式分行虽然指标也 OK
  （9.1pt / 46 行 / 无溢出），但脚本的 `pitch` 是**均匀值**，把原文段间
  15–19pt 的空隙摊到 46 行里，越往下累积偏移越大，实测 7 段偏差 >1 行
  （最大 2.27 行），且逐行擦除会把表格横线擦淡。**这类要老实退回 `SAME`**，
  并在交付说明里写明「试过，仍不可行」——不要为了中文化牺牲可读性。
  根治要按每段首行 y 分组排版，而不是均匀铺满 bbox。

**Y15｜`add_pdf_outline.py` 反复重跑别用 `saveIncr()`。**
每次增量保存都往 PDF 尾部追加一版对象，跑三四次文件就明显膨胀。
改成 `book.save(tmp, garbage=4, deflate=True)` + `os.replace(tmp, pdf)`，
既原子又顺带清掉旧版本对象。目录页码每轮回填后都要重跑书签，这条必踩。

**Y16｜渲染器修好后要回头清理「上轮留下的待办」。**
上一轮代理常会在回报里写「译文已备好待脚本修好」（如某两块因墨量阈值不够
被迫回退 SAME）。修完脚本要**把这些明确待办逐条补上**，而不是只重跑一遍了事；
同时派一轮「只改 `_figzh.txt`、不动正文、逐图目视」的补译，把早期为躲叠字
而留英文的名词短语、说明框句子翻出来。本项目第二轮又补译 37 块。
注意派活时要明确列出**不要动**的白名单（公式、代码字面量、曲线标签、
`out-of-crop` 正文句、整图有意保留英文的密集示意图），否则代理会好心办坏事。

**Y17｜「正文整块不含中文」扫描要分清真漏译与解析断块。**
交付前必查第 7 条会报出若干「整块不含中文」的块，逐条判读后通常是：
① 代码里的三引号提示词字符串被解析成 `p` 块（按规范代码不译，正确；
   可在译文里用反引号包成行内代码，让 `add_rich` 用等宽字体，呈现更像代码）；
② 框架名做小节标题（`5.3.1 RAGAs`、`8.5.4 RAPTOR`），原文就是纯专名，照留；
③ 一旁注被拆成两块（「所用模型为」+「GPT-4o-mini」），连起来语义完整，别改；
④ 罗马数字页码块（`xiii` / `xviii`），`build_docx` 会静默丢弃。
本项目 9 处命中**无一是真漏译**。不要把量化命中直接当 bug 修。

**Y18｜给渲染器加 `ZH ERASE`（只擦英文、不写任何字）。**
有一类残留不是「该不该译」的问题，而是**同一句话被拆成两块**：
Manning 图里的蓝色超链接文字（`month`、`Google Docs)`、`or from the user.`、
`ImageLoader in LangChain are used; for audio, we use`）常被 `extract_fig_texts`
提成独立小块，而整句中文已由旁边的长块画出。写 `SAME` → 英文与中文叠印成糊字；
再译一遍 → 语义重复；不擦 → 图上留残片。**正解是只擦不写**。
实现：在 `SAME` 分支后加 `if cn.strip()=='ERASE'`，取底色、按 `line_bboxes`
逐行入 `eraseq`（不进 `drawq`），报告记 `erase-only`。`check_cov/check_zh`
把 `ERASE` 当成合法译文，不会报缺译。本项目清了 4 块，两张明显叠字的图恢复干净。
**自动找候选**：同一 fig 内，取 `status=OK` 的块与 `KEEP/SAME` 的块，
算 `KEEP 块 bbox 与任一 OK 块 bbox 的交叠面积 / KEEP 块面积 > 0.40`，
命中的大概率就是这类残片。但**必须目视复核**——公式符号 `=`、代码字面量
`PROMPT [....]`、孤立链接标注 `Zendesk / GDPR & CCPA` 也会命中，它们不该擦。

**Y19｜批量改 `_figzh.txt` 时，段定位必须绑定当前 `@@FIG` 变量。**
踩过一次：用 `next((f for f in figs if in_seg), '')` 去取「当前图的待改 id 集」，
`in_seg` 只是布尔值，结果永远返回 `figs` 的第一个 key —— 于是第二张图的
同号块被误改成 `ERASE`，真正要改的块却没动，而且原译文被整段吞掉。
正确写法：逐行扫描时维护 `cur_fig` 与 `cur_t` 两个变量，命中 `(cur_fig, cur_t)`
才替换。改完必须做两件事：① 打印所有 `ERASE`（或改动）的 `(fig, id)` 列表核对；
② 从 `work/*_figtrans.json` 反查被误改块的原译文并恢复。
文件可能是 CRLF，`re.split(r'(?=^@@T \d+$)', ..., re.M)` 会因行尾 `\r`
一个都匹配不上却静默成功 —— 用 `splitlines()` 逐行处理更稳。

**Y20｜交付后不要无限「继续」。**
两轮质量清理之后，剩下的限制（跨行合并表格列、曲线逐字标签、环带碎片、
原书自相矛盾的「六个/七个步骤」）都属于**解析层或原书自身**，改动会牵动
块序列与全书分页，收益小于风险。此时应把已知限制写全、质检报告补齐，
明确告诉用户「全书已完工」，而不是继续找活干。判断标准：新的改动是否还能
在不重排块序列的前提下提升可读性；不能就收尾。

**Y21｜跨行合并的表格说明列，用「按原始每行 y 定位」根治。**
Y14 说这类块（10 个单元格并成一个 490pt 大块）只能退回英文，那是**均匀 pitch**
时代的结论。真正的修法是给渲染器加 `per-line` 模式：

1. 判据要严：译文含显式 `\n`、且 `len(译文明文行) == len(line_bboxes)`、
   且 `行数 >= 6`、`bbox 高 > 150pt` 才启用。普通多行标签不受影响。
2. 每行单独进 `drawq`：`ty_i = 原行 y0 + (原行高 - fs)/2`，
   `x0_i = 原行 x0`，`centered=False`（左对齐，与左侧行名同一列基线）。
   原文段间 15–19pt 的空隙就自然保留下来，不再累积偏移。
3. **字号要按最小行距收一档**：原文同段内行距常只有 9pt，而按整列宽求出的
   字号可能是 9.1–9.2pt，逐行贴回去会上下叠字。
   `min_gap = min(相邻行 y 差)`，`fs = min(fs, int(min_gap * 0.94))`。
   本项目收后为 8.4pt，仍清晰可读。
4. **溢出按整块列宽判，不是按该行英文 bbox 宽**：原文短行的墨迹宽只有 40pt，
   中文 8 字约 67pt 完全放得进 156pt 的列；若按行 bbox 宽算会误报 76% OVERFLOW。
5. 报告加 `layout: 'per-line' | 'block'` 字段，便于核对哪些块走了新模式。

实测：表 6.1（32 行）段落空隙回来了、叠字消失；表 7.1（46 行）**从整列英文
变成 10 段中文**，与左侧层名逐段对齐、无白块、无压线、无残留。
到这一步，「跨行合并表格列不可中文化」这条限制才算真正解决，不要再写进交付说明。
配套：译文必须**按原文行数严格一行对一行**地写；可用
`page.get_text('dict')` 按 `x0` 落在列范围内、`y0` 落在块范围内把 46 行英文
逐行抽出来，再逐行译，别凭语感估行数。

## Z. EPUB 源 + 锚点槽位 + 统计图（145k 词 Manning MEAP 实测）

第七种形态。**这一组的前提是「手上是 EPUB」**：块边界由 XHTML 标签给定，
PDF 流程里最贵的那两件事（版面聚类、图区归属）直接消失。但代价转移到三个地方：
嵌套容器的递归、槽位名的纪律、OCR 拆词后的语义重建。

### Z1. EPUB 不要转成 PDF 再解析 ★

见过这条弯路：拿到 `.epub`，先 `soffice --convert-to pdf` 或 Calibre 转 PDF，
然后套 PDF 流程去聚类图元、反算代码缩进、判图区归属。

**这是把已有结构标注亲手拆掉。** EPUB 里 `chapter-N.html` 的
`<div class="readable-text">` / `<h2>` / `<pre class="code-area">` /
`<div class="figure-container">` / `<table class="MsoNormalTable">`
已经把「这是什么块、从哪到哪」写清楚了。PDF 流程要花几千行代码去猜的东西，
这里一个 `cssselect()` 就拿到。

判据：
```bash
unzip -l book.epub | grep -E 'OEBPS/Text/.*\.(html|xhtml)'   # 有章节 HTML → 走 EPUB 流程
```

顺带的好处：代码 `<pre>` 里的缩进**原样保留**（不用 x 坐标反算）、
图 `<img src>` 直接 `z.read()`（不用裁图）、表格 `<tr><td>` 直接读。

代价（要提前知道）：
- 图内文字**仍在像素里**，OCR 环节一个都省不了；
- 嵌套管得多（见 Z2）；
- EPUB 常见的 `&#65;` 实体、`<span/>` 空占位、`<br/>` 换行都要在解析时处理。

### Z2. 嵌套容器必须递归，`callout`/`sidebar`/`dialog` 里还有整块内容 ★

第一版按「顶层 div 逐个处理」写，结果 **ch04 的表格和 ch03 的代码块全丢**，
但块数看起来正常（因为丢的块被当成容器的一部分吞掉了）。

实测的嵌套关系：

```
div.callout-container.sidebar-container.prompt-response-sidebar.prompt-sidebar   ← 对话
├── div.readable-text  → <strong>说话人</strong> + <p>提问</p>
├── div.readable-text  → <p>[150 lines of tangled JavaScript]</p>
└── div.browsable-container.listing-container     ← 对话里还能有代码清单
    └── div.code-area-container > pre.code-area

div.callout-container.admonition-block            ← 便签
├── h5  → NOTE / DEFINITION / WARNING
└── div.readable-text → <p>正文</p>

div.browsable-container.browsable-table-container  ← 表格容器
├── h5  → Table 9.1 …
└── <table class="MsoNormalTable">

div.browsable-container.figure-container           ← 图
├── <img src="../Images/03__image012.png"/>
└── <h5>Figure 3.12 …
```

**必须写的**：一个 `walk(container, ctx)` 递归函数，容器类型各自产出
`{type:'dialog'|'callout'|'sidebar', parts:[子块...]}`，子块仍可再嵌套。
译文格式用**点号 uid**（`14` → 它的第 16 个子块是 `14.16`）承载层级（Z5）。

另一个坑：**`browsable-table-container` 里可能有多个 `<table>`**。
ch04 的 `p72` 容器里并排放了两张表（`Use Case` 与 `Aspect`）。
只取 `cssselect('table')[0]` 会静默丢掉第二张；正确做法是遍历全部 `table`，
第一张沿用容器 caption，后续的加后缀（`(2)`）。

### Z3. 图区的 `h1` 不是标题，是章名；`h5` 是图注不是小标题

EPUB 里 `<h1>` 是章标题、`<h5>` 是 figure/listing/table 的 **caption**。
若按「h 标签 = 各级标题」统一处理：

- `<h1>` 变成正文里的重复章名（章首页已有 `chapter_open`，于是出现两遍）；
- `<h5>` 变成 22 个无意义的「图注级标题」，图注反而丢了。

修法：`h1` 直接跳过（它的内容进 `chapter_open`）；
`h5` 只作为所在容器的 `caption` 读取，不产出 `heading` 块。
真正的节标题是 `h2/h3/h4`。

顺带：`div.sub-sub-section-heading` 里的 `h4` 才是四级标题。

### Z4. 验收解析结果：叶子文本包含检查，不是数块数 ★

数块数会骗人：**块数对、内容漏**。第一版丢了两张表和三段代码，
但「ch04 = 294 块」与最终一致。

可靠做法是把解析结果拍平成文本，与 `squash(doc.body.text_content())` 比对：

```python
def tight(s):
    return re.sub(r'\s+', '', re.sub(r'[*`]', '', s))

out = tight(' '.join(flatten(blocks)))        # 你的解析产物
for el in doc.body.iter():                    # 原文所有叶子
    if el.tag in ('p','h2','h3','h4','li','td','th','pre','blockquote'):
        t = tight(el.text_content())
        if t and t not in out:
            print('MISSED', el.tag, t[:80])
```

要点：
- **必须先去空白再比对**，否则 `\u00a0` 与全角空格会造成大量假缺失；
- 允许白名单：`<h1>`（章名已进 `chapter_open`）、`<h3>This chapter covers`（渲染成「本章内容」）；
- 实测 2873 块 / 75 图，最后只剩 1 条白名单命中 —— 这时才算解析真的完整。

只跑 token 频次对比（`Counter(src.split()) - Counter(out.split())`）噪音太大：
代码块被拆成单词后，`if`/`return` 的差额会淹没真正的缺失（实测 ch07 报 912 个"缺"，
其中真正缺的只有 0 个）。

### Z5. 槽位名写错不会报错，只会重复内容 ★

锚点槽位格式里，`speaker` 是合法槽位名。于是这段**语法完全正确**：

```
### 94 [dialog:prompt]
speaker 提示词 根据下面的 Gherkin 特性，生成：(a) Kotlin 的 Cucumber 步骤定义；…
```

它把整段提示词正文塞进了说话人标签，结果：
① 标签栏出现一大段正文；② 真正的正文块（`94.0`）缺失。
**覆盖率闸门不报错** —— 槽位名合法、正文非空、没有多余槽位。

发现方式只有两种，都要做：
1. **反向检查「过长的标签」**：`speaker` / `label` / `title` 长度 > 40 就有嫌疑
   （正常是 `提示词`、`模型响应（CLINE）`、`Cursor`）。实测 5 处，最长 266 字。
2. **块内结构检查**：`dialog` 的 `speaker` 应当与 `parts[0]` 的文本不重叠。

同理，`text`/`caption` 混用也很危险：把图注写成 `text` 会进正文段落，
闸门同样不报错。

### Z6. OCR 会把一个词拆成几块，逐块翻译会叠字 ★

`Word-of-the-day` 在图上是一个词，OCR 却给出三段：
`Word-of-the-` / `day` / `-`（坐标相邻、字高一致）。逐块填译文的后果：

```
原图：  Word-of-the-day  →  译文叠加：  一词 每日
```

字都写在同一行，互相压盖；报告 `MISSING 0 / OVERFLOW 0`，全绿。

两道防线：
1. **先按行合并再翻译**（`tools/fig_lines.py`）：垂直重叠 > 70%、水平间隙 < 1.6 倍字高、
   字高相近（> 55% 彼此），合并成一个区域。**只做行内合并，不做跨行合并** ——
   跨行合并会把不同卡片连成一整块（实测 35 块并成 2 块，结构信息全丢）。
2. **同一方框内的多行要合并成一个区域，用 `\n` 分行**（`tools/draw_figs.py` 的
   `fit_multi`）。原图一个方框里 4 行字被 OCR 成 4 个块，若各自居中换行，
   4 段中文会叠在一起（实测 ch04_f09 的「步骤 1」框全糊）。

### Z7. 原图已有编号时，译文不要再带序号 ★

图里每个卡片左上角有圆形徽标 `①②③④⑤`（OCR 常识别成 `1.`、`2.`），
译文若写 `1. token 级`，图上就成了 `① 1. token 级`。
同理流程图的圆框编号（`1. 首轮评审`）。

规则：**原图有独立序号图元时，译文只写标签文字**。
判据：OCR 结果里有孤立的 `\d+\.?` 块（宽度 < 30px），且它紧邻主标签左侧。

### Z8. 把统计图当截图保留，会让中文版缺一半图 ★★★

本次最大的分流错误。第一版把 49 张全归为 `shot`（「界面截图」），
其中包括 **12 张 matplotlib 统计图**。它们的标题、轴名、图例都可原位汉化。

**但自动判据两次都失败，别指望脚本能判对：**

| 判据 | 结果 | 结论 |
|---|---|---|
| 深色占比 > 0.45 → shot | 64/75 判成 diagram | 网页截图底色是白的，判不出 |
| 顶部白带 > 0.75 且近白 > 0.55 → shot | 70/75 判成 shot | 示意图顶部也常是白底 |
| 文字块 > 60 → shot | 11 张，其中 3 张是示意图 | 密集示意图被误判 |

根因：**示意图、统计图、网页截图在像素层面高度相似**（白底 + 深色文字 +
若干方块），差别在语义而不在统计量。硬凑判据只会把错误从一头挪到另一头。

正确做法是**人工表 + 联系表**：
1. `fig_kind.py --init` 出草稿表 `work/fig_kind_manual.json`（全标 diagram）；
2. `fig_kind.py --sheet` 出联系表（24 张/版、标 key、按类型染色）；
3. 对着联系表把 `chart` / `shot` 改进人工表 —— **这是唯一真相**；
4. `fig_kind.py` 读人工表产出 `work/fig_kind.json`。

人工判据三问（看图时在心里过一遍）：
1. 有没有浏览器/IDE 的 chrome（标签栏、URL 栏、工具栏、按钮）？有 → 截图。
2. 有没有坐标轴 + 网格线 + 图例？有 → 统计图，**可以汉化**。
3. 底色是深色（>55% 像素 luminance < 70）？是 → 多为深色 IDE 截图。

实测覆盖：把 12 张统计图从 `shot` 改成 `diagram` 后，图内中文化从 26 张升到 34 张。
最终 75 张 = diagram 34 + shot 41，与 `figs_zh/` 实际产物逐张核对一致。

**但统计图不能套用示意图的擦除参数**：
- 轴刻度数字必须跳过（`^[\d\s.,%$^()eE×x/+-]+$` 不处理）；
- 竖排轴名要按「一列一字」重排（Z9）；
- 网格线必须进结构保护，否则擦字时把网格擦断。

### Z9. 统计图的竖排轴名：字号一超就压刻度 ★

`Average Price (INR)` 是旋转 90° 的窄条。字号取 `min(框宽*0.98, 条长/字数/1.06)`，
若不封顶会出现两种坏结果：
- 取到 20px → 压住 `250/200/150` 刻度数字；
- 取到 8px → 8 个字挤在条中间，上下留大片空白。

实测稳定值：**封顶 14–15px**，且把单位括注（`（印度卢比）`）纳入字数计算，
不要为了"字少好看"把单位删掉（删了只留 4 字，中间空、两头挤）。

另一个坑：**OCR 常整块漏检竖排轴名**（`px_bbox` 里根本没有它）。
所以 `chart_spec.json` 要支持 `extra`：手工给 `px_bbox` + 译文，走竖排分支。

横排标题则相反 —— **允许略超框宽**：`limit = max(bw+12, bw*1.6)`。
`Medicine Type` 被 OCR 框卡得只剩 144px，按框宽断行会变成
`药品类` / `型` 两行。

### Z10. 章名在四处各存一份，改一处必须全改 ★

章名散落在四个地方，实测有 5 章不一致：

| 位置 | 来源 |
|---|---|
| 文件名 `05_第5章_XXX.docx` | `docs.json` 的 `title` |
| 页眉 `氛围工程｜第 5 章 XXX` | `build_docx` 的 `ch_label` 参数（来自 `docs.json`） |
| 目录条目 | `build_front.py` 读 `docs.json` |
| 章首页大标题 | `trans.json` 的 `chapter_open.title`（译者写的） |

译者写的章内标题往往更贴原文，`docs.json` 里的是解析时随手填的。修法：
**以章内标题为唯一真相**，用脚本回填 `docs.json`，再重建全链：

```python
for d in docs:
    inner = next(b['title'] for b in trans[d['id']] if b['type']=='chapter_open')
    d['title'] = inner
```

验收：`docs.json` / 文件名 / 页眉 / 目录 / 章首页 五处逐章比对，必须 11/11 一致。

### Z11. 合并 PDF 时 `draw_rect` 盖不住旧页码，要用 redaction ★

合订 PDF 的页码必须在 PDF 层重写（各分册都从 1 开始）。第一次的做法是
`page.draw_rect(footer_rect, fill=(1,1,1), overlay=True)` 涂白再写新数字。

结果：`页码错位 401 页`，取文本得到 `'1\n2'` —— **旧数字还在**。
`draw_rect` 的 fill 只是新增一块白色图形，**不删除原有文字**，
文本层里两个数字都在；而且新写的数字若落点与旧数字重叠，两个数字会并排显示。

正确做法：`add_redact_annot(rect, fill=(1,1,1))` + `apply_redactions()`，
真正把旧文字从内容流里删掉，再 `insert_text` 写新页码。

配套注意：
- 遮罩带要覆盖整条页脚（`rect.y1-70 ~ rect.y1`），左右不留边 ——
  各分册页码的 y 会有 1–2px 偏移；
- 新页码的**基线**要落在遮罩带内且不与旧字形重叠（旧字形占 `y1-48 ~ y1-36`，
  新基线取 `y1-36` 往下会撞，取 `y1-52` 才安全）；
- 验收用**页脚 clip 区域取文本**判断，不要用「每页最后一行」（正文末行会误报）。

### Z12. 目标文件被预览器占用：写临时名 + `os.replace`，失败就换名 ★

`pymupdf.save()` 在目标被 PDF 阅读器打开时抛
`FzErrorSystem: cannot remove file ... Permission denied`（它内部是先删后写）。
`os.remove` 同样失败。

正确做法：
```python
tmp = out + '.tmp'
merge_pdf(paths, tmp, entries)
try:
    os.replace(tmp, out)
except PermissionError:
    os.replace(tmp, out.replace('.pdf', '_修订.pdf'))
    print('原文件被占用，已输出修订副本')
```
**不要**为了让 `os.replace` 成功去 `taskkill` 阅读器进程 —— 用户可能正在看。
交付时说明「旧文件被占用，新内容在 `_修订.pdf`」，关掉阅读器后改名即可。

### Z13. 目录页码的基准是「页脚号」还是「全书页号」，只能选一个 ★

`build_front.py` 里 `cur = 3`（封面 1 + 目录 2）→ 目录 11/11 全部偏大 2 页。
原因：目录里写的是**页脚号**（正文从 1 开始），而 `cur` 算的是**全书页号**。

两个约定必须一致，本项目选「页脚号」：
- 目录写 `cur = 1`（正文首页的页脚号是 1）；
- 书签写 `pg`（pymupdf 的 0-based 页序 + 1），但要与 `.get_toc()` 的页码口径对齐；
- 验收：`目录写的页 == 书签页 - 前置页数`，逐条比对（11/11）。

另一个坑：**封面若溢出到 2 页，后面全部偏移 1 页**。
封面必须严格 1 页（`blank(doc, 3)` 这类必须按 A4 高度实测），
`ls out/pdf/00_封面.pdf` 的页数要等于 1。

### Z14. 下游路径常量分散在三个脚本里，改目录要一起改 ★

把 `out/pdf` 改成 `out/分册_pdf` 后，`merge_book.py` 找不到分册、`IndexError: list index out of range`；
改了 `merge_book.py` 又发现 `build_all.py` / `build_front.py` 还写旧路径。

规则：**输出目录只在一处定义**（`tools/common.py` 的 `OUT` / `PDF` / `DOCX`），
三个脚本都 import。改完用 `grep -n "PDF = " tools/*.py` 确认没有第二份字面量。

同类坑：`build_all.py` 曾把 docx 写到 `out/` 根、PDF 写到 `out/pdf/`，
而 `merge_book.py` 按「同名去 docx」找文件 → 一份都找不到，
`merge_docx([])` 直接抛 `IndexError`。合并前必须 `assert len(cand) >= 2` 并打印实际份数。

### Z15. 交付前自审要查的五类「脚本查不出」的问题

工程闸门（覆盖/页码/图片三数）全绿，仍然可能交付一个错的东西。
本次自审抓到 2 个真 bug + 1 个分流错误，全部是闸门不查的：

| 类别 | 检查方法 | 本次实测 |
|---|---|---|
| 章名一致性 | `docs.json` vs `trans.chapter_open.title` vs 页眉 vs 目录 | 5 章不一致（Z10） |
| 标签污染 | `speaker`/`label`/`title` 长度 > 40 | 5 处，最长 266 字（Z5） |
| 图分类 | 逐张看联系表（contact sheet） | 12 张统计图被误判为截图（Z8） |
| 图内叠加 | OCR 二次识别输出图 + 放大看 | 编号重复、拆词叠字（Z6/Z7） |
| 译文长度比 | 段落 `汉字数/原文字符数` 分布 | 中位 25.0、p90 28.2，无异常 |

长度比是个好用的粗筛：**中位数落在 22–28、p90 < 32** 说明既没漏译也没擅自扩写。
比值 < 5 的基本都是「含 URL 的句子」，比值 > 34 的要抽看是否加了原文没有的解释。

做一张 **contact sheet**（每 24 张图一格、标上 key）能一眼看完 75 张图的分类对不对，
比逐张点开快一个数量级：

```python
for si in range(0, len(keys), 24):
    sheet = Image.new('RGB', (COLS*TW, rows*CH), 'white')
    # 每格贴缩略图 + 红色 key 文字
```

---

## AA. 统一多级目录与章内导览合并（255 页 Manning MEAP 实战）

> 来源：《Rearchitecting LLMs》MEAP V07 中文版，9 章 / 255 页合订 /
> 167 条目录条目 / 345 个 `LINK_GOTO` 内跳链接 / 61 图。
> 这一组专治「目录看起来改好了，用户翻正文说没改」：
> 两次返工分别出在**需求分层没拆清**和**下游链没刷新**。
> 格式仍为症状 → 原因 → 做法；可与 Z11（redaction）、Z12（文件占用）、
> X11/X12（书签与下游一致性）、Y13（二级书签排序）、X13（内容级自查）对照看。
>
> **配套脚本已随技能附带**（配置驱动、跨平台）：`scripts/toc_common.py`、
> `toc_build.py`、`toc_links.py`、`toc_verify.py` + `assets/unified_toc.json.example`；
> 三步命令与调参见 `references/workflows.md`「9. 配套脚本用法」。
> 本组正文里出现的 `rebuild_toc.py` / `merge_final.py` / `add_toc_links.py` /
> `verify_links.py` / `check_toc_pages.py` 是当时的项目专版名，
> 通用版分别对应 `toc_build.py(rebuild)` / `toc_build.py(merge)` /
> `toc_links.py` / `toc_verify.py`（三方核对与模拟点击合并进同一脚本）。

### AA1. 「把本章小节目录合并到目录」要先拆成三层，别只做一层 ★★★

**症状**：交付后用户复核说「具体章节内容还是有本章小节目录，功能没实现」。
上一轮明明已经把 9 页插页合并进 p3–p6 的统一目录，全书检索「本章小节目录」0 命中。

**原因**：交付物里其实有三层不同的「目录样东西」，改一层不等于改全部：

| 层 | 长什么样 | 出处 | 位置 |
|---|---|---|---|
| ① 译者插页 | 标题就叫「本章小节目录」，每章 1 页 | **自己加的** | 各章首页之后，共 9 页 |
| ② 章内导览 | 标题「本章内容」+ 4~5 条要点 | 原书 *In this chapter* | 9 个章首页，共 9 处约 40 条 |
| ③ 简要目录 | welcome 页「简要目录」+ 三部分/附录清单 | 原书 brief contents | p7，19 段正文 |

上一轮只处理了 ①，用户看到的是 ②。两者措辞不同、来源不同，
只按自己记忆里的关键词检索就必然漏掉。

**做法**：接这类需求先做**三层盘点**，把证据摆给用户确认，再动手：

```python
# PDF 全文 + docx 完整 XML（含页眉、文本框、表格）一起扫
for kw in ('本章小节目录', '本章内容', 'In this chapter', '简要目录', '小节目录'):
    pdf_hits = [i + 1 for i in range(doc.page_count)
                if kw in doc[i].get_text()]
    z = zipfile.ZipFile(docx_path)
    xml = ''.join(z.read(n).decode('utf-8', 'ignore')
                  for n in z.namelist() if n.endswith('.xml'))
    print(kw, 'PDF', pdf_hits, 'DOCX', re.sub(r'<[^>]+>', '', xml).count(kw))
```

`Document.paragraphs` 扫不到页眉和文本框，必须用 zip 读全部 XML。
本次盘点结论：9 页插页（PDF 独有）、9 处「本章内容」（PDF + 10 个 docx 共 9 次）、
19 段 brief contents（front docx）。**先列编号清单 + 执行方案，等用户拍板**（AA2）。

### AA2. 删原书内容前要拍板 + 留可回退开关，别改源数据 ★

**症状**：用户要「章节里不再有」，最直接的做法是把 9 个 `chapter_open.toc`
从 `trans.json` 里删掉。但这会破坏「原文块序列 vs 译文块序列逐块一致」的质检基线
（本项目 1 978 块 / 97 943 字全对齐），且内容不可回溯。

**原因**：`chapter_open.toc` 是**源数据**，渲染层只是它的一个消费者。
删数据 = 改真相来源；改渲染 = 改呈现，两者代价差一个数量级。

**做法**：三方案摆给用户选（本次选 A）：

| 方案 | 代价 | 适用 |
|---|---|---|
| A. 渲染层跳过，源数据保留 | 最小，可一键恢复 | 用户要「正文别再列」，导航已在统一目录 |
| B. 只重新交付新文件 | 零改动 | 用户其实打开的是旧副本 |
| C. 导览条目也补进目录，正文保留 | 目录膨胀、措辞与小节标题不一致 | 想让目录更详细 |

A 的实现是一个显式开关，**源 JSON 一个字节都不动**：

```python
# build_docx.py
# 章内导览已并入前置统一多级目录（p3–p6，167 条），章节正文不再重复输出
KEEP_CHAPTER_TOC = os.environ.get('KEEP_CHAPTER_TOC', '0') == '1'
...
if KEEP_CHAPTER_TOC and blk.get('toc'):
    ...  # 原本的「本章内容」标题 + List Bullet 列表
```

交付说明写清口径：源数据仍保留 1 978 块（含 9 个导览），
`KEEP_CHAPTER_TOC=1` 可重建对照版，`audit_book.py` 因此继续全绿。
动手前把改动涉及的文件打包备份（脚本 / 9 个分册 docx / 合订 docx+PDF /
`front_meta.json` / `chapter_pages.json`）。

### AA3. 目录条目与页码必须同源：用分册 PDF 书签，不要用正文文本搜索 ★

**症状**：早期目录用「在合订 PDF 里搜标题文字」定位小节页，
换行标题、重复词会漏定位，全书 152 条里漏了 5 条
（如「3.3 连接结构、行为与优化」「9.15 小结」），目录条目数对不上书签。

**原因**：文字搜索面对的是**排版后的断行文本**，不是结构；同一个短语还可能在正文里多次出现。

**做法**：LibreOffice 把 docx 转 PDF 时会从标题样式（Heading 1/2/3）自动生成 outline，
每条带**精确局部页**。以它作唯一真相来源：

```python
with pymupdf.open(sub_pdf) as sub:
    ol = [(lvl, title.strip(), local_page)
          for lvl, title, local_page in sub.get_toc() if title.strip()]
```

本次收集 167 条 = 10 章级 + 56 小节(h2) + 101 子小节(h3)。
**合订书签定位也用同一份 outline**（`final_page = 章起始页 + local_page - 1`），
目录印刷页码、链接落点、书签三者就不会互相对不上。
旧文本搜索只可作为兜底，不能当主口径。

### AA4. 两遍构建消除「目录页数 P ↔ 全书页码」的循环依赖 ★

**症状**：目录里要印全书页码，而目录自己占 P 页；P 不定，全书页码就不定。
先算页码再排目录 → 排完发现页数变了 → 全表作废。

**原因**：这是循环依赖，但有个可拆的性质：**P 只由条目数和排版决定**，
页码数字右对齐、宽度不影响换行（1 位变 3 位也不会把标题挤换行）。

**做法**：两遍构建，第二遍复核收敛，不收敛就退出：

```
第 1 遍：用占位页码（全 0）生成前置页 docx → soffice 转 PDF → 量出 P
         → 版面 = 封面 1 + 版权 1 + 目录 P + welcome 2 + 各章分册页数
第 2 遍：按 P 算出每条最终页码 → 重建前置页 docx/PDF
         → 断言总页数 == 2 + P，且 P 与第 1 遍相同
```

本次 P=4，全书 255 页，ch01–ch09 起始页 9/19/39/65/92/127/163/188/223。
验收输出要打印「第 2 遍：页数收敛 ✓」，别把「生成成功」当通过。
（V5 / Y10 / U12 的「新增页后目录两轮回填」是同一思想，这里是把它形式化。）

### AA5. 目录行解析的 y 带下限要覆盖续页首行，否则静默漏行 ★

**症状**：统一目录 4 页，`front_meta.json` 167 条，挂链接脚本只解析出 159 行，
fail-closed 校验拦下并中止。

**原因**：p3 有「目录」大标题，首行 y≈128；**p4–p6 没有大标题，首行从 y≈70 起**
（页眉在 y≈39）。行识别写了 `100 < bb[1] < 780`，把续页顶部的 8 行静默吃掉：
p4 的「4 ▪」「4.1」、p5 的「6.3.1」「计算任务损失」「计算 logits 损失」、
p6 的「注册钩子并打分」「8.3.2」「8.4」。159 + 8 = 167 正好对上。

**做法**：y 带下限放到 55（页眉 y≈39 仍排除），上限保持避开页脚；
并且**用 fail-closed 行数校验兜底**，不要用「差不多」的容差：

```python
if t.isdigit() and bb[2] > 480 and 55 < bb[1] < 780:
    nums.append((int(t), bb))
elif bb[1] > 55 and bb[3] < 780 and bb[0] < 480:
    titles.append((txt, bb))
...
if len(rows) != len(entries):
    print('行数与 front_meta 不一致，中止（fail-closed）')
    return 1
```

排查手法值得记：打印每页「原始标题行数 / 页码行数 / 配对行数」，
三者相等但总和少 8，就说明是**筛选条件吃掉整行**，不是配对算法的问题；
再用「条目 key 多重集差集」定位到具体 8 条，比逐页肉眼翻快得多。

### AA6. 挂链接前做四方一致性校验，不一致就别产出文件 ★

**症状**：目录行链接挂错页，读者点「9.15 小结」跳到别处；
或者印刷页码改了但链接没跟着改，文件看着完好。

**做法**：挂链接前把四个来源对齐，任一不符立即中止：

| 来源 | 核对内容 |
|---|---|
| 解析出的目录行 | 行数 == `front_meta` 条目数 |
| 每行标题 | `norm(row_text) == display_key(entry)` |
| 每行右对齐页码 | `printed_page == entry.page` |
| 合订 PDF 书签 | `bookmark_page == entry.page`（章级按章号、小节按 norm 标题） |

匹配键要按层级分开：章级行印刷成「N ▪ 章名」，键是 `norm(num + title)`；
小节行标题自带编号，键就是 `norm(title)`，不能再拼 `num`。
每条挂**两个** `LINK_GOTO`（标题区 + 页码区），落点用目标页标题行的 y，
不要只给页首（读者会先撞见一大片页眉留白）：

```python
doc[pno - 1].insert_link({
    'kind': pymupdf.LINK_GOTO, 'from': rect,
    'page': target - 1,
    'to': pymupdf.Point(rect.x0, title_y if title_y is not None else 0),
})
```

本次 167 行 × 2 = 334 个行链接 + 11 个页眉「返回目录」= 345，
落点复核 167/167 正确。再配一个 `toc_verify.py` 逐个**模拟点击**：
矩形内必须有可见文字、目标页必须含对应章标题/小节编号、两区域落点一致。

### AA7. `pymupdf` 保存回原文件：临时文件 + `replace`，与「文件被占用」是两回事 ★

**症状**：`doc.save(dst, garbage=4, deflate=True)` 在 `dst == src` 时抛
`ValueError: save to original must be incremental`。

**原因**：pymupdf 对「保存到自己正在读的文件」只允许增量保存，
而增量保存不能用 `garbage=4`（重整对象流）。这和 Z12 的
「预览器独占导致 `os.replace` 失败」是**不同根因**，两个都要处理。

**做法**：

```python
if Path(dst).resolve() == src.resolve():
    tmp = Path(str(dst) + '.tmp')
    doc.save(tmp, garbage=4, deflate=True)
    doc.close()
    tmp.replace(dst)          # 失败再按 Z12 退到「_修订.pdf」
else:
    doc.save(dst, garbage=4, deflate=True)
    doc.close()
```

注意 `doc.close()` 必须在 `replace` 之前，否则 Windows 上文件仍被句柄占用。

### AA8. 合订页码用 redaction 真删，白矩形会吃掉正文末行 ★

**症状**：用户报告「PDF 第 13 页最后一行字只显示一半」。

**原因**：旧合订脚本用 `draw_rect(Rect(0, r.height - 70, ...))` 涂白盖子文档页码，
白底从 y=771.9 起，而正文末行 bbox 是 y=767.2–778.9，下半截正好被盖掉。
**全书 56 页受影响**（p7/p11/p13/p18/p29/p36…），不是单页问题。
画白矩形还只是在视觉层遮挡，文本层里旧页码仍在，复制文字会拿到两个页码（Z11）。

**做法**：精确定位子 PDF 自己的页脚页码块，`add_redact_annot` + `apply_redactions()`
连文本层一起删，再写全书连续页码：

```python
FOOTER_MIN_Y, FOOTER_MAX_Y = 786.0, 830.0   # 版心之外；正文最低到 ~779.5
for b in pg.get_text('blocks'):
    if not (b[4] or '').strip().isdigit():
        continue
    x0, y0, x1, y1 = b[:4]
    if y0 < FOOTER_MIN_Y or y1 > FOOTER_MAX_Y:
        continue
    if abs((x0 + x1) / 2 - pg.rect.width / 2) > 40:   # 必须水平居中
        continue
    pg.add_redact_annot(pymupdf.Rect(x0 - 2, y0 - 2, x1 + 2, y1 + 2),
                        fill=(1, 1, 1))
pg.apply_redactions()
```

本次 255 处页脚真删除，0 个正文块被覆盖。验收：逐页
`get_text(clip=页脚区)` 比对 1..255 连续，且末页最后一行目视完整。

### AA9. 装饰字符与中英混排别用 CJK 字体硬画，前置页走 docx → LibreOffice ★

**症状**：用 pymupdf 的 `china-ss` 直接绘制目录行时，拉丁字符被拆成全角宽度
（`1.1` 显示成 `1 . 1`、`LLM` 显示成 `L L M`），金色方块 `▪` 直接丢字。

**做法**：前置页（封面/版权/目录）**整页交给 python-docx 排版**
（制表位右对齐页码、章级金色 ▪ + 斜体章号、小节两级缩进），
再用 LibreOffice headless 转 PDF，字体与混排由 Office 引擎处理。
若确实必须在 PDF 层绘制，按字符类型分段：拉丁用 `helv`、中文用 `china-ss`，
各自正常，别指望单一 CJK 字体兼顾两者。

### AA10. 改任一分册后必须跑完整下游链，即使页数没变 ★

**症状**：删掉 9 处章内导览后，各章页数（10/20/26/27/35/36/25/35/33）
与 157 条书签**完全没变**，目录页码也就没变；
但合订 docx 是 docxcompose 从旧分册合并出来的，里面仍留着 9 个「本章内容」。

**原因**：「页码没变」只说明目录那一步可以复用，**不代表所有产物都最新**。
合订 docx、合订 PDF、链接注解是三份独立产物。

**做法**：把链固定成一条命令，不许挑着跑：

```
分册 docx → soffice 转分册 PDF → toc_build.py --step rebuild（两遍构建前置页）
→ toc_build.py --step merge（合订 docx + 合订 PDF + 两级书签）
→ toc_links.py（目录行 + 页眉返回目录）
→ toc_verify.py（三方核对 + 模拟点击）→ 项目自有的内容级 / 排版层 QA
```

本次每段都重跑，最终合订 PDF 与 docx 中「本章内容」检索均为 0。
与 X12 同一条纪律：判断「是否最新」看产物时间戳 + 内容断言，不看推算。

### AA11. 交付说明写「当前状态 + 旧文件自检提示」，历史措辞要标清 ★

**症状**：用户连续两轮说「功能没实现」。除 AA1 的分层误判外，
还有两个放大器：① 打开的是本地旧副本（261 页、含插页）；
② `DELIVERY.md` 里保留着「先在每章插 1 页本章小节目录」等历史描述，读起来像还没改。

**做法**：文档顶部放一个醒目状态块，给**可自己验证的判据**：

```
当前目录状态：全书 255 页；导航目录只有 p3–p6 一处（167 条，逐条可点击）；
章节正文不再有任何「本章小节目录」插页，也不再有「本章内容」章内导览。
自检：若看到 261 页或上述字样，说明打开的是旧文件，请重新取用。
```

历史问题表保留（有价值的沿革），但每条标注「已被 #N 取代」，
并在正文里明确写「已移除 / 0 命中」。本次新增 4c「章内导览合并验证」
小节列出 9 个分册、合订 docx、合订 PDF 三层的残留数字。

### AA12. 内容级自查要单独一层：四类逐项比对，别只看工程闸门 ★

**症状**：块序列、图片数、页码、书签全绿，用户要求「自己审核生成的内容」时
仍查出 76 条图内普通英文词漏译与 5 处图内段落溢出。

**做法**：工程体检之外再跑四类**内容**比对，各自出量化结论（与 X13 呼应）：

| 类别 | 判据 | 本次结果 |
|---|---|---|
| 代码块 | 逐字符 diff（不是只数行数） | 180 块 / 2 293 行 / 0 差异 |
| 表格 | 逐格 + 数值单元格核对 | 18 表 / 472 格 / 0 差异 |
| 数字 | 数值等价（含 268 million → 2.68 亿等单位换算） | 2 042 个全等价 |
| 图内文字 | 「该译未译」逐条判读 | 1 468 块，补译 76 条，MISSING/OVERFLOW 0 |

「整块不含中文」的命中大多是 `ZH SAME` 保留代码标识符等合理情况，
要分类判读再改，别一键全补。结论写进交付说明，不要只报「检查通过」。

### AA13. 图内说明文字要按整段合并，不能逐行塞进单行窄框 ★

**症状**：OCR 把一段说明切成多个单行块（ch03 图 3.3 的 5 段实为整段），
逐行填中文后每行都塞进那一行的窄框 → 溢出、重叠。

**做法**：① 连续 OCR 行合并成整段，译文写给首块 id；
② 首块带 `merge_bbox` 作为擦除区与排版区；
③ 首块带 `_merge_members`，`fig_raster` 的「下方邻块避让」要排除同组成员，
否则框下沿被裁到只剩一行高、字号暴涨。
本次合并 5 处段落，是 T1–T5 之外另一类「报告全绿但图很丑」的问题。

### AA14. 目录与章节的验收必须目视 + 关键词断言各一遍 ★

**症状**：脚本能证明页码对、链接落点对，证明不了「三级缩进好不好看」
「章首页删掉导览后有没有留下一块空洞」。

**做法**：两层都做，缺一不可：

- **断言层**：全书检索 `本章内容` / `本章小节目录` / `小节目录` 命中页数必须为 0；
  `front_meta` 条目数 == 目录解析行数 == 链接行数 / 2；
  目录三方（书签 / 配置 / 印刷）逐条一致；链接类型全部为 `LINK_GOTO`。
- **目视层**：把目录首页、目录续页、2~3 个章首页渲染成 PNG 放大看：
  章级金色 ▪ 与斜体章号、小节两级缩进、右对齐页码竖线、
  续页顶部无截行、章首页「章号 → 章名 → 英文原题 → 横线 → 正文」无空洞重叠。

本次 4 页目录 + p9/p65/p223 章首页目视通过，断言层
167/167 三方一致、345/345 链接、终检 20/20。
