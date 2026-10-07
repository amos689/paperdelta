# Third-party research fixtures

[简体中文说明](THIRD_PARTY_NOTICES.zh-CN.md)

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

## Optional Word dependencies

The `docx` extra uses python-docx (MIT) and its lxml dependency (BSD). They are
installed as separate packages and retain their own bundled notices. PaperDelta
does not vendor their source. The generated Word demonstration and native test
fixtures are original project material, separate from the third-party paper corpus.

## Optional PDF dependencies

The `pdf` extra installs pdfplumber and its dependencies, including pdfminer.six,
Pillow and pypdfium2. Their own package and PDFium distribution notices apply;
PaperDelta does not vendor those libraries or their native binaries. ReportLab
is a development-only generator for original PDF fixtures and the bundled demo.
The installed PDF workflow does not require ReportLab or a TeX installation.

## Native Word/PDF study (1.1)

The separately distributed `validation/native-v1/papers/` originals retain **CC BY 4.0**, copyright their respective authors. PaperDelta does not relicense these works; its MIT license covers original tool code. Original PDF/DOCX bytes are unchanged. Annotations, excerpts and reports are study derivatives. Preserve attribution and the [license link](https://creativecommons.org/licenses/by/4.0/) and indicate changes when reusing them. No author endorsement is implied. [Study and source identities](validation/native-v1/README.md).

- **climate-repetition** (development): Yangxueqing Jiang, Norbert Schwarz, Katherine J. Reynolds, Eryn J. Newman. [Repetition increases belief in climate-skeptical claims, even for climate science endorsers](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0307294) (Aug 7, 2024). DOI `10.1371/journal.pone.0307294`; original publisher PDF and DOCX supplement `.s002`.

- **science-journalism** (development): Anne M. Dijkstra, Anouk de Jong, Marco Boscolo. [Quality of science journalism in the age of Artificial Intelligence explored with a mixed methodology](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0303367) (Jun 18, 2024). DOI `10.1371/journal.pone.0303367`; original publisher PDF and DOCX supplement `.s001`.

- **abstract-quality** (held-out): Taesoon Hwang, Nishant Aggarwal, Pir Zarak Khan, Thomas Roberts, Amir Mahmood, Madlen M. Griffiths, Nick Parsons, Saboor Khan. [Can ChatGPT assist authors with abstract writing in medical journals? Evaluating the quality of scientific abstracts generated by ChatGPT and original abstracts](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0297701) (Feb 14, 2024). DOI `10.1371/journal.pone.0297701`; original publisher PDF and DOCX supplement `.s003`.

- **pet-repeatability** (held-out): Gregory D. Ayers, Allison S. Cohen, Seong-Woo Bae, Xiaoxia Wen, Alyssa Pollard, Shilpa Sharma, Trey Claus, Adria Payne, Ling Geng, Ping Zhao, Mohammed Noor Tantawy, Seth T. Gammon, H. Charles Manning. [Reproducibility and repeatability of 18F-(2S, 4R)-4-fluoroglutamine PET imaging in preclinical oncology models](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0313123) (Jan 9, 2025). DOI `10.1371/journal.pone.0313123`; original publisher PDF and DOCX supplement `.s006`.

## Markdown parsing dependency

The core uses markdown-it-py and its mdurl dependency, both under MIT licenses.
They are installed separately, are not vendored, and retain their distributed
license notices. The parser is used for static source structure only; it does
not provide or execute a Quarto/Pandoc engine.

## Native Word/PDF study (1.3)

The twenty original files under `validation/native-v2/papers/` retain **CC BY 4.0**, copyright their respective authors. Original PDF/DOCX bytes are unchanged; annotations, excerpts and result records are study derivatives. Preserve attribution, the [license link](https://creativecommons.org/licenses/by/4.0/) and a description of changes when reusing derivatives. No author endorses PaperDelta. Sources, exact file hashes and the metadata-only family split are in the [study manifest](validation/native-v2/sources.json) and [study guide](validation/native-v2/README.md). The MIT Python distributions exclude these materials; the separately licensed evaluation bundle includes them.

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

## Native Word/PDF study (1.8)

The twelve unchanged originals in `validation/native-v3/papers/` retain **CC BY 4.0**, copyright their respective authors. No endorsement is implied. Preserve attribution, the [license](https://creativecommons.org/licenses/by/4.0/) and a description of derivative changes. PaperDelta’s MIT license covers its original code; these originals are included only in the separate evaluation bundle. [Source URLs, acquisition metadata and exact hashes](validation/native-v3/sources.json) and [study protocol and results](validation/native-v3/README.md) retain the full history.

- **plosgenetics-1011480** (development): Christian Benner, Anubha Mahajan, Matti Pirinen. [Refining fine-mapping: Effect sizes and regional heritability](https://journals.plos.org/plosgenetics/article?id=10.1371/journal.pgen.1011480). DOI `10.1371/journal.pgen.1011480`.

- **plosgenetics-1011507** (held-out): Sara Formichetti, Agnieszka Sadowska, Michela Ascolani, Julia Hansen, Kerstin Ganter, Christophe Lancrin, Neil Humphreys, Mathieu Boulard. [Genetic gradual reduction of OGT activity unveils the essential role of O-GlcNAc in the mouse embryo](https://journals.plos.org/plosgenetics/article?id=10.1371/journal.pgen.1011507). DOI `10.1371/journal.pgen.1011507`.

- **plosmedicine-1004501** (development): Raphaele Houlbracq, Camille Le Ray, Béatrice Blondel, Nathalie Lelong, Anne Alice Chantry, Thomas Desplanches, ENP2021 Study Group. [Episiotomies and obstetric anal sphincter injuries following a restrictive episiotomy policy in France: An analysis of the 2010, 2016, and 2021 National Perinatal Surveys](https://journals.plos.org/plosmedicine/article?id=10.1371/journal.pmed.1004501). DOI `10.1371/journal.pmed.1004501`.

- **plosmedicine-1004504** (held-out): Karin Källén, Mikael Norman, Charlotte Elvander, Christina Bergh, Verena Sengpiel, Henrik Hagberg, Teresia Svanvik, Ulla-Britt Wennerholm. [Maternal and perinatal outcomes after implementation of a more active management in late- and postterm pregnancies in Sweden: A population-based cohort study](https://journals.plos.org/plosmedicine/article?id=10.1371/journal.pmed.1004504). DOI `10.1371/journal.pmed.1004504`.

- **peerj-pmc11740737** (development): . [Do goats recognise humans cross-modally?](https://doi.org/10.7717/peerj.18786). DOI `10.7717/peerj.18786`.

- **peerj-pmc11748422** (held-out): Mitcov Ana, Ko Daegeun, Ko Kwanyoung, Kim Jaeho, Oh Neung-Hwan, Kim Hyun Seok, Choe Hyeyeong, Chung Haegeun. [Composition of soil fungal communities and microbial activity along an elevational gradient in Mt. Jiri, Republic of Korea.](https://doi.org/10.7717/peerj.18762). DOI `10.7717/peerj.18762`.

- **scientific-reports-pmc11782514** (development): Sridhar Arun, Bakke Ingunn, Gopalakrishnan Shreya, Osoble Nimo Mukhtar Mohamud, Hammarqvist Emilie Prytz, Pettersen Henrik P. Sahlin, Sandvik Arne Kristian, Østvik Ann Elisabet, Hansen Marianne Doré, Bruland Torunn. [Tofacitinib and budesonide treatment affect stemness and chemokine release in IBD patient-derived colonoids.](https://doi.org/10.1038/s41598-025-86314-2). DOI `10.1038/s41598-025-86314-2`.

- **scientific-reports-pmc11782508** (held-out): Zaghloul Nourhan A., Gouda Mona K., Elbahloul Yasser, El Halfawy Nancy M.. [Azurin a potent anticancer and antimicrobial agent isolated from a novel Pseudomonas aeruginosa strain.](https://doi.org/10.1038/s41598-025-86649-w). DOI `10.1038/s41598-025-86649-w`.

The optional `pdf` extra also installs pypdf for reviewed copies. It is installed separately, retains its own license, and is not vendored.
