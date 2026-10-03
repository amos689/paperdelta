PaperDelta
==========

`English <#english>`_ · `简体中文 <#chinese>`_ · `GitHub <https://github.com/amos689/paperdelta>`_

English
-------

Review how experiment changes affect an existing research paper. PaperDelta
connects declared CSV/JSON evidence to numbers, comparisons and figure provenance
in LaTeX and optional Word/PDF manuscripts, then shows affected locations in an offline report.

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

Optional Word review: install ``paperdelta[docx]`` and run
``paperdelta demo --document docx --out word-demo --open``. Paragraphs and ordinary
tables use native positions; Word files are read-only and unsupported structures
remain explicit.

Checks cover declared evidence and supported LaTeX/Word/PDF structures. They do not certify
scientific truth or infer a correct mapping from matching numbers alone. The
original implementation is MIT licensed; separately licensed paper evaluation
sources are excluded from the Python distributions.

.. _chinese:

简体中文
--------

检查实验结果变化影响了现有论文的哪些位置。PaperDelta 将明确声明的 CSV/JSON
证据关联到 LaTeX 及可选 Word/PDF 稿件中的数字、比较和图表来源，在离线报告中集中展示待复核内容。

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

可选 Word 检查：安装 ``paperdelta[docx]`` 后运行
``paperdelta --lang zh-CN demo --document docx --out word-demo --open``。
段落和普通表格使用原生位置；Word 文件保持只读，不支持的结构会明确报告。

检查限于已声明证据和受支持的 LaTeX/Word/PDF 结构，不认证科学正确性，也不以数字相同证明
映射正确。原创实现采用 MIT 许可；单独许可的论文评测源码不包含在 Python 发行包中。

PDF and shared manuscripts / PDF 与多稿件
-----------------------------------------

Install ``paperdelta[pdf]`` and run ``paperdelta demo --document pdf --out pdf-demo --open``.
Original-page highlights, explicit source/export comparisons and shared metrics
help find a corrected source whose exported PDF is stale. PDF is read-only;
scans and unreliable content remain unverified. No OCR is performed.

安装 ``paperdelta[pdf]`` 后运行
``paperdelta --lang zh-CN demo --document pdf --out pdf-demo --open``。
原页高亮、明确的源稿/导出稿比较和共享指标，可以帮助发现源稿已更新但 PDF 仍过期的
问题。PDF 保持只读；扫描件及不可靠内容不参与验证，不进行 OCR。

`PDF guide <https://github.com/amos689/paperdelta/blob/main/docs/pdf.md>`_ ·
`PDF 中文指南 <https://github.com/amos689/paperdelta/blob/main/docs/zh-CN/pdf.md>`_

Visual binding workbench / 可视化绑定工作台
--------------------------------------------------------------------

Run ``paperdelta studio`` inside a project to inspect evidence, calculate metrics,
select LaTeX/Word/PDF positions and explicitly save reviewed bindings. The local
browser interface supports English/Chinese, draft download/restore and original-PDF
point selection. No Node.js, cloud account or model key is needed.

在项目中运行 ``paperdelta --lang zh-CN studio``，即可在本地浏览器查看证据、计算指标、
选择 LaTeX/Word/PDF 位置并明确确认绑定。支持中英文、草稿下载/恢复和 PDF 原页点选，
无需 Node.js、云账号或模型密钥。

`Workbench guide <https://github.com/amos689/paperdelta/blob/main/docs/studio.md>`_ ·
`工作台指南 <https://github.com/amos689/paperdelta/blob/main/docs/zh-CN/studio.md>`_
