# 有歧义的手写表格

[English](README.md)

这是预期拒绝的样例。声明的锚点匹配两个表格单元格，数值相同不足以确定对应模型。
在仓库根目录运行：

```sh
paperdelta --lang zh-CN -C examples/ambiguous-table check --report build/review
```

预期退出 **2**，位置状态为 **unknown**，并给出锚点歧义诊断，不生成补丁。
数据本身可读取，问题是映射缺少足够的上下文。

在样例副本中，作者可明确选择前缀 `Ours & ` 来解决映射，选择依据必须是实验身份，
不能是当前两个相同的值。PaperDelta 不会自动选择第一个匹配数字。
