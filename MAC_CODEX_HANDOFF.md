# 给 Mac Codex 的 PaperDelta 完整交接提示词

[English](MAC_CODEX_HANDOFF.en.md) · [用户迁移步骤](START_ON_MAC.md)

本文件供项目主人将迁移包交给 Mac 上的 Codex 时使用。用户发送启动提示词后，
请把以下内容作为本轮任务说明，结合实际文件和主机结果执行。整理日期：2026-10-03。

## 项目背景与当前基线

PaperDelta 是一个开源 Python CLI 和可选只读 MCP 工具，帮助研究者及编程 agent
检查“实验数据已经变了，现有论文哪里需要复核”。它将 LaTeX 中的数值、比较和图表
关联到明确声明的 CSV/JSON 证据，输出可追溯诊断及离线 HTML。它不是自动写论文工具，
一致性通过也不代表科学结论正确或实验已经执行。

当前版本为 `0.2.0a1`，原 Windows 仓库验收提交为
`5ea7d27e28e5308f6ef3cf5ab4c7f807fb575f64`。交接版在该候选上补充文档和材料，
不改变运行源码、测试或安装 wheel。具体文件身份以 `TRANSFER.json` 和
`handoff/BASELINE.json` 为准。ZIP 没有 `.git` 历史，不能假定这个提交能在本目录解析。

已实现：中英双语 CLI/报告/MCP 展示/CI 摘要；同一离线 HTML 切换语言并保留状态；
只读 `doctor`；强类型 `paperdelta guide` 接入向导；明确确认后写入绑定；过期输入
拒绝；位置修复与上下文预览；补丁、事务及恢复；十三个只读 MCP 工具。
机器字段、错误码、证据 ID 和科学判定不随语言变化。向导命令是 `guide`，没有
`bind --guide` 这个选项。

先阅读以下内容，再按需要深入实现：

1. [项目介绍](README.zh-CN.md)与[上手](docs/zh-CN/quickstart.md)。
2. [v0.2 验收及限制](docs/zh-CN/v0.2-acceptance.md)。
3. [Mac 验证设计](docs/zh-CN/macos.md)、[语言约定](docs/zh-CN/languages.md)。
4. [向导与修复](docs/zh-CN/guided-bindings.md)、[贡献说明](CONTRIBUTING.zh-CN.md)。
5. `tools/validate_platform.py`、`tools/validate_python_matrix.py`、
   `tests/test_platform_io.py` 和 `.github/workflows/ci.yml`。

## 已有证据与不能扩大解释的部分

| 项目 | 交接时的实际状态 |
| --- | --- |
| Windows | Python 3.11–3.14 各 234 通过、3 项 POSIX 专用测试跳过；32 个运行文件/资源身份一致。 |
| Linux | 本地 QEMU 中的 glibc 用户空间。修复缺少 devpts 的环境后，3.12 完整 237 项通过，另外三个版本各 5 项平台测试通过；不声称四套都重新全量通过。 |
| macOS | 尚无实机通过记录。本轮就是补足真实 Mac 证据。 |
| 真人测试 | 独立参与者为零；用户已明确批准上线前由机器测试和 Codex 开发者判断验收，不安排真人试用门槛。 |
| 论文语料 | 十篇已见论文、合成证据、150 项相关案例，126 项完整预期通过、24 项已知失败。不是新的留出集或通用准确率。 |
| 小模型 | 历史映射评测未达到完整有效映射目标；不启用未经证实的自动绑定。 |
| 发布 | 本地开发预览候选；没有本轮远程 CI、GitHub/PyPI 发布记录。 |

## 本轮要完成什么

在这台 Mac 的真实 macOS 上，验证已验收候选能安装、检查、切换中英文、正确写入和
恢复，并执行现有全量测试。发现问题时完成范围内的兼容性修复，补充必要回归，重新
构建安装包并验证。最后返回可在 Windows 原仓库审查、合并和复现的工作包。

你是开发者和第一位使用者，可以据实给出本机发布验收判断。授权包含本项目内创建
虚拟环境、安装项目依赖、必要的源码/测试/工具修复和双语文档同步。请先检查并直接
推进；只有缺少系统组件、系统权限或必须由主人做的操作时，才解释原因并请求协助。
保留项目范围：这次不增加统计分析、论文生成、监听服务或编辑器集成等新产品功能。

## 1. 接收和记录

先确认根目录、`pyproject.toml` 版本及 `install/` 下的 wheel。用 Python 标准库读取
`TRANSFER.json`，逐一检查其中 `files` 列出的相对路径：路径须在项目内、存在、
不是符号链接，SHA256 与清单相同。修改前将检查数量和结果保存到新建的
`build/mac-receipt/`；记录 `TRANSFER.json` 与 `handoff/BASELINE.json` 自身的哈希。
不一致时先定位传输/解压问题，不通过更新清单来掩盖变化。

记录 `sw_vers`、`uname -m`、原生硬件架构、所选 Python 绝对路径和版本、
`platform.machine()`、`sysctl.proc_translated`（键不存在也记录）及 `git --version`。
不记录序列号、整套环境变量或凭据。Apple Silicon 使用原生 arm64 Python；Intel 使用
x86_64。不要以 Rosetta、Linux 容器或改写 `platform.system()` 代替原生 Mac 验收。

选择已有的原生 Python 3.11–3.14，至少完成一个版本；存在多个版本可逐一验证。
没有合适 Python 时再请主人安装；不要替换系统 Python。下文 `python3` 指你实际选定
的解释器，必要时替换为其绝对路径。不要复用 Windows 虚拟环境。

为生成可靠的改动补丁，在校验后、编辑前建立本机 Git 基线。如果项目本身没有 `.git`，
可在这个解压目录 `git init -b mac-validation`；已有仓库则先检查状态并保留已有修改。
使用**仓库局部配置** `user.name=PaperDelta contributors` 和
`user.email=101008326+amos689@users.noreply.github.com`，不修改全局身份。
只加入经清单校验的项目文件，排除 `build/`、环境、缓存及生成的 egg-info，提交接收
基线并记录本机提交 ID。这个 ID 与 Windows 基线 ID 不同是正常的。

## 2. 原包原生验证

在项目根目录运行，输出目录每次用新名字：

```sh
python3 tools/validate_platform.py --wheel install/paperdelta-0.2.0a1-py3-none-any.whl --out build/mac-validation-original-01 --require-system Darwin --expected-arch arm64
```

Intel 将最后的 `arm64` 改为 `x86_64`。脚本会新建 `venv-core` 和 `venv-full`，
安装所需依赖，执行核心安装冒烟、Ruff、实际安装包的全量测试、示例和本地 Git CI
演示，保存日志、JUnit、源码/安装包身份和 `evidence.json`。
不要用 editable 安装的通过结果替代安装 wheel 的验收。

当前完整基线为 **237 项测试**；macOS 的 POSIX 案例应运行，完整验收要求零失败、
零错误、零跳过。新增回归会提高数量，实际计数以 JUnit 为准，解释差异。
检查源码与安装包全部运行资源一致，不只检查版本号。
第一次失败也要保留，区分依赖下载/权限/运行环境故障和产品缺陷。

## 3. 作为第一位使用者检查双语工作流

使用前一步实际安装包环境；在 `build/` 的示例副本上操作，保留原始示例。
至少体验：

- `doctor`、`check`、`--help` 的 `en`/`zh-CN` 输出，以及语言选择优先级。
- 示例六个绑定通过；仅修改数据后出现对应诊断，而非论文不变就忽略。
- `guide` 的实际终端输入、中文路径、身份字段前导零、取消不写入和最终明确确认。
- 补丁预览/应用/重查/恢复与位置修复，保持来源、指标、单位、科学定义及原字节。
- Mac 浏览器打开生成的离线 HTML，切换中英文，检查筛选/展开状态与焦点、中文显示。
  如本机工具允许，补充窄屏和键盘操作。记录实际浏览器；无法自动操作时明确未测项。
- 可选 MCP 安装存在时验证现有只读工具；没有模型账号或 API key 不影响此项。

已有全量套件包含真实 POSIX 终端和 stdio MCP 测试；不要把自动终端输入记作独立真人
试验。浏览器无法验证时继续其他工作，但不要声称全部体验验收完成。
相关命令与正确示例见前述文档，执行前查看当前 CLI 帮助。

## 4. 修复与重新验收

先复现再作最小必要修复，重点关注 Mac 路径/大小写/Unicode、权限/文件锁、终端、
编码、进程行为和依赖安装。不要通过删除断言、跳过测试、放宽路径边界或取消最终
确认来取得绿色结果。仅在验证工具本身有缺陷时修正它，并解释为什么仍测到相同契约。
保留原失败和修复后证据，超时要区分运行缓慢与死锁。

任何运行代码或资源修改后，旧 `install/` wheel 都不能代表新代码。为开发建立局部
`.venv-dev`，安装 `.[dev,mcp]`，再在新目录构建 wheel，例如：

```sh
python3 -m venv .venv-dev
.venv-dev/bin/python -m pip install -e '.[dev,mcp]'
.venv-dev/bin/python -m build --wheel --outdir build/mac-candidate-01
python3 tools/validate_platform.py --wheel build/mac-candidate-01/paperdelta-0.2.0a1-py3-none-any.whl --out build/mac-validation-fixed-01 --require-system Darwin --expected-arch arm64
```

Intel 同样替换架构。保留原 wheel，不需仅因本机修复自动改版本号；用不同路径和
SHA256 区分候选。重建后的环境仍由验证器新建。如果只变更测试/工具/文档而运行文件
未变，说明身份核对结果，再使用匹配的原 wheel 验证。

运行 `python3 tools/check_docs.py`。同步相关英文/中文页面及语言切换入口，新增维护
页面注册到 `docs/translations.json`。`docs/evidence/`、`tests/corpus/`、`evaluations/`
中的已有冻结文件不覆写；新证据写新目录。原始许可证不改。保持 noreply 邮箱，不在
文档中增加真实邮箱。只按实际跑过的硬件/系统/Python/浏览器报告兼容范围；一台
Apple Silicon 通过不能写成 Intel 也通过。远程 CI 配置存在不表示已经执行。

## 5. 回传文件：这是必须完成的交付

创建新的 `build/mac-return-UTC时间戳/`，整理完再生成同级
`PaperDelta-Mac-Return-UTC时间戳.zip` 和 `.zip.sha256`。回传目录至少包含：

| 路径 | 必须包含的内容 |
| --- | --- |
| `REPORT.zh-CN.md`、`REPORT.en.md` | 相互链接的中英文结果；问题、修复原因、实际命令/退出码、通过/失败/跳过数、手工体验、未测项、是否建议本机候选验收。 |
| `handoff.json` | Windows 源基线、本机接收提交、TRANSFER 哈希、原/最终 wheel 哈希、OS/硬件/进程架构/Python、测试证据相对路径、是否修改代码、最终状态。 |
| `changes.patch` | 相对本机接收基线的 `git diff --binary --full-index`；包括新增源码/测试/双语文档。仅暂存明确要交付的文件，避免遗漏 untracked 新文件。无修改则为空并明确说明。 |
| `changed-files/`、`deleted-files.json` | 按项目相对路径保存新增/修改文件；单独列删除路径。每项记录修改前后 SHA256，可与 Windows 原仓库核对；删除/新增的一侧为 null。 |
| `evidence/` | 接收校验、每次失败与修复后的 evidence JSON、命令日志、JUnit、核心冒烟、示例/CI 结果、必要 HTML/截图及浏览器说明。保留原来的相对层级。 |
| `artifacts/` | 如果改了运行代码，附最终重新构建并实际测试的 wheel；没有改则引用原 wheel 哈希即可。 |
| `MANIFEST.json` | 对以上每个回传文件记录相对路径、大小、SHA256；不把自身列入自身哈希。 |

不要把 `.git/`、虚拟环境、pip 缓存、模型权重、密钥、整套临时工作目录或另一份完整
项目塞进回传 ZIP。公开证据中的本机用户名/主目录用 `<home>`、项目路径用
`<checkout>` 代替；脱敏副本注明替换规则及原/公开哈希，本机原记录保留。
这既保持隐私，也使故障与代码修改可核验。回传 ZIP 不自动上传到外部服务。

打包后重新读取 ZIP，验证成员及 MANIFEST 哈希。`.zip.sha256` 使用
`SHA256  ZIP文件名` 格式，使主人能在 ZIP 同级执行 `shasum -a 256 -c 文件名.zip.sha256`。
即使环境阻塞、未通过或没有源码修改，也应返回已有证据及准确的未完成项。

最后在 Mac 对话用中文告诉主人：

```text
结果：通过 / 部分完成 / 阻塞（只能按实际证据选择）
本机：macOS 版本、硬件架构、Python；实际测试计数及跳过项
修改：主要修复，或“运行代码未修改”
未验证/未解决：明确列出，或“本轮约定范围内无”
请带回 Windows：两个可点击的本机绝对路径（ZIP 与 .sha256）
下一步：放进 Windows 原项目 build/mac-return-inbox/，请原对话核对和合并。
```

本轮不自动发布、不推送 GitHub/PyPI，也不改全局 Git 身份。交接由主人拷贝文件完成，
无需假定可以访问或向 Windows 的原对话发送消息。
