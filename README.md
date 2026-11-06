# patchsim

Measure how far textual similarity to the gold patch goes as a proxy for the correctness of a candidate patch.

## Why this is hard

A bug usually has more than one correct fix. A candidate can touch another file, guard the
input at the caller instead of the callee, or rewrite a loop the gold patch only adjusted, and
still pass the tests; another candidate can differ from the gold patch by one character and fail.
Benchmarks such as SWE-bench (Jimenez et al., "SWE-bench: Can Language Models Resolve Real-World
GitHub Issues?", ICLR 2024, arXiv 2310.06770) therefore judge a patch by running tests, and
similarity to the reference is at best a proxy. How good a proxy it is depends on the metric
(files, lines, tokens, characters, syntax), and the answer needs an uncertainty interval that
respects the fact that instances from the same repository are not independent. patchsim computes
the metrics and measures how well each one separates resolved from unresolved candidates.

## Install

```
pip install git+https://github.com/vipul21435/patchsim
```

Python 3.10 or newer; no runtime dependencies beyond the standard library.

## Quickstart

`examples/demo.py` writes a toy benchmark (8 gold patches over 3 made-up repositories, 12
candidates from two made-up systems, hand-set outcomes) and runs `patchsim analyze` on it:

```
$ python examples/demo.py /tmp/patchsim-demo
# patchsim analysis

12 candidates, 7 resolved, 3 repositories; 500 cluster-bootstrap replicates, seed 0.

Empty candidate patches: 0, excluded.
AST mode per candidate: patch_lines 12.

| metric | n | AUC | 95% interval | within-instance AUC | best accuracy | threshold | majority |
|---|---|---|---|---|---|---|---|
| file_precision | 12 | 0.529 | [0.250, 0.750] | 0.375 [0.250, 0.500] | 0.583 | 1.000 | 0.583 |
| file_recall | 12 | 0.529 | [0.250, 0.750] | 0.375 [0.250, 0.500] | 0.583 | 1.000 | 0.583 |
| file_f1 | 12 | 0.529 | [0.250, 0.750] | 0.375 [0.250, 0.500] | 0.583 | 1.000 | 0.583 |
| location_jaccard | 12 | 0.529 | [0.250, 0.750] | 0.375 [0.250, 0.500] | 0.583 | 1.000 | 0.583 |
| token_f1 | 12 | 0.786 | [0.500, 1.000] | 0.750 [0.500, 1.000] | 0.750 | 1.000 | 0.583 |
| chrf | 12 | 0.743 | [0.500, 1.000] | 0.750 [0.500, 1.000] | 0.750 | 1.000 | 0.583 |
| ast_similarity | 12 | 0.657 | [0.625, 0.750] | 0.875 [0.750, 1.000] | 0.750 | 0.857 | 0.583 |
| function_jaccard | 12 | 0.529 | [0.250, 0.750] | 0.375 [0.250, 0.500] | 0.583 | 1.000 | 0.583 |
| edit_size_balance | 12 | 0.500 | [0.500, 0.500] | 0.500 [0.500, 0.500] | 0.583 | 1.000 | 0.583 |

Within-instance AUC uses only pairs of candidates for the same instance, one resolved and one not (4 instances, 4 pairs for the first metric).

## File sets

- resolved touching files outside gold: 1 of 7 (0.143)
- resolved missing gold files: 1 of 7 (0.143)
- unresolved touching exactly gold files: 4 of 5 (0.800)

## Disagreements (chrf)

high similarity unresolved:
- acme__widgets-1 (sys-b): 0.872
- gamma__cli-1 (sys-a): 0.746
- acme__widgets-3 (sys-a): 0.634

low similarity resolved:
- gamma__cli-2 (sys-a): 0.528
- beta__parse-3 (sys-a): 0.569
- acme__widgets-2 (sys-a): 0.870

different files, resolved:
- gamma__cli-2 (sys-a): cli/compat.py
```

These numbers describe the toy data only. The three subcommands on your own files:

```
patchsim score   --candidates preds.jsonl --gold gold.jsonl --out rows.jsonl
patchsim analyze --candidates preds.jsonl --gold gold.jsonl --outcomes results.json \
                 --n-boot 2000 --json analysis.json --markdown analysis.md
patchsim compare --candidates preds.jsonl --gold gold.jsonl --outcomes results.json \
                 --a system-one --b system-two --markdown compare.md
```

Options shared by all three:

- `--ignore-new-files` sets aside files a candidate creates that the gold patch does not touch
  (reproduction scripts and scratch tests that agents often leave in their final diff); the
  dropped paths are listed per candidate.
- `--sources DIR` gives the pre-patch files of instance `i` at `DIR/i/<path>`; both patches
  are applied to them and the AST metric uses the post-patch source (see below).
- `--include-system NAME` (repeatable) keeps only those systems.

`analyze` leaves empty candidate patches out unless `--keep-empty` is given: an empty patch is
never resolved and scores zero on every metric, so keeping it lifts every AUC with the same
easy cases.

Inputs:

- candidates: JSONL, one object per line with `instance_id`, a system name (`model`, `system`
  or `model_name_or_path`) and a unified diff (`patch`, `model_patch` or `diff`);
- gold: JSONL or a JSON list with `instance_id` and `patch` (the SWE-bench dataset layout);
- outcomes: JSONL with `instance_id`, `resolved` and optionally the system name, or a JSON
  object with a `resolved` list of instance ids, in which case every other scored instance
  counts as unresolved.

## How it works

Diffs are parsed into files and hunks. Original line `n` is position `2n`; the gap after
original line `k`, where a pure insertion lands, is position `2k + 1`. A run of changed lines
between two context lines touches the positions of the lines it removes, or the one gap if it
removes nothing. This keeps insertions comparable with edits without inventing line numbers.

Per candidate C against gold G:

| metric | formula |
|---|---|
| file precision, recall, F1 | P = \|F(C) ∩ F(G)\| / \|F(C)\|, R = \|F(C) ∩ F(G)\| / \|F(G)\|, F1 = 2PR / (P + R) over the sets of paths |
| location Jaccard | \|L(C) ∩ L(G)\| / \|L(C) ∪ L(G)\| over (path, position) pairs; also reported per file |
| token F1 | 2 \|T(C) ∩ T(G)\| / (\|T(C)\| + \|T(G)\|) over multisets of (side, token), ∩ taking minimum counts |
| chrF | per order n = 1..6, P_n = m_n / \|C_n\|, R_n = m_n / \|G_n\|; P, R their means; (1 + β²)PR / (β²P + R), β = 2 |
| AST similarity | token F1 formula over multisets of Python AST node types |
| function Jaccard | Jaccard of the sets of (path, function name) changed; `same_functions` when equal |
| edit size | ratio = size(C) / size(G); balance = min / max, size = added + removed lines |

Details and the choices behind them:

- Tokens are identifiers, numbers and single non-space characters of the added and removed
  lines; blank and whole-line `#` comment lines are dropped, and each token is tagged with its
  side, so adding `x` never matches removing `x`.
- chrF follows the character n-gram F-score of Popović ("chrF: character n-gram F-score for
  automatic MT evaluation", Tenth Workshop on Statistical Machine Translation, 2015,
  https://aclanthology.org/W15-3049/): precision and recall are averaged arithmetically over
  n-gram orders up to 6, and β gives recall β times the weight of precision. The paper reports
  β = 1 and β = 3; patchsim uses β = 2 (a parameter of `chrf()`), between the two. Here n-grams
  are taken within each changed line with whitespace removed and tagged by side; orders where
  both sides are empty are skipped. Character n-grams give partial credit to `rstrip` against
  `strip`, which token F1 does not.
- AST similarity is a simplified relative of the syntax-match component of CodeBLEU (Ren et al.,
  "CodeBLEU: a Method for Automatic Evaluation of Code Synthesis", arXiv 2009.10297): a multiset
  of node types rather than subtrees, and no data-flow term. Without repository content it works
  on the patch lines (`ast_mode: patch_lines`): the lines are parsed as one dedented block, or
  failing that one by one, with block headers completed by `pass` and unparseable lines (`else:`,
  continuation lines) skipped; node types are tagged by side. With `--sources`, each patch is applied
  to the pre-patch files and node types come from the whole functions (or top-level statements)
  of the post-patch file that contain the added lines (`ast_mode: post_patch_source`). Hunks
  are applied strictly: context and removed lines must match exactly (trailing whitespace
  aside), at the stated line or the nearest offset, with no fuzz. If a file is missing or a
  hunk does not apply, that candidate falls back to `patch_lines`, and the report counts how
  many candidates used each mode. Expression-context nodes (`Load`, `Store`, `Del`) are
  dropped. The metric is None when neither patch touches a `.py` file.
- Changed functions are read from the patch: the nearest `def` line above each changed line
  inside the hunk, or the function named in the hunk header.

Analysis, for each metric, over candidates with a known outcome:

- ROC AUC = P(s⁺ > s⁻) + ½ P(s⁺ = s⁻), computed from mid-ranks as
  (R⁺ − n⁺(n⁺ + 1)/2) / (n⁺ n⁻); the tests check it against a brute-force count of pairs.
- A percentile bootstrap interval that resamples whole repositories (the part of a SWE-bench id
  before the final `-number`), so that correlated instances from one repository move together.
  Replicates that lose a class are dropped and counted. A simulation test with a random effect
  per repository checks that the bootstrap standard error is within 0.7 to 1.4 times the true
  sampling standard deviation, and that it is wider than an item-level bootstrap.
- Within-instance AUC: the same probability counted only over pairs of candidates for the same
  instance, one resolved and one not, Σᵢ Uᵢ / Σᵢ Pᵢ over instances i, where Pᵢ is the number of
  such pairs and Uᵢ the number in which the resolved candidate scores higher (ties ½). The
  pooled AUC mixes two effects: whether a metric ranks candidates for one task, and whether
  tasks that are easy to resolve also have small, easy-to-match gold patches. The
  within-instance AUC keeps only the first; it needs several systems on the same instances.
  Its interval resamples repositories and sums Uᵢ and Pᵢ over the instances drawn. A test
  checks it against a brute-force count and builds a case where it differs from the pooled AUC.
- The best accuracy of a single rule "resolved when score ≥ t" over all t, against the majority
  baseline max(p, 1 − p).
- The share of resolved candidates touching files outside the gold patch, the share missing a
  gold file, the share of unresolved candidates touching exactly the gold files, and example
  instance ids for each kind of disagreement.

Comparison of two systems A and B (`compare`), on the instances both attempted:

- the mean of each metric for each system and the mean paired difference mean(B − A);
- resolved counts (both, only A, only B, neither) and the difference in resolve rate;
- the AUC within each system and the difference AUC_B − AUC_A, to see whether similarity is a
  better proxy for one system than for the other.

Every interval comes from a bootstrap over repositories in which an instance keeps both of its
candidates, so the two systems are always compared on the same draw (a paired design). A
general `cluster_bootstrap(stat, clusters)` does the resampling; a simulation test checks that
its interval for a mean covers the true value at close to the nominal rate when the data have a
random effect per cluster.

## Results on real public data

Not run yet. The planned source is the SWE-bench experiments repository
(https://github.com/SWE-bench/experiments) for per-submission resolved lists, with gold patches
from the SWE-bench Verified dataset card (https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified).
As checked on 2026-11-06, neither page states a licence (the GitHub API reports no licence for
the repository and the dataset card has no licence field), and the experiments repository keeps
predictions outside git, so only fetch scripts and summary numbers will be committed here.

## Limitations

- Status: the metrics, the analysis and the `score` and `analyze` subcommands work. Not yet
  implemented: the `compare` mode for two systems, a command-line option to supply repository
  content for the post-patch AST mode (the Python function accepts it), the fetch scripts and
  results on real data, and charts.
- Function detection from the patch is a heuristic: nested functions, methods with the same name
  in different classes, and changes outside any visible `def` are not resolved.
- Location overlap compares positions in the original file only; two patches that insert the
  same code one line apart share nothing.
- Similarity is measured against one gold patch; an instance with several valid fixes penalises
  every fix but the one recorded.

## Related tools

- [evalstats](https://github.com/vipul21435/evalstats): intervals and paired tests for evaluation results.
- [patchmin](https://github.com/vipul21435/patchmin): the minimal subset of a patch that still fixes the tests.
- [issuelint](https://github.com/vipul21435/issuelint): checks issue text for leakage of the solution.
- [graderguard](https://github.com/vipul21435/graderguard): audits graders for reward hacking and flakiness.
- [reporewind](https://github.com/vipul21435/reporewind): resolves Python fix commits into source and test patches.

## Licence

MIT, see [LICENSE](LICENSE).

Built by Vipul Raj Jha · https://vipul21435.github.io
