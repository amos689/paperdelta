# 静态源码与 PDF 导出示例

[English](README.md)

本原创示例采用 MIT 许可，声明了一份 Quarto 正文、一份 Markdown 附录和一份 PDF
导出，通过明确绑定共享准确率指标。不执行 Quarto，也不声称演示 PDF 由渲染器生成。

在已安装 `paperdelta[pdf]` 的源码仓库中运行：

```sh
paperdelta --lang zh-CN -C examples/static-manuscript check --report build/review
paperdelta --lang zh-CN -C examples/static-manuscript studio
```

初始状态有七处数字和一条比较结论通过，两项导出比较均一致。在可丢弃的副本中，
把 CSV 中 Ours 的三次结果改为 `0.807`、`0.809`、`0.811`，再把 `.qmd` 和 `.md`
源码的 `84.1` 替换为 `80.9`。重新检查：改正后的源码数字通过，与 81.0% 基线的
比较失败，未更新 PDF 的准确率导出过期。PaperDelta 对本示例中所有稿件均只读。

PDF 解析身份是明确声明的一部分。依赖升级改变身份时，应复核并修复绑定，不能把
旧坐标当成当前结果。当前生成器是 [build_markdown_demo.py](../../tools/build_markdown_demo.py)，
支持范围见[源码语法与限制](../../docs/zh-CN/markdown-quarto.md)。
