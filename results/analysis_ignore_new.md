# patchsim analysis

2871 candidates, 1230 resolved, 12 repositories; 2000 cluster-bootstrap replicates, seed 0.

Empty candidate patches: 83, excluded.
AST mode per candidate: patch_lines 2871.

| metric | n | AUC | 95% interval | within-instance AUC | best accuracy (in-sample) | threshold | held-out accuracy | majority |
|---|---|---|---|---|---|---|---|---|
| file_precision | 2871 | 0.646 | [0.614, 0.686] | 0.615 [0.571, 0.680] | 0.600 | 1.000 | 0.565 | 0.572 |
| file_recall | 2871 | 0.690 | [0.652, 0.715] | 0.613 [0.581, 0.642] | 0.653 | 1.000 | 0.653 | 0.572 |
| file_f1 | 2871 | 0.702 | [0.665, 0.744] | 0.624 [0.577, 0.687] | 0.666 | 1.000 | 0.666 | 0.572 |
| location_jaccard | 2871 | 0.762 | [0.726, 0.778] | 0.737 [0.698, 0.778] | 0.734 | 0.167 | 0.723 | 0.572 |
| token_f1 | 2871 | 0.781 | [0.747, 0.800] | 0.740 [0.694, 0.787] | 0.739 | 0.567 | 0.732 | 0.572 |
| chrf | 2871 | 0.805 | [0.775, 0.824] | 0.768 [0.724, 0.819] | 0.759 | 0.472 | 0.756 | 0.572 |
| ast_similarity | 2871 | 0.752 | [0.696, 0.777] | 0.705 [0.645, 0.750] | 0.727 | 0.658 | 0.715 | 0.572 |
| function_jaccard | 2843 | 0.616 | [0.577, 0.706] | 0.605 [0.569, 0.650] | 0.649 | 0.750 | 0.648 | 0.570 |
| edit_size_balance | 2871 | 0.653 | [0.627, 0.672] | 0.579 [0.538, 0.631] | 0.634 | 0.850 | 0.630 | 0.572 |

Within-instance AUC uses only pairs of candidates for the same instance, one resolved and one not (295 instances, 1912 pairs for the first metric).

Best accuracy is in-sample: the threshold is chosen and scored on the same candidates. Held-out accuracy chooses it on all repositories but one and scores the one left out, in turn.

## AUC of chrf minus AUC of each other metric

Paired: both AUCs on the same candidates and the same bootstrap draws.

| metric | n | AUC chrf - AUC metric | 95% interval |
|---|---|---|---|
| file_precision | 2871 | 0.159 | [0.116, 0.186] |
| file_recall | 2871 | 0.115 | [0.081, 0.144] |
| file_f1 | 2871 | 0.103 | [0.057, 0.130] |
| location_jaccard | 2871 | 0.043 | [0.025, 0.063] |
| token_f1 | 2871 | 0.024 | [0.011, 0.037] |
| ast_similarity | 2871 | 0.053 | [0.038, 0.089] |
| function_jaccard | 2843 | 0.190 | [0.085, 0.234] |
| edit_size_balance | 2871 | 0.152 | [0.124, 0.170] |

## File sets

- resolved touching files outside gold: 125 of 1230 (0.102)
- resolved missing gold files: 80 of 1230 (0.065)
- unresolved touching exactly gold files: 807 of 1641 (0.492)

## Disagreements (chrf)

Against the best threshold t = 0.472: unresolved candidates scoring at least t, and resolved candidates scoring below t.

high similarity unresolved: 265
- psf__requests-1766 (20240628_autocoderover-v20240620): 1.000
- django__django-15315 (20241128_SWE-Fixer_Qwen2.5-7b-retriever_Qwen2.5-72b-editor_20241128): 0.971
- django__django-11603 (20240728_sweagent_gpt4o): 0.957
- django__django-14559 (20240728_sweagent_gpt4o): 0.954
- django__django-14559 (20241028_agentless-1.5_gpt4o): 0.954

low similarity resolved: 427
- django__django-12209 (20241128_SWE-Fixer_Qwen2.5-7b-retriever_Qwen2.5-72b-editor_20241128): 0.000
- sympy__sympy-13877 (20241028_agentless-1.5_gpt4o): 0.010
- sympy__sympy-22456 (20241029_OpenHands-CodeAct-2.1-sonnet-20241022): 0.015
- sympy__sympy-22456 (20250225_sweagent_claude-3-7-sonnet): 0.015
- sympy__sympy-24562 (20250225_sweagent_claude-3-7-sonnet): 0.028

different files, resolved: 153
- astropy__astropy-14182 (20250225_sweagent_claude-3-7-sonnet): astropy/io/ascii/core.py
- astropy__astropy-14309 (20240728_sweagent_gpt4o): pyproject.toml
- astropy__astropy-14309 (20240628_autocoderover-v20240620): astropy/io/registry/base.py
- astropy__astropy-14539 (20240728_sweagent_gpt4o): pyproject.toml
- astropy__astropy-14995 (20240728_sweagent_gpt4o): pyproject.toml
