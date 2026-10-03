# Figure provenance fixture

The original synthetic chart uses `research-paper/results/metrics.csv`. Its PDF,
PNG preview and sidecar were produced by `plot_accuracy.py` with Matplotlib.
The full comparison-reversal demo copies these artifacts into its project.

The sidecar is an imported declaration of input, script and output hashes. It is
not an authenticated execution record. When the CSV changes, the checker flags
the figure until its declared dependencies and output are recorded again.

To regenerate inside an already-created demo, explicitly run:

```sh
python -m pip install 'matplotlib>=3.9,<4'
python build/demo/comparison-reversed/scripts/plot_accuracy.py --project build/demo/comparison-reversed
```

Then run `paperdelta -C build/demo/comparison-reversed check`. Its figure provenance
will match again; unresolved numbers and the false comparison will still fail.
The checker itself never calls this script. All material here is original and
covered by this repository's MIT license.
