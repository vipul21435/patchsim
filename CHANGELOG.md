# Changelog

## 0.1.0 (unreleased)

- Unified diff parser with original-file positions for edits and insertions, and strict hunk
  application (exact context, nearest offset, no fuzz) to rebuild post-patch files.
- Metrics: file precision, recall and F1; location Jaccard per file and overall; token multiset
  F1; character n-gram F-score; AST node-type similarity (patch lines or post-patch source);
  changed-function overlap; edit-size ratio and balance.
- Analysis: rank AUC, repository-clustered bootstrap interval, within-instance AUC over pairs of
  candidates for the same task, best single-threshold accuracy against the majority baseline,
  file-set shares and disagreement examples. Empty candidate patches are left out by default.
- `patchsim score`, `patchsim analyze` and `patchsim compare` (paired two-system comparison of
  mean similarity, resolve rate and AUC) with Markdown and JSON output; `--ignore-new-files`,
  `--sources` and `--include-system` options.
- `examples/demo.py` with a toy benchmark; `scripts/` to fetch SWE-bench Verified data and six
  public submissions and to reproduce the README results and chart.
