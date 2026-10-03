# Educational Framework for AI-Driven RF Signal Processing on FPGA

A five-module progressive curriculum that integrates FPGA digital design, RF communications, embedded firmware, and machine learning into a single hardware-grounded learning sequence, paired with a benchtop reference implementation that instantiates each cross-domain interface as a directly observable design problem.

## Overview

The framework targets senior-undergraduate and master's-level electrical engineering students who have completed introductory coursework in each of the four constituent disciplines individually but lack experience integrating them into a working system. Three STM32 Nucleo nodes (two cooperative targets running a DATA/ACK ping-pong protocol, one interceptor capturing the bidirectional traffic and running a button-gated PAUSE protocol) feed a Digilent Nexys A7-100T FPGA over a 43-byte CRC-protected forwarding frame; the FPGA emits per-emitter feature vectors over USB-UART to a host machine, where four classifier families (random forest, SVM, MLP, 1-D CNN) are trained on a labeled dataset and the deployed pipeline runs against the live FPGA stream.

Modules 1–4 were executed end-to-end on physical hardware. Module 5 is fully specified across eight lab handouts and left as future cohort work. Four cross-domain integration faults surfaced organically during execution and are documented in [TestLog.md](TestLog.md) and the paper.

## Hardware Platform

| Component | Model | Role |
|-----------|-------|------|
| FPGA Development Board | Digilent Nexys A7-100T (Artix-7 `xc7a100tcsg324-1`) | Ingestion, parsing, CRC verification, feature extraction, host export |
| Microcontroller (×3) | STM32 Nucleo-L476RG | Cooperative target A, cooperative target B, interceptor (Threat) firmware |
| LoRa Transceiver (×3) | Adafruit RFM95W (Semtech SX1276) | RF transmission and reception in the U.S. 915 MHz ISM band, 906.5 MHz channel |

## Repository Layout

```text
.
├── Code/
│   ├── Nucleo_RFM95_TargetA/        # STM32 firmware: cooperative target A (DATA initiator)
│   ├── Nucleo_RFM95_TargetB/        # STM32 firmware: cooperative target B (ACK responder)
│   ├── Nucleo_RFM95_Threat/         # STM32 firmware: interceptor (Threat) with PAUSE TX scheduler
│   ├── Nucleo_RFM95W_Base/          # Shared firmware skeleton (LH1-A through LH1-C bring-up)
│   ├── ingest_top/                  # Vivado FPGA project: full Module 2 ingestion pipeline
│   ├── ila_0_ex/                    # Vivado ILA debug-bitstream example for Module 3
│   ├── Nexys_LoopBack/              # Vivado loopback projects for LH1-E toolchain validation
│   ├── AIML/                        # Module 4 ML pipeline (preprocess, train, deploy, live demo)
│   ├── EngagementSim/               # Pre-hardware Python EW engagement simulator (legacy)
│   ├── Tools/                       # Capture, dataset collection, EDA, Vivado-report parsers
│   ├── STM32/                       # CubeMX shared project assets
│   ├── Labs/                        # Lab-handout-specific working files
│   └── NeededFiles/                 # Master XDC and reference assets
├── LessonPlans/
│   ├── Module 1/ ... Module 5/      # Per-module lesson plan + LabHandouts/LH*-A..H
│   ├── Template/
│   ├── glossary.tex
│   └── Curriculum_Sequence.tex      # Top-level curriculum sequence document
├── ResearchPaper/
│   ├── FinalReport/
│   │   ├── Eschete_RF_AI_FPGA_Curriculum.{tex,pdf}    # IEEE-format paper
│   │   └── figures/wiring_diagram.png                 # Per-node hardware wiring (Threat / Target A / Target B)
│   └── Sources/                     # Reference PDFs and bibliography sources
├── Notes/                           # Working references and configuration screenshots
├── Eschete_Presentation.pptx        # Project presentation slide deck
├── TestLog.md                       # Running validation log across all lab handouts
├── FigList.txt                      # Figure inventory for the paper
└── README.md
```

## Curriculum Modules

Each module spans four sessions of ~3 hours and ships eight lab handouts (`LH<n>-A` through `LH<n>-H`) under [LessonPlans/Module N/LabHandouts/](LessonPlans/).

| Module | Topic | Status |
|--------|-------|--------|
| 1 | RF Hardware and Subsystem Design | Executed on hardware (LH1-A through LH1-H) |
| 2 | FPGA RTL Design and Simulation | Executed on hardware (LH2-A through LH2-H) |
| 3 | System Integration and Data Collection | Executed on hardware; C3 (modulation) removed at design time, C4 (distance) deferred under schedule |
| 4 | AI-Driven Classification Pipeline | Executed on hardware (LH4-A through LH4-H), live three-task demo at 2 fps |
| 5 | System Validation and Benchmarking | Fully specified (LH5-A through LH5-H); cohort execution left as future work |

## Headline Results

- **Module 2 ingestion pipeline:** Vivado timing closed at 100 MHz with all 105,975 endpoints meeting setup and hold; CDC report empty; 10/10 verification testbenches pass, including byte-for-byte agreement with an independent Python reference across three recorded captures (clean, mixed, ~5% bit-flipped).
- **Module 3 dataset:** 2,197 labeled feature vectors collected across the TX-power sweep (C1, four levels), the spreading-factor sweep (C2, SF7–SF10), and the active-station-count sweep (C5, configurations C5a and C5b). Nine-check data-integrity audit passed.
- **Module 4 classifiers:** 1-D CNN over 8-frame sequences reaches 0.985 test accuracy on the spreading-factor task (95% Wilson CI [0.965, 0.993]), narrowly outperforming the random forest, SVM, and MLP baselines that all tied at 0.963–0.966 within Wilson-CI overlap.
- **Module 4 live demo:** 362 frames classified across a 3-minute timed run on physical hardware, 2.00 fps aggregate, every frame correctly classified, host inference latency p99 = 1.6 ms (8 ms budget).
- **Documented integration faults:** four cross-domain faults surfaced during execution — a missing NVIC interrupt enable, a synthesis-vs-simulation reset divergence converting block RAM into discrete flip-flops, a missing PA register write breaking link-budget monotonicity, and a session-confounded frequency-error feature — each documented in `TestLog.md` and propagated as corrected procedure into the published handouts.

## Recommended Starting Points

- **Paper (full narrative):** [ResearchPaper/FinalReport/Eschete_RF_AI_FPGA_Curriculum.pdf](ResearchPaper/FinalReport/Eschete_RF_AI_FPGA_Curriculum.pdf) and the corresponding `.tex` source.
- **Curriculum:** [LessonPlans/](LessonPlans/) — start with `Module 1/Module1.tex` for the lesson plan and the `LabHandouts/LH1-*.tex` files for the per-handout deliverables.
- **Validation evidence:** [TestLog.md](TestLog.md) — running record of every executed lab handout.
- **FPGA implementation:** [Code/ingest_top/](Code/ingest_top/) — Vivado project for the Module 2 ingestion pipeline.
- **Firmware:** [Code/Nucleo_RFM95_TargetA/](Code/Nucleo_RFM95_TargetA/), [Code/Nucleo_RFM95_TargetB/](Code/Nucleo_RFM95_TargetB/), [Code/Nucleo_RFM95_Threat/](Code/Nucleo_RFM95_Threat/) — STM32CubeIDE projects for the three roles.
- **ML pipeline:** [Code/AIML/](Code/AIML/) — preprocess, train, select, and deploy scripts; per-stage manifest JSONs and archived run logs under `Code/AIML/Logs/`.
- **Datasets:** [Code/Tools/CampaignCollect/logs/](Code/Tools/CampaignCollect/logs/) — per-campaign CSVs and the merged `merged_dataset.csv`.
- **Pre-hardware engagement simulator (legacy):** [Code/EngagementSim/](Code/EngagementSim/) — Python EW simulator developed during the design phase before the hardware platform came online.

## Status

Modules 1–4 are validated on hardware: evidence is archived in `TestLog.md`, the per-stage manifests under `Code/AIML/`, and the Vivado synthesis/implementation reports under `Code/ingest_top/`. Module 5 cohort execution and the deferred C3/C4 dataset campaigns remain open.

## TODO

- **Add figures to empty references.** A number of `\labfigure` and `\includegraphics` placeholders across the lesson plans and lab handouts still resolve to missing images (and the figure caption is the only thing rendered). The full inventory of expected figures is in [FigList.txt](FigList.txt); each entry needs the corresponding photo, schematic, or screenshot captured and dropped into the relevant `LessonPlans/Module N/Images/` (or per-handout) directory.
- **Formatting pass on all lesson plans and lab handouts.** Tighten layout consistency across [LessonPlans/](LessonPlans/) — section spacing, code-listing widths, table column widths, page breaks before deliverable boxes, and consistent use of the `tcolorbox` info/warning/deliverable styles defined in each module's `LabHandout_Preamble.tex`. The goal is for any handout in any module to look visually identical to any other.

## Citation

If you use this framework or build on its curriculum, please cite:

```bibtex
@techreport{eschete2026rfaifpga,
  title       = {An Educational Framework for {AI-Driven} {RF} Signal Processing on {FPGA}},
  author      = {Eschete, Jude},
  institution = {Stevens Institute of Technology, Department of Electrical and Computer Engineering},
  year        = {2026},
  note        = {Project advisor: Bernard Yett}
}
```

## License

This repository is dual-licensed by content type:

- **Code** (`Code/` — STM32 firmware, FPGA RTL, Python ML pipeline, tooling): [MIT License](LICENSE).
- **Curriculum materials** (`LessonPlans/` — lesson plans, lab handouts, glossary, diagrams): [Creative Commons Attribution 4.0 International (CC BY 4.0)](LessonPlans/LICENSE).
- **Paper** (`ResearchPaper/` — LaTeX source, PDF, figures, bibliography support): [Creative Commons Attribution 4.0 International (CC BY 4.0)](ResearchPaper/LICENSE).

External works referenced by the paper (cited publications, third-party datasheets, IEEE source PDFs) retain their original copyrights and are not covered by these licenses; they are included only as bibliographic supporting material.

## Contact

- **Jude Eschete** — author and primary contributor · [github.com/JEschete](https://github.com/JEschete)
- **Bernard Yett** — project advisor, Stevens Institute of Technology
