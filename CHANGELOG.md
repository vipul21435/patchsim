# Changelog

## 0.1.0 - 2026-11-06

### Added

- Unified diff parser with original-file positions for edits and insertions, merging of
  sections that name the same file, and strict hunk application (exact context, nearest
  offset, no fuzz) to rebuild post-patch files.
- Metrics comparing a candidate patch with the gold patch: file precision, recall and F1;
  location Jaccard per file and overall; token multiset F1; character n-gram F-score; AST
  node-type similarity (from patch lines or post-patch source); changed-function overlap;
  edit-size ratio and balance.
- `patchsim score` to compute the metrics for every candidate in a set of instances.
- `patchsim analyze` with rank AUC against resolved outcomes, a repository-clustered
  bootstrap interval, within-instance AUC over pairs of candidates for the same task, best
  single-threshold accuracy (in-sample, with a leave-one-repository-out accuracy beside it)
  against the majority baseline, file-set shares and disagreement examples. Empty candidate
  patches are left out by default.
- `analyze --vs-metric` for the paired AUC difference between one metric and every other.
- `patchsim compare` for a paired comparison of two systems on mean similarity, resolve rate
  and AUC.
- Markdown and JSON output, and the options `--ignore-new-files`, `--sources` and
  `--include-system`.
- Input checks that stop with a one-line message and exit status 2: missing files, malformed
  lines, missing keys, non-boolean `resolved`, NaN scores, `--level` outside (0, 1), negative
  `--n-boot` or `--examples`, duplicate rows, non-string diffs and non-UTF-8 files.
- `examples/demo.py` with a toy benchmark.
- `scripts/` to fetch SWE-bench Verified data and six public submissions and to reproduce the
  README results table and ROC chart.
- README with usage, a description of each metric, results on real public data, related work
  and limitations.

### Known limitations

See the Limitations section of the README for what is not implemented and how far the
real-data results reach.
