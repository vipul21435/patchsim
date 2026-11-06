"""How well each similarity metric predicts test-based resolution."""

from __future__ import annotations

from .io import outcome_for
from .score import METRICS
from .stats import best_threshold, cluster_bootstrap, clustered_bootstrap_auc, stratum_pairs


def attach_outcomes(rows: list[dict], outcomes: dict) -> list[dict]:
    """Copy rows that have a known outcome, adding a ``resolved`` field."""
    out = []
    for r in rows:
        y = outcome_for(outcomes, str(r["system"]), str(r["instance_id"]))
        if y is not None:
            out.append({**r, "resolved": y})
    return out


def within_instance_auc(
    rows: list[dict], metric: str, n_boot: int = 2000, level: float = 0.95, seed: int = 0
) -> dict[str, object]:
    """AUC over (resolved, unresolved) pairs of candidates for the same instance.

    Only instances where some systems resolved and others did not contribute.
    The interval resamples repositories; each drawn repository brings the pair
    counts of all its instances (see :func:`patchsim.stats.stratified_auc`).
    """
    parts = stratum_pairs(
        [float(r[metric]) for r in rows],
        [bool(r["resolved"]) for r in rows],
        [str(r["instance_id"]) for r in rows],
    )
    repo = {str(r["instance_id"]): str(r["repo"]) for r in rows}
    keys = sorted(parts)
    u = [parts[k][0] for k in keys]
    p = [parts[k][1] for k in keys]

    def stat(idx: list[int]) -> float | None:
        den = sum(p[i] for i in idx)
        return sum(u[i] for i in idx) / den if den else None

    res = cluster_bootstrap(stat, [repo[k] for k in keys], n_boot, level, seed)
    return {**res, "n_instances": len(keys), "n_pairs": sum(p)}


def _share(num: int, den: int) -> dict[str, object]:
    return {"count": num, "of": den, "share": num / den if den else None}


def analyze(
    rows: list[dict],
    metrics: tuple[str, ...] = METRICS,
    n_boot: int = 2000,
    seed: int = 0,
    level: float = 0.95,
    examples: int = 5,
    example_metric: str = "chrf",
    exclude_empty: bool = True,
) -> dict[str, object]:
    """Per-metric AUC with a repository-clustered bootstrap interval and best
    threshold accuracy, file-set shares and disagreement examples.

    ``rows`` must carry a ``resolved`` field (see :func:`attach_outcomes`). Rows
    where a metric is None (e.g. AST similarity without Python files) are left
    out of that metric only; ``n`` reports how many were used. Empty candidate
    patches are dropped first unless ``exclude_empty`` is False: they can never be
    resolved and score zero on every metric, so keeping them inflates every AUC by
    the same easy cases.
    """
    n_empty = sum(1 for r in rows if r.get("empty_candidate"))
    if exclude_empty:
        rows = [r for r in rows if not r.get("empty_candidate")]
    per_metric = {}
    for m in metrics:
        sub = [r for r in rows if r.get(m) is not None]
        s = [float(r[m]) for r in sub]
        y = [bool(r["resolved"]) for r in sub]
        boot = clustered_bootstrap_auc(s, y, [str(r["repo"]) for r in sub], n_boot, level, seed)
        per_metric[m] = {"n": len(sub), "n_resolved": sum(y), **boot, **best_threshold(s, y)}
        per_metric[m]["within_instance"] = within_instance_auc(sub, m, n_boot, level, seed)

    resolved = [r for r in rows if r["resolved"]]
    unresolved = [r for r in rows if not r["resolved"]]
    shares = {
        "resolved_touching_files_outside_gold": _share(
            sum(1 for r in resolved if r["extra_files"]), len(resolved)
        ),
        "resolved_missing_gold_files": _share(
            sum(1 for r in resolved if r["file_recall"] < 1), len(resolved)
        ),
        "unresolved_touching_exactly_gold_files": _share(
            sum(1 for r in unresolved if r["same_files"]), len(unresolved)
        ),
    }

    def pick(rs: list[dict], reverse: bool) -> list[dict]:
        keyed = [r for r in rs if r.get(example_metric) is not None]
        keyed.sort(key=lambda r: (r[example_metric], r["instance_id"]), reverse=reverse)
        return [
            {
                "instance_id": r["instance_id"],
                "system": r["system"],
                example_metric: r[example_metric],
            }
            for r in keyed[:examples]
        ]

    disagreements = {
        "metric": example_metric,
        "high_similarity_unresolved": pick(unresolved, True),
        "low_similarity_resolved": pick(resolved, False),
        "different_files_resolved": [
            {
                "instance_id": r["instance_id"],
                "system": r["system"],
                "extra_files": r["extra_files"],
            }
            for r in sorted(resolved, key=lambda r: r["instance_id"])
            if not r["same_files"]
        ][:examples],
    }
    return {
        "n_candidates": len(rows),
        "n_empty": n_empty,
        "empty_excluded": exclude_empty,
        "ast_modes": {
            str(k): sum(1 for r in rows if r.get("ast_mode") == k)
            for k in sorted({r.get("ast_mode") for r in rows}, key=str)
        },
        "n_resolved": len(resolved),
        "n_repos": len({r["repo"] for r in rows}),
        "level": level,
        "n_boot": n_boot,
        "seed": seed,
        "metrics": per_metric,
        "shares": shares,
        "disagreements": disagreements,
    }
