# 本地验证与候选发行包

[English](../local-validation.md)

发行验收采用机器测试与开发者审查。非正式用户反馈与这些测量分开，不作为发行
门槛。当前范围见 [0.5 发行检查](v0.5.md)，各次平台运行和文件哈希随发行版附上。
[a2 历史验收](release-acceptance.md)不自动覆盖之后的代码。

## 当前检查入口

[v0.2 验收记录](v0.2-acceptance.md)链接历史代码的证据：四个 Windows Python 安装版本、
双语纯核心 wheel、语料回归、性能、浏览器及实际开发者操作。下方历史平台表仍是 a2 证据。

在 Python 3.11+ 开发环境运行：

```sh
python -m pip install -e '.[dev,mcp]'
python tools/run_tests.py -q
python -m ruff check src tests tools
python -m ruff format --check src tests tools
python tools/check_docs.py
python tools/validate_examples.py --out build/example-replay
python tools/demo_ci.py --out build/ci-replay
```

输出目录须新建；测试包装器选择项目内临时目录。对于已准备好的**非 editable
安装环境**：

```sh
python tools/validate_python_matrix.py \
  --python .venv-py311/Scripts/python.exe \
  --python .venv-py313/Scripts/python.exe \
  --python .venv-py314/Scripts/python.exe \
  --out build/python-matrix-replay
```

此程序不安装软件。各环境须事先安装匹配代码和 dev/MCP 依赖。它核对导入源码及
资源身份、保存 JUnit/日志，也支持 `.venv-3.11/bin/python` 等 POSIX 环境路径。

## 历史平台证据

| 环境 / 版本 | a2 实际证据 |
| --- | --- |
| Windows 3.11.17 / 3.12.14 | 各 162 项完整测试，独立非 editable 3.11 安装及单独纯核心 wheel 验证 |
| Windows 3.13.16 / 3.14.8 | 各 151 项完整测试，随后分别运行 2 项进程及 10 项 CI 适配测试 |
| Alpine 3.24.2，内核 6.18.52，x86_64，Python 3.14.8 | 151 项零跳过，纯核心安装、真实 MCP/Git、样例及冻结映射控制；进程/CI 后续单独运行 |
| Ubuntu Base 24.04.5 / glibc 2.39 用户空间 | Python 3.11.17 / 3.12.15 / 3.13.16 / 3.14.8 各 162 项零跳过，安装包、纯核心、样例和 CI 演示 |
| Mac 准备 | Windows 167 项中 164 通过、3 项 POSIX 跳过，只验证启动流程，不代表 Mac |

Windows 矩阵依赖包括 Pydantic 2.13.5、PyYAML 6.0.3、pylatexenc 2.11、MCP 2.2.0、
pytest 9.1.1。Linux 位于项目内 QEMU 11.1.0 软件模拟，两个虚拟 CPU、3 GiB 内存；
Ubuntu Base 是 Alpine 内核下 ext4 磁盘中的 chroot，不是启动 Ubuntu 或远程执行器。
模型运行时不是依赖；模拟环境计时不是性能证据。

额外 CPython 来自项目内 uv 0.12.22/python-build-standalone，未改系统 Python、
PATH 或注册表。QEMU/Alpine/Ubuntu/uv 下载均核验发布者哈希。环境与测试路径含
中文和空格，拥有的虚拟机运行后关机，回环服务关闭。

原始证据及准备失败分别保留：

- [Windows 151 项矩阵](../evidence/python-matrix-mapping.json)、
  [a1](../evidence/python-matrix.json)、[较早 a2](../evidence/python-matrix-a2.json)、
  [交互测试](../evidence/interactive-validation.json)。
- [Alpine 执行](../evidence/linux-alpine-a2/evidence.json)、
  [JUnit](../evidence/linux-alpine-a2/junit.xml)、
  [来源](../evidence/linux-alpine-a2/provenance.json)。
- [glibc 执行](../evidence/linux-glibc-a2/evidence.json)、
  [矩阵](../evidence/linux-glibc-a2/matrix.json)、
  [来源及准备失败](../evidence/linux-glibc-a2/provenance.json)、
  [Windows 包装器回归](../evidence/linux-glibc-a2/windows-evidence.json)。
  首次程序沿 POSIX venv 链接到了基础解释器，保留调用路径后修正；核心与测试未变。
- [Windows 进程检查](../evidence/process-writes-windows.json)、
  [Linux 进程检查](../evidence/process-writes-linux/evidence.json)、
  [CI 适配器](../evidence/ci-adapter/evidence.json)、
  [Mac 准备](../evidence/macos-preparation.json)。

两个真实进程场景在写入者完成首个文件替换后暂停。其他应用/恢复返回 WRITE_LOCKED，
且不修改文件。一项继续完成，另一项被强制终止，留下 RECOVERY_REQUIRED；恢复
全部原字节后原补丁可再次执行。它验证本地进程死亡，不保证断电、网络文件系统或
任意第三方编辑。

## 其他检查与解释

| 检查 | 入口 / 证据 |
| --- | --- |
| 三个样例、中文/BOM/CRLF 补丁恢复 | `tools/validate_examples.py`；[记录](../evidence/owned-examples.json) |
| 比较逆转及正向数值变化 | `tools/demo.py`；[记录](../evidence/workflow-demo.json) |
| Calkit/scitexlintr 工作流 | [对比](comparison.md) |
| 原始语料和 a2 重放 | [评测](evaluation.md) |
| 500 指标 / 20 文件 / 10 MB CSV | `tools/benchmark.py`；[a2 记录](../evidence/performance-final.json) |
| 离线报告 | [a2 浏览器](../evidence/report-browser-qa.json)、[v0.2 双语浏览器](../evidence/v0.2-report-browser.json) |
| 原创 TeX 编译 | [编译记录](../evidence/tex-smoke.json) |
| 纯核心安装 | [a2 安装](../evidence/package-smoke-a2.json) |
| 身份与拒答评分 | [冻结控制](../evidence/mapping-controls/evidence.json)、[分步跟进](staged-model-evaluation.md) |
| 目标快照/声明变化 | `tools/demo_ci.py`；[CI 指南](ci.md) |

当时内置编译器无法解析平台目录，改由项目内已核验 Tectonic 0.17.0 编译补丁前后
原创样例，有非致命 Fontconfig 提示；核心用户无需安装 TeX。自动化与 AI 操作均不
增加独立参与者，也不生成真人耗时。

## 构建与审计

```sh
python tools/build_release.py --out build/release-candidate
python tools/audit_release.py --directory build/release-candidate
```

版本决定三个文件名：`paperdelta-VERSION-py3-none-any.whl`、
`paperdelta-VERSION.tar.gz`、`paperdelta-evaluation-VERSION.zip`。
wheel/源码包含原创 MIT 代码、测试、原创样例和配对文档。另有许可的论文及输出仅
放入独立评测 ZIP，保留声明。聚合许可表达式 `MIT AND CC-BY-4.0 AND CC-BY-SA-4.0`
不改变各组件许可；原创映射题集及控制仍为 MIT。

审计只读归档，不解压、不执行；核验 wheel RECORD、当前源码/语言包/资源、全部
维护文档、样例、测试/工具、许可、原语料字节及冻结协议身份。历史试验须对照自己的
保存实现，不能把锁改成新实现。发行包不得带环境、模型、原生程序、事务或凭证。
`package-audit.json` 是包外哈希记录。

Git 属性禁止冻结语料/证据/评测换行转换，不得更新锁来使新代码通过，见
[Git 字节审计](../evidence/corpus-git-identities.json)。重放使用已见输入，不是新的
留出评测。构建工具不会对外发布。

历史审计：[a1](../evidence/package-audit.json)、[a2](../evidence/package-audit-a2.json)、
[映射](../evidence/package-audit-mapping.json)、[Linux](../evidence/package-audit-linux.json)、
[进程](../evidence/package-audit-process.json)、[CI](../evidence/package-audit-ci.json)、
[glibc](../evidence/package-audit-glibc.json)、[最终 a2](../evidence/package-audit-final.json)。
[最终 a2 安装/身份](../evidence/release-replay-final.json)属于
`build/release-candidate-final`，不属于 v0.2。中间包保留自身证据；只更新文档不等于
重新执行平台测试。

## 产品收敛后的 Mac

实机验证前，无需模型即可重放历史试验：

```sh
python tools/replay_study.py mapping-v1 --out build/mapping-replay
python tools/replay_study.py staged-v2 --out build/staged-v2-replay
python tools/replay_study.py staged-v3 --out build/staged-v3-replay
python tools/replay_study.py corpus-a2 --out build/corpus-a2-replay
python tools/regress_corpus.py --out build/current-corpus-regression
```

前四项将哈希核对后的归档实现复制到新工作区，与保存结果逐项比较。语料模式需要
独立语料包。最后一项用当前核心检查同一批已见输入，先保存新协议，再比较所有
结果，不重写旧锁。`evaluations/implementations` 保存带提交及字节身份的原创 MIT
历史代码；重新评分不需要模型权重。

使用重新审计且版本匹配的包，按[中文迁移指南](../../START_ON_MAC.md)或
[英文指南](../../START_ON_MAC.en.md)操作。[原生验证](macos.md)创建新环境，拒绝错误
系统/架构或 Rosetta。需要项目方在真实 Mac 执行；可迁移 ZIP 本身不是兼容性证据。
