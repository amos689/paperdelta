# 批量绑定与持续审查

[English](../workflows.md)

以下工作流适用于 PaperDelta 0.3.0。在论文项目目录运行命令，或在子命令前加
`-C /path/to/project`。子命令前加 `--lang zh-CN` 使用中文提示。检查不会执行实验或绘图代码。

## 直接生成完整离线示例

```sh
paperdelta --lang zh-CN demo --out paperdelta-demo --open
```

核心安装包内含原创 LaTeX/CSV 示例和预先生成的 PDF 图，无需克隆仓库、模型、TeX
或绘图依赖。若浏览器没有打开，手动打开 `paperdelta-demo/review/report.html`。
报告可切换中英文，`before/` 保留检查通过的基线。

默认 `changed` 场景只将数据从 84.1% 改为 80.9%，产生四处旧数字、一处失效比较和
图表依赖变化。其**实际检查退出码为 1**，符合预期；**演示命令创建成功退出 0**。
`demo --scenario baseline` 保留未变基线；`demo --scenario safe-update` 将结果改为
84.5%，生成 `changes.pdpatch.json` 和 `changes.diff` 供复核，不自动应用。数值更新
不会重新生成图表。每次运行必须使用新的 `--out` 目录。

## 批量接入结果表

```sh
paperdelta init --paper paper/main.tex --data results/metrics.csv
paperdelta --lang zh-CN batch guide
```

只声明一次 CSV 来源、列类型和记录身份，再选择分组身份列、结果字段、固定筛选、
单位、聚合、预期记录数及预期种子。这些选择可在表格中复用。预期数量和种子描述
实验原本应该包含的运行，不能根据文件中碰巧剩下多少行来推断。

每项指标显示来源证据及论文候选位置。建议依据行名、表头和实验身份，不以数字
相同证明映射。明确选择一个或多个位置，核对显示格式并填写理由；可修改、跳过
或取消。最终复核支持全部或部分选择，最后输入“确认”才写入接受的配置。英文
向导使用 `accept`，论文文件保持原样。

脚本调用时，在已声明 `benchmark` 来源的项目中（例如内置演示）保存 `request.json`：

```json
{
  "source": "benchmark",
  "fields": ["accuracy"],
  "group_by": ["model"],
  "where": {"dataset": "Data-A", "split": "test"},
  "unit": "fraction",
  "reduce": "mean",
  "expected_count": 3,
  "expected_seeds": ["1", "2", "3"],
  "display": {"kind": "percent", "places": 1}
}
```

```sh
paperdelta batch scan --request request.json --out catalog.json
paperdelta schema batch-selection
paperdelta batch propose --catalog catalog.json --selections selections.json --out proposal.json
paperdelta bind --proposal proposal.json --interactive
```

`batch scan` 返回指标的 `choice_id` 及排序后的位置 `candidate_id`。`selections.json`
是 JSON 数组，每项包含 `choice_id`、`candidate_ids`、`rationale` 和可选 `display`
覆盖。ID 必须来自当前目录，不自动接受候选。来源尚未写入配置时可用 `--draft`
提供草稿。完整契约见 `schema batch-request` 和 `schema batch-catalog`。

当前批量分组支持 CSV；JSON 来源及派生指标继续使用[现有向导和分步工具](guided-bindings.md)。
正文重复引用可单独选择显示格式；缺少实验身份或位置歧义仍需明确复核。

字面表格单元格可使用 `table` 锚点，以表头、行前缀及从零开始的结果列索引区分多个
数字，并在数值修改后保留定位。表头变化、重复行、多行或多列合并不会被猜测处理，
需明确修复或使用其他受支持的唯一锚点。这是限定范围的静态解析，不是任意 TeX 展开。

## 明确审查覆盖范围

```sh
paperdelta scope show
paperdelta scope set --file paper/results.tex --region table --require-complete
paperdelta scope set --file paper/results.tex --region table --require-complete --accept
```

不加 `--accept` 只预览。文件和区域共同限定完整性要求中的**未绑定数字候选**。
文件列表为空表示所有包含的文件，区域列表为空表示这些文件的全部内容。区域支持
`abstract` 和 `table`；不存在的文件及没有候选区域的选择会被拒绝。
`--allow-incomplete` 关闭完整性门槛，仍展示覆盖情况；`scope clear --accept` 清除范围限制。

所有已经确认的数字、结论和图表仍会检查，包括范围外的绑定。不支持的构造和
未登记图引用继续显示，并继续阻止 `require_complete_coverage` 下的成功退出。
范围选择不能把未知解析变成对渲染后论文区域的认证。

年份等非结果数字可从 `scan` 中获取候选 ID，然后记录理由：

```sh
paperdelta scope exclude --candidate CANDIDATE_ID --name publication_year --reason "年份，不是实验结果"
paperdelta scope exclude --candidate CANDIDATE_ID --name publication_year --reason "年份，不是实验结果" --accept
paperdelta scope remove-exclusion --name publication_year --accept
```

排除记录保存位置、理由及附近文本身份。数字、附近上下文或定位变化后，记录过期，
需要重新复核。已有数字绑定和结论不能被排除。报告分别列出已检查、未绑定、范围外
和排除项；失败的科学检查不会消失。范围修改在 `.paperdelta/config-backups/` 保存
旧配置，并在 CI 配置差异中显示。

## 编辑时持续更新报告

```sh
paperdelta snapshot create submitted-v1
paperdelta --lang zh-CN watch --baseline submitted-v1 --report build/paperdelta --open
```

监听默认每秒检查内容哈希，合并 0.5 秒内的连续保存，然后完整重查。论文、已配置
数据、图表、来源记录、审阅记录、基线和配置变化均触发检查；还能发现新增 `.tex`
包含文件，跳过环境及生成目录。可用 `--interval` 和 `--debounce` 调整时间，不使用
结果缓存。

发现变化后，报告立即标为**等待重查**，退出码为 2，直到新检查完成。旧发现仍可
阅读，但不表示当前通过；检查中再次变化会继续重查。监听期间 HTML 每三秒刷新，
浏览器允许会话存储时保留语言、筛选、展开证据及滚动位置。

处理清单分别指向证据问题、失效位置、过期排除、待复核结论、数值修改和图表更新。
失效或未知结论继续阻止关联数字的自动修改。监听不会应用补丁或运行脚本。
`Ctrl+C` 停止监听并写入静态最终报告；若仍有未核验变化，退出码保持 2。强制终止
进程无法更新页面状态，因此使用报告前仍需留意生成时间并在必要时重新检查。

`--once` 只检查一次，`--max-checks N` 限定次数；`--format json` 每行输出一个事件，
完整报告仍在 `report.json`。

## 升级已有项目

旧的版本 1 配置仍可读取，既有身份保持稳定。明确使用表格锚点、审查范围或排除后，
接受的配置升级为版本 2 并保留备份，旧客户端不能读取新字段。新报告采用版本 2，
读取器仍接受版本 1。旧快照和审阅记录保留，过期或限定工具版本的提案及补丁需重新
生成。详见[报告契约](report-format.md)。

Agent 可通过四个会话工具使用同一候选机制，见 [Agent 指南](agent-guide.md)。
机器协议测试证明工具行为，不代表模型自动映射准确率。
