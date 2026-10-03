# 在 Mac 上开始使用 PaperDelta

这是从 Windows 项目整理的便携源码包，版本 0.1.0a2。包含源码、文档、测试、
原创示例和 Python wheel；不含 Windows 虚拟环境、临时结果或本地模型权重。
尚未取得真实 Mac 的运行结果，下面的命令用于开始使用及补充验证。

## 1. 拷贝和解压

将 `paperdelta-0.1.0a2-mac-transfer.zip` 通过 U 盘、移动硬盘或网盘复制到 Mac，
双击解压。把解压后的 `paperdelta-0.1.0a2` 文件夹放到你希望保存项目的位置。
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
.venv/bin/python -m pip install ./install/paperdelta-0.1.0a2-py3-none-any.whl
.venv/bin/python -m paperdelta -C examples/research-paper check --report build/review
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

详细的架构与验证范围见 [macOS 适配说明](docs/macos.md)。
`install/paperdelta-evaluation-0.1.0a2.zip` 是可选的真实论文评测材料，
有单独的许可说明；上述使用和测试步骤不要求解压它。
