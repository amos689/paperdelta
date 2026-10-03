# 开发证据记录

[English](../progress.md)

2026-10-02 开始，2026-10-03 悉尼时间更新。当前范围以 [v0.2 记录](v0.2-plan.md)为准。
a2 有独立[本地验收决定](release-acceptance.md)，新功能须单独验证。项目方接受机器
本地测试及 Codex 开发者/首位使用者判断，真人反馈放到上线后。Mac 实机等产品收敛，
远程 CI 和外部发布尚未执行。

## v0.2 实现与已记录检查点

| 范围 | 已实现行为 | 证据 / 限制 |
| --- | --- | --- |
| 语言 | 中英文 CLI 帮助、错误、提示、文本/Markdown、MCP 展示，机器字段和原文稳定 | [语言约定](languages.md)；[基础检查](../evidence/v0.2-foundation.json)190 通过、3 项 POSIX 跳过，之后 29 项定向检查 |
| 报告 | 同一离线 HTML 切换语言，保留筛选/证据展开，优先级、覆盖分组及证据导航 | [真实 Chrome](../evidence/v0.2-report-browser.json)、32 项相关 Python 检查；桌面/手机、无外部请求或脚本错误 |
| 诊断 | 只读 doctor 给出环境/配置/证据动作，结构化命令输出及事务号 | 基础测试覆盖；语言偏好与证据配置分离 |
| 人工向导 | 类型化来源/身份/单位/聚合，多位置选择及最终明确确认 | [教程](guided-bindings.md)；两种语言均有十绑定脚本化流程 |
| 位置修复 | 明确新旧上下文与选择、最新哈希，保留指标/结论定义 | 取消、歧义、重叠、过期及部分确认测试 |
| 共用构造器 / MCP | 十三个只读工具，枚举选项及可执行步骤，不确认、不改论文 | [构造器检查点](../evidence/v0.2-builder.json)：226 通过、3 项 POSIX 跳过；真实 stdio 分步提案测试 |
| 本地模型跟进 | v2/v3 独立协议及原始失败 | [结果](staged-model-evaluation.md)：v2 有效操作 0/12、v3 3/15；都没有有效完整提案或必要拒答 |
| 文档 | 维护页面完整配对、可执行双语教程、当前截图及演示字幕 | [贡献规则](../../CONTRIBUTING.zh-CN.md)；最终分发检查待完成 |
| 隐私 | 仓库提交邮箱及维护者元数据使用已验证 GitHub noreply | `101008326+amos689@users.noreply.github.com`，未改全局身份 |

这些检查点不是 v0.2 最终安装包/平台验收，剩余检查见[交付记录](v0.2-plan.md)。
它们不生成真人观察、一般模型准确率，也不批准自动映射器。

## 保留的 a1/a2 证据

| 范围 | 历史结果 | 记录 |
| --- | --- | --- |
| Windows / Linux | 四个 Windows Python 版本，Alpine 3.14、glibc 3.11–3.14，完整与定向运行分开 | [版本、数量及安装范围](local-validation.md) |
| 进程写入 | 真实锁竞争、终止写入进程、必须恢复的日志及字节恢复 | [Windows](../evidence/process-writes-windows.json)、[Linux](../evidence/process-writes-linux/evidence.json) |
| 首次接入 | 13 步 CLI、10 个自编绑定、8 处数据变化发现/修改、10 项重查通过、精确恢复 | [开发者记录](../evidence/developer-first-use/evidence.json) |
| 终端审查 | Agent 驱动真实 ConPTY 确认一项，四个 TeX 文件不变；12 项流程测试 | [交互记录](../evidence/interactive-validation.json) |
| 映射控制 | 九个参考映射、三次拒答，五个错误身份仍数值通过 | [控制](../evidence/mapping-controls/evidence.json)，不计模型/真人测量 |
| 原始本地模型 | 十二份答案可解析、十二份提案无效，零参考匹配/必要拒答 | [基线](local-model-evaluation.md) |
| 发现 / 样例 | AST 摘要/表格/重复优先，歧义表格、中文/字面宏、BOM/CRLF 修改恢复 | [样例](../evidence/owned-examples.json) |
| 只改数据 | 84.1→80.9：四处旧数字、失效比较、图依赖变化；84.1→84.5：三文件四处修改及恢复 | [演示](../evidence/workflow-demo.json) |
| CI | 即使 PR 改快照仍读目标提交，列声明变化/覆盖减少；10 项真实 Git 测试及 actionlint | [指南](ci.md)、[记录](../evidence/ci-adapter/evidence.json)，无远程运行 |
| 竞品 | 完整配置 Calkit 流水线、scitexlintr 数值/文本修复，对照 PaperDelta 比较失效拒改 | [CLI 对比](comparison.md)，未证明独立接入/耗时收益 |
| 语料 | 十篇有许可论文、各一数值、各十五相关场景；开发 75/75、首次留出 51/75，两篇动态 TeX 未知 | [评测](evaluation.md)、[首次留出](../evidence/corpus-held-out-first.json) |
| 语料重放 | 原始/a2 实现复现全部原逐例结果，包括 24 项完整预期失败 | [a2](../evidence/corpus-interactive-v2.json)、[原始](../evidence/corpus-original-replay.json) |
| 性能 | 500 绑定、20 TeX、10 MB CSV，最终 a2 二十次暖运行 P95 1.866 秒 | [源码/硬件](../evidence/performance-final.json)，早期 1.724 秒保留 |
| 报告 / 编译 | 实际无头 Chrome、原创 TeX 补丁前后编译、51.68 秒真实报告录像 | [浏览器](../evidence/report-browser-qa.json)、[编译](../evidence/tex-smoke.json)、[录像](../evidence/demo-recording.json) |
| 分发 | MIT wheel/源码与语料分开，纯核心安装、字节身份及许可 | [最终 a2 审计](../evidence/package-audit-final.json)、[重放](../evidence/release-replay-final.json) |
| Mac 准备 | 原生验证器、Apple Silicon/Intel CI、文件系统/PTY 案例，仅 Windows 启动验证 | [准备](../evidence/macos-preparation.json)，没有 Mac 通过结论 |

语料是原论文文本加合成证据，不是复现原实验；每篇一个标注不能证明整篇准确率。
开发者自编输入和映射，不是独立首次使用。操作时记录程序误以为 apply 输出 JSON，
实际写入早已成功；之后用同一事务重查恢复，未重复写入。

## 设计决定及后续

- 小型探针后选择 pylatexenc 2.11 与显式字面宏，不证明它在广泛论文上优于 TexSoup。
- 标准 argparse、转义离线模板，各界面共用检查结果。MCP 2.x 可选，精确提案文本
  避免宿主浮点转换。
- 单文件原子替换、系统锁和日志，不声称多文件整体原子；断电/网络文件系统未测。
- 来源身份、一致性、历史、来源记录及作者审阅独立。审阅不能使错误谓词通过，
  文件哈希不能证明实际执行。
- 真人接入/竞品时间按[上线后方案](first-use-trial.md)收集，三人/十分钟仍为目标。
- 产品收敛后按[迁移指南](../../START_ON_MAC.md)做 Mac；远程 CI 及 GitHub/包发布单独安排。

原 PD-101–104、PD-201–205、PD-301–304 有本地功能证据；PD-001/003/004 有样例、
解析/约定；PD-002 有配置对比；PD-401–404 有开发者接入、Agent 和本地 CI，未测独立
采用或远程执行；PD-501–505 有限定语料、性能、文档、演示及产物。v0.2 单独跟踪完成，
不继承旧版“通过”状态。
