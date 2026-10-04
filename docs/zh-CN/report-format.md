# 报告交换约定，版本 6

[English](../report-format.md)

`paperdelta schema report` 输出**完整存储报告**的 JSON Schema。
[仓库中的 schema](../schemas/report.schema.json)记录当前约定，读取器支持版本 1–6。配置、提案、
快照、图来源、作者审阅和补丁有各自 schema；快照内嵌完整报告。

## Schema 6 的统计结果

显式统计指标增加 `statistics`，包含均值、SD、SE、n、ddof、分析单位、算法与运算
精度，以及可选的区间方法、水平、假设、自由度、端点和分位数引擎版本。数值保留为
十进制文本；无理数和区间计算明确为数值近似。声明、样本数与证据记录必须一致，
schema 1–5 不允许统计结果。旧定义省略新的可选字段以保留身份。复合原文位置可含
多个数字，但整体仍须精确定位、完整匹配，并独立接受。详见[统计指南](statistics.md)。

## Schema 5 的实验证据

TSV、XLSX 证据增加明确的 `format`。TSV 保留行号；XLSX 使用 `key`、`sheet`、
从 1 开始的 `row` 及 `cell`。标准化导出使用 `format: records`、严格的导入选择，
以及包含导出/工具身份、平台、来源、创建时间、精度、快照哈希的 `provenance`。
每条选中记录都能定位其原快照与原生指针，平台、选择、精度和定位哈希必须一致。
这与 schema 4 比较论文源稿/PDF 的 `exports` 是不同概念。

旧 CSV/JSON 证据省略这些新字段，保持序列化身份。schema 1–4 报告不能含新格式
证据。[导入](../schemas/evidence-import.schema.json)和
[可移植导出](../schemas/evidence-export.schema.json) schema 描述明确的输入约定，
[实验证据指南](experiment-evidence.md)说明精度、快照与缺失值。

报告包含 `report_schema_version`、`tool_version` 和 `ruleset_version`。未知字段和
未支持的主版本会被拒绝。每次核心检查都用报告模型校验输出，包括错误报告。
校验涵盖数值状态、证据记录、位置、结论、图表、诊断、变化、影响组和覆盖，
不接受任意嵌套对象代替这些约定。

## 数字和位置

指标 `value` 是有限十进制**文本**，不是浮点近似。来源记录与类型化筛选保留 JSON
类型。外部消费时应使用支持精确十进制的解析器；转成二进制浮点可能损失精度或
身份。`count` 可选择任意 JSON 数据：记录容器严格，但其中 `value` 保留原始数据。

`location.start/end` 是从 0 开始的 Unicode 字符偏移；`byte_start/end` 是原 UTF-8
文件中的字节偏移。结束位置均不包含在范围内，行列从 1 开始。原文及两种长度
必须匹配，保留 BOM 和 CRLF。位置本身不授权写入；数值补丁须重新推导，所有输入
哈希也必须仍匹配。

Word 位置使用 `format: docx`、`parser`、`context` 和 `locator`，记录 OOXML
部件、段落序号、样式、章节及可选的表、行、列。它们的 `start/end` 指向提取文本，
绝不是文件包字节。原生位置没有源码行号或字节地址，需要报告 schema 3。
上述 UTF-8 字节与行列说明仅适用于 LaTeX，详见 [Word 位置约定](word.md)。

## 分开的状态维度

- 指标为 `ok` 或 `unknown`；数值位置、结论与图表为 `pass`、`mismatch` 或 `unknown`。
- 变化描述相对明确基线的证据或定义身份；舍入后的值通过时，底层证据仍可能变化。
- 结论审阅为 `unreviewed`、`reviewed` 或 `superseded`，不会改变一致性结论。
- 图表来源比较声明的字节身份，不证明实际执行或图形代表的科学内容正确。

覆盖计数须与实际存储结论一致。候选数字、未绑定候选、未支持区域和未登记图表
分别统计。未支持区域目前按构造/文件报告，不是渲染页面面积百分比。候选包含
非结果数字，未绑定比例不能解释为结果召回率。

## Agent 视图的区别

MCP/Agent 响应增加 `agent_view`，将证据截断到十行，记录原始总数，并把 Decimal
编码成字符串以兼容宿主。这是**展示视图**，不是完整存储报告。不要将其
保存为基线或送进存储报告校验器；归档和独立验证请通过 CLI/API 获取完整 JSON。

Python 使用 `StoredReport` 验证后，应调用 `model_dump(by_alias=True)` 保留传输字段
`coverage.pass`。核心原始结果已使用这些字段名。哈希标识内容，不是签名。

存储版 JSON 保留规范英文消息和稳定机器代码。CLI 文本、Markdown、HTML 和 MCP
解释属于本地化展示层，论文与数据原文不翻译。离线 HTML 在同一文件内切换语言，
保留筛选和展开状态，详见[语言兼容说明](languages.md)。

破坏性修改需要新 schema 版本及迁移文档。0.3.0 的新报告使用版本 2，新增 `actions`、可选 `watch`，以及
`coverage.review_scope`、`outside_scope_numbers` 和 `exclusions`。版本 1 仍可读取，
新字段使用默认值。等待重查时退出码为 2，即使保留的旧发现全部通过。消费者应
检查顶层退出码及监听状态，不能从通过计数推断结果是否新鲜。

配置版本 2 增加范围、排除及表格单元格锚点。旧配置保留语义和基线身份；明确接受
新特性后才升级并备份。详见[工作流迁移](workflows.md)。

## Schema 4 的 PDF 与导出比较

PDF 位置使用 `format: pdf`、`parser`、原文 `context` 与 `locator`。定位包含
从 1 开始的 `page`、十进制 `bbox`/`page_box`、块身份与文本偏移，以及可选
区域/表格/行/列。边界框以页面左上角为原点，单位为 PDF 点，形式为
`[x0, top, x1, bottom]`。start/end 指向抽取模型，不是 PDF 字节。

可选 `exports` 条目记录源稿/PDF 路径、指标、两侧绑定列表，以及 `aligned`、
`stale`、`source_outdated` 或 `unknown` 状态，只比较明确绑定的指标，不保证
全文相同。操作建议增加 `reexport_pdf`。有资源限制的原页 PNG 仅嵌入 HTML
展示，不写入存储报告或快照。详见 [PDF 语义](pdf.md)。

配置 schema 3 引入 Word 原生位置；schema 4 增加 PDF 区域、解析身份以及
`paper.companions` 和可选 `export_of`。使用旧 CSV/JSON 证据时，LaTeX 报告使用
schema 2，Word 使用 3，含 PDF 的使用 4；新证据格式要求 schema 5。读取器兼容版本 1–6。
