# Offline demonstration

[简体中文](zh-CN/demo.md)

Watch the v0.2 report in [English](assets/v0.2/demo.en.webm) or
[Simplified Chinese](assets/v0.2/demo.zh-CN.webm). Each recording has matching interface
text and captions. The report itself switches languages in the same offline file.
The [record](evidence/v0.2-media.json) identifies the videos, source reports and browser.
The earlier [a2 video](assets/paperdelta-demo.webm) remains historical material.

These are actual reports generated from owned synthetic fixtures, with presentation
captions. They do not measure real-paper accuracy, model quality or human usability.

1. Before the experiment update, seven declared checks agree with supplied evidence:
   Ours 84.1%, baseline 81.0%.
2. Only CSV changes, to Ours 80.9%. Four numeric references, one comparison and one
   recorded figure need review; all LaTeX files remain unchanged.
3. Expand the abstract finding to inspect the selected test rows and their mean.
4. Inspect the false comparison: 80.9% no longer exceeds 81.0%. Related numeric
   patches are withheld until the author handles the claim.
5. Inspect changed figure input identity. Explicitly regenerate the plot; hashes
   do not prove visual correctness.
6. A separate 84.1% → 84.5% case applies four guarded replacements across three
   files, rechecks successfully and restores the original bytes.

Recreate reports with `python tools/demo.py --out build/fresh-demo`. To record from
them, the optional development recorder needs Node, Playwright, a browser and its
FFmpeg helper; none is a core checking dependency:

```sh
node tools/record_demo.cjs build/fresh-demo build/recording-en en
node tools/record_demo.cjs build/fresh-demo build/recording-zh zh-CN
```

Use fresh directories. `PAPERDELTA_PLAYWRIGHT`, `PAPERDELTA_BROWSER_EXECUTABLE` and
`PLAYWRIGHT_BROWSERS_PATH` can select existing local development installations.
The recorder never installs software or changes the source paper.
