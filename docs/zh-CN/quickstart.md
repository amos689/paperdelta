# 快速开始

[English](../quickstart.md)

静态 `.md` 和 `.qmd` 稿件共用同一证据与复核流程。核心演示、原始位置、经复核写入及
明确的源稿/PDF 比较见 [Markdown/Quarto 源码支持](markdown-quarto.md)。

**可视化接入：** 运行 `paperdelta --lang zh-CN studio`，在浏览器中声明证据和确认数字绑定；详见[工作台指南](studio.md)。以下保留完整 CLI / JSON 教程。

安装可选 `docx` 扩展后，Word 稿件沿用相同审查流程。
参见 [Word 支持与只读边界](word.md)；下方 LaTeX 示例仍然有效。

在 Python 3.11+ 环境安装：`python -m pip install paperdelta`。
运行 `paperdelta --lang zh-CN demo --out paperdelta-demo --open` 即可查看内置报告。
结果表可用[批量绑定、范围和监听](workflows.md)；源码开发仍支持 `python -m pip install -e .`。
以下命令在论文
项目根目录执行；若从其他目录运行，将 `-C /path/to/project` 放在子命令之前。
`--lang zh-CN` 同样放在子命令之前；可用 `settings --language zh-CN` 保存偏好。

## 完整的首次映射

假设 `paper/main.tex` 包含：

```tex
Our method achieves 84.1\% accuracy on Data-A.
```

`results/metrics.csv` 包含：

```csv
dataset,model,split,seed,accuracy
Data-A,Ours,test,1,0.839
Data-A,Ours,test,2,0.841
Data-A,Ours,test,3,0.843
```

创建发现配置，查看候选：

```sh
paperdelta init --paper paper/main.tex --data results/metrics.csv
paperdelta --lang zh-CN scan
```

交互式接入可运行 `paperdelta --lang zh-CN guide`，依次选择来源类型、身份、单位、
聚合和位置，再做最终审查，详见[向导教程](guided-bindings.md)。下面的 JSON 路径
为脚本及 Agent 提供相同的提案约定。

把以下内容保存为 `mapping-input.json`。人或现有 Agent 可以起草输入，检查器会从
真实数据重新计算值。理由保留示例原文，字段与材料不随界面语言翻译。

```json
{
  "additions": {
    "sources": {
      "benchmark": {
        "path": "results/metrics.csv", "format": "csv",
        "primary_key": ["dataset", "model", "split", "seed"],
        "columns": {
          "dataset": "string", "model": "string", "split": "string",
          "seed": "integer", "accuracy": "decimal"
        }
      }
    },
    "metrics": {
      "ours": {
        "source": "benchmark", "field": "accuracy",
        "where": {"dataset": "Data-A", "model": "Ours", "split": "test"},
        "reduce": "mean", "expected_seeds": [1, 2, 3], "unit": "fraction"
      }
    },
    "occurrences": {
      "abstract_accuracy": {
        "file": "paper/main.tex",
        "anchor": {"prefix": "Our method achieves ", "suffix": " accuracy on Data-A."},
        "metric": "ours", "display": {"kind": "percent", "places": 1}
      }
    }
  },
  "rationale": {
    "occurrences:abstract_accuracy": "The author identifies mean test accuracy for Ours on Data-A, seeds 1–3."
  }
}
```

```sh
paperdelta propose --input mapping-input.json --out mapping-proposal.json
paperdelta bind --proposal mapping-proposal.json
paperdelta bind --proposal mapping-proposal.json --accept occurrences:abstract_accuracy
paperdelta --lang zh-CN check --report build/paperdelta
```

预览包含所选记录、身份和重算结果。确认只添加选中的绑定及其依赖指标、来源，
旧配置备份至 `.paperdelta/config-backups/`，论文保持原样。提案不能覆盖已有 ID。

需要逐项审查时，将含 `--accept` 的命令换成：

```sh
paperdelta --lang zh-CN bind --proposal mapping-proposal.json --interactive
```

每张卡片展示理由、论文上下文、单位、计算、来源身份及最多五条选中记录。
输入 `e`/“证据”查看全部记录，`y`/“是”选择，`n`/“否”或空白跳过，`q`/“取消”
放弃整次选择。只有最后输入 `accept`/“确认”才保存。保存前再次核对输入；数据、
论文或配置变化时须重做提案。输入阶段取消或中断不保存；开始保存后的中断属于
错误，不能声称已取消。

提示写入终端错误流，标准输出为最终 JSON。交互模式要求输入和错误输出都连接
终端；脚本使用显式 `--accept` ID，不可混用。确认只记录映射，因此正确绑定的旧
数字仍可能检查失败；它不声明作者审阅、不修改论文。旧工具版本提案须重新生成。

如希望 Git 审查映射，请提交接受后的 `paperdelta.yaml`。直接修改此文件也视作
项目声明。提案边界不能阻止另有文件系统权限的 Agent 直接编辑它。

## 更新和修复

段落改写或移动后，使用 `paperdelta --lang zh-CN repair guide` 显式提议新位置。
它保留指标与结论定义，不代表科学内容已正确，详见[位置修复](guided-bindings.md)。

改结果前，用 `paperdelta snapshot create before-rerun` 保存快照。更新后运行：

```sh
paperdelta --lang zh-CN check --baseline before-rerun --report build/paperdelta
paperdelta fix --report build/paperdelta/report.json --out change-1.pdpatch.json
paperdelta apply change-1.pdpatch.json
paperdelta apply change-1.pdpatch.json --write
```

`apply` 默认给出统一 diff；它重新计算替换，拒绝过期输入、变化映射、不完整数值
范围及重叠。重复指定 `fix --only OCCURRENCE_ID` 可选择修复项。相关比较错误或
未解析时会阻止关联数值修复，直到作者处理结论及其配置。

已应用或中断的事务输出 ID。`paperdelta recover ID` 预览逆向恢复，加 `--write`
才恢复原文字节；若文件被后续编辑，恢复拒绝。请在不再需要前保留事务备份。

## 记录作者审阅

从 `paperdelta check --format json` 读取结论的 `state_fingerprint`。审阅过该精确
证据与表述的作者可用以下单行命令：

```sh
paperdelta review record --claim main_comparison --state sha256:ACTUAL_HASH --reviewer "Author name" --note "Checked the selected test runs" --attest-reviewed
```

声明不会使错误谓词通过，不改变基线、不接受映射。证据或表述变化使旧记录失效；
恢复旧状态可以匹配先前记录，历史仍保留。本地记录是声明，不是身份认证或执行证明。

## 字面宏与发现限制

对于 `\score{84.1}` 这样的字面宏，初始化时用 `--macro score=1`，或声明
`paper.macros: {score: 1}`。它只描述字面参数，不运行或展开宏。动态 TeX 和歧义
包含返回未知。锚点必须包围完整数字：仅用 `.` 作为后缀可能切入小数，因此会被拒绝。

原创多文件样例 `examples/research-paper` 包含三个种子、基线、百分点差、重复位置
及比较结论。

文字型 PDF 与 LaTeX/Word/PDF 共享指标流程见 [PDF 指南](pdf.md)。按需安装
`paperdelta[pdf]` 或 `paperdelta[docx,pdf,mcp]`。PDF 保留原页坐标，源稿与导出稿
关系需要明确声明。
