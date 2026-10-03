# Third-party research fixtures

PaperDelta's original code is MIT-licensed. Paper sources under
`tests/corpus/papers/` retain the licenses below; the project's MIT license does
not relicense them. No author or upstream project endorses PaperDelta.

Python wheels and source distributions contain PaperDelta's original code and
exclude the third-party corpus and corpus-output JSON. Those materials are
distributed in a separate `paperdelta-evaluation-VERSION.zip` with this notice,
their original notices, file digests and a combined license inventory. The full
repository retains them under their existing paths. See
[local release instructions](docs/local-validation.md).

The [corpus manifest](tests/corpus/manifest.json) records exact commits, download
URLs, byte counts and SHA-256 digests. Preserved `source/` files are unmodified.
Evaluation makes disposable copies and injects synthetic data, numeric values
and contexts. These are test cases, not corrections to the authors' papers or
reproductions of their experiments. Paper text derived from a CC BY-SA work
retains CC BY-SA 4.0.

| Fixture | Work / attribution | License and retained notice |
| --- | --- | --- |
| ml-finance | Akram Khan (2026), *Machine Learning in Quantitative Finance: A Systematic Review of Methods, Applications, and Open Challenges (2015–2025)*, SSRN Working Paper 6562398. [Source](https://github.com/ayk5511/ml-finance-survey) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), [notice](tests/corpus/papers/ml-finance/source/LICENSE) |
| rf-curriculum | Jude Eschete (2026), *An Educational Framework for AI-Driven RF Signal Processing on FPGA*, Master's Capstone Report, Stevens Institute of Technology. [Source](https://github.com/JEschete/cross-domain-rf-ml) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), [paper-specific notice](tests/corpus/papers/rf-curriculum/source/ResearchPaper/LICENSE) |
| hwo-bows | *Chasing rainbows and ocean glints: Inner working angle constraints for the Habitable Worlds Observatory*. Copyright (c) 2023 @mkenworthy. [Source and authors](https://github.com/mkenworthy/HWObows) | [MIT notice](tests/corpus/papers/hwo-bows/source/LICENSE) |
| legwork | *LEGWORK: A python package for computing the evolution and detectability of stellar-origin gravitational-wave sources with space-based detectors*. Copyright (c) 2021 @TeamLEGWORK. [Source and authors](https://github.com/TeamLEGWORK/LEGWORK-paper) | [MIT notice](tests/corpus/papers/legwork/source/LICENSE) |
| reflectometry | A. R. McCluskey and coauthors, *Advice on describing Bayesian analysis of neutron and X-ray reflectometry*. [Source and authors](https://github.com/arm61/reporting_sampling) | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), explicitly declared in the [paper source](tests/corpus/papers/reflectometry/source/src/tex/ms.tex). Its repository MIT notice applies to code, not this manuscript. |
| coronal-abundances | *Modeling Time-Variable Elemental Abundances in Coronal Loop Simulations*. Copyright (c) 2024 @jwreep. [Source and authors](https://github.com/jwreep/ebtel_abundances) | [MIT notice](tests/corpus/papers/coronal-abundances/source/LICENSE) |
| ce-accretors | *Rejuvenated accretors have less bound envelopes*. Copyright (c) 2022 @mathren. [Source and authors](https://github.com/mathren/CE_accretors) | [MIT notice](tests/corpus/papers/ce-accretors/source/LICENSE) |
| pzflow | *Probabilistic Forward Modeling of Galaxy Catalogs with Normalizing Flows*. Copyright (c) 2022 @jfcrenshaw. [Source and authors](https://github.com/jfcrenshaw/pzflow-paper) | [MIT notice](tests/corpus/papers/pzflow/source/LICENSE) |
| rossby-ridge | *Further Evidence of Modified Spin-down in Sun-like Stars: Pileups in the Temperature–Period Distribution*. Copyright (c) 2021 @trevordavid. [Source and authors](https://github.com/trevordavid/rossby-ridge) | [MIT notice](tests/corpus/papers/rossby-ridge/source/LICENSE) |
| centre-of-mass | *Accurate Centre of Mass Estimation*. Copyright (c) 2024 @scams-research. [Source and authors](https://github.com/scams-research/centre-of-mass) | [MIT notice](tests/corpus/papers/centre-of-mass/source/LICENSE) |

Upstream references cited within a paper retain their own copyrights. This
corpus does not include the cited articles, external datasets, PDFs or images.
Repository MIT grants above cover associated source documentation where no
separate manuscript grant was found. Original author and copyright notices
remain in the sources. Dependencies and prior-art probes are listed separately
in [research notes](docs/research.md) and
[package metadata](docs/evidence/package-metadata.json).
