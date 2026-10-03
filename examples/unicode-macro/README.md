# 中文路径与显式宏参数

这个原创小例子使用中文文件名、中文上下文、JSON Pointer 和一个已声明的字面量宏参数。
从仓库根目录执行：

```sh
paperdelta -C examples/unicode-macro check --report build/review
```

预期退出码为 **0**，一个绑定通过。`/test/accuracy` 指向测试结果；训练结果 0.990
不参与检查，注释里的 99.0 也不是候选。宏 `score` 的一个参数被显式声明为可检查文本，
不意味着支持任意宏展开。

在副本中将测试结果改为 0.845，会报告 84.1 应改为 84.5，并能产生局部补丁。
`tools/validate_examples.py` 会在副本中加入 UTF-8 BOM 和 CRLF，再实际应用和恢复，
核对范围外字节保持一致。此例验证源文件检查，不声称已配置中文 PDF 字体或排版。
