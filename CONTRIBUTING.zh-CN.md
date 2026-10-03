# 贡献指南

[English](CONTRIBUTING.md)

通过[中英文问题表单](https://github.com/amos689/paperdelta/issues/new/choose)提交缺陷或
功能建议，附上命令、版本及最小原创论文/数据样例。附件中移除私人路径、凭据及
未公开研究内容。安全漏洞请按[安全政策](SECURITY.zh-CN.md)私下报告。

PR 默认使用英文模板。创建 PR 时，在网址末尾添加 `?template=zh-CN.md` 后再填写；
已有查询参数时添加 `&template=zh-CN.md`。也可参考[中文模板](.github/PULL_REQUEST_TEMPLATE/zh-CN.md)。
讨论可以使用任一语言；新增用户界面消息和维护文档需配齐两种语言。

使用 Python 3.11 以上版本，安装 `python -m pip install -e '.[dev,mcp]'`。
运行 `python tools/run_tests.py -q`、`python -m ruff check src tests tools` 和
`python -m ruff format --check src tests tools`。测试在 `.tools/test-runs` 下创建
独立临时目录，不要改用可能由其他进程占用的共享临时目录。

从具体论文及数据样例出发，说明检查器应知道什么、应保持哪些未知，以及哪些字节
允许改变。欢迎补充解析边界、数据身份错误、宏约定、明确单位转换，以及降低首次
映射难度的文档。

保持检查器独立于模型供应商、实验执行和 TeX 编译。新的数值补丁规则必须覆盖输入
过期、准确位置和恢复，不得悄悄强化科学结论。保留未知状态和覆盖分母，不能通过
删除案例提高通过率。

使用原创样例，或记录导入材料的许可和授权。源文件公开不代表论文、图表或数据集
可以再分发。复制实现时记录上游署名。当前代码为本项目编写，相关工作见
[调研记录](docs/zh-CN/research.md)。

默认许可证为 MIT。schema 变化应包括迁移决定、版本行为和示例。仓库包含跨平台
CI 配置，但只有真实成功运行才算兼容性证据。

中英文消息一起添加，保留占位符和机器标识符。维护中的文档应有对应译文并互相
链接，详见[语言约定](docs/zh-CN/languages.md)。原许可证及冻结研究记录保持不变。
新研究锁定新的实现身份，不得修改旧锁文件，让变更后的代码冒充原实验复现。

需要邮箱隐私时，在本仓库的 Git 局部配置中使用自己的 GitHub noreply 邮箱。
不要在样例或公开日志中写入个人邮箱；第三方作者署名及许可证原文保持完整。
