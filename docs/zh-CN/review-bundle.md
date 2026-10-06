# 分享与重放选定的审查内容

[English](../review-bundle.md)

便携审查包包含选定报告，以及可选的、复现已接受检查所需的精确输入。
完整配置中的声明、审查范围和排除项保持原样。减少导出文件不会悄悄缩小检查范围。
哈希证明字节完整性，不证明作者身份或审批。

## 从 Studio 导出

1. 打开“分享选择的审查文件”，可填写已保存的比较快照名。
2. 选择 HTML、JSON、Markdown 或 SARIF 报告。原始输入默认均不选中。
3. 逐项选择输入，或明确点击“选择重放所需全部输入”。
4. 预览范围、结果、文件列表和内容。文本预览最多展示 4,096 个字符，实际导出完整文件；
   二进制输入展示大小和哈希。
5. 确认已复核选择后，下载 ZIP。

报告可能含原稿文字、证据数值、路径和原生页面预览。分享前请检查所选内容，工具不上传。
改变选择或切换语言会取消旧确认。输入字节改变后，必须刷新并重新复核预览才能导出。

## 使用命令行

在论文目录准备完整选择：

```sh
paperdelta --lang zh-CN bundle preview --all-inputs --baseline submitted-v1 --out review-plan.json
```

创建压缩包前先阅读 `review-plan.json`。无需历史比较时省略 `--baseline`。
选择部分输入时，用重复的 `--input 相对路径` 替代 `--all-inputs`；只导出报告则两者均省略。
通过 `--reports html json md sarif` 选择报告格式，默认 HTML 和 JSON。

```sh
paperdelta --lang zh-CN bundle create --plan review-plan.json --out paperdelta-review.zip
paperdelta --lang zh-CN bundle inspect paperdelta-review.zip
paperdelta --lang zh-CN bundle replay paperdelta-review.zip --out reproduced-review
```

创建操作拒绝覆盖已有压缩包。重放需要新输出目录、包内记录的相同 PaperDelta 版本，以及
原稿需要的可选读取器。重放含 Word/PDF 的 1.5.0 包时安装 `paperdelta[docx,pdf]==1.5.0`。
请把收到的压缩包放在所选本地工作目录内。

`inspect` 核对清单字节与预览，不验证科学结论是否真实。只有包含完整输入的选择可以重放。
重放会重新检查并比较报告内容和范围，保留失败或不完整状态：成功复现的不一致仍返回 1，
不完整或结果不同返回 2。不执行脚本、Notebook 单元格或文档宏。

输出 JSON 给出新 HTML 报告位置。原始输入、绑定标识、审查范围和排除项保持不变。
部分输入包仍可查看，但不能作为完整检查已复现的证明。

## 限制

最多 512 个所选文件、单文件 32 MiB、所选内容合计 128 MiB、压缩包 160 MiB。
文件名必须可跨平台使用。拒绝清单外成员、重名或名称冲突、路径越界、Git 管理文件、
符号链接、加密成员及字节不一致。清单没有数字签名，发送方可信度与字节验证需分别判断。
JSON 计划与 ZIP 请保存在已声明稿件及输入路径以外。
