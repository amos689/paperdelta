# TSV、Excel 与可移植的离线导出

[English](README.md)

这些自有合成样例遵循仓库 MIT 许可，工作簿由 `tools/studio_evidence_fixture.py` 生成，
不是真实科研样本。文本模型编号 `001` 与 `1` 不同；一条已接受绑定读取 TSV，另一条
读取静态 XLSX 中的 `结果 Results!C3`。

安装 PaperDelta 后，在仓库根目录运行：

```sh
paperdelta --lang zh-CN -C examples/evidence-native check --report build/review
paperdelta --lang zh-CN -C examples/evidence-native studio
paperdelta --lang zh-CN -C examples/evidence-native evidence import import.json --out build/experiment.pdevidence.json
paperdelta --lang zh-CN -C examples/evidence-native evidence inspect build/experiment.pdevidence.json
```

两条绑定均通过。主结果保留 `0.80000000000000000000000000001` 的存储文本，显示为
`80.0%`。这些额外位数用于验证解析精度，不代表 Excel 重存数值单元格后能保留的
精度。再次导入请使用新路径，不会替换旧导出。可在 Studio 中将生成的导出添加为
新来源，查看快照与列声明；此操作不会替换已有绑定。

这里的全部命令只需核心包，无需网络。MLflow/W&B 请求、认证、精度边界和明确的
来源更新，详见[实验证据指南](../../docs/zh-CN/experiment-evidence.md)。
