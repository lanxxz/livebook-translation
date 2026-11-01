# 踩坑清单（62 条）

> A–F 来自《Grokking Streaming Systems》中文版实战（11 章 / 336 页 / 346 图 / 1918 段）。
> G–J 来自《Financial AI in Practice》（Manning，14 章 + 附录 / 464 页 / 113 图）实战。
> 每条格式：**症状 → 原因 → 做法**。动手前扫一遍，能省掉大半返工。
>
> 两本书的差异本身也是一条经验：**Grokking 是手绘示意图 + 短标签；Manning 是两色排版 + 长正文 + 代码密集 + 多作者前后不一致**。前者难在图内文字排版，后者难在块结构归属与超长工作量。

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
