# 原生 Mac 验收 — 2026-10-03

[English](../macos-validation-2026-10-03.md)

**建议通过本机开发预览版验收。** macOS 27.0.1（构建 26A434）、Apple Silicon
arm64、原生 CPython 3.12.14 和 3.14.6。最终安装包套件各 **241 项通过，零失败、
零错误、零跳过**。未修改产品运行代码，未发布、推送或安排独立真人试用。
[机器记录](../evidence/macos-native-20261003/summary.json)列出被测 wheel、源码身份和证据位置。

## 接收与执行

编辑前，`TRANSFER.json` 的 1,060 个文件全部通过路径、符号链接和 SHA256 校验。
`handoff/BASELINE.json` 中版本、Windows 源提交、wheel、32 个运行文件/资源、
26 个原测试文件和 29 个工具均一致。Windows 源提交为
`5ea7d27e28e5308f6ef3cf5ab4c7f807fb575f64`；另建的 Mac 接收提交为
`722c0032d88ba2692f6737c48e86272dd293e735`。Git 身份只在本仓库设置，使用交接指定的 noreply 邮箱。

未变更的 `install/paperdelta-0.2.0a1-py3-none-any.whl` 的 SHA256 为
`c6f119ad4ded3e7866dd0f7efd233cac9466fd26cf9d9afe0eefdd7b6cf80c78`。
两套原始测试均为 237 项通过；新增四项验证工具回归后最终为 241 项。每套最终测试
都逐一比对安装包与源码的 32 个运行文件/资源。本轮只改工具、测试和文档，因此在
全新环境中再次测试匹配的原 wheel，无须重建。原始及最终安装、JUnit、命令日志均保留。

每个已记录解释器均执行以下完整命令：

```sh
/path/to/native/python tools/validate_platform.py --wheel install/paperdelta-0.2.0a1-py3-none-any.whl --out build/NEW_DIRECTORY --require-system Darwin --expected-arch arm64
```

每次成功验证都包含独立核心/完整安装、双语核心冒烟、仅数据变化诊断、Ruff
检查/格式、完整安装包测试、样例及本地 Git CI 场景。独立硬件查询记录为
`hw.optional.arm64=1`、`hw.machine=arm64` 和 `sysctl.proc_translated=0`。

## 开发者体验与浏览器

使用已安装的 Python 3.14 wheel，开发者实际驱动 CLI 与 POSIX 终端：双语
help/doctor/check、各层语言优先级、六处示例绑定通过、只改数据检出不一致、中文
路径中十处向导绑定及 `001` 模型身份、构造/最终阶段取消不写入，以及最终明确确认。
十处数值修改完成预览、应用、重查及 UTF-8 BOM/CRLF 原字节恢复。位置修复保持
来源、指标、单位、显示和结论定义，以及所有非配置输入字节。真实 stdio MCP
连接列出十三个只读工具，并完成不写入的项目检查。输入由开发者编写，独立真人为零。

使用现有浏览器 QA 无头驱动原生 Google Chrome 154.0.8037.97，验证双语、五类
筛选、跨语言搜索、证据展开、状态与焦点保留、Enter/Tab 操作、离线/无脚本阅读、
1365×1000 桌面和 375×812 窄屏。没有外部请求、脚本错误或横向溢出。已目视检查
中文桌面与窄屏截图。

## 保留的失败与修正

- 首次安装因沙箱 DNS 无法解析 PyPI 而失败；在授权范围内解除该运行限制，用新目录
  重新安装依赖并通过。
- 原浏览器记录器将所有主机写成 Windows。现改为记录实际系统、内核、架构和 Node
  版本，并增加焦点和键盘检查；旧错误标注记录仍保留，并明确被后续记录取代。
- Rosetta 查询受限/缺失时原先被写为 `false`。现保留退出码、标准输出/错误，未知时
  记为 `null`；四项回归覆盖原生、转译、键缺失和拒绝访问。本机成功查询实际返回 `0`。
- 首次补充体验记录器直接比较 YAML 字典；保存时展开默认字段，导致错误断言。原脚本、
  日志和诊断保留。修正后比较完整类型化来源/指标/结论定义，并独立核对其他文件字节。
  产品行为未变，完整体验复跑通过。

## 范围与回传

本轮未测 Intel Mac、Python 3.11/3.13、其他 macOS、Safari/Firefox、远程 CI、
独立真人、断电耐久性或网络文件系统。约定的本机验收范围内未发现未解决问题。
历史语料和模型限制维持原记录，本轮未重新评分。

Mac 回传 ZIP 包含双语报告、完整索引二进制补丁、修改文件与前后哈希、失败/最终
日志和 JUnit、必要 HTML/截图、wheel 哈希、未解决/未测事项及经过核验的清单。
公开文本将项目路径替换为 `<checkout>`、主目录替换为 `<home>`；本机原记录保留
在 `build/`，来源索引记录脱敏前后哈希。将 ZIP 及对应 `.zip.sha256` 一起复制到
Windows 原仓库的 `build/mac-return-inbox/`，验证校验文件后审查并合并补丁。
接收时的 `TRANSFER.json` 和 `handoff/BASELINE.json` 保持不变。

## Windows 核对与合并

2026-10-03，原 Windows 工作目录核对了回传 ZIP 校验值、全部 321 个成员、320 条
清单记录及 21 个修改文件的前后哈希。回传中的迁移清单和基线与发往 Mac 的包一致。
两份最终 JUnit 与执行记录相符：各 241 项通过，原 237 项保留，并新增四项验证工具
测试。32 个运行文件及原 wheel 未变。公开来源索引的 288 个文件和五处原运行哈希
引用也通过核对。

两处工具修复、四项回归和双语说明已接受。合并后的套件在 Windows Python 3.12.14
重新执行，使用已安装的原 wheel，**238 项通过、3 项仅限 POSIX 的测试跳过**。
新版浏览器检查在 Windows Chrome 154.0.8037.93 通过，包括语言切换焦点和键盘操作，
没有外部请求或脚本错误。Ruff 和文档检查通过。这是新增的 Windows 复核；本轮未为
工具变更重新运行 Linux。

[原始回传 ZIP](../evidence/macos-native-20261003/return.zip)完整保留 Mac 失败和成功的
记录、双语报告、脚本、补丁及清单，原字节不改。
[合并记录](../evidence/macos-merge-20261003/integration.json)、
[Windows 套件](../evidence/macos-merge-20261003/windows-regression.json)和
[Windows 浏览器](../evidence/macos-merge-20261003/windows-browser.json)记录接收端复核。
新增证据另存新目录，历史记录保持原样。更新后的候选目录为
`build/release-candidate-v0.2-mac`。
