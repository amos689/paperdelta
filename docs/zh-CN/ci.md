# CI 与只改数据的提交

[English](../ci.md)

当前可复用 Action、问题变化、SARIF 及独立 paper-preflight 联合作业见
[1.5 接入指南](v1.5.md)。下方历史验证保留原有范围。

下文执行数量属于 a2 历史证据；当前发行验证见 [0.3.0 说明](v0.3.md)。使用配置
版本 2 的范围、排除及表格单元格时，应固定到 0.3.0 或更新的检查器提交。
适配器按 ID 列出排除变化，并在设置变化中展示范围调整。

仓库 `.github/workflows/ci.yml` 是**工具开发**矩阵：Windows、Linux、macOS，Python
3.11–3.14，只读权限、测试、静态检查、原创样例验证、代码/评测分包、内容审计和
JUnit 留存。每个提交的真实结果和可下载证据见
[Actions 运行记录](https://github.com/amos689/paperdelta/actions/workflows/ci.yml)，
工作流文件本身不构成跨平台证据。

macOS 分为 `macos-15` Apple Silicon 和 `macos-15-intel`，各四个 Python 版本。
[原生验证器](macos.md)将 wheel 安装到纯核心和完整测试环境，核对系统/CPU，执行
真实 POSIX 终端及文件系统测试并保存日志。评估支持范围时，以每项作业记录的
系统、架构及测试数量为准。

开发时从官方仓库解析 checkout v6.1.0、setup-python v6.3.0、upload-artifact v4.6.2，
并在工作流固定提交 ID。更新应明确进行并重验相关检查。

## 论文仓库的工作流

[可复制模板](../../examples/ci/paper-check.yml)检查每个 PR，失败时仍保留产物，最终
保留检查器退出码。论文输入与检查器分别检出；启用前配置仓库变量：

- `PAPERDELTA_REPOSITORY`：`amos689/paperdelta`，或经审查的可信 fork。
- `PAPERDELTA_REVISION`：经审查的完整 40 字符提交 SHA。

从[发行版](https://github.com/amos689/paperdelta/releases)选择经审查的提交，复制完整
SHA，不要换成可变的分支名称；缺设置时模板会拒绝。需要时更换
基线名 `submitted-v1`。历史检出使 PR 目标提交可访问；手动运行采用选定提交。
检查器从固定来源安装；`python -I` 排除论文目录和 `PYTHONPATH` 对导入路径的影响，
只执行可信检查器副本。模板采用只读权限和普通 `pull_request` 事件。

若只做当前状态检查，在干净环境安装可信发行版或 wheel 后运行：

```sh
paperdelta --lang zh-CN -C paper-project check --report build/paperdelta
```

保留退出码作为作业结论，失败时也上传 `paper-project/build/paperdelta/`，把 `report.md`
放入摘要。必要检查不完整是退出 2，不能当作成功。适配器生成含声明变化及当前发现
的 `ci-summary.md`；存在 `GITHUB_STEP_SUMMARY` 时自动追加，遵循 GitHub 的
[作业摘要接口](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary)。
正式安装包同时发布到 PyPI 和 GitHub Releases。CI 中应固定 PaperDelta 版本，明确
安排工具升级；从 GitHub 下载产物时可用 SHA256SUMS 核对。

CSV/JSON、图表、来源记录、配置和 LaTeX 的相关变化都应触发检查。不要只展示 Git
diff 内的 LaTeX 行：`test_data_only_change_finds_every_affected_span_and_false_claim`
只改 CSV，却检查所有受影响论文位置。

历史比较应读取 PR 目标提交中已保存的基线，再用 `--baseline` 指定。不要从本次
修改新建快照并把它称作旧状态。映射、规则、快照和审阅声明的变化也应接受审查，
可编辑本地记录不等于已认证的批准。

不可信论文 PR 中，只执行已安装检查器，不执行论文仓库脚本。使用只读令牌和普通
`pull_request`。当前适配器不写远程评论；下载报告不需要这些权限。

## 目标提交快照包装器

包装器可用 `--lang zh-CN` 或 `--lang en` 切换帮助、诊断、报告和作业摘要，沿用 CLI
的参数、环境、项目偏好、系统语言优先顺序。存储报告及 `ci-context.json` 的机器字段
与身份保持稳定，Git 等第三方原始错误保留其原语言。

在匹配包的环境中，从**可信 PaperDelta 副本**运行 `tools/ci_check.py`：

```sh
python -I /trusted/paperdelta/tools/ci_check.py \
  --project /workspace/paper-repository \
  --base-commit FULL_TARGET_COMMIT_SHA \
  --snapshot submitted-v1 --report build/paperdelta
```

先获取目标提交。适配器直接用 Git 读取该提交的快照 blob，不读取 PR 工作树中同名
文件；报告旁的 `ci-context.json` 记录目标 SHA 和快照哈希。缺少目标快照时明确标记
历史不可用，仍做当前检查；缺提交或快照损坏是错误，不检出或执行目标源文件。

`--config` 选择规范的项目相对配置路径；`--summary-file` 可追加到论文根目录外的
其他 CI 摘要文件，完整检查仍在项目相对目录保存 `ci-summary.md`。输出不能覆盖
检查输入、配置、快照或审阅声明。

## 检查规则自身的变化

版本 1 CI 上下文比较选定配置及 `.paperdelta/baselines`、`.paperdelta/reviews` 的
JSON 文件。每个新增、修改、删除项含类别和目标/当前 SHA256；包括已删除文件和
新声明。配置用核心安全加载器及严格模型解析，分别列出 sources、metrics、
occurrences、claims、figures 的 ID 变化，以及舍入、论文配置、完整覆盖等设置变化。
只改格式仍是文件变化，但语义不变；任一侧无法解析时语义比较不可用，不宣称相等。

声明变化不自动改变数值结论。例如删除四个数值绑定和一个比较后，可能只剩一个
通过绑定；摘要仍必须显示覆盖减少及被删 ID。PR 改写快照会显示为声明变化，历史
比较仍用目标提交的原快照。

只读取普通 Git 元数据文件：最多 2000 个、单文件 32 MiB、每侧合计 64 MiB；配置
仍限 1 MiB。检查中声明变化会报错。摘要转义原文、限制显示行数和值，最大 900 KiB；
完整 JSON 及常规报告保留在产物目录。

## 复现本地示例

在可信检出中安装 Git 和 PaperDelta 后运行：

```sh
python tools/demo_ci.py --out build/ci-demo
```

它创建两个新合成仓库，不改已有论文：

| 场景 | 当前检查 | CI 审查 |
| --- | --- | --- |
| 只改数据，84.1% → 80.9% | 退出 1，五处不一致 | TeX 字节未变，仍显示所有影响 |
| 同样更新并删绑定、改写快照 | 退出 0，剩一个已确认检查 | 列出四个数值位置、一个结论的删除及两个声明文件变化，仍比较原目标快照 |

查看生成的 `build/ci-demo/CASE/build/review/ci-summary.md`，或历史
[只改数据摘要](../evidence/ci-adapter/data-only/ci-summary.md)和
[改变声明摘要](../evidence/ci-adapter/changed-declarations/ci-summary.md)。重跑用新目录。

a2 的十项适配器测试在四个 Windows Python 版本和 Alpine Linux/Python 3.14 上
通过，包括真实 Git 对象、退出码、摘要、隔离导入和输出保护。该时点 Windows 3.12
完整套件通过 162 项。两个工作流通过 [actionlint](https://github.com/rhysd/actionlint)
1.7.12 静态检查。[证据与文件哈希](../evidence/ci-adapter/evidence.json)只证明本地和
静态检查。后续远程结果在 Actions 单独记录，不改变这些原始数量。
