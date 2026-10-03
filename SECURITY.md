# Security policy

[简体中文](SECURITY.zh-CN.md)

Security fixes target the latest published alpha and the current `main` branch.
Earlier development builds do not receive separate backports. This is a small
project with best-effort responses and no guaranteed response time.

## Report a vulnerability privately

Use [GitHub private vulnerability reporting](https://github.com/amos689/paperdelta/security/advisories/new).
Include the affected version, a minimal reproduction, expected boundary and
observed impact. English and Simplified Chinese reports are welcome. Use synthetic
paper/data inputs where possible; omit credentials and private research material.

Keep vulnerability details out of public issues until a fix or disclosure plan
has been agreed. If the private reporting form is unavailable, open an issue asking
for a private contact route without revealing the vulnerability. The GitHub noreply
address in package metadata is an attribution address, not a support mailbox.

## Security boundaries

The checker reads explicitly configured local evidence. Core checks do not execute
experiments, compile TeX or call a model provider. The optional MCP server exposes
read-only tools; accepting mappings and applying patches remain explicit CLI actions.
Local reports can contain manuscript text, input paths and evidence excerpts, so
review their contents before sharing them.

`apply --write` and `recover --write` modify local files with hash checks and a
recovery journal. They do not provide a power-loss or network-filesystem guarantee.
See [rules and limits](docs/rules.md) and [CI isolation](docs/ci.md). A passing
consistency report does not establish the scientific correctness of a paper.
