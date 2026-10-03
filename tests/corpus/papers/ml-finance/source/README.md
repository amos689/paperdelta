# Machine Learning in Quantitative Finance — A Systematic Review (2015–2025)

This repository accompanies the paper:

> Khan, A. (2026). *Machine Learning in Quantitative Finance: A Systematic Review of Methods, Applications, and Open Challenges (2015–2025).* SSRN Working Paper. <https://ssrn.com/abstract=6562398>

It contains the LaTeX source of the paper, the bibliography, the supplementary survey database, and reproduction notes. The paper argues that the field's most pressing problem is reproducibility, and the materials here are the author's commitment to the same standard.

**Author:** Akram Khan
**ORCID:** [0009-0002-7521-8648](https://orcid.org/0009-0002-7521-8648)
**SSRN abstract:** [6562398](https://ssrn.com/abstract=6562398)
**Contact:** [1819ak@gmail.com](mailto:1819ak@gmail.com)
**Companion paper:** Khan (2026), *Volatility Forecasting with Machine Learning: A Horse Race Across GARCH, HAR, and Tree-Based Models*, SSRN [6663418](https://ssrn.com/abstract=6663418) — empirical case study scoring 2 on the Reproducibility Disclosure Score rubric introduced in §10.5 of this paper. Repository: [github.com/ayk5511/volatility-forecasting](https://github.com/ayk5511/volatility-forecasting).

## Contents

```
ml-finance-survey/
├── README.md                       # This file
├── LICENSE                         # CC BY 4.0 + CC0 + MIT (per artifact)
├── .gitignore
├── data/
│   ├── survey_database.csv         # Annotated survey database (119 rows, growing toward 227)
│   └── README.md                   # Database schema + provenance notes
└── paper/
    ├── main.tex                    # Master LaTeX file
    ├── main.pdf                    # Compiled PDF — the version intended for SSRN distribution
    ├── sections/                   # 13 section files (intro through conclusion + appendix)
    ├── bib/references.bib          # Bibliography
    └── submission-ssrn/
        ├── Khan_2026_ML_Quantitative_Finance_Survey_v2.pdf   # Corrected version (April 2026)
        ├── SSRN_REVISION_v2_NOTES.txt                        # Revision summary
        └── SSRN_SUBMISSION_METADATA.txt                      # Original SSRN submission metadata
```

## Database scope (read this carefully)

The PRISMA flow reported in §2 of the paper is:

> 4,783 unique records → 847 screened → 196 full-text-eligible → +31 from forward/backward citation = **227 included studies**.

The current `data/survey_database.csv` covers **119 of those 227 studies** in full detail (header row plus 119 data rows). The remaining 108 studies are in the screening logs but have not yet been entered into the structured database. Database population is ongoing and will be released in version-tagged updates.

This gap is acknowledged here, in the paper's appendix, and on the SSRN abstract page rather than papered over. If a study you expect to find is missing, please open a [GitHub Issue](https://github.com/ayk5511/ml-finance-survey/issues) with the citation and a one-line method/benchmark note — accepted submissions are added in the next release with attribution.

## What changed in v2 (April 2026)

The first SSRN version (Abstract ID 6562398, distributed 2026-04-12) had a number of issues identified in a pre-distribution self-review. v2 corrects them without changing the paper's argument, methodology, sample size, or quantitative findings. Highlights:

- **Appendix tables completed.** v1 contained an internal "TODO" comment marking the master tables as illustrative; v2 has populated, real tables for all six application domains (return prediction, risk, portfolio, derivatives, microstructure, alternative data).
- **Reproducibility self-honoring.** The paper argued that ~21% code-sharing is the field's worst problem; v2 ships the survey database (119 rows) and full LaTeX source under permissive licenses.
- **Citation hygiene.** Three pairs of duplicate bibliography entries removed; one wrong-year fix; a `\citeyear` rendering bug repaired.
- **Author metadata.** Stable contact email, fixed cover-page date, GitHub and SSRN permalinks added to the author footnote.

The complete change log is in [`paper/submission-ssrn/SSRN_REVISION_v2_NOTES.txt`](paper/submission-ssrn/SSRN_REVISION_v2_NOTES.txt).

## How to cite

```bibtex
@article{Khan2026MLQuantFinanceSurvey,
  title   = {Machine Learning in Quantitative Finance: A Systematic Review of Methods, Applications, and Open Challenges (2015--2025)},
  author  = {Khan, Akram},
  year    = {2026},
  journal = {SSRN Working Paper},
  number  = {6562398},
  url     = {https://ssrn.com/abstract=6562398}
}
```

## Reproducing the paper

```bash
git clone https://github.com/ayk5511/ml-finance-survey.git
cd ml-finance-survey/paper
tectonic main.tex
```

Or with pdflatex:

```bash
cd paper
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

The bibliography compiles with no undefined references against a stock TeX Live distribution. If yours produces warnings, please report them on Issues.

## Contributing

Contributions are welcome via pull request. Useful contributions include:

- **Adding studies** to `data/survey_database.csv` (please follow the schema in `data/README.md`).
- **Correcting errors** in existing rows — wrong years, mis-classified methodologies, missing code links.
- **Suggesting new comparison-table entries** for the appendix.
- **Reporting LaTeX compile issues** on uncommon TeX distributions.

Please open an Issue first for substantive scope changes (new domains, new methodological families) before submitting a PR.

## Licensing

| Component | License |
|-----------|---------|
| Paper text and figures (`paper/main.pdf`, `paper/main.tex`, `paper/sections/`) | CC BY 4.0 |
| Survey database (`data/survey_database.csv`) | CC0 1.0 (public domain dedication) |
| Build scripts and any future code | MIT |

See [`LICENSE`](LICENSE) for full text. The database is released under CC0 to maximize reuse — derivative reviews, meta-analyses, and benchmarks are explicitly encouraged.

## Other links

- [SSRN author page](https://papers.ssrn.com/sol3/cf_dev/AbsByAuth.cfm?per_id=11116668)
- [ORCID profile](https://orcid.org/0009-0002-7521-8648)
