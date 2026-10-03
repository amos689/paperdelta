# 分步接口的本地模型试验

[English](../staged-model-evaluation.md)

2026-10-03，Qwen3-8B Q4_K_M 完成了一次单独记录的分步接口试验。十二个案例都在
无效的第一步操作处停止，没有有效提案、参考身份匹配或成功的必要拒答，也没有
确认任何绑定。该结果不能证明模型能够可靠使用分步接口。

作者编写的控制案例通过同一构造器完成了九个参考映射；三个脚本化拒答也是控制，
不属于模型测量。构造器的结构正确性与模型能否正确使用它是两回事。

| 测量 | 分步 v2 结果 |
| --- | ---: |
| 案例数 / 返回操作数 | 12 / 12 |
| 有效操作 / 核心验证通过的提案 | 0 / 0 |
| 身份约定匹配 | 可映射 9 例中的 0 例 |
| 符合预期的拒答 | 必须拒答 3 例中的 0 例 |
| 重试 / 响应修复 / 已确认绑定 | 0 / 0 / 0 |
| 独立参与者 | 0 |
| 真人准确率 / 确认耗时 | 未测量 |

[协议](../evidence/local-model-staged-v2/protocol.json)锁定源码、原 v1 案例字节、
初始提示和模型及运行时来源。每个请求都在推理之前保存；原始响应、步骤错误和
耗时保存在[运行目录](../evidence/local-model-staged-v2/)中。
[评分](../evidence/local-model-staged-v2/score.json)与
[控制结果](../evidence/local-model-staged-v2/controls.json)分别记录；运行结束后，
本次拥有的回环服务已[停止](../evidence/local-model-staged-v2/server-lifecycle.json)。

每个独立案例提供原始项目文件、任务要求、只读扫描及扁平步骤 schema。草稿由
评测程序保存在内存中，模型不能访问文件系统或 shell。它可选择 source、metric、
derived、locations、finish 或 abstain，最多八步；出现无效步骤即停止，不重试。
提示中没有参考答案、其他案例、快速开始示例或评分反馈。开发者编写并知道此套
案例的答案，因此它不是盲评。

采样设置为 temperature 0.7、top-p 0.8、top-k 20、min-p 0、presence penalty 1.5、
repeat penalty 1、seed 20261003，关闭思考。单步输出上限 2048 token，上下文
16384 token。只约束 JSON 语法，不约束答案 schema。使用与
[单次请求试验](local-model-evaluation.md)相同的固定模型和运行时文件，并重新核对哈希。

评分同时报告严格参考约定匹配，以及只忽略 `expected_count` 的身份比较：构造器
给聚合增加了明确数量检查，而部分旧参考没有该字段。实验范围、来源身份、种子、
单位、聚合、派生、显示和目标位置仍须严格匹配。这两种指标都不是真人精度或模型
的一般准确率。实现、接口及可能的请求次数与 v1 不同，因此不能作为接口质量的
受控因果对比。

首轮暴露了值得独立改善的接口问题：部分枚举参数在步骤 schema 中只有宽泛的
字符串类型，返回结果也没有明确列出当前可执行步骤。后续改进必须建立新运行，
并保留这次失败记录。

在与记录匹配的源码版本中复现：

```sh
python -m tools.evaluate_staged_mappings controls --directory build/staged-controls.json
python -m tools.evaluate_staged_mappings prepare --directory build/staged-run --model MODEL --provenance provenance.json
python -m tools.evaluate_staged_mappings run --directory build/staged-run --endpoint http://127.0.0.1:PORT/v1/chat/completions
python -m tools.evaluate_staged_mappings score --directory build/staged-run
```

请使用新的输出路径。程序验证锁定实现及案例；实现变化时须重新准备一次独立
运行。它不会修改 v1 锁文件或改写已保存模型答案。运行时和模型权重只是可选本地
临时依赖，不随 PaperDelta 分发。
