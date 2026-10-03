# Language selection and stable machine data

[简体中文](zh-CN/languages.md)

The v0.2 development version supports English (`en`) and Simplified Chinese
(`zh-CN`) for CLI help, terminal confirmation, diagnostics, text/Markdown reports
and MCP descriptions and explanations. Offline HTML reports also include both
languages. Complete documentation pairing is in progress; see the [delivery ledger](v0.2-plan.md).

## Choose a language

Place global options before the command:

```sh
paperdelta --lang en -C examples/research-paper check
paperdelta --lang zh-CN -C examples/research-paper check
paperdelta --lang zh-CN -C examples/research-paper doctor
paperdelta --lang zh-CN -C examples/research-paper mcp
```

Selection order is `--lang`, `PAPERDELTA_LANG`, the project's UI preference,
the system message locale, then English. `auto` proceeds to the next source.
Aliases such as `zh_CN` and `en-US` select the corresponding supported language.
An unsupported explicit choice is an error; an unsupported system locale falls
back to English. A manuscript's language does not select the interface language.

Save a project preference with:

```sh
paperdelta -C examples/research-paper settings --language zh-CN
paperdelta -C examples/research-paper settings --format json
```

The only file changed by this operation is `.paperdelta/ui.json`. It is independent
of `paperdelta.yaml` and scientific identities and is ignored in this checkout's
Git configuration. Your paper repository can add the same ignore entry.
Use `settings --language auto` to resume system-language selection. If a preference
file is malformed, an explicit flag bypasses it so it can be repaired:

```sh
paperdelta --lang en settings --language en
```

## Terminal and agent behavior

Chinese confirmation accepts `是`/`否`/`证据`/`取消` in addition to `y`/`n`/`e`/`q`.
The final confirmation accepts `确认` or `accept`. Blank input still skips or cancels.
Neither translated wording nor choosing a language changes which mappings are saved.

MCP tool names, arguments, IDs and annotations stay the same. Descriptions,
explanations and next-action text use the language chosen when the server starts.
Separate server instances retain their own language. A localized MCP view is still
a presentation view, not a complete stored report or writable proposal.

## Scientific records and command results

The report's language selector switches the same offline HTML file. Filters,
search terms and expanded evidence remain in place; search covers both languages.
The initial language follows the command that generated the report. No network,
browser storage or external translation service is required. With JavaScript disabled,
the initially selected version remains readable. Impact links reveal the corresponding
finding and its evidence. Coverage details group by file and rule while retaining
all occurrence counts. Unknown inputs and invalid claims appear before numeric fixes.

Configuration keys, enum values, schema fields, identifiers, file paths and exact
numeric values are language independent. Original manuscript, data and author text
are not translated. The stored version-1 report retains canonical English messages;
human renderers translate live structured messages. Locale changes never change
evidence identities, numeric patches or review state. Third-party diagnostic text
can appear as original technical detail below a translated explanation.

Previously supported configuration/report/snapshot version 1 remains readable.
Historical snapshots are used for comparison without rewriting them. Proposals and
patches remain bound to the tool version: regenerate a2 proposals/patches with v0.2
and review them again before accepting or writing. Existing transaction journals
remain subject to their original byte-identity and recovery checks.

All action commands accept `--format json`, including `propose`, `fix`, `apply`,
`recover`, `snapshot create`, `review record`, `init`, `bind`, `settings` and `doctor`.
Their result objects retain existing result fields and add `command_result_version: 1`
and `command`. An applied patch reports `transaction_id` directly. The default
`check`/`scan` JSON schemas are unchanged. `schema` always emits JSON and `mcp`
reserves standard output for its protocol.

Explicit `--format json` sends a JSON error to standard output with a stable
`error` code, canonical `message` and localized `display_message`. Interactive
prompts remain on standard error. For compatibility, action commands without an
explicit JSON request retain their ordinary error stream behavior; scripts should
always request JSON explicitly.

## Translation maintenance

Catalogs live in `src/paperdelta/locales/en.json` and `zh-CN.json`. `msg()` creates
a canonical string with a message identity and arguments; `tr()` renders UI text.
Language contexts are isolated across asynchronous tasks. Model validators retain
typed error locations and message identities instead of translating a formatted
English traceback. Catalog validation checks key parity and exact placeholders.

| English | 简体中文 |
| --- | --- |
| binding | 绑定 |
| occurrence | 论文位置 / 位置绑定 |
| claim | 结论 |
| proposal | 提案 |
| evidence | 证据 |
| baseline / snapshot | 基线 / 快照 |
| mismatch / unknown | 不一致 / 未知 |
| review / superseded | 复核 / 已失效 |
| recovery | 恢复 |
| aggregation / unit | 聚合 / 单位 |

Add both translations for a new user-facing message. Preserve placeholders and
literal command/configuration names. Run the language tests and catalog check as
part of the normal test suite. Original license texts and frozen evidence logs
retain their original bytes; translate their explanatory documentation instead.
