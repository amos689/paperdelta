# 中文路径与显式宏参数

[English](README.md)

这个原创样例使用中文文件名、中文上下文、JSON Pointer 及一个声明过的字面宏参数。
从仓库根目录运行：

```sh
paperdelta --lang zh-CN -C examples/unicode-macro check --report build/review
```

预期退出 **0**，一个绑定通过。`/test/accuracy` 指向测试结果；训练结果 0.990
不参与检查，注释中的 99.0 也不是候选。声明宏 `score` 的一个参数可检查，并不
意味着支持任意宏展开。

在副本中把测试结果改为 0.845，会报告 84.1 应改成 84.5，并可生成局部补丁。
`tools/validate_examples.py` 在副本中加入 UTF-8 BOM 和 CRLF，实际应用并恢复，
检查范围外字节不变。该样例验证源文件检查，不声称配置好了中文 PDF 字体或排版。
