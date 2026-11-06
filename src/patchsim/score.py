"""Score candidate patches against gold patches with every metric."""

from __future__ import annotations

from .astsim import ast_similarity, function_overlap
from .diff import parse_diff
from .io import Candidate
from .metrics import edit_size, file_prf, location_overlap
from .stats import repo_of
from .textsim import chrf, token_f1

METRICS = (
    "file_precision",
    "file_recall",
    "file_f1",
    "location_jaccard",
    "token_f1",
    "chrf",
    "ast_similarity",
    "function_jaccard",
    "edit_size_balance",
)


def score_pair(candidate: str, gold: str) -> dict[str, object]:
    """All metrics for one candidate diff against one gold diff."""
    c, g = parse_diff(candidate), parse_diff(gold)
    row: dict[str, object] = {}
    row.update(file_prf(c, g))
    row["same_files"] = c.paths == g.paths
    row["extra_files"] = sorted(c.paths - g.paths)
    row.update(location_overlap(c, g))
    row["token_f1"] = token_f1(c, g)
    row["chrf"] = chrf(c, g)
    row.update(ast_similarity(c, g))
    row.update(function_overlap(c, g))
    row.update(edit_size(c, g))
    row["empty_candidate"] = not c.files
    return row


def score_all(candidates: list[Candidate], gold: dict[str, str]) -> list[dict[str, object]]:
    """One row per candidate whose instance has a gold patch; others are skipped."""
    rows = []
    for cand in candidates:
        if cand.instance_id not in gold:
            continue
        row: dict[str, object] = {
            "instance_id": cand.instance_id,
            "system": cand.system,
            "repo": repo_of(cand.instance_id),
        }
        row.update(score_pair(cand.patch, gold[cand.instance_id]))
        rows.append(row)
    return rows
