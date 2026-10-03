# PaperDelta CI review

Current check exit code: **0**.
1 confirmed: 1 pass, 0 mismatch, 0 unknown.
4 unbound numeric candidates; 0 unsupported regions; 0 unregistered figure references.

Target commit: <code>3a8782db1e7dfe07e93508a000d16f2bc59bb29e</code>.
Historical baseline: <code>read_from_target_commit</code>.

## Repository declaration changes

Compared with the target commit. These changes are separate from numerical consistency; snapshot and review files are declarations, not authenticated approval.

| Kind | Path | Change | Target SHA256 | Current SHA256 |
| --- | --- | --- | --- | --- |
| <code>baseline</code> | <code>.paperdelta/baselines/submitted-v1.json</code> | <code>modified</code> | <code>sha256:266c3dc849e2f934343e3f21d87c5211183f8d5b161843441c1c29016774179e</code> | <code>sha256:d64b4619574897e77b6f50d4bc2001e89a7e6723225eba90b88c5aa264d6a08d</code> |
| <code>configuration</code> | <code>paperdelta.yaml</code> | <code>modified</code> | <code>sha256:ffee690f79d0050ac98b544592350891bc5d7951ffae784d8be83df511127769</code> | <code>sha256:ab1928eccf89ca11a01b6cb23c623d32fb528321ad3e109900f9c5286d9016d3</code> |

Configuration semantics: **changed**.

- <code>occurrences</code>: added <code>[]</code>; removed <code>[&#x27;abstract_accuracy&#x27;, &#x27;appendix_accuracy&#x27;, &#x27;gain_text&#x27;, &#x27;table_accuracy&#x27;]</code>; changed <code>[]</code>.
- <code>claims</code>: added <code>[]</code>; removed <code>[&#x27;main_comparison&#x27;]</code>; changed <code>[]</code>.
Named-ID lists show at most 50 entries per category; full lists are in JSON.

## Current findings

No diagnostics from the declared checks.

Full artifacts: report.html, report.json, report.md and ci-context.json.
A successful check covers confirmed bindings; it does not certify the whole paper.
