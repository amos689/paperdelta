# Contributing

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
