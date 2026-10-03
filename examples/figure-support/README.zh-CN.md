# 图表来源样例

[English](README.md)

原创合成图表使用 `research-paper/results/metrics.csv`。PDF、PNG 预览和伴随记录
由 `plot_accuracy.py` 通过 Matplotlib 生成，完整的比较反转演示会把它们复制到项目。

伴随文件是导入的输入、脚本和输出哈希声明，不是经过认证的执行记录。CSV 改变后，
检查器会标出该图，直到重新记录声明的依赖和输出。

在已创建的演示中明确重新生成：

```sh
python -m pip install 'matplotlib>=3.9,<4'
python build/demo/comparison-reversed/scripts/plot_accuracy.py --project build/demo/comparison-reversed
```

然后运行 `paperdelta -C build/demo/comparison-reversed check`，图表来源将重新匹配；
尚未处理的数字和失效比较仍然失败。检查器本身不调用绘图脚本。这里所有材料均为
原创，使用本仓库的 MIT 许可证。
