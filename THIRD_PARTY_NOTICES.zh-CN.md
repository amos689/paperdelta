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

## 原生 Word/PDF 试验（1.1）

单独发行的 `validation/native-v1/papers/` 原文件采用 **CC BY 4.0**，版权属于各自作者。PaperDelta 不改变这些作品的许可，MIT 只覆盖原创工具代码。PDF/DOCX 保留原字节，标注、摘录和报告为试验衍生材料。复用时保留作者署名与[许可链接](https://creativecommons.org/licenses/by/4.0/)，注明修改；不暗示作者背书。[试验与来源身份](validation/native-v1/README.zh-CN.md)。

- **climate-repetition** (development): Yangxueqing Jiang, Norbert Schwarz, Katherine J. Reynolds, Eryn J. Newman. [Repetition increases belief in climate-skeptical claims, even for climate science endorsers](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0307294) (Aug 7, 2024). DOI `10.1371/journal.pone.0307294`; original publisher PDF and DOCX supplement `.s002`.

- **science-journalism** (development): Anne M. Dijkstra, Anouk de Jong, Marco Boscolo. [Quality of science journalism in the age of Artificial Intelligence explored with a mixed methodology](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0303367) (Jun 18, 2024). DOI `10.1371/journal.pone.0303367`; original publisher PDF and DOCX supplement `.s001`.

- **abstract-quality** (held-out): Taesoon Hwang, Nishant Aggarwal, Pir Zarak Khan, Thomas Roberts, Amir Mahmood, Madlen M. Griffiths, Nick Parsons, Saboor Khan. [Can ChatGPT assist authors with abstract writing in medical journals? Evaluating the quality of scientific abstracts generated by ChatGPT and original abstracts](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0297701) (Feb 14, 2024). DOI `10.1371/journal.pone.0297701`; original publisher PDF and DOCX supplement `.s003`.

- **pet-repeatability** (held-out): Gregory D. Ayers, Allison S. Cohen, Seong-Woo Bae, Xiaoxia Wen, Alyssa Pollard, Shilpa Sharma, Trey Claus, Adria Payne, Ling Geng, Ping Zhao, Mohammed Noor Tantawy, Seth T. Gammon, H. Charles Manning. [Reproducibility and repeatability of 18F-(2S, 4R)-4-fluoroglutamine PET imaging in preclinical oncology models](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0313123) (Jan 9, 2025). DOI `10.1371/journal.pone.0313123`; original publisher PDF and DOCX supplement `.s006`.

## Markdown 解析依赖

核心使用 MIT 许可的 markdown-it-py 及其 mdurl 依赖。它们作为独立软件包安装，
不复制进本项目源码，保留各自发行包的许可声明。解析器仅用于静态源码结构，
不提供或执行 Quarto/Pandoc 引擎。

## 原生 Word/PDF 试验（1.3）

`validation/native-v2/papers/` 下的二十份原文件保留 **CC BY 4.0**，著作权归各自作者。原 PDF/DOCX 字节未修改；标注、摘录与结果记录属于试验衍生材料。复用时保留作者署名、[许可链接](https://creativecommons.org/licenses/by/4.0/)并说明修改。作者并未为 PaperDelta 背书。来源、精确文件哈希及基于元数据的论文家族划分见[来源清单](validation/native-v2/sources.json)和[试验指南](validation/native-v2/README.zh-CN.md)。MIT Python 分发包排除此材料，单独许可的评测包包含它们。

- **plos-0290868** (development): Joseph Kathono, Vincent Nyongesa, Shillah Mwaniga, Georgina Obonyo, Obadia Yator, Maryann Wambugu, Joy Banerjee, Erica Breuer, Malia Duffy, Joanna Lai, Marcy Levy, Simon Njuguna, Manasi Kumar. [Adolescent perspectives on peripartum mental health prevention and promotion from Kenya: Findings from a design thinking approach](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0290868) (2024-01-02). DOI `10.1371/journal.pone.0290868`.

- **plos-0294127** (held-out): Jose Danilo B. Diestro, Abdelsimar T. Omar II, Yu-qing Zhang, Teruko Kishibe, Alexander Mastrolonardo, Melissa Mary Lannon, Katrina Ignacio, Eduardo Pimenta Ribeiro Pontes Almeida, Anahita Malvea, Ange Diouf, Arjun Vishnu Sharma, Qingwu Yang, Zhongming Qiu, Mohammed A. Almekhlafi, Thanh N. Nguyen, Atif Zafar, Vitor Mendes Pereira, Julian Spears, Thomas R. Marotta, Forough Farrokhyar, Sunjay Sharma. [Perfusion vs non-perfusion computed tomography imaging in the late window of emergent large vessel ischemic stroke: A systematic review and meta-analysis](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0294127) (2024-01-02). DOI `10.1371/journal.pone.0294127`.

- **plos-0303601** (development): B. Dempsey, S. Callaghan, M. F. Higgins. [Providers’ experiences with abortion care: A scoping review](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0303601) (2024-07-01). DOI `10.1371/journal.pone.0303601`.

- **plos-0304516** (held-out): Lijuan Guo, Pin Zhao, Shilong Xue, Zhaowei Zhu. [Association of urinary bisphenol A with hyperlipidemia and all-cause mortality: NHANES 2003–2016](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0304516) (2024-07-01). DOI `10.1371/journal.pone.0304516`.

- **plos-0308906** (development): Inge Dhamanti, Elida Zairina, Ida Nurhaida, Salsabila Salsabila, Fitri Yakub. [Development and validation of trigger tools in primary care: A scoping review](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0308906) (2025-01-02). DOI `10.1371/journal.pone.0308906`.

- **plos-0312751** (held-out): Nader Muthanna, Xiaoyue Guan, Fouad Alzahrani, Badr Sultan Saif, Abdelrahman Seyam, Ahmed Alsalman, Ahmed Es Alajami, Ang Li. [Impact of regenerative procedure on the healing process following surgical root canal treatment: A systematic review and meta-analysis](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0312751) (2025-01-02). DOI `10.1371/journal.pone.0312751`.

- **plos-0317954** (development): Ewilly Jie Ying Liew, Andrei O. J. Kwok, Sharon G. M. Koh, Shairil R. Ruslan, M. Shahnaz Hasan, Yeh Han Poh. [Examining doctors’ business analytics capabilities in using the electronic medical record system for decision-making effectiveness in intensive care units: Impact of the COVID-19 pandemic](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0317954) (2025-07-01). DOI `10.1371/journal.pone.0317954`.

- **plos-0324599** (held-out): Hanen Ben Ameur, Fouad Jamaani, Mohammed N. Abu Alfoul. [The dynamic connectedness among infectious diseases, geopolitical risks, cryptocurrency, and commodity markets: Evidence from a partial and multiple wavelet analysis](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0324599) (2025-07-01). DOI `10.1371/journal.pone.0324599`.

- **elife-110428** (development): Stijn Robben, Patricia Davidson, Rita S Rodrigues Ribeiro, Thomas Voets. [A high-throughput assay for the measurement of Ca<sup>2+</sup> oscillations and insulin release from uniformly sized <i>mouse β-cell (MIN6</i>) spheroids](https://elifesciences.org/articles/110428) (2026-10-05). DOI `10.7554/eLife.110428`.

- **elife-110341** (held-out): Matthew Milton, Sahar H Farag, Diana Garay-Baquero, Jennie Gullick, Kinga Niedobecka, Daniel Burns, Rita Szoke-Kovacs, Patrick Trimby-Smith, Alex Look, Richard Stopforth, Marco Lepore, David K Cole, Laura Denney, Andrew White, Sally Sharpe, Alasdair Leslie, Andres Vallejo, Liku Tezera, Paul Elkington, Salah Mansour. [Human CD1c-autoreactive T-cells recognise <i>Mycobacterium tuberculosis</i>-infected antigen-presenting cells and display cytotoxic effector programmes](https://elifesciences.org/articles/110341) (2026-10-05). DOI `10.7554/eLife.110341`.

- **elife-109903** (development): Pedro A Perez, Chung-Chih Liu, Alessandra Ferrari, Nicole K Littlejohn, John Paul Kennelly, Emma Marie Robinson, Vân TB Nguyen-Tran, Jon Athanacio, Sean B Joesph, Zaid Amso, Peter Tontonoz, Supriya Srinivasan. [NK2R signaling governs intestinal lipid mobilization and mucosal inflammation](https://elifesciences.org/articles/109903) (2026-10-05). DOI `10.7554/eLife.109903`.

- **elife-110200** (held-out): Beth A Shen, Kyle L Asfahl, Bentley Lim, Savannah K Bertolli, Samuel S Minot, Matthew C Radey, Kelsi M Penewit, Billy Ngo, Stephen J Salipante, Christopher D Johnston, S Brook Peterson, Andrew L Goodman, Joseph D Mougous. [The type VI secretion system governs strain maintenance in a wild mammalian gut microbiome](https://elifesciences.org/articles/110200) (2026-10-02). DOI `10.7554/eLife.110200`.
