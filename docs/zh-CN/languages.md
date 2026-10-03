# 语言选择与稳定的机器数据

[English](../languages.md)

v0.2 开发版已为命令行帮助、终端确认、诊断、文字/Markdown 报告及 MCP 说明提供
英文 `en` 和简体中文 `zh-CN`。离线 HTML 切换及全部文档的对应译文仍在实施，
具体状态见[交付记录](v0.2-plan.md)。

## 选择语言

全局选项放在子命令之前：

```sh
paperdelta --lang en -C examples/research-paper check
paperdelta --lang zh-CN -C examples/research-paper check
paperdelta --lang zh-CN -C examples/research-paper doctor
paperdelta --lang zh-CN -C examples/research-paper mcp
```

优先级为 `--lang`、`PAPERDELTA_LANG`、项目界面设置、系统消息语言、英文。
`auto` 表示继续查找下一项。`zh_CN`、`en-US` 等别名会选择对应的支持语言。
明确指定了不支持的语言时会报错；系统语言未受支持时回退为英文。
论文语言与界面语言独立。

保存项目界面设置：

```sh
paperdelta -C examples/research-paper settings --language zh-CN
paperdelta -C examples/research-paper settings --format json
```

此操作只修改 `.paperdelta/ui.json`，与 `paperdelta.yaml` 和实验身份分开。本仓库已
忽略该界面文件；自己的论文仓库可以添加同样的 Git 忽略项。
`settings --language auto` 恢复跟随系统语言。界面文件损坏时，可用明确的语言参数
绕过旧设置后重设：

```sh
paperdelta --lang zh-CN settings --language zh-CN
```

## 终端与 Agent 行为

中文确认支持 `是`、`否`、`证据`、`取消`，也支持 `y`、`n`、`e`、`q`。
最后输入 `确认` 或 `accept` 才保存，空行仍用于跳过或取消。
语言和提示翻译不会改变实际保存的映射。

MCP 工具名称、参数、ID 和属性保持统一；说明、解释及下一步提示使用服务启动时
选择的语言。不同服务实例各自保留语言设置。翻译后的 MCP 结果仍是展示视图，
不能当作完整归档报告或可直接写入的提案。

## 实验记录与命令结果

配置键、枚举值、schema 字段、ID、文件路径和精确数值保持语言无关。论文、数据
及作者文字保留原样。版本 1 归档报告中的消息保留标准英文；面向人的显示层翻译
运行时的结构化消息。切换语言不会改变证据身份、数值补丁或复核状态。
第三方原始诊断可能作为翻译说明下的技术详情保留。

继续读取原有版本 1 配置、报告和快照；历史快照用于比较，不重写原记录。
提案及补丁仍绑定工具版本：a2 的提案/补丁需要在 v0.2 重新生成并复核后再确认或
写入。既有事务日志的恢复仍须通过原有的字节身份校验。

所有操作命令均可使用 `--format json`，包括 `propose`、`fix`、`apply`、`recover`、
`snapshot create`、`review record`、`init`、`bind`、`settings` 和 `doctor`。
结果保留原有字段，并增加 `command_result_version: 1` 和 `command`。成功应用补丁
会直接返回 `transaction_id`。`check`/`scan` 的 JSON schema 保持不变；`schema`
始终输出 JSON；`mcp` 的标准输出仅用于协议。

明确指定 `--format json` 时，错误以 JSON 输出到标准输出，含稳定的 `error` 代码、
标准英文 `message` 和当前语言的 `display_message`。交互提示仍输出到标准错误。
为了兼容，操作命令未明确请求 JSON 时沿用原有的错误输出方式；脚本应始终明确
指定 JSON 格式。

## 翻译维护

词条位于 `src/paperdelta/locales/en.json` 和 `zh-CN.json`。`msg()` 生成带消息 ID
和参数的标准字符串，`tr()` 生成界面文本。异步任务的语言上下文互不干扰。
模型校验保留字段路径和消息 ID，不依赖翻译已经拼接好的英文堆栈。
目录检查验证词条完整性和占位符一致性。

| English | 简体中文 |
| --- | --- |
| binding | 绑定 |
| occurrence | 论文位置 / 位置绑定 |
| claim | 结论 |
| proposal | 提案 |
| evidence | 证据 |
| baseline / snapshot | 基线 / 快照 |
| mismatch / unknown | 不一致 / 未知 |
| review / superseded | 复核 / 已失效 |
| recovery | 恢复 |
| aggregation / unit | 聚合 / 单位 |

新增自有界面词条时同步添加两种语言，保留占位符及命令/配置名称，并运行语言
测试和词条检查。许可证原文与冻结证据日志保持原始字节，通过说明文件提供翻译。
