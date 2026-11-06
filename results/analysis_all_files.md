# patchsim analysis

2929 candidates, 1230 resolved, 12 repositories; 2000 cluster-bootstrap replicates, seed 0.

Empty candidate patches: 25, excluded.
AST mode per candidate: patch_lines 2929.

| metric | n | AUC | 95% interval | within-instance AUC | best accuracy (in-sample) | threshold | held-out accuracy | majority |
|---|---|---|---|---|---|---|---|---|
| file_precision | 2929 | 0.657 | [0.611, 0.687] | 0.620 [0.564, 0.668] | 0.606 | 1.000 | 0.576 | 0.580 |
| file_recall | 2929 | 0.700 | [0.655, 0.720] | 0.624 [0.585, 0.648] | 0.660 | 1.000 | 0.660 | 0.580 |
| file_f1 | 2929 | 0.702 | [0.657, 0.733] | 0.631 [0.570, 0.678] | 0.662 | 1.000 | 0.662 | 0.580 |
| location_jaccard | 2929 | 0.762 | [0.724, 0.776] | 0.732 [0.687, 0.769] | 0.738 | 0.167 | 0.733 | 0.580 |
| token_f1 | 2929 | 0.731 | [0.695, 0.741] | 0.682 [0.610, 0.706] | 0.721 | 0.567 | 0.717 | 0.580 |
| chrf | 2929 | 0.779 | [0.748, 0.790] | 0.735 [0.680, 0.753] | 0.742 | 0.472 | 0.740 | 0.580 |
| ast_similarity | 2929 | 0.703 | [0.654, 0.719] | 0.656 [0.591, 0.683] | 0.708 | 0.748 | 0.695 | 0.580 |
| function_jaccard | 2901 | 0.620 | [0.583, 0.705] | 0.606 [0.566, 0.652] | 0.653 | 0.750 | 0.649 | 0.578 |
| edit_size_balance | 2929 | 0.617 | [0.581, 0.629] | 0.549 [0.485, 0.582] | 0.632 | 0.875 | 0.628 | 0.580 |

Within-instance AUC uses only pairs of candidates for the same instance, one resolved and one not (298 instances, 1992 pairs for the first metric).

Best accuracy is in-sample: the threshold is chosen and scored on the same candidates. Held-out accuracy chooses it on all repositories but one and scores the one left out, in turn.

## File sets

- resolved touching files outside gold: 296 of 1230 (0.241)
- resolved missing gold files: 80 of 1230 (0.065)
- unresolved touching exactly gold files: 674 of 1699 (0.397)

## Disagreements (chrf)

Against the best threshold t = 0.472: unresolved candidates scoring at least t, and resolved candidates scoring below t.

high similarity unresolved: 238
- psf__requests-1766 (20240628_autocoderover-v20240620): 1.000
- django__django-15315 (20241128_SWE-Fixer_Qwen2.5-7b-retriever_Qwen2.5-72b-editor_20241128): 0.971
- django__django-14559 (20241028_agentless-1.5_gpt4o): 0.954
- django__django-14559 (20241029_OpenHands-CodeAct-2.1-sonnet-20241022): 0.954
- scikit-learn__scikit-learn-13496 (20241028_agentless-1.5_gpt4o): 0.939

low similarity resolved: 518
- django__django-12209 (20241128_SWE-Fixer_Qwen2.5-7b-retriever_Qwen2.5-72b-editor_20241128): 0.000
- sphinx-doc__sphinx-9230 (20241029_OpenHands-CodeAct-2.1-sonnet-20241022): 0.000
- sphinx-doc__sphinx-9258 (20241029_OpenHands-CodeAct-2.1-sonnet-20241022): 0.000
- sphinx-doc__sphinx-8595 (20241029_OpenHands-CodeAct-2.1-sonnet-20241022): 0.000
- sphinx-doc__sphinx-8721 (20241029_OpenHands-CodeAct-2.1-sonnet-20241022): 0.001

different files, resolved: 315
- astropy__astropy-13579 (20241029_OpenHands-CodeAct-2.1-sonnet-20241022): reproduce_error.py, test_edge_cases.py
- astropy__astropy-14096 (20241029_OpenHands-CodeAct-2.1-sonnet-20241022): reproduce_error.py, test_edge_cases.py
- astropy__astropy-14182 (20250225_sweagent_claude-3-7-sonnet): astropy/io/ascii/core.py
- astropy__astropy-14309 (20240728_sweagent_gpt4o): pyproject.toml
- astropy__astropy-14309 (20240628_autocoderover-v20240620): astropy/io/registry/base.py
