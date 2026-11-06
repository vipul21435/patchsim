# patchsim analysis

2871 candidates, 1230 resolved, 12 repositories; 2000 cluster-bootstrap replicates, seed 0.

Empty candidate patches: 83, excluded.
AST mode per candidate: patch_lines 8, post_patch_source 2863.

| metric | n | AUC | 95% interval | within-instance AUC | best accuracy | threshold | majority |
|---|---|---|---|---|---|---|---|
| file_precision | 2871 | 0.646 | [0.614, 0.686] | 0.615 [0.571, 0.680] | 0.600 | 1.000 | 0.572 |
| file_recall | 2871 | 0.690 | [0.652, 0.714] | 0.613 [0.581, 0.642] | 0.653 | 1.000 | 0.572 |
| file_f1 | 2871 | 0.702 | [0.665, 0.744] | 0.624 [0.577, 0.686] | 0.666 | 1.000 | 0.572 |
| location_jaccard | 2871 | 0.762 | [0.726, 0.778] | 0.737 [0.698, 0.778] | 0.734 | 0.167 | 0.572 |
| token_f1 | 2871 | 0.781 | [0.747, 0.800] | 0.740 [0.694, 0.787] | 0.739 | 0.567 | 0.572 |
| chrf | 2871 | 0.805 | [0.775, 0.824] | 0.768 [0.724, 0.819] | 0.759 | 0.472 | 0.572 |
| ast_similarity | 2871 | 0.772 | [0.754, 0.818] | 0.706 [0.661, 0.775] | 0.741 | 0.878 | 0.572 |
| function_jaccard | 2843 | 0.616 | [0.577, 0.706] | 0.605 [0.569, 0.650] | 0.649 | 0.750 | 0.570 |
| edit_size_balance | 2871 | 0.653 | [0.627, 0.672] | 0.579 [0.538, 0.631] | 0.634 | 0.850 | 0.572 |

Within-instance AUC uses only pairs of candidates for the same instance, one resolved and one not (295 instances, 1912 pairs for the first metric).

## File sets

- resolved touching files outside gold: 125 of 1230 (0.102)
- resolved missing gold files: 80 of 1230 (0.065)
- unresolved touching exactly gold files: 807 of 1641 (0.492)

## Disagreements (chrf)

high similarity unresolved:
- psf__requests-1766 (20240628_autocoderover-v20240620): 1.000
- django__django-15315 (20241128_SWE-Fixer_Qwen2.5-7b-retriever_Qwen2.5-72b-editor_20241128): 0.971
- django__django-11603 (20240728_sweagent_gpt4o): 0.957
- django__django-14559 (20240728_sweagent_gpt4o): 0.954
- django__django-14559 (20241028_agentless-1.5_gpt4o): 0.954

low similarity resolved:
- django__django-12209 (20241128_SWE-Fixer_Qwen2.5-7b-retriever_Qwen2.5-72b-editor_20241128): 0.000
- sympy__sympy-13877 (20241028_agentless-1.5_gpt4o): 0.010
- sympy__sympy-22456 (20241029_OpenHands-CodeAct-2.1-sonnet-20241022): 0.015
- sympy__sympy-22456 (20250225_sweagent_claude-3-7-sonnet): 0.015
- sympy__sympy-24562 (20250225_sweagent_claude-3-7-sonnet): 0.028

different files, resolved:
- astropy__astropy-14182 (20250225_sweagent_claude-3-7-sonnet): astropy/io/ascii/core.py
- astropy__astropy-14309 (20240728_sweagent_gpt4o): pyproject.toml
- astropy__astropy-14309 (20240628_autocoderover-v20240620): astropy/io/registry/base.py
- astropy__astropy-14539 (20240728_sweagent_gpt4o): pyproject.toml
- astropy__astropy-14995 (20240728_sweagent_gpt4o): pyproject.toml
