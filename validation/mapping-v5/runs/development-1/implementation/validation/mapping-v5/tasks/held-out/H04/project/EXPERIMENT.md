# Author's data export notes

Record identity columns are dataset, model, checkpoint, split, seed. All five are strings; preserve leading zeros in seed IDs. Measurement fields are decimal values.

The authoritative evidence file for the requested result is results/export.json.

Use the saved mean at runs -> evaluation/test -> score.mean in the JSON export. The neighboring CSV is a separate trial log. JSON values are fractions; its explicit metadata identifies the experiment and complete seed set.

score stores fraction accuracy (0 to 1).
