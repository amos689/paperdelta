PaperDelta
==========

`English <#english>`_ · `简体中文 <#chinese>`_ · `GitHub <https://github.com/amos689/paperdelta>`_

English
-------

Review how experiment changes affect an existing research paper. PaperDelta
connects declared CSV/JSON evidence to numbers, comparisons and figure provenance
in LaTeX, then shows affected locations in an offline report.

Install with Python 3.11 or newer in a virtual environment:

.. code-block:: shell

   python -m pip install paperdelta
   paperdelta demo --out paperdelta-demo --open

The complete original demo ships in the core package. No model key, GPU, TeX,
checkout or plotting dependency is required. The changed scenario intentionally
reports outdated numbers and a false claim; the demo creates files but does not
apply paper edits. Every run uses a new output directory.

Batch binding, explicit review scopes, traceable exclusions and file watching
support repeated review. Reports and CLI prompts support English and Chinese.
Verified numeric edits have a preview and recovery journal. Seventeen optional
MCP tools are available through ``python -m pip install 'paperdelta[mcp]'``.

`Quick start <https://github.com/amos689/paperdelta/blob/main/docs/quickstart.md>`_ ·
`Workflows <https://github.com/amos689/paperdelta/blob/main/docs/workflows.md>`_ ·
`Agent guide <https://github.com/amos689/paperdelta/blob/main/docs/agent-guide.md>`_ ·
`Limits <https://github.com/amos689/paperdelta/blob/main/docs/rules.md>`_

Checks cover declared evidence and supported static LaTeX. They do not certify
scientific truth or infer a correct mapping from matching numbers alone. The
original implementation is MIT licensed; separately licensed paper evaluation
sources are excluded from the Python distributions.

.. _chinese:

简体中文
--------

检查实验结果变化影响了现有论文的哪些位置。PaperDelta 将明确声明的 CSV/JSON
证据关联到 LaTeX 中的数字、比较和图表来源，在离线报告中集中展示待复核内容。

使用 Python 3.11 以上版本，在虚拟环境安装：

.. code-block:: shell

   python -m pip install paperdelta
   paperdelta --lang zh-CN demo --out paperdelta-demo --open

核心包自带完整原创演示，无需模型密钥、GPU、TeX、源码仓库或绘图依赖。变化场景
会有意检出旧数字和失效结论；演示创建文件，不自动修改论文，每次需使用新输出目录。

批量绑定、明确审查范围、可追踪排除和文件监听支持持续使用。报告及命令行支持
中英文；验证后的数值修改可预览并通过事务恢复。安装
``python -m pip install 'paperdelta[mcp]'`` 可使用十七个可选 MCP 工具。

`快速开始 <https://github.com/amos689/paperdelta/blob/main/docs/zh-CN/quickstart.md>`_ ·
`工作流 <https://github.com/amos689/paperdelta/blob/main/docs/zh-CN/workflows.md>`_ ·
`Agent 指南 <https://github.com/amos689/paperdelta/blob/main/docs/zh-CN/agent-guide.md>`_ ·
`限制 <https://github.com/amos689/paperdelta/blob/main/docs/zh-CN/rules.md>`_

检查限于已声明证据和受支持的静态 LaTeX，不认证科学正确性，也不以数字相同证明
映射正确。原创实现采用 MIT 许可；单独许可的论文评测源码不包含在 Python 发行包中。
