# Five explicit seeds, mean, uncertainty and n

[简体中文](README.zh-CN.md)

Run `paperdelta -C examples/seed-statistics check --out build/review` from the
repository root. These are small, owned illustrative results, not a reproduced study.

The same declared observations supply four independently located displays: mean ±
sample SD, n, confidence level and a two-sided Student-t interval. One run per seed,
`ddof: 1`, the analysis unit and the sampling assumption are explicit. The text says
95%; changing the declaration to 90% also invalidates that separately bound level.
The program checks values under the declared assumption; it cannot establish that
experimental runs are independent or normally distributed.

In a copy, change the first result from 80 to 79 and the last from 84 to 85.
The mean stays 82, but the SD and interval change. The affected compound displays
become mismatches. Removing a seed or its value instead produces unknown results;
it never changes n by silently excluding an observation.

See the [statistical guide](../../docs/statistics.md) for display grammar,
precision and supported methods. Word and PDF use the same calculations and
native read-only locations; Studio can bind their compound expressions too.
