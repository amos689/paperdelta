# 接入向导与位置修复

[English](../guided-bindings.md)

1.0 的统计绑定要求明确声明种子、n、SD 约定和区间方法；复合显示、批量模板与
只读智能体共用契约，详见[统计指南](statistics.md)。

安装可选 `docx` 扩展后，Word 稿件沿用相同审查流程。
参见 [Word 支持与只读边界](word.md)；下方 LaTeX 示例仍然有效。

当前发行版：[0.3.0](v0.3.md)，包含[安装包演示和新工作流](workflows.md)。下文明确标注旧版本的记录保留为历史。

v0.2 的 `guide` 命令在内存中构建提案，随后使用与 `bind --interactive` 相同的
明确确认流程，无需手写嵌套 JSON。请在终端运行；重定向输入会被拒绝。
语言参数放在子命令之前。

## 首次接入

在论文和结果所在目录执行：

```sh
paperdelta init --paper paper/main.tex --data results/metrics.csv
paperdelta --lang zh-CN doctor
paperdelta --lang zh-CN guide
```

`init` 只写入空配置和发现提示，不确认绑定。已有配置时直接运行 `guide`。
向导会依次询问：

1. 来源路径、标识符、CSV 身份列及每列的明确类型。`001` 等模型 ID 应保留为
   字符串；JSON 使用准确的 JSON Pointer。
2. 结果字段、精确筛选条件、来源单位、聚合方式和预期记录数。`unique` 检查
   唯一一条记录，其他聚合必须明确给出记录数。实验有种子时，请明确选择种子列
   和种子集合。CSV 筛选文本和字符串种子保留空格及前导零；种子列表中不要添加
   分隔用空格，除非空格本来就是身份的一部分。
3. 论文中的准确位置、绑定名、显示方式和实验身份理由。可一次选择十处或更多
   位置，名称会添加 `_1`、`_2` 等后缀。数值相同不会自动选中位置。
4. 是否继续添加另一组，然后逐项复核提案证据。对需要的绑定选择“是”，最后
   输入“确认”才保存，也可使用 `y` 和 `accept`。

来源单位和显示方式独立：来源比例 `fraction` 为 `0.841` 时，可以按百分比显示
成 `84.1\%`。可以复用已有指标，也可计算差值、比值、百分点差或相对百分比变化。

构造期间输入 `:q`、输入结束或中断都会取消且不保存映射。最终复核期间，空行
跳过当前绑定，最后确认时空行则取消保存。来源或配置变化后必须重新创建提案。
确认会保存配置备份，论文和结果原始字节保持不变。

锚点构造会避开相邻数值候选，避免批量数值修改后，锚点仍依赖其他位置的旧数值。
无法区分或缺少上下文的位置会被拒绝，并提示添加可区分的文字。不支持的动态
TeX 仍是未知状态。向导不推断科学身份，也不改写结论。

## 文件移动或句子改写后

移动文件后应更新论文的 `\input` 路径，保证当前入口仍可读取。条件允许时，在
编辑之前保存快照：

```sh
paperdelta snapshot create before-edit
```

编辑后检查失效位置并选择替换位置：

```sh
paperdelta repair scan --baseline before-edit
paperdelta --lang zh-CN repair guide --baseline before-edit
```

基线可选。提供基线时展示此前记录的原文；未提供时展示旧锚点定义，不虚构历史。
数值修复必须明确选择当前候选。结论修复必须明确选择可访问的文件以及仅出现
一次的完整句子。请自行核对新文字的含义，原有判定规则和实验范围保持固定。

修复只改变已有位置绑定或结论绑定的论文文件与锚点，不替换指标、单位、显示
规则或结论判定。来源声明、图表记录及论文入口移动仍须明确编辑配置。不会
自动选择同值候选。位置修复后仍可能存在数值或结论不一致；修复位置不等于
确认结果一致。

脚本可从 `repair scan` 复制 `candidate_id`，并明确提供绑定：

```sh
paperdelta repair propose --binding occurrences:abstract_accuracy --candidate CANDIDATE_ID --rationale "摘要已移动，对应同一实验" --out repair.json
paperdelta repair apply repair.json --format json
paperdelta repair apply repair.json --accept occurrences:abstract_accuracy --format json
```

结论修复将 `--candidate` 换成 `--file paper/results.tex --exact "当前句子。"`。
预览包含前后定义、当前上下文和重新计算的检查报告。可用 `--interactive` 替代
`--accept`。确认时检查输入哈希并获取写锁，返回配置备份路径。部分确认后配置
已变化，原提案剩余部分也随之失效，需要重新扫描和生成。恢复备份前应检查差异，
避免覆盖之后的工作。

## Agent 使用相同的分步构造器

MCP 提供十三个只读工具，保留原有五个，并新增六个与向导共用的构造步骤：

| 工具 | 需要明确的选择 |
| --- | --- |
| `start_binding_draft` | 读取当前来源样本及候选 ID |
| `add_draft_source` | 路径、格式、CSV 列类型及主键 |
| `add_draft_metric` | 来源、字段、单位、聚合、筛选、预期数量及种子 |
| `add_draft_derived` | 运算及两个已有指标 ID |
| `add_draft_locations` | 候选 ID、名称、显示方式及实验身份理由 |
| `finish_binding_draft` | 重新检查，返回待作者复核的提案 |

每步把返回的 `draft_json` 原样传入下一步。筛选值和种子以原始字符串传递，由列
类型决定解释方式。每一步都检查草稿身份及已观察输入的全部哈希。十进制筛选值
经过 JSON 往返仍保持精确。可用 `paperdelta schema binding-draft` 查看结构。

`scan_binding_repairs` 和 `propose_binding_repair` 提供只读修复发现及单个绑定的
修复提案。MCP 不提供确认、文件写入或审阅声明工具。检查返回的提案后再保存，
并通过普通 CLI 复核。提案有效只说明结构一致，不证明 Agent 选择了正确实验；
实验身份不明时仍应拒绝推断。

本地脚本化终端测试覆盖十处重复位置、中英文等价、歧义、精确类型身份、取消、
输入过期、修复选择和数值修改后的字节级恢复。这些属于机器验证，不是独立真人
使用或模型质量证据；完整状态见[实施记录](v0.2-plan.md)。
