# Guided bindings and location repairs

[简体中文](zh-CN/guided-bindings.md)

The v0.2 `guide` command constructs a proposal in memory and then opens the same
explicit review used by `bind --interactive`. It does not require nested JSON.
Use a terminal: redirected input is rejected. Choose a language before the command.

## First connection

From a directory containing your paper and results:

```sh
paperdelta init --paper paper/main.tex --data results/metrics.csv
paperdelta --lang en doctor
paperdelta --lang en guide
```

`init` writes an empty configuration and discovery hints. It accepts no bindings.
Use `guide` directly when a configuration already exists. The guide asks for:

1. A source path, an identifier, CSV identity columns and an explicit type for each
   column. Keep model IDs such as `001` as strings. JSON uses an exact JSON Pointer.
2. A result field, exact filters, source unit, aggregation and expected record count.
   `unique` checks for one record; other aggregations require a count you supply.
   If seeds are part of the experiment, explicitly choose the seed column and set.
   CSV filter text and string seeds retain spaces and leading zeros. Do not insert
   separator spaces into a seed list unless they are part of the seed identity.
3. The exact paper locations, a binding name, display format and an explanation of
   their experimental identity. You can select ten or more locations together;
   identifiers receive `_1`, `_2`, etc. Equal numbers alone never select locations.
4. An optional further group, followed by evidence review for each proposed binding.
   Choose `y` for the bindings you want and type `accept` at the final prompt.

The source unit and displayed format are separate: a `fraction` of `0.841` can be
shown as a percentage `84.1\%`. Existing metrics can be reused. Derived metrics
support differences, ratios, percentage point differences and relative changes.

Entering `:q`, reaching end of input or interrupting construction cancels without
saving mappings. During final review, blank input skips a binding and a blank final
confirmation cancels. Source/configuration changes require a fresh proposal.
Acceptance saves a configuration backup and leaves paper/result bytes unchanged.

The context builder avoids depending on neighbouring numeric candidates. A numeric
patch can therefore update multiple locations without making their anchors depend
on the old neighbouring values. Indistinguishable or contextless positions are
rejected with a request for distinguishing text. Unsupported dynamic TeX remains
unknown. The guide does not infer scientific identities or rewrite claims.

## A moved file or edited sentence

Update the manuscript's `\input` paths after moving files; the current entry point
must still be readable. Keep a snapshot before editing when possible:

```sh
paperdelta snapshot create before-edit
```

After editing, inspect broken locations and choose replacements:

```sh
paperdelta repair scan --baseline before-edit
paperdelta --lang en repair guide --baseline before-edit
```

The baseline is optional. With one, review includes the previous recorded text;
without one, the old anchor definition is shown, without inventing missing history.
Numeric repairs select an explicit current candidate. Claim repairs require an
explicit reachable file and a unique exact sentence. Review the new wording yourself:
the stored predicate and experiment scope remain unchanged.

Repairs only change the paper file/anchor of an existing occurrence or claim. They
cannot substitute a metric, unit, display rule or predicate. Source declarations,
figure records and a moved entry point still require deliberate configuration edits.
Equal-valued candidates are never automatically chosen. A repaired location can still
have a numeric or claim mismatch; repairing its location does not assert consistency.

For scripts, copy a `candidate_id` from `repair scan` and supply an explicit binding:

```sh
paperdelta repair propose --binding occurrences:abstract_accuracy --candidate CANDIDATE_ID --rationale "Abstract moved; same experiment" --out repair.json
paperdelta repair apply repair.json --format json
paperdelta repair apply repair.json --accept occurrences:abstract_accuracy --format json
```

For a claim, replace `--candidate` with `--file paper/results.tex --exact "Current sentence."`.
The preview includes both definitions, current context and a recomputed report.
`--interactive` can replace `--accept`. Acceptance is guarded by input hashes and a
write lock, and returns the backup path. A partial acceptance invalidates the remaining
old proposal because the configuration has changed: rescan and propose the remainder.
Do not restore a backup over subsequent work without reviewing its differences.

## The same construction stages for agents

The MCP adapter exposes thirteen read-only tools. The original five remain available;
six new construction stages share the guide's builder:

| Tool | Explicit choices |
| --- | --- |
| `start_binding_draft` | Read current source samples and candidate IDs |
| `add_draft_source` | Path, format, CSV column types and primary key |
| `add_draft_metric` | Source, field, unit, aggregation, filters, expected count/seeds |
| `add_draft_derived` | Operation and two existing metric IDs |
| `add_draft_locations` | Candidate IDs, names, display and experimental rationale |
| `finish_binding_draft` | Recheck and return a proposal for author review |

Carry `draft_json` unchanged from one stage to the next. Exact filter and seed values
are strings; the declared column type decides how to interpret them. The draft's
identity and all observed input hashes are checked at every stage. Decimal selectors
remain exact through JSON round trips. See `paperdelta schema binding-draft`.

`scan_binding_repairs` and `propose_binding_repair` provide read-only repair discovery
and single-binding proposals. There are no MCP acceptance, file-writing or review
attestation tools. Store a returned proposal only after inspecting it, then use the
normal CLI review. A valid proposal is evidence of structural consistency, not proof
that the agent chose the correct experiment. Abstention remains appropriate when the
experiment identity is unclear.

Local scripted terminal tests cover ten repeated locations, Chinese/English
equivalence, ambiguity, exact typed identity, cancellation, stale inputs, repair
selection and byte-exact numeric recovery. They are machine checks, not independent
human-use or model-quality evidence; see the [implementation ledger](v0.2-plan.md).
