# 显式统计与不确定性

[English](../statistics.md)

PaperDelta 1.0 可以针对同一组明确标识的观测，检查均值、标准差 SD、标准误 SE、样本数、
置信水平和区间，并在 LaTeX、Word、PDF 中绑定完整的“均值 ± 离散程度”或“[下端点, 上端点]”。
`±` 的含义由用户声明，程序不根据数值猜测。

从[五种子示例](../../examples/seed-statistics/README.zh-CN.md)开始。CSV、TSV、静态 Excel
和[可移植实验导出](experiment-evidence.md)共用计算。统计结果组要求表格中的观测标识；
原始 JSON 数组继续使用已有的标量、均值与计数流程。

## 声明观测

```yaml
schema_version: 6
paper: {entry: paper.tex}
sources:
  runs:
    path: results.tsv
    format: tsv
    primary_key: [model, seed]
    columns: {model: string, seed: integer, accuracy: decimal}
metrics:
  accuracy:
    source: runs
    field: accuracy
    where: {model: method}
    reduce: statistics
    unit: percent
    expected_count: 5
    seed_column: seed
    expected_seeds: [1, 2, 3, 4, 5]
    statistics:
      ddof: 1
      unit_of_analysis: 独立实验种子
      confidence_interval:
        method: student_t
        level: '0.95'
        assumption: independent_normal_observations
```

每行选中记录代表一条观测。应列出完整预期标识，不能只列删除失败结果后剩余的标识。
`seed_column` 也可指定其他观测标识列，但类型必须明确为字符串或整数。预期列表、实际
标识集合与样本数必须一致。重复种子、缺种子、缺测量值或非有限值会得到**未知**结果，
不会剔除记录、补零或静默对重复步骤求均值。

MLflow/W&B 历史中可能每个种子有多条记录。需要明确选择运行、指标、步骤或检查点，使
每条观测只对应一个结果，并区分数据集、划分和模型身份。数字相等不能证明身份相同。
离线导出仍受原平台存储精度限制。

## 声明统计约定

- `ddof: 1` 以 `n − 1` 为方差分母；`ddof: 0` 以 `n` 为分母。
- SD 为相应方差的平方根；SE 为声明的 SD 除以 `sqrt(n)`。
- `n` 是通过完整标识集合检查后的数值观测数。
- 双侧 Student-t 区间要求样本 SD（`ddof: 1`），自由度为 `n − 1`，置信水平必须明确。
  端点为 `mean ± t((1 + level)/2, n − 1) × SE`。

采样假设由作者声明。程序不能证明种子、受试者或测量相互独立或服从正态分布；给同一
受试者的重复测量分配不同标识，也不能使它们独立。无须支持的区间时，省略
`confidence_interval`。本版不实现预测区间、bootstrap、加权、配对、聚类分析或假设检验。
均值更大、区间不重叠均不会自动产生显著性结论。

公式依据 [NIST 均值置信区间](https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm)
与[离散程度定义](https://www.itl.nist.gov/div898/handbook/eda/section3/eda356.htm)。测试另用
[NIST t 分位数表](https://www.itl.nist.gov/div898/handbook/eda/section3/eda3672.htm)及自由度为 1
时独立的 Cauchy 闭式分位数进行核验。

## 绑定论文实际显示的内容

每个位置引用统计指标，并明确选择显示分量：

| 分量 | 示例 | 含义 |
| --- | --- | --- |
| `mean`、`sd`、`se` | `82.00`、`1.58`、`0.71` | 单个声明的统计量 |
| `n` | `5` | 必须选择 `display.kind: integer` |
| `confidence_level` | `95\%` | 95% 水平可用零位小数的百分比显示 |
| `ci_lower`、`ci_upper` | `80.04`、`83.96` | 独立定位的区间端点 |
| `mean_sd`、`mean_se` | `82.00 \pm 1.58` | 均值与明确选择的 SD 或 SE |
| `ci`、`mean_ci` | `[80.04, 83.96]` | 区间，可在前面带上均值 |

```yaml
occurrences:
  abstract_result:
    file: paper.tex
    anchor: {prefix: 'Accuracy: $', suffix: '$.'}
    metric: accuracy
    display:
      kind: decimal
      places: 2
      statistics: {component: mean_sd, show_n: true}
```

这要求完整表达式，例如 `82.00 \pm 1.58 (n = 5)`。`show_n: false` 不包含样本数后缀。
`spread_places` 可单独指定 SD/SE 或区间端点的小数位，否则使用普通 `places`。
`confidence_level` 始终按 fraction 数量处理，与实验指标自身单位无关。

识别 Unicode `±` 和 LaTeX `\pm`。支持“均值 ± 离散程度”“[下端点, 上端点]”或
“均值 [下端点, 上端点]”，可追加 `(n = 整数)`，允许空白变化。带百分号的复合显示
要求每个数值结果分量都带百分号。不推断共享尾部百分号、非对称 `+a/−b`、任意宏或
跨单元格复合表达式；可单独绑定受支持的分量，或明确调整声明。

## Studio、终端与智能体

在 Studio 中选择**显式统计**，填写完整种子列表、SD 约定与分析单位，按需声明区间
假设和水平。绑定时选择显示分量；复合表达式需选中**同一表达式内的全部数字**，含已显示
的 n，作为一个绑定暂存。每个原文位置独立；均值与区间可以复用同一统计指标但使用不同
锚点。切换语言会保留尚未完成的设置和选择。

批量设置与可复用实验模板提供相同控件。每次批量暂存中，一个指标选择一个完整复合
表达式；其他位置另行暂存。模板迁移统计约定，不携带论文位置。接受前核对完整表达式、
带类型的实验身份和统计结果。

`paperdelta guide`、`paperdelta batch guide`、JSON 绑定提案及可选 MCP 草稿/批量工具
共用相同契约，MCP 保持只读。复合锚点失效时，在修复界面选择其**第一个数字**，再检查
提案中的完整表达式后接受。LaTeX 修改沿用预览、备份和事务机制；Word/PDF 保持只读。

## 数值与兼容性边界

原始数字文本不会先转换为二进制浮点。均值与方差矩采用精确有理数运算；平方根与除法
至少保留 80 位十进制有效数字，较大观测可提升至最多 260 位。新增统计路径支持最多
10,000 条观测，每条最多 100 位有效数字，指数与数量级在 ±200 内。已有标量限制不变。
置信水平使用 `0.5` 至 `0.999` 的精确字符串，最多六位小数。

Student-t 分位数使用独立的 [mpmath 运算上下文和正则化不完全 beta 函数](https://www.mpmath.org/doc/current/functions/gamma.html#betainc)，
通过有界区间搜索、二分法和残差检查计算。无理数与区间端点是数值近似值。报告记录精度、
算法、分位数引擎版本、方法、水平、自由度、n 和分析单位；精确解析证据不等于精确统计推断。

新字段使用配置/报告 schema 6。schema 1–5 及旧标量、CSV/JSON 身份仍可读取且保持不变。
接受统计提案时，经过通常的审阅与备份升级配置。已有指标语义不会自动改变；选择
`statistics` 是明确的新声明。派生运算与比较论断引用统计指标时使用其**均值**，不会
自动比较不确定性或检验显著性。
