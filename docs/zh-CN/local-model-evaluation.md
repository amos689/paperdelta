# 本地模型提案试验

[English](../local-model-evaluation.md)

本文保留 a2 时期的单次请求基线；v0.2 [分步试验](staged-model-evaluation.md)有独立
协议和结果。2026-10-03，本地 **Qwen3-8B Q4_K_M** 产生十二份 JSON 答案，提案全部
无效，没有接受任何绑定，三个必要拒答也都未完成。此配置**不建议用于无人确认的
自动映射**，失败证据保留。

| 测量 | 实测 |
| --- | ---: |
| 案例 / 独立请求 / 每例尝试 | 12 / 12 / 1 |
| 完整 JSON 答案外壳 | 12 |
| 核心校验通过的提案 | 0 |
| 无效提案 | 12 |
| 参考目标匹配 | 可映射 9 例中的 0 例 |
| 预期拒答 | 必须拒答 3 例中的 0 例 |
| 重试 / 答案修复 / 已确认绑定 | 0 / 0 / 0 |
| 独立参与者 | 0 |
| 真人准确率 / 确认耗时 | 未测量 |

[冻结评分](../evidence/local-model-v1/score/report.json)区分答案外壳与有效映射，
[提交](../evidence/local-model-v1/submission.json)未经修改就评分。十二份精确请求、
原始 HTTP 响应和逐例记录随[推理前协议](../evidence/local-model-v1/protocol.json)与
[执行记录](../evidence/local-model-v1/execution.json)保留。

## 模型看到的输入

每次只提供该任务的导出项目、要求、只读扫描、proposal-input schema、通用规则
和 Agent 指南。没有工具、文件系统、其他案例对话或评分反馈，排除参考答案和控制。
未提供完整快速开始样例，这是 schema 加文档的基线，不是最佳可实现 Agent 方案。
开发者编写并知道题集答案，因此不是独立盲评，也不代表论文总体。

首轮推理前保存并哈希所有请求。只约束普通 JSON 语法，不强制答案 schema 或参考
值。采样：temperature 0.7、top-p 0.8、top-k 20、min-p 0、presence penalty 1.5、
repeat penalty 1、seed 20261003、最大输出 4096 token，关闭思考。每次使用 16384
token 上下文、关闭提示缓存。所有响应正常停止，无输出上限截断。

官方 [Qwen 仓库](https://huggingface.co/Qwen/Qwen3-8B-GGUF/tree/7c41481f57cb95916b40956ab2f0b139b296d974)
固定提交 `7c41481f57cb95916b40956ab2f0b139b296d974`。GGUF 为 5,027,783,488 字节，
SHA256 为 `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`。
官方 [llama.cpp b11146](https://github.com/ggml-org/llama.cpp/releases/tag/b11146)
报告构建 11146、提交 `7fe450e19`。CUDA 13.4 归档和模型均匹配发布者摘要，使用
记录的 Windows RTX 5080 Laptop GPU。服务仅监听回环、离线加载，关闭 Web UI
及 MCP 代理，运行后[停止](../evidence/local-model-v1/server-lifecycle.json)。便携运行时
和权重是忽略的本地依赖，不属于 PaperDelta 包或运行要求。

## AI 开发者判断

这是 Codex 对已有建议的审查，不是真人观察，评分中的真人字段仍为 null。

| 案例 | 原建议的具体问题 |
| --- | --- |
| C01–C03 | 编造派生均值或三操作数差值，缺指标定义，把路径当来源 ID |
| C04 | 理由键未限定；比例列和百分数列相减不等于要求的均值 |
| C05 | 来源 ID 无效、谓词不完整，位置引用未定义指标 |
| C06 | 未声明来源、不支持的派生均值；单独列种子不能修复 |
| C07 | 使用点式字段而非 JSON Pointer，来源声明不存在 |
| C08 | 无效来源和错误单位，解释误称旧论文值一致 |
| C09 | 同值锚点歧义、不支持的派生均值、多加结论 |
| C10 | 缺身份信息仍选择数据集 |
| C11 | 必需种子缺失仍尝试求平均 |
| C12 | 没有显著性检验证据，却把准确率差当作 p 值 |

核心在确认或写论文前拒绝这些提案，但不证明能识别所有结构合理、科学含义错误
的映射。负控制已展示错误身份也可数值相同，仍需审查证据。

验收覆盖确定性检查器、显式绑定流程与 Agent 接口，不批准此小模型作自动映射器。
独立的 [AI 开发者流程](../evidence/developer-first-use/evidence.json)通过文档接口完成
十个显式绑定、八处数据变化发现、补丁及恢复。合成输入和映射均由同一开发者编写，
不是模型评分替代品或独立用户试验。

## 复现运行结构

使用匹配的历史 a2 源码发行包、另装回环模型服务，记录实际模型/运行时来源 JSON：

```sh
python tools/evaluate_mappings.py export --out build/fresh-model-inputs
python tools/run_local_mapping_eval.py prepare --inputs build/fresh-model-inputs --out build/fresh-model-run --model Qwen3-8B-Q4_K_M --provenance model-provenance.json
python tools/run_local_mapping_eval.py run --directory build/fresh-model-run --endpoint http://127.0.0.1:8080/v1/chat/completions
python tools/evaluate_mappings.py score --submission build/fresh-model-run/submission.json --out build/fresh-model-score
```

程序拒绝复用已经启动的运行，验证准备请求的哈希并保留失败。评分不调用模型。
新提示、思考模式、模型或校验反馈循环须新建记录，不替换本结果。GPU 采样不保证
生成字节完全相同。
