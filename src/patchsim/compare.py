"""Compare two systems on the instances both attempted."""

from __future__ import annotations

from .score import METRICS
from .stats import auc, cluster_bootstrap


def compare(
    rows: list[dict],
    a: str,
    b: str,
    metrics: tuple[str, ...] = METRICS,
    n_boot: int = 2000,
    level: float = 0.95,
    seed: int = 0,
    exclude_empty: bool = True,
) -> dict[str, object]:
    """Paired comparison of systems ``a`` and ``b`` on their shared instances.

    For each metric: the mean for each system and the mean paired difference
    d = mean(b - a), and the AUC for resolution within each system with the
    difference AUC_b - AUC_a. Every interval comes from one repository-clustered
    bootstrap per quantity, in which an instance keeps both of its candidates, so
    the two systems are compared on the same draw. Means use every shared
    instance; AUCs leave out empty patches when ``exclude_empty`` is set, as in
    :func:`patchsim.analysis.analyze`. ``rows`` need ``resolved`` for the outcome
    counts and AUCs; without it those parts are None.
    """
    by = {s: {str(r["instance_id"]): r for r in rows if r["system"] == s} for s in (a, b)}
    ids = sorted(set(by[a]) & set(by[b]))
    ra = [by[a][i] for i in ids]
    rb = [by[b][i] for i in ids]
    repos = [str(r["repo"]) for r in ra]
    has_y = all("resolved" in r for r in ra + rb)

    def boot(stat):
        return cluster_bootstrap(stat, repos, n_boot, level, seed)

    out_metrics: dict[str, dict] = {}
    for m in metrics:
        keep = [k for k in range(len(ids)) if ra[k].get(m) is not None and rb[k].get(m) is not None]
        xa = {k: float(ra[k][m]) for k in keep}
        xb = {k: float(rb[k][m]) for k in keep}
        ks = set(keep)

        def mean_diff(idx, ks=ks, xa=xa, xb=xb):
            sel = [i for i in idx if i in ks]
            return sum(xb[i] - xa[i] for i in sel) / len(sel) if sel else None

        entry: dict[str, object] = {
            "n": len(keep),
            "mean_a": sum(xa.values()) / len(keep) if keep else None,
            "mean_b": sum(xb.values()) / len(keep) if keep else None,
            "diff": boot(mean_diff),
        }
        if has_y:

            def auc_of(rs, idx, m=m):
                use = [rs[i] for i in idx if rs[i].get(m) is not None]
                if exclude_empty:
                    use = [r for r in use if not r.get("empty_candidate")]
                return auc([float(r[m]) for r in use], [bool(r["resolved"]) for r in use])

            def auc_diff(idx, auc_of=auc_of):
                x, y = auc_of(ra, idx), auc_of(rb, idx)
                return None if x is None or y is None else y - x

            entry["auc_a"] = boot(lambda idx, f=auc_of: f(ra, idx))
            entry["auc_b"] = boot(lambda idx, f=auc_of: f(rb, idx))
            entry["auc_diff"] = boot(auc_diff)
        out_metrics[m] = entry

    outcomes = None
    if has_y:
        ya = [bool(r["resolved"]) for r in ra]
        yb = [bool(r["resolved"]) for r in rb]
        pairs = list(zip(ya, yb, strict=True))
        outcomes = {
            "resolved_a": sum(ya),
            "resolved_b": sum(yb),
            "both": pairs.count((True, True)),
            "only_a": pairs.count((True, False)),
            "only_b": pairs.count((False, True)),
            "neither": pairs.count((False, False)),
            "rate_diff": boot(
                lambda idx: sum(yb[i] - ya[i] for i in idx) / len(idx) if idx else None
            ),
        }
    return {
        "a": a,
        "b": b,
        "n_shared": len(ids),
        "n_only_a": len(set(by[a]) - set(by[b])),
        "n_only_b": len(set(by[b]) - set(by[a])),
        "n_repos": len(set(repos)),
        "n_boot": n_boot,
        "level": level,
        "seed": seed,
        "outcomes": outcomes,
        "metrics": out_metrics,
    }
