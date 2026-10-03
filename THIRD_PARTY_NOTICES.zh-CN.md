# 第三方研究样例说明

[English](THIRD_PARTY_NOTICES.md)

PaperDelta 原创代码采用 MIT 许可证。`tests/corpus/papers/` 下论文源码仍适用
下列原许可证，项目的 MIT 许可证不会重新授权这些材料。作者及上游项目均未
为 PaperDelta 背书。本页是说明译文，原始许可文字和作者声明保持不变。

Python wheel 和源码发行包包含原创代码，不包含第三方论文语料及语料评测 JSON。
这些材料放在独立的 `paperdelta-evaluation-VERSION.zip` 中，连同本声明、原声明、
文件摘要及合并许可清单分发；完整仓库保留原路径。
详见[本地发行说明](docs/zh-CN/local-validation.md)。

[语料清单](tests/corpus/manifest.json)记录准确提交、下载地址、字节数及 SHA256。
保存的 `source/` 文件未修改。评测复制到临时目录，再注入合成数据、数值和上下文；
它们是测试案例，不是对作者论文的修正，也不是实验复现。由 CC BY-SA 作品衍生的
论文文本继续采用 CC BY-SA 4.0。

| 样例 | 作品及署名 | 许可证和保留声明 |
| --- | --- | --- |
| ml-finance | Akram Khan（2026），*Machine Learning in Quantitative Finance: A Systematic Review of Methods, Applications, and Open Challenges (2015–2025)*，SSRN Working Paper 6562398。[来源](https://github.com/ayk5511/ml-finance-survey) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)，[声明](tests/corpus/papers/ml-finance/source/LICENSE) |
| rf-curriculum | Jude Eschete（2026），*An Educational Framework for AI-Driven RF Signal Processing on FPGA*，Stevens Institute of Technology 硕士结业报告。[来源](https://github.com/JEschete/cross-domain-rf-ml) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)，[论文专用声明](tests/corpus/papers/rf-curriculum/source/ResearchPaper/LICENSE) |
| hwo-bows | *Chasing rainbows and ocean glints: Inner working angle constraints for the Habitable Worlds Observatory*，Copyright (c) 2023 @mkenworthy。[来源及作者](https://github.com/mkenworthy/HWObows) | [MIT 声明](tests/corpus/papers/hwo-bows/source/LICENSE) |
| legwork | *LEGWORK: A python package for computing the evolution and detectability of stellar-origin gravitational-wave sources with space-based detectors*，Copyright (c) 2021 @TeamLEGWORK。[来源及作者](https://github.com/TeamLEGWORK/LEGWORK-paper) | [MIT 声明](tests/corpus/papers/legwork/source/LICENSE) |
| reflectometry | A. R. McCluskey 及合作者，*Advice on describing Bayesian analysis of neutron and X-ray reflectometry*。[来源及作者](https://github.com/arm61/reporting_sampling) | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)，见[论文源码声明](tests/corpus/papers/reflectometry/source/src/tex/ms.tex)。仓库 MIT 声明适用于代码，不适用于此论文 |
| coronal-abundances | *Modeling Time-Variable Elemental Abundances in Coronal Loop Simulations*，Copyright (c) 2024 @jwreep。[来源及作者](https://github.com/jwreep/ebtel_abundances) | [MIT 声明](tests/corpus/papers/coronal-abundances/source/LICENSE) |
| ce-accretors | *Rejuvenated accretors have less bound envelopes*，Copyright (c) 2022 @mathren。[来源及作者](https://github.com/mathren/CE_accretors) | [MIT 声明](tests/corpus/papers/ce-accretors/source/LICENSE) |
| pzflow | *Probabilistic Forward Modeling of Galaxy Catalogs with Normalizing Flows*，Copyright (c) 2022 @jfcrenshaw。[来源及作者](https://github.com/jfcrenshaw/pzflow-paper) | [MIT 声明](tests/corpus/papers/pzflow/source/LICENSE) |
| rossby-ridge | *Further Evidence of Modified Spin-down in Sun-like Stars: Pileups in the Temperature–Period Distribution*，Copyright (c) 2021 @trevordavid。[来源及作者](https://github.com/trevordavid/rossby-ridge) | [MIT 声明](tests/corpus/papers/rossby-ridge/source/LICENSE) |
| centre-of-mass | *Accurate Centre of Mass Estimation*，Copyright (c) 2024 @scams-research。[来源及作者](https://github.com/scams-research/centre-of-mass) | [MIT 声明](tests/corpus/papers/centre-of-mass/source/LICENSE) |

论文引用的上游文献各自保留版权。本语料不包含这些被引文章、外部数据集、PDF
或图像。没有发现独立论文授权时，上表仓库 MIT 授权适用于其相关源码说明。
作者和版权声明仍保留在原文件中。依赖及既有工作的探测记录另见
[调研记录](docs/zh-CN/research.md)和[包元数据](docs/evidence/package-metadata.json)。

## 可选 Word 依赖

`docx` 扩展使用 python-docx（MIT）及其 lxml 依赖（BSD）。它们作为独立包安装，
保留各自附带的许可说明；PaperDelta 不内嵌这些依赖的源码。生成的 Word 演示与
原生测试样例属于本项目原创材料，与第三方论文语料分开。

## 可选 PDF 依赖

`pdf` 扩展安装 pdfplumber 及其依赖，包括 pdfminer.six、Pillow 和 pypdfium2。
这些包及 PDFium 发行物保留各自声明；PaperDelta 不内置其库源码或原生二进制。
ReportLab 仅作为开发依赖生成原创 PDF 测试样例和演示，安装后的 PDF 工作流
无需 ReportLab，也无需安装 TeX。
