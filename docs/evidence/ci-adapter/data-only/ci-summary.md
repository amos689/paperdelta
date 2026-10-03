# PaperDelta CI review

Current check exit code: **1**.
6 confirmed: 1 pass, 5 mismatch, 0 unknown.
0 unbound numeric candidates; 0 unsupported regions; 0 unregistered figure references.

Target commit: <code>7a7993980ad3488122953d0cfecc8e3d21beb291</code>.
Historical baseline: <code>read_from_target_commit</code>.

## Repository declaration changes

Compared with the target commit. These changes are separate from numerical consistency; snapshot and review files are declarations, not authenticated approval.

| Kind | Path | Change | Target SHA256 | Current SHA256 |
| --- | --- | --- | --- | --- |
| — | No declaration file changes | — | — | — |

Configuration semantics: **unchanged**.

Named-ID lists show at most 50 entries per category; full lists are in JSON.

## Current findings

- <code>VALUE_MISMATCH</code> at <code>paper/abstract.tex:2</code>: <code>&#x27;84.1\\%&#x27; should display &#x27;80.9\\%&#x27; from metric ours</code>
- <code>VALUE_MISMATCH</code> at <code>paper/results.tex:8</code>: <code>&#x27;84.1&#x27; should display &#x27;80.9&#x27; from metric ours</code>
- <code>VALUE_MISMATCH</code> at <code>paper/results.tex:16</code>: <code>&#x27;3.1&#x27; should display &#x27;-0.1&#x27; from metric gain</code>
- <code>VALUE_MISMATCH</code> at <code>paper/appendix.tex:4</code>: <code>&#x27;84.1&#x27; should display &#x27;80.9&#x27; from metric ours</code>
- <code>CLAIM_FALSE</code> at <code>paper/results.tex:17</code>: <code>The confirmed comparison no longer holds for the selected evidence</code>

Full artifacts: report.html, report.json, report.md and ci-context.json.
A successful check covers confirmed bindings; it does not certify the whole paper.
