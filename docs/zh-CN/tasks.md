# 按当前任务开始

[English](../tasks.md)

PaperDelta 将明确声明的实验证据与论文位置对应起来。先选择你要完成的任务，再按需
阅读详细指南。工作台、报告和命令行诊断均支持英文及简体中文。

## 不配置自己的论文，先体验完整修订

```sh
python -m pip install --upgrade paperdelta
paperdelta --lang zh-CN demo --document markdown --scenario safe-update --out revision-demo
paperdelta --lang zh-CN -C revision-demo studio
```

使用新的目录。在“审查与修订”中打开 `table_accuracy`，查看证据，选择数值修改，
预览差异后再明确确认。随后通过“修改历史与恢复”恢复原始字节。这不会改变你现有
论文的内容。详见[逐步修订指南](v1.7.md)。

## 第一次接入现有论文

1. 在论文目录运行 `paperdelta --lang zh-CN studio`，选择论文入口及证据文件。
   Word/PDF 需要可选安装 `paperdelta[docx,pdf]`。
2. 查看数据行，明确列类型及唯一记录身份。`001` 等模型编号保持为文本。明确选择
   模型、数据集、划分、种子、单位和聚合方式；建议仍需复核。
3. 定义实验，在证据旁查看候选原文位置。选择真正对应的位置，明确保存已复核绑定。
4. 若以后会重复使用相同约定，保存已复核实验定义。下次使用“按此定义审查候选位置”
   即可减少重复表单输入，位置复核及最终确认仍然保留。

绑定数字是在声明它的含义，正确的绑定也可能揭示论文数值已过时。
[工作台](studio.md) · [证据格式](experiment-evidence.md) ·
[JSON 示例](quickstart.md) · [统计约定](statistics.md)。

## 检查下一轮实验的影响

改变实验前，在 Studio 中保存快照，或运行：

```sh
paperdelta snapshot create submitted-v1
```

按你原有的流程运行实验。Studio 观察文件保存，在新检查完成前标为等待重查。
选择快照，然后打开受影响任务，查看原文上下文、新旧结果和证据。

受支持的 LaTeX/Markdown/Quarto 数字可以选择修改并预览差异；比较结论错误或未知时，
应先修正并复核结论，不能仅替换数字。过期图形和导出稿需用你自己的程序重新生成，
再检查和复核声明的依赖。记录一条审阅说明本身不能让错误结论通过。
[修订与恢复](v1.7.md) · [Notebook/Quarto 生成记录](v1.6.md)。

## 将审查结果发给合作者

在 Studio 中打开“分享选定的审查文件”，选择要分享的报告和确切输入，预览归档内容，
再明确导出。HTML 可离线打开；包含必要输入时，可按说明重放检查。预览会说明缺少的
输入及因此受限的范围。接收者可以切换报告语言。详见[便携审查包](review-bundle.md)。

需要 Word 或 PDF 副本时，在修改工作台选择已绑定位置，预览原文中的准确位置，
再明确确认导出新批注副本。原稿不变。[Word 批注与 PDF 高亮](v1.8.md)。

## 投稿前复核

重新执行检查，可选与已提交的快照比较：

```sh
paperdelta --lang zh-CN check --baseline submitted-v1 --report build/submission-review
```

复核未处理的不一致、未知、未绑定/排除内容、过期图形及源稿/导出稿差异。修正后再次
检查，将最终报告和所选证据与项目共同保留。退出 0 表示声明范围内必需的已接受检查
通过，不是对整篇论文及其科学结论的认证。
[检查范围](rules.md) · [CI 与 PR 审查](ci.md)。

命令行使用 `paperdelta --lang en ...` 切换英文。Studio/报告中使用语言选择器；切换
会清除写入确认，同时保留工作选择。详见[语言设置](languages.md)。
