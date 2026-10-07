# 原生文档审查试验 3

[English](README.md)

本试验对应已批准的 PaperDelta 1.8 工作。样本选择和原件获取已完成；解析器开发、
独立位置标注、批注副本验收和留出评分尚未开始，目前没有准确率结果。

八个新论文家族提供十二份保持原字节的文件：八份 PDF、四份出版社 DOCX 补充材料。
PLOS Genetics、PLOS Medicine、PeerJ 和 Scientific Reports 构成四个元数据分层。
每层首个合格家族用于开发，第二个用于留出评测；正文及补充材料始终属于同一划分。
两侧各四个家族、六份文件。[开发前锁](pre-development-lock.json) 写入前，尚未查看
任何原始版面或结果正文。

[预定方案](protocol-plan.json) 固定了有界元数据窗口、合格条件、家族划分、独立原文
位置标注和全部四类结果。[有效选择锁](selection-lock-cloud-transport.json) 先于原件
下载。[来源清单](sources.json) 保留标题、作者、DOI、许可、分发地址和文件哈希。
原件均采用 CC BY 4.0，著作权归各原作者。评测配套的是受控合成证据，不是复现论文实验。

首次采集误用了 Europe PMC 字段，使两个分层返回空结果。修正后又遇到已停用的 PMC
OA API。最初的空结果、四家族不足记录、采集器快照和修订说明均保留。完成的采集使用
官方公开 PMC Cloud Service。这些传输层修正没有放宽样本窗口、合格条件或划分规则；
修正时仍未查看原始页面或结果正文。

元数据由 PLOS 和 Europe PMC 提供。PMC 原件于 2026-10-07 从 NIH NLM NCBI PubMed
Central Article Datasets 获取。本冻结研究快照不代表 NLM 当前最新数据，也不表示
NLM、NIH 或出版社为本项目背书。详见[官方分发说明](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/)。

在单独冻结实现之前，不得查看留出页面、正文或位置。已发布的 native-v1/native-v2
原件、标注和首次结果保持不变；今后对它们运行属于已见输入回归。开发者标注和自建
测试不属于独立真人研究。
