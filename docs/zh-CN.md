# PaperDelta 中文指南

PaperDelta 用来检查实验结果变化影响了论文的哪些位置。当前是可本地运行的
0.1.0a2 alpha，已[通过本地开发者验收](release-acceptance.md)。
已完成一轮受控真实文本评测，部分动态 TeX 模板仍无法检查；
上线前按项目方安排采用机器本地测试和 Codex 开发者审查验收，真人反馈放到上线后。
Windows/Linux 已有本地实测，macOS 和远程 CI 尚未验证。实测结果见 [进度记录](progress.md)。

从 Windows 复制到 Mac，请看[Mac 拷贝、安装与测试步骤](../START_ON_MAC.md)。
已准备独立的 Apple Silicon/Intel CI 和本机验证脚本；真实 Mac 结果待执行后补充。

本地 Qwen3-8B 的一次固定参数试验产生 12 份无效提案，均被拒绝；
当前不承诺小模型一键自动映射。[原始结果和限制](local-model-evaluation.md)已保留。
我按文档完成的十处显式绑定、数据变更、八处修改及恢复流程通过验收。

另已完成 Calkit、scitexlintr 和 PaperDelta 的[本地命令行工作流对比](comparison.md)。
三者都能按各自配置处理数据变更；尚未测量独立用户的接入与审查耗时。

## 先运行演示

使用 Python 3.11 以上版本，在本仓库的虚拟环境中执行：

```text
python -m pip install -e .
paperdelta -C examples/research-paper check --report build/review
python tools/demo.py --out build/demo
```

打开 `build/demo/comparison-reversed/review/report.html`。演示只改 CSV，不改论文，
把平均准确率从 84.1% 改成 80.9%，应发现四处数字不一致，以及“优于 81.0% 基线”
的比较条件不再成立，还会指出已有来源记录的结果图需要重新生成。
另一条演示把结果改成 84.5%，验证四处数字补丁、跨文件写入、
写后检查和原始字节恢复。演示使用原创测试样例，不能代表真实论文上的准确率。

输出目录不会被覆盖，再运行时请换一个 `--out`。检查本身不需要模型密钥、GPU、
LaTeX 安装，也不执行论文仓库里的实验脚本。

## 接入自己的论文

1. 用 `init --paper paper/main.tex --data results/metrics.csv` 建立空配置。
2. 用 `scan --format json` 查看候选数字和数据列。
3. 人或现有 agent 编写映射提案，明确数据集、模型、划分、种子、字段、聚合和单位。
4. `propose --input 输入.json --out 提案.json` 会重新计算并验证提案。
5. `bind --proposal 提案.json` 只预览。加 `--interactive` 可在终端逐项查看证据：
   `y` 选中、`n` 或空行跳过、`e` 展开全部数据、`q` 取消；最后输入 `accept` 才保存。
   脚本也可用 `--accept occurrences:某个ID` 明确选择映射。
6. `check --report build/paperdelta` 生成终端、JSON、Markdown 和离线 HTML 报告。

[英文快速开始](quickstart.md) 给出了可完整照做的 CSV、LaTeX 和提案 JSON。
一个提案可含多个映射；接受其中一项时，只加入它及其必需依赖。接受映射不会改论文。

## 日常使用

在修改实验结果前，用 `snapshot create submitted-v1` 保存参照状态。之后运行
`check --baseline submitted-v1 --report build/paperdelta`，查看变化和所有相关位置。

`fix --report build/paperdelta/report.json --out changes.pdpatch.json` 生成数值修改提案。
`apply changes.pdpatch.json` 默认预览，只有 `--write` 才写入。旧文件、数据或配置
一旦改变，旧补丁会被拒绝。比较结论失效时，需要先审阅该结论，不能只批量修改数字。

写入时会输出事务 ID。`recover ID` 预览恢复，`recover ID --write` 恢复原始字节；
作者在事务之后修改过文件时，恢复会拒绝覆盖。保留 `.paperdelta/transactions` 中的
备份，直到确认无需撤回。

人工审阅记录、映射确认、数值修改和基线保存是四个不同动作。审阅需要声明当前
`state_fingerprint`，证据变化后会失效。审阅记录不能让错误检查变成通过。

## 理解结果

| 状态 | 含义 |
| --- | --- |
| 退出码 0 | 已确认且必需的检查与给定证据一致 |
| 退出码 1 | 存在已确认的不一致 |
| 退出码 2 | 配置、证据、必要解析不完整，或没有已确认绑定 |

报告会另外列出未绑定数字、未支持区域和未登记图引用。启用
`require_complete_coverage: true` 后，这些未覆盖内容也会阻止通过。零错误不等于
整篇论文正确；同一个数字也可能来自完全不同的实验，不能凭数值相等自动建立映射。

可选 MCP 提供五个只读工具，见 [agent 接入](agent-guide.md)。完整约束见
[规则说明](rules.md)，计划和完成证据见 [开发计划](development-plan.md) 与
[进度记录](progress.md)。
