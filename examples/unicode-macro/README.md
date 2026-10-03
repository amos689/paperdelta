# Chinese paths and explicit macro arguments

[简体中文](README.zh-CN.md)

This original example uses Chinese filenames and text, JSON Pointer and an
explicitly declared literal macro argument. From the repository root:

```sh
paperdelta -C examples/unicode-macro check --report build/review
```

Expected exit **0**, with one passing binding. `/test/accuracy` selects the test
result; the training value 0.990 is excluded, and the commented 99.0 is not a
candidate. One `score` argument is declared checkable literal text. This does not
enable arbitrary macro expansion.

Changing the test result to 0.845 in a copy reports that 84.1 should become 84.5
and produces a local patch. `tools/validate_examples.py` adds UTF-8 BOM and CRLF
in a copy, applies and recovers the patch, and verifies unchanged bytes outside
its range. This checks source files; it does not configure Chinese PDF fonts or
typesetting.
