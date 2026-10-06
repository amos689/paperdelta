# Share and replay a selected review

[简体中文](zh-CN/review-bundle.md)

A portable review contains selected reports and optionally the exact inputs needed
to reproduce the accepted checks. It retains the complete configured declarations,
review scope and exclusions. Selecting fewer files never silently reduces the
checked scope. Hashes establish byte integrity, not authorship or approval.

## Export from Studio

1. Open **Share selected review files**. Optionally name an existing comparison snapshot.
2. Choose HTML, JSON, Markdown or SARIF reports. Raw inputs start unchecked.
3. Select input files, or explicitly choose **Select all inputs required for replay**.
4. Preview the scope, results, file list and contents. Text previews show up to 4,096
   characters; the full selected file is included. Binary inputs show size and hash.
5. Confirm you have reviewed the selection, then download the ZIP.

Reports can contain original manuscript text, evidence values, paths and native
page previews. Inspect the selection before sharing it. No upload is performed.
Changing files or language invalidates the old confirmation. Changed input bytes
make export fail until a fresh preview is reviewed.

## Use the CLI

From the paper directory, prepare a complete selection:

```sh
paperdelta bundle preview --all-inputs --baseline submitted-v1 --out review-plan.json
```

Read `review-plan.json` before creating the archive. Omit `--baseline` if no saved
comparison is wanted. To choose a subset, replace `--all-inputs` with repeated
`--input relative/path` arguments. A report-only selection omits both. Select report
formats with `--reports html json md sarif` (default: HTML and JSON).

```sh
paperdelta bundle create --plan review-plan.json --out paperdelta-review.zip
paperdelta bundle inspect paperdelta-review.zip
paperdelta bundle replay paperdelta-review.zip --out reproduced-review
```

Creation refuses to overwrite an existing archive. Replay requires a new output
directory, the exact recorded PaperDelta version and the optional readers required
by the original manuscript. Install `paperdelta[docx,pdf]==1.5.0` for a 1.5.0 bundle
with Word/PDF. Place the archive inside your chosen local working directory.

`inspect` verifies the listed bytes and previews; it does not establish that a
report's scientific claim is true. Only complete input selections are replayable.
Replay reruns checking, compares report content and scope, and preserves failing
or incomplete checks: a reproduced mismatch still exits 1; an incomplete or changed
result exits 2. No scripts, notebook cells or document macros are executed.

The output JSON points to the fresh HTML report. Original inputs, binding IDs,
review scope and exclusions remain intact. A partial archive can still be viewed
but cannot be presented as a reproduced complete check.

## Limits

At most 512 selected files, 32 MiB per file, 128 MiB combined selected contents and
a 160 MiB archive are supported. Portable file names are required. Unlisted members,
duplicate or colliding names, traversal paths, Git metadata, symbolic links,
encrypted members and mismatched bytes are refused. The manifest is unsigned;
trust the sender separately from byte verification. Keep the JSON plan and ZIP
outside any declared manuscript/input paths.
