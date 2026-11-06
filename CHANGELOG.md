# Changelog

## 0.1.0 (unreleased)

- Unified diff parser with original-file positions for edits and insertions.
- Metrics: file precision, recall and F1; location Jaccard per file and overall; token multiset
  F1; character n-gram F-score; AST node-type similarity (patch lines or post-patch source);
  changed-function overlap; edit-size ratio and balance.
- Analysis: rank AUC, repository-clustered bootstrap interval, best single-threshold accuracy
  against the majority baseline, file-set shares and disagreement examples.
- `patchsim score` and `patchsim analyze` with Markdown and JSON output.
- `examples/demo.py` with a toy benchmark.
