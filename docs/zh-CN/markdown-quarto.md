# Markdown 与 Quarto 源码审查

[English](../markdown-quarto.md)

PaperDelta 1.2 支持 UTF-8 `.md` 和 `.qmd` 文件中的字面正文与规则竖线表格。
两种读取器都包含在核心包内，无需安装 Quarto、Pandoc、笔记本内核、模型或文档渲染程序。

```sh
python -m pip install paperdelta
paperdelta --lang zh-CN demo --document markdown --out markdown-demo --open
paperdelta --lang zh-CN demo --document quarto --out quarto-demo --open
```

每次需要新的输出目录。默认场景把实验证据从 84.1% 改为 80.9%，保留论文原稿，
展示两处旧数值和一条失效的比较结论。`--scenario baseline` 展示证据一致的状态；
`safe-update` 会改变证据，但不会为这两种格式生成源码补丁。

## 接入现有源码

```sh
paperdelta init --paper paper.qmd --data results.csv
paperdelta --lang zh-CN studio
```

也可以在未配置的项目中直接启动 Studio，选择 `.md` 或 `.qmd` 入口。声明证据
列类型、记录主键、筛选条件、单位和聚合方式，再选择对应的源码数字，审阅提案并
明确接受。两处数值相同不能证明它们属于同一项实验。

终端 `guide`、批量绑定、实验模板、快照、范围、监听、经复核的绑定修复和可选的
只读 MCP 共用同一模型。切换中英文保留选择和草稿。`82.00 ± 1.58 (n = 5)`、
`[80.04, 83.96]` 等完整字面表达式可以使用[显式统计流程](statistics.md)绑定。

## 支持的源码结构

| 源码 | 检查位置与身份 |
| --- | --- |
| 段落、标题、普通列表和引用块 | 原始源码区块及章节内的字面数字位置 |
| 包围完整数字的普通强调格式 | 保留格式与原始数字字节 |
| Markdown 链接及引用式链接 | 仅使用可见的字面标签，不把链接地址当作结果 |
| 带分隔行的规则竖线表格 | 明确的一行表头、字面行标签、列名和原始单元格位置 |
| 明确声明的附属 `.md` / `.qmd` 文件 | 独立稿件共享具名指标 |

表格至少需要两列，各行列数必须一致。行顺序变化不会暗中改变绑定对象：每次重新
解析已接受的表头和行身份。重复行或重复区块保持歧义。标题、表头、标签、上下文或
格式变化可能使锚点失效，此时用 `paperdelta repair` 或 Studio 复核新位置；仅修改
字面数值可以保留原绑定。

读取器采用 CommonMark 区块结构加竖线表格，并不实现完整的 Pandoc/Quarto 语言。
发现候选或绑定通过，只说明核对了字面源码，不保证最终渲染页面。更广泛的语言规则
见 [CommonMark 规范](https://spec.commonmark.org/0.31.2/)、
[Quarto Markdown 语法](https://quarto.org/docs/authoring/markdown-basics.html)及
[Quarto 执行规则](https://quarto.org/docs/computations/execution-options.html)。

## 原始位置与只读审查

Schema 8 的位置包含 `format: markdown` 或 `quarto`、原始字符和 UTF-8 字节区间、
从一开始的行列、解析器身份、章节及可选的表/行/单元格坐标。区间右端不包含在内。
BOM、CRLF 和 Unicode 原样保留；上下文按文本转义展示，不执行 HTML。源码哈希
参与过期预览拒绝、快照及文件监听。

本版 Markdown 和 Quarto **保持只读**。请在源码编辑器中修改原文件，再重新检查。
即使已提供原始字节位置，`fix` 也不能向这两种格式应用补丁；受保护的 LaTeX 补丁
流程继续独立可用。

## 保持未验证的内容

- 不计算 YAML 元数据、围栏代码、缩进或行内代码、行内执行、短代码、动态包含及围栏 div。
- 不把原始 HTML、图片及替代文本、引文、交叉引用和可见网址解释为论文数值证据。
- 公式、原始 TeX 区块、Pandoc 网格/简单表格、不规则竖线表格、依赖渲染的属性和
  不支持的行内语法保持未验证。
- 数字实体、转义和拼接不同数字片段的格式不会被伪造为连续源码区间。不安全的
  Unicode 控制字符使整个文件的读取失效；不确定的组合字符使相应区块失效。
- 单元格中的不支持语法可能使整个表格未验证；行内不支持结构可能使整个段落未验证。
  这类保守边界通过 `MARKDOWN_*` 诊断和覆盖率明确展示。
- 原始 HTML 标签可能影响解析区块之外的内容，例如隐藏容器和 CSS。因此，非注释
  HTML 会使该源码文件的全部数值读取保持未验证。

存在不支持内容时返回退出码 2，即使部分已接受绑定通过，也不会暗中算作完整覆盖。
因此，含 YAML 或可执行单元的普通 Quarto 文档可能同时有已验证字面结果和未完成的
总体检查。不执行、获取或跟随代码、过滤器、项目配置、远程资源及包含。其他静态文件
应声明为附属稿件，不能依赖自动遍历 include。

资源上限：每份源码 4 MiB、20,000 行、每行/行内区块 65,536 个字符、10,000 个
源码区块；每表最多 100 列和 10,000 个单元格。超限输入被拒绝或明确标为未验证。

## 明确声明 PDF 导出关系

安装 `paperdelta[pdf]` 以读取 PDF，再声明 PDF 及其实际源稿：

```sh
paperdelta manuscript add --file export.pdf --export-of paper.qmd
paperdelta manuscript add --file export.pdf --export-of paper.qmd --accept
```

第一条预览声明，第二条接受并保留备份。在两份文档中明确绑定各项待比较指标。
当源稿已按新证据改正、PDF 仍保留旧结果时，报告会标出导出过期。不渲染或重写 PDF；
请用自己的流程重新生成，再复核位置，必要时修复已变化的解析身份。

[原创源码/PDF 示例](../../examples/static-manuscript/README.zh-CN.md)包含 Quarto 正文、
Markdown 附录和 PDF。比较只覆盖明确声明的指标，不覆盖渲染设置、全部正文、图片
或整份文档的一致性。

## 兼容性

新 Markdown/Quarto 配置和报告采用 schema 8；添加静态附属稿件会先预览升级，再
明确接受。既有 schema 1–7 项目保留原有身份并继续可用。兼容的 0.6–1.1 Studio
草稿可以经验证后恢复。参见[报告契约](report-format.md)、[发行说明](v1.2.md)和
[Agent 工作流](agent-guide.md)。
