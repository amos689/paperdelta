# 离线演示

[English](../demo.md)

观看 v0.2 的[简体中文录像](../assets/v0.2/demo.zh-CN.webm)或
[英文录像](../assets/v0.2/demo.en.webm)。每份录像的界面和字幕使用对应语言；报告
本身则在同一个离线文件内切换。[记录](../evidence/v0.2-media.json)标识视频、报告
源码和浏览器；较早的 [a2 录像](../assets/paperdelta-demo.webm)作为历史材料保留。

这是原创合成样例生成的实际报告，加上演示字幕，不测量真实论文准确率、模型质量
或真人可用性。

1. 实验更新前，七项声明检查与证据一致：Ours 84.1%，基线 81.0%。
2. 只改 CSV，使 Ours 降到 80.9%；四处数字、一项比较和一张已记录来源的图需复核，
   所有 LaTeX 文件保持不变。
3. 展开摘要发现，查看选中的测试行及均值。
4. 查看失效比较：80.9% 已不大于 81.0%，作者处理结论前关联数值补丁被阻止。
5. 查看图表输入身份变化。绘图必须明确执行；哈希不证明视觉内容正确。
6. 独立的 84.1% → 84.5% 场景在三文件应用四处受保护替换，重查通过并恢复原字节。

`python tools/demo.py --out build/fresh-demo` 可重建报告。可选开发录像工具需要
Node、Playwright、浏览器及其 FFmpeg 辅助程序；核心检查不依赖这些组件：

```sh
node tools/record_demo.cjs build/fresh-demo build/recording-en en
node tools/record_demo.cjs build/fresh-demo build/recording-zh zh-CN
```

使用新目录。`PAPERDELTA_PLAYWRIGHT`、`PAPERDELTA_BROWSER_EXECUTABLE` 和
`PLAYWRIGHT_BROWSERS_PATH` 可指定已有本地开发组件。录像工具不安装软件、不改论文。
