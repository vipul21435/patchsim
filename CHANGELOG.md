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
- Best-threshold accuracy labelled in-sample, with a leave-one-repository-out accuracy beside
  it; disagreement sets defined by the best threshold, with their counts.
- `analyze --vs-metric`: paired AUC difference between one metric and every other.
- Post-patch AST mode counts the code around removed lines in the pre-patch file, and a line
  in a class body outside any method counts that statement rather than the whole class.
- Bad input (missing file, malformed line, missing key, non-boolean `resolved`) ends with a
  one-line message and exit status 2.
- `patchsim score`, `patchsim analyze` and `patchsim compare` (paired two-system comparison of
  mean similarity, resolve rate and AUC) with Markdown and JSON output; `--ignore-new-files`,
  `--sources` and `--include-system` options.
- `examples/demo.py` with a toy benchmark; `scripts/` to fetch SWE-bench Verified data and six
  public submissions and to reproduce the README results and chart.
- Sections of one diff that name the same file are merged into one file patch, so location
  overlap and post-patch AST keep every hunk.
- Whole-line `#` comments are dropped only in file types where `#` starts a comment, and are
  compared when nothing else changed.
- Parser: `--` and `++` lines inside zero-context hunks stay in the hunk; `diff --git` paths
  may contain spaces. A hunk stated past the end of the file is searched from the end.
- `--sources` reads nothing outside the instance directory. Changed functions end at the
  first line outside the `def` body.
- Input checks: NaN scores, `--level` outside (0, 1), negative `--n-boot` or `--examples`,
  duplicate rows, non-string diffs, non-UTF-8 files, directories given as files, and outcomes
  without system names for more than one system all stop with a one-line message.
