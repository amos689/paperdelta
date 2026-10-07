# Native review study 3

[简体中文](README.zh-CN.md)

This is the preregistered document study for the approved PaperDelta 1.8 work.
Selection and acquisition are complete; parser development, gold annotation,
annotated-copy validation and held-out scoring have not started. There are no
accuracy results yet.

Eight new article families provide twelve unchanged originals: eight PDFs and
four publisher DOCX supplements. PLOS Genetics, PLOS Medicine, PeerJ and Scientific
Reports supply the four metadata strata. Each first eligible family is used for
development and each second for held-out evaluation. An article and its supplement
stay together: four families and six files per split. No original layout or result
text was inspected before the [pre-development lock](pre-development-lock.json).

[The plan](protocol-plan.json) fixes bounded metadata windows, eligibility, the
family split, independent original-position annotation and all four outcomes.
[The authoritative selection lock](selection-lock-cloud-transport.json) precedes
original-file downloads. [Sources](sources.json) retain titles, authors, DOI,
licenses, distribution URLs and exact file hashes. All originals are CC BY 4.0;
their authors retain copyright. These articles are paired with controlled
synthetic evidence, not reproductions of their experiments.

The first attempt used an invalid Europe PMC field and returned no candidates for
two strata. The corrected attempt encountered the retired PMC OA API. The original
zero-result records, four-family shortage lock, collector snapshots and amendments
remain here. The completed collection uses the official public PMC Cloud Service.
Sample windows, article eligibility and split rules were not relaxed after these
transport corrections; original pages and result text had not been inspected.

Metadata is provided by PLOS and Europe PMC. PMC originals were accessed through
the NIH NLM NCBI PubMed Central Article Datasets on 2026-10-07. This frozen research
snapshot does not represent the most current data available from NLM. No NLM, NIH
or publisher endorsement is implied. See the [official distribution documentation](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/).

Held-out pages, text and positions must remain uninspected until a separate
implementation freeze. Published native-v1/native-v2 originals, gold and first
results remain unchanged; future runs on them are observed-input regressions.
Developer annotation and authored tests are not independent human studies.
