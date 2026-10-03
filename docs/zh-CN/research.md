# PaperDelta 实现调研

[English](../research.md)

以下为调研当日的历史观察，不代表仓库或 issue 的当前状态。

调研日期：2026-10-02。目的：决定 A 方案如何实现、哪些现有成果值得采用，以及独立项目是否有足够明确的价值。

## 1. 调研后的定位修正

“从实验数据自动生成论文数字”和“检查论文数字是否过期”都已经有实现。Calkit 和 scitexlintr 是需要认真对比的直接相关项目；不能将这些基础能力宣传成 PaperDelta 的独创功能。

建议将 PaperDelta 定位为：**面向已有 LaTeX 论文的实验变更审查工具，让研究者和 AI agent 看清一次结果变化影响了哪些表述，并审核相应修改。**

产品假设是，用户愿意保留自己的实验脚本、目录、论文模板和写作习惯，只增加一份小型映射文件，就能获得跨结果、正文、表格和结论的变更报告。这里的差异来自接入成本和完整工作流程；它仍需在开发第一阶段通过实际案例验证。

最初调研查看了官方文档、仓库 README、相关源码、测试文件和公开 issue。后续开发已在隔离环境中实测 Calkit 与 scitexlintr 的相关 API，见 [reference-probe.json](../evidence/reference-probe.json)，并完成一个多文件论文的[本地命令行工作流对比](comparison.md)。其中包括 Calkit 的 DVC 管线、scitexlintr 的数值与文本快照修复、PaperDelta 的影响报告与关联补丁拒绝。这些结果不构成独立使用者的安装、接入或审查耗时测评。检索没有覆盖 GitHub 全部项目，也不能据此保证原创性或未来 star 数量。

## 2. 最值得参考的项目

| 项目与来源 | 已核验的能力 | 对 PaperDelta 的启发与采用方式 |
| --- | --- | --- |
| [Calkit](https://github.com/calkit/calkit/blob/423e54f03f812a3564168fe3a487b410ceaf62be/docs/questions.md) | 用结构化问题、回答和证据连接结果；支持条件式回答、证据变化检查、过期状态及 LaTeX 输出 | 最重要的竞品基线。参考证据类型和状态区分；首版独立读取 CSV/JSON，后续接入其证据和流水线元数据。不能把条件判断或证据失效本身作为独有能力 |
| [scitexlintr](https://github.com/arjunrajlaboratory/scilintr/blob/a03cfc2d8ccf034414a058ac62949bfaf014f720/tex/scitexlintr/README.md) | 通过 manifest、数值/文本包装宏检查漂移，支持图表登记、格式化数值和局部修复；也支持 HTML | 直接参考诊断规则、格式处理与修复边界。优先探索 manifest 互通，而非复制全部规则。重点验证 PaperDelta 对普通手写论文的接入优势 |
| [showyourwork](https://github.com/showyourwork/showyourwork/blob/51621e9d1ede93809a09143a9a0ca88ce1d76667/docs/latex.rst) | 将图与生成脚本连接，将外部变量文件纳入构建依赖 | 参考图表来源展示和依赖关系。PaperDelta 读取结果及生成记录，首版不承担整个论文构建系统 |
| [onlycodes-paper](https://github.com/hyang0129/onlycodes-paper/blob/54fb117f83577ece62b147e5a16b6f3ff383cda1/build_numbers.py) | CSV 中记录来源信息，以组合键生成 LaTeX 数值，并定位正文使用处 | 参考可读的结果键和“正文位置 → 数据单元”追踪。所检视树中未见 LICENSE，先仅参考设计，不直接复用代码 |
| [papercheck](https://github.com/cgarryZA/papercheck/tree/8e66cc957d829847ceea1d086a61b2fd9c403f1f) | 确定性检查与 agent 配合；保存问题、人工检查和补丁记录；检查原文片段是否存在 | 参考“候选问题、已接受问题、补丁”的区分。PaperDelta 在此基础上自行设计文件哈希前置条件和证据状态，不把原文存在等同于论证成立 |
| [reviewdog](https://github.com/reviewdog/reviewdog/blob/efaa3c82bf8cf4b21e4d0f82c511146693cc293f/proto/rdf/README.md) | 标准诊断数据包含位置、规则、严重性和修改建议，可接入代码审查 | 输出可对接的诊断格式。实验文件变动可能影响未修改的论文行，所以整体影响报告必须保留，不能只显示 Git diff 内的行 |
| [DVC](https://dvc.org/doc/user-guide/project-structure/dvcyaml-files) | 声明依赖、输出、参数和流水线状态，通过锁文件记录内容信息 | 参考内容指纹与依赖失效；后续只读导入 DVC 元数据。首版不要求用户安装 DVC |
| [Quarto](https://quarto.org/docs/computations/inline-code.html) | 将计算结果嵌入正文 | 可作为“从写作入口避免手抄数字”的对照方案。PaperDelta 服务已有论文的变更审查，暂不开发另一套文档渲染器 |

这些项目解决的层次不同。已有规范流水线的用户可能直接使用 Calkit 或 showyourwork 就足够；已经采用 scitexlintr 包装宏的用户也不一定需要迁移。PaperDelta 应通过互通和低成本接入赢得使用，而不是要求用户重建工作流。

## 3. 两个影响产品设计的具体发现

### 3.1 审核记录需要对应被审核的证据状态

[Calkit issue #1606](https://github.com/calkit/calkit/issues/1606) 在核验时为 open。它提出用回答及证据的内容指纹记录一次确认，避免依赖“最后编辑了哪次提交”来判断是否需要复核。这说明显式审核状态已有前人在推进。

PaperDelta 可参考这种问题定义，但需要自己明确：绑定确认、数值检查和人工审阅是三件不同的事。数字变化但显示结果仍因舍入而相同，也应在影响报告中留下记录；不能用重新生成基线来自动消除待审事项。

### 3.2 相同数字不能证明来自同一个实验

scitexlintr 的 README 明确说明，其按数值查找裸值的规则可能把无关但相同的数字识别为冲突。PaperDelta 的自动发现只能产生候选映射；正式绑定必须包含数据集、模型、划分、指标及必要的种子或运行标识。

另一个公开案例是 [LingTai issue #100](https://github.com/Lingtai-AI/lingtai/issues/100)：报告者描述了多轮论文润色后，文字内部保持一致，却把结果对应到错误实验设置的情况。该 issue 已关闭；它是一例定性需求信号，不能当作错误发生率或市场规模的证据。

因此，报告卡片除了“旧值和新值”，还应显示“从哪个实验、哪几行记录、按什么规则计算”。

## 4. 解析、定位与修复的参考选择

| 候选 | 核验内容 | 决策 |
| --- | --- | --- |
| [pylatexenc LatexWalker](https://pylatexenc.readthedocs.io/en/latest/latexwalker/) | 提供节点位置、上下文及宏参数定义；官方说明它不是完整 LaTeX 引擎 | 首选解析候选。先用真实论文试验支持范围，再固定版本；当前 latest 文档涉及 3.x 接口，不能把不同版本 API 混写 |
| [TexSoup](https://github.com/alvinwan/TexSoup) | 面向 LaTeX 的容错搜索和树操作 | 作为解析试验的对照。是否能稳定保留原始位置和格式，比作者自报的解析成功率更重要 |
| [tree-sitter-latex](https://github.com/latex-lsp/tree-sitter-latex) | 面向编辑器的 LaTeX 语法树，明确采用尽力解析且不覆盖全部 TeX 行为 | 留作后续编辑器扩展候选；首版先验证 Python 路线，减少安装负担 |

PaperDelta 应保留原始文件与位置映射，用语法节点限定可检查区域，按局部文本范围生成补丁。不能把整篇 LaTeX 当普通字符串做全局替换，也不能把语法树重新序列化后覆盖论文。

scitexlintr 的 [`_engine.py`](https://github.com/arjunrajlaboratory/scilintr/blob/a03cfc2d8ccf034414a058ac62949bfaf014f720/tex/scitexlintr/src/scitexlintr/_engine.py) 及 [`test_apply_fixes.py`](https://github.com/arjunrajlaboratory/scilintr/blob/a03cfc2d8ccf034414a058ac62949bfaf014f720/tex/scitexlintr/tests/test_apply_fixes.py) 值得参考：从后往前应用替换，跳过重叠范围，保护注释与转义。PaperDelta 还需在应用前重新核对文件、数据和映射指纹，避免旧报告改写新内容。

## 5. 其他值得跟踪的方向

- [ASTRA](https://github.com/LightconeResearch/astra-spec) 将分析输入、输出和决策建模为声明式规范，README 标明仍处于 early alpha。适合借鉴实体命名和未来导出思路，暂不作为核心依赖，以免跟随尚在变化的规范扩大范围。
- [sciwrite-lint](https://github.com/authentic-research-partners/sciwrite-lint) 覆盖引文、论文内部一致性和图文关系等检查，部分依赖本地模型。它提醒我们应把“检查自有实验结果”与“检索并判断外部论文证据”分开，后者暂不进入 PaperDelta 首版。
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) 可支持后续本地 stdio 接口。先保持核心函数和 CLI 稳定，agent 适配层只调用核心结果，不另建一套判断逻辑。

## 6. 具体复用策略

| 部分 | 做法 | 原因 |
| --- | --- | --- |
| LaTeX 节点解析 | 采用通过兼容性试验的现有库 | 没有必要从零实现完整解析器 |
| CSV/JSON、十进制运算、文件指纹 | 使用 Python 标准库，新增严格的数据契约 | 降低部署成本，并明确数值含义 |
| 数据选择、映射确认、影响报告 | 自行实现 | 这是本项目需要验证的主要使用价值 |
| 论文诊断规则 | 参考 scitexlintr 的问题分类和公开失败案例；优先互通 manifest | 避免重复维护大量通用 lint 规则 |
| 实验流水线 | 使用已有结果；后续只读适配 Calkit/DVC | 不承担任务调度、训练和环境重建 |
| 审查系统 | 核心输出 JSON、Markdown、离线 HTML；后续接 reviewdog | 一份事实模型服务不同界面 |
| Agent 接入 | 首版 CLI 使用指南及结构化契约，随后提供小型 MCP 适配层 | 不需要新建通用 agent 框架或要求额外模型账户 |

核心能力应独立于任一竞品运行。互通适配器失败时，应报告该适配器不可用，而不是让整个数值检查依赖失效。

## 7. 来源与版本记录

以下版本来自本次 GitHub API 读取。源码链接固定到对应提交，便于之后复核。未来采用依赖前仍需检查实际发布版本、对应目录的许可证及接口兼容性。

| 仓库 | 本次记录的提交 | 许可证核验 |
| --- | --- | --- |
| Calkit | `423e54f03f812a3564168fe3a487b410ceaf62be` | 已读取根目录 LICENSE，MIT |
| scilintr / scitexlintr | `a03cfc2d8ccf034414a058ac62949bfaf014f720` | 已读取 scitexlintr 子目录 LICENSE，MIT |
| showyourwork | `51621e9d1ede93809a09143a9a0ca88ce1d76667` | 已读取根目录 LICENSE，MIT |
| papercheck | `8e66cc957d829847ceea1d086a61b2fd9c403f1f` | 已读取根目录 LICENSE，MIT |
| reviewdog | `efaa3c82bf8cf4b21e4d0f82c511146693cc293f` | 已读取根目录 LICENSE，MIT |
| pylatexenc | `e4ddf2bad063a2bb79bd17abe2e5bce59375bf88` | 已读取 LICENSE.txt，MIT |
| onlycodes-paper | `54fb117f83577ece62b147e5a16b6f3ff383cda1` | 所检视仓库树中未发现许可证文件，暂不复制源码 |

补充阅读入口：

- Calkit 的 [`questions.py`](https://github.com/calkit/calkit/blob/423e54f03f812a3564168fe3a487b410ceaf62be/calkit/questions.py)、[来源记录文档](https://docs.calkit.org/provenance/)、[从写作开始的教程](https://docs.calkit.org/tutorials/writing-first/)。
- scitexlintr 的 [`snapshot_mismatch.py`](https://github.com/arjunrajlaboratory/scilintr/blob/a03cfc2d8ccf034414a058ac62949bfaf014f720/tex/scitexlintr/src/scitexlintr/_rules/snapshot_mismatch.py) 和 [`_finding.py`](https://github.com/arjunrajlaboratory/scilintr/blob/a03cfc2d8ccf034414a058ac62949bfaf014f720/tex/scitexlintr/src/scitexlintr/_finding.py)。
- papercheck 的 [`verify.py`](https://github.com/cgarryZA/papercheck/blob/8e66cc957d829847ceea1d086a61b2fd9c403f1f/src/papercheck/core/verify.py)、[`ledger.py`](https://github.com/cgarryZA/papercheck/blob/8e66cc957d829847ceea1d086a61b2fd9c403f1f/src/papercheck/core/ledger.py)、[`patch.schema.json`](https://github.com/cgarryZA/papercheck/blob/8e66cc957d829847ceea1d086a61b2fd9c403f1f/schemas/patch.schema.json)。

引用源码、移植片段或再分发测试材料时，记录来源和许可声明。当前规划未复制上述项目代码；论文、数据及代码的许可也不能相互替代。

## 8. 需要通过原型回答的问题

1. 普通 LaTeX 论文能否在 10 分钟左右为 10 个关键结果建立可靠映射，而不重写论文模板？
2. 一个 CSV 更新后，影响报告能否比逐文件 diff 更快帮助作者找出遗漏的摘要、表格和结论？
3. 与使用 Calkit、scitexlintr 完成同一任务相比，独立工具是否明显减少配置或复核工作？
4. AI 提出的映射能否以足够低的误配率节省工作，而不是制造额外的确认负担？

若第 3 项不能成立，优先把范围缩成已有生态的接入和报告层。应先证明使用价值，再决定投入多少独立产品工程。
