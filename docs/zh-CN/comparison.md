# 本地工作流对比

[English](../comparison.md)

这是开发者准备的命令行对比，环境为 Windows、Python 3.12.14、Calkit 0.47.12、
scitexlintr 0.2.1、PaperDelta 0.1.0a1。
[命令与输出](../evidence/reference-workflows.json)保留版本、退出码、耗时和文件哈希。

同一份原创四文件论文与 CSV，初始 Ours 为 84.1%、Baseline 为 81.0%。五个数值
位置覆盖摘要、表格、差值和附录，一句话声明 Ours 优于 Baseline。只修改 Ours 的
三个 test 行，使均值降至 80.9%；基线、train 行和论文不变。本对比没有图，图表
由独立的 PaperDelta 演示验证。

## 本次实现所需配置

| 工具 | 明确配置 | 初始论文的修改 |
| --- | --- | --- |
| PaperDelta | YAML 声明 CSV 类型、主键、种子集、两个均值、一个差值、五个数值位置和一个比较 | 未改任何已有 TeX 文件 |
| Calkit | 原创 CSV→JSON 导出器、五个有证据的问题、两个 DVC 阶段及条件式提升/比较回答 | 三个内容文件的六处结果替换为生成回答宏，主文件添加一条包含 |
| scitexlintr | 导出器执行同样筛选计算；manifest 和生成的数值/文本宏 | 三个内容文件的六处结果增加包装宏，主文件添加一条包含 |

这是可运行配置，不声称已最小化任何工具的接入成本。结果位置可是一整句话；数量
不衡量配置难度，长 YAML 未必比短脚本难。没有测量安装或真人映射耗时。

Calkit 原生计算已声明的条件答案；scitexlintr 的导出器计算条件并把文本放入
manifest，再由 linter 检查和修复 `SciText` 快照。这样文本流程也有完整可运行输入。
导出器属于对比辅助代码，不是已发布的 PaperDelta 适配器。

## 观察到的更新和审查行为

| 工具 | 只改 CSV 后 | 下一步与结果 |
| --- | --- | --- |
| PaperDelta | 退出 1，四个数值不一致和一个错误比较，论文未变 | `fix` 返回 2，四项修改均关联失效比较，不生成补丁或编辑源码 |
| Calkit | `check questions --json` 返回 1，上游证据过期 | `calkit run` 重跑导出与 question→LaTeX 阶段，生成 80.9%、-0.1 点及“不优于”，证据检查返回 0 |
| scitexlintr | 显式重建 manifest/宏后，lint 返回 1，五项数值和文本快照不一致 | `--write` 修改三个源文件、更新数值/文本，重查返回 0 |

三种流程都按配置运行。Calkit 通过流水线更新声明模板；scitexlintr 在生成宏旁保留
可审查快照；PaperDelta 保留现有手写源码，集中展示位置，并在关联比较为假时限制
数值写入。它们是不同工作流选择；本试验不能证明更高准确率或更短接入时间。

比较逆转时 PaperDelta 拒绝写入是预期行为；独立的正向变化演示覆盖应用、重查和
恢复。Calkit 证据检查通过表示所配置证据是当前的；scitexlintr 通过表示所选规则
通过；这些结果及 PaperDelta 的退出 0 都不证明科学正确性。

## 复现

先激活安装了 PaperDelta 的开发环境，再在检出根目录创建独立参考环境；后者不是
运行时依赖：

```sh
python -m venv .venv-references
# Windows：
.venv-references/Scripts/python -m pip install calkit-python==0.47.12 scitexlintr==0.2.1
# POSIX 改用 .venv-references/bin/python，安装相同包。
python tools/compare_workflows.py --out build/reference-workflows
```

程序保留完整临时项目、配置差异和命令记录；为 Calkit 创建专用本地 Git/DVC 仓库，
不提交、不改远程，只执行原创导出器。重跑须使用新输出路径。默认开发环境是仓库
的 `.venv`，参考环境可显式指定。

准备时首版程序错误期待生成 TeX 使用字面连字符，Calkit 实际正确输出 `{-}`。
第二次把 scitexlintr 的百分数值写为字符串，其渲染器要求数值比例。成功运行前
修正了这两处程序假设。早期输出保留于 `build/reference-workflows-first` 和
`build/reference-workflows-v2`，归档成功记录为 v3。

本运行没有编译参考论文、测阅读或确认时间、评估模型，也没有独立新用户。独立
首次使用对比按项目方安排放在上线后；macOS 和远程 CI 尚未验证。
[调研记录](research.md)链接了配置依据的原始文档和源码。
