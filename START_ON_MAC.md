# 在 Mac 上开始使用 PaperDelta

[English](START_ON_MAC.en.md)

## 安装发行版

Mac 已有 Python 3.11 以上版本时，创建并激活虚拟环境，然后运行：

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install paperdelta
paperdelta --lang zh-CN demo --out paperdelta-demo --open
```

安装包自带演示和报告；需要继续开发时使用下面的 GitHub 源码方式。

## 从 GitHub 安装

使用 Python 3.11 以上版本，在 Mac 终端执行：

```sh
git clone https://github.com/amos689/paperdelta.git
cd paperdelta
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
paperdelta --lang zh-CN -C examples/research-paper doctor
python tools/demo.py --out build/demo
```

打开 `build/demo/comparison-reversed/review/report.html`，选择简体中文。
接入自己的论文见[快速开始](docs/zh-CN/quickstart.md)，各 Mac 架构的运行结果见
[Actions](https://github.com/amos689/paperdelta/actions/workflows/ci.yml)。
若要继续开发，将克隆后的 `paperdelta` 文件夹作为 Mac 上 Codex 的项目目录；
开发依赖和检查命令见[贡献指南](CONTRIBUTING.zh-CN.md)。

## 首次实机验证的历史迁移方式

下文保留最初 Windows → Mac 交接及回传步骤。所列 `build/` 文件是当时本地生成的
迁移包，不随 GitHub 克隆分发；新的安装可直接使用上面的仓库流程。

**交给 Mac 上的 Codex 工作，请使用新增的 Codex 交接版：**
`build/mac-transfer-v0.2-codex/paperdelta-0.2.0a1-mac-codex-transfer.zip`。
同目录的 `SHA256SUMS` 是校验文件；两个文件一起拷贝。原先的
`build/mac-transfer-v0.2/` 保留不动。

交接版保留已验收 0.2.0a1 wheel 和运行源码，补充双语交接提示词、完整文档引用材料
及修改基线。包含源码、测试、示例和历史证据，不含 Windows 虚拟环境、模型权重或
Git 历史。论文评测材料保留[各自的许可证](THIRD_PARTY_NOTICES.zh-CN.md)。
此交接包最初没有 Mac 实测记录；[2026-10-03 Mac 回传](docs/zh-CN/macos-validation-2026-10-03.md)
现已补充 Apple Silicon macOS 27.0.1、Python 3.12.14 / 3.14.6 的原生结果；
这份本地回传不包含 Intel 测试，后续 CI 另行记录。

## 历史交接：把迁移包交给 Mac Codex

### 1. 在 Windows 拷贝两个文件

在资源管理器打开本项目的 `build/mac-transfer-v0.2-codex` 文件夹。
把 ZIP 和 `SHA256SUMS` 一起复制到能在两台电脑上使用的 U 盘、移动硬盘或你已有的网盘。
不用拷贝整个 Windows 工作目录，也不用先把项目上传 GitHub。

### 2. 在 Mac 保存并解压

把这两个文件先复制到 Mac 本机，例如“下载”中的 `PaperDelta-transfer` 文件夹。
双击 ZIP，得到 `paperdelta-0.2.0a1` 文件夹。把它移动到一个长期保存的位置，
例如个人目录下的 `Developer` 文件夹；没有 `Developer` 就在 Finder 中创建。
建议使用本机磁盘上的目录。

确认打开项目文件夹后直接看见 `pyproject.toml`、`src`、`tests`、`install`、
`MAC_CODEX_HANDOFF.md` 和 `TRANSFER.json`。如果只看见另一个同名文件夹，继续进入一层。
保留原 ZIP 和校验文件，后面可能需要核对修改前的内容。

可选手动校验：打开“终端”，输入 `cd `（末尾保留空格），将**存放 ZIP 和
SHA256SUMS 的文件夹**拖入终端，按回车，再执行：

```sh
shasum -a 256 -c SHA256SUMS
```

应出现 `paperdelta-0.2.0a1-mac-codex-transfer.zip: OK`。
不熟悉终端可以跳过这一步，提示词会让 Codex 核对解压后每个文件。

### 3. 在 Mac 的 Codex 中打开本地项目

打开并登录 Mac 上的 Codex。通过“添加项目/打开文件夹”一类的入口，选择刚才的
`paperdelta-0.2.0a1` 文件夹，然后在这个项目中新建对话。
如果界面使用“Projects → 项目菜单 → Edit project → Add folder”，将同一文件夹
添加为本地项目的主目录。不同版本名称可能不同，关键是让对话实际访问这个本机目录。
只把 ZIP 当附件发给一个普通聊天，不能代替打开本地项目。
这里使用的是[官方文档中的本地项目工作方式](https://learn.chatgpt.com/docs/projects)。

### 4. 原样发送这段启动提示词

```text
当前打开的文件夹是 PaperDelta 的 Mac 交接项目。请先完整阅读
MAC_CODEX_HANDOFF.md，再核对 TRANSFER.json 和 handoff/BASELINE.json。
按照交接文件完成本机原生 macOS 验证、必要的兼容性修复和中英文文档同步。
我授权你在这个项目内创建环境、安装项目依赖、修改必要代码并运行测试；
由你作为开发者和第一位使用者验收，不安排真人用户测试。
不要发布或推送。请保留真实失败记录，最终生成交接文件要求的回传 ZIP、
SHA256 校验文件、中英文报告、代码差异和测试证据，告诉我应拷贝哪两个文件回 Windows。
先检查项目和环境，然后直接开始；只有确实需要我操作系统安装或授权时再说明原因。
```

完整的[中文交接提示词](MAC_CODEX_HANDOFF.md)和[英文版](MAC_CODEX_HANDOFF.en.md)
已随包保存。那边可以通过这两份文件取得背景，不需要你重述整个开发过程。

### 5. 等 Mac Codex 完成并带回结果

Codex 会检查 Mac 架构、Python 和 Git，建立 Mac 自己的环境，再运行安装包测试。
如缺少合适 Python 或 Git，让它说明最少需要你完成的安装；不必提前安装整套开发工具。
安装依赖需要联网，PaperDelta 的日常检查本身不需要模型密钥、GPU 或 TeX。

完成后，它应给出两个文件：`PaperDelta-Mac-Return-时间戳.zip` 和对应的
`.sha256`。ZIP 应包含双语结论、修复文件和补丁、安装包身份、测试日志、JUnit、
未解决项；没有代码修改时也要返回测试证据。中途失败也应保留并回传记录。

把这两个文件复制回 Windows 本项目新建的 `build/mac-return-inbox/` 目录，
不要直接覆盖现有源码。然后在**Windows 这条对话**发送：

```text
Mac 的 Codex 已完成本轮工作，回传文件放在 build/mac-return-inbox/。
请先核对回传包、基线、修改和测试证据，再合并必要修复，运行 Windows 回归，
更新双语说明和发布候选。如果仍有 Mac 未验证项，请明确列出。
```

回传包是两边衔接的依据；不要依赖新对话自动知道本次历史或自动发送结果。

## 手动操作参考

以下步骤可由 Mac Codex 执行，你采用上述交接方式时无需再手动运行一遍。

## 1. 拷贝和解压

将交接 ZIP 通过 U 盘、移动硬盘或网盘复制到
Mac，双击解压，把解压后的 `paperdelta-VERSION` 文件夹放到希望保存的位置。
不要从 Windows 复制 `.venv`：Python 环境要在 Mac 上重新建立。

打开 Mac 的“终端”，输入 `cd `（末尾有一个空格），把解压后的项目文件夹拖进
终端，再按回车。下面的命令都在这个文件夹内执行。

## 2. 确认 Python

```sh
python3 --version
```

需要 Python 3.11 或更新版本；当前测试矩阵为 3.11–3.14。
如果没有 Python，或版本低于 3.11，从
[Python 官方 Mac 下载页](https://www.python.org/downloads/macos/)安装当前稳定版，
安装后重新打开终端。官方 universal2 安装包可用于 Apple Silicon 和 Intel。
不要修改系统自带 Python；使用下面的项目虚拟环境。
参见 [Python 官方 macOS 说明](https://docs.python.org/3/using/mac.html)。

## 3. 先跑一个示例

逐行运行：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install ./install/paperdelta-*-py3-none-any.whl
.venv/bin/python -m paperdelta --lang zh-CN -C examples/research-paper doctor
.venv/bin/python -m paperdelta --lang zh-CN -C examples/research-paper check --report build/review
open examples/research-paper/build/review/report.html
```

安装时需要联网获取普通 Python 依赖；日常检查不需要联网、模型密钥、GPU、
TeX 或 Xcode。看到六个已确认绑定通过并打开报告，就说明基本检查流程已跑通。

再体验“数据变化，论文未修改”的完整演示：

```sh
.venv/bin/python tools/demo.py --out build/mac-demo
open build/mac-demo/comparison-reversed/review/report.html
```

它在新目录复制示例、修改数据并展示影响；不会修改原始示例。
重新运行时换一个输出目录，例如 `build/mac-demo-2`。

## 4. 完整 Mac 验证

完整验证还需要 Git，并会联网安装测试和 MCP 依赖。先检查：

```sh
git --version
```

然后运行：

```sh
python3 tools/validate_platform.py --out build/mac-validation --require-system Darwin
```

脚本自动使用 `install/` 中的 wheel，创建两个新的局部虚拟环境，分别检查
基础安装和完整测试环境。它会测试文件锁、进程中断恢复、中文及重音路径、
真实终端确认、MCP、示例和本地 Git 场景，并保存操作系统、架构、日志及结果。
Apple Silicon 请使用原生 arm64 Python；脚本发现 Rosetta 转译时会停止并提示。
重新测试请换输出目录，不覆盖第一次记录。

结束后，把终端最后打印的结果发回当前对话。若失败，保留
`build/mac-validation/evidence.json` 及对应的 `.log`；这些记录能定位实际兼容问题。
无需上传整个虚拟环境。

详细的架构与验证范围见 [macOS 适配说明](docs/zh-CN/macos.md)。
`install/paperdelta-evaluation-VERSION.zip` 保存真实论文评测材料及其许可。
Codex 交接版已经按原路径补齐文档所引用的冻结材料，无需再解压此内层 ZIP。
