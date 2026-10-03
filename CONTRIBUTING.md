# Contributing

[简体中文](CONTRIBUTING.zh-CN.md)

Use the [English or Chinese issue forms](https://github.com/amos689/paperdelta/issues/new/choose)
for bugs and feature requests. Include the command, version and a minimal original
paper/data example. Remove private paths, credentials and unpublished research from
attachments. Report vulnerabilities through the [security policy](SECURITY.md).

Pull requests use an English template by default. To use Chinese, append
`?template=zh-CN.md` to the new pull request URL before writing (or
`&template=zh-CN.md` if it already has a query). See the
[Chinese template](.github/PULL_REQUEST_TEMPLATE/zh-CN.md). Write in either language;
new user-facing messages and maintained documentation need both translations.

Use Python 3.11+ and install `python -m pip install -e '.[dev,mcp]'`.
Run `python tools/run_tests.py -q`, `python -m ruff check src tests tools` and
`python -m ruff format --check src tests tools`. Tests use fresh project-local
scratch directories under `.tools/test-runs`; do not replace them with a shared
temporary directory that another process might own.

Start with a concrete paper/data example and state what the checker should know,
what it should leave unknown, and which bytes it may change. Useful contributions
include missing parser cases, data identity mistakes, macro contracts, explicit
unit conversions and documentation that reduces first-time mapping work.

Keep the checker independent of model providers, experiment execution and TeX
compilation. A new numeric patch rule needs stale-input, exact-span and recovery
coverage. It must not silently strengthen a scientific claim. Preserve unknown
states and coverage denominators; do not improve a pass rate by dropping cases.

Use original fixtures or record permission and license for imported material.
Public source availability alone does not grant redistribution rights to papers,
figures or datasets. Record upstream attribution for any copied implementation.
Current code was written for this project; related work is in `docs/research.md`.

The default license is MIT. Schema changes should include a migration decision,
version behavior and examples. Cross-platform CI configuration is checked in;
only actual successful runs count as compatibility evidence.

Add English and Simplified Chinese messages together; preserve placeholders and
machine identifiers. Pair maintained documentation pages and link to their matching
translation. See [language conventions](docs/languages.md). Keep original licenses
and frozen study records intact. New studies pin a new implementation identity;
do not update an old lock to make a changed implementation appear reproduced.

Use a GitHub noreply address in this repository's local Git configuration when
contributing with email privacy. Do not place personal addresses in fixtures or
published logs. Third-party author credits and license texts remain intact.
