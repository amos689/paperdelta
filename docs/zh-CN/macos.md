# macOS 准备与实机验证

[English](../macos.md)

源码、纯 Python wheel 和原创样例可以按 [Mac 快速开始](../../START_ON_MAC.md)
迁移。Mac 上需重新创建环境，不复制 Windows 虚拟环境、可执行文件或推理模型。
重新构建的 0.2.0a1 迁移包包含当前已通过本地验收的核心。旧 0.1.0a2 包保留为历史
版本，请核对 `TRANSFER.json` 使用匹配的包。

**真实 macOS 运行仍待验证**。工作流定义、Windows 测试或 Linux 上的 POSIX 运行
都不算 Mac 证据。项目方有 Mac，迁移包和验证命令用于之后取得实际结果。

## 架构和安装

macOS 工作流配置了八种组合：

| 运行器 | Python 架构 | Python 版本 |
| --- | --- | --- |
| `macos-15` | Apple Silicon `arm64` | 3.11、3.12、3.13、3.14 |
| `macos-15-intel` | Intel `x86_64` | 3.11、3.12、3.13、3.14 |

标签来自 [GitHub 运行器说明](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)，
指定系统系列及架构，并非固定镜像。每次运行记录实际主机和解释器版本，目前
没有远程 CI 成功记录。

[Python macOS 安装器](https://docs.python.org/3/using/mac.html)提供支持两种架构的
universal2 构建。使用原生解释器和项目虚拟环境。检查器不需要 Homebrew、CUDA、
TeX 发行版或应用签名；安装依赖可能联网，检查过程保持本地运行。

## 实际检查范围

`tools/validate_platform.py` 使用匹配的 wheel，在新的输出目录建立基础安装和
完整测试环境，然后执行：

1. 基础 CLI 成功、仅数据变化导致失败、HTML 输出及未安装 MCP 时的诊断。
2. 已安装包源码身份检查和完整 pytest。
3. 真正的进程锁竞争、中断写入及恢复。
4. NFC/NFD 重音文件名、中文目录及 BOM/CRLF 恢复。
5. POSIX 符号链接根目录、越界链接拒绝和文件权限保持。
6. 真正的 POSIX 伪终端确认与取消，JSON 标准输出与终端提示分开；这些是自动化
   终端操作，不是真人测试。
7. 公开样例、测试中的真实 stdio MCP 以及本地 Git CI 场景。

原生 macOS/Linux 有跳过测试时，脚本不会宣布成功。Windows 可以跳过三项仅限
POSIX 的测试，并如实记录。CI 上传结果 JSON、日志及 JUnit，不上传虚拟环境。
不要求安排真人测试。

使用经过审计的源码仓库而非迁移 ZIP 时：

```sh
python3 tools/validate_platform.py --wheel build/release-candidate/paperdelta-*-py3-none-any.whl --out build/mac-validation --require-system Darwin
```

Apple Silicon 增加 `--expected-arch arm64`，Intel 增加 `--expected-arch x86_64`。
macOS CI 同时检查系统和架构，拒绝把 Rosetta 运行算作原生 Apple Silicon 证据。

路径使用项目中存储的原始拼写和大小写。Unicode 测试保持每种声明拼写一致，不
声称所有文件系统都可互换 NFC/NFD 别名或大小写。网络磁盘和断电耐久性不在
已验证范围内。

## 迁移包和完整性

`tools/build_transfer.py` 从已审计源码包和 wheel 开始。ZIP 包含 Mac 快速开始、
源码、测试、文档、原创样例、`install/` 下的 wheel，以及单独许可的评测 ZIP。
它检查每个文件，在 `TRANSFER.json` 中保留逐文件 SHA256，并在 ZIP 旁生成
`SHA256SUMS`。安装步骤不修改系统 Python。

完整验证脚本在 Windows 上的成功只能验证脚本本身及 Windows 路径。
[历史准备记录](../evidence/macos-preparation.json)列出此前实际检查；Mac 实机结果
必须另行记录。
