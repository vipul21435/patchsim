"""ROC AUC, a clustered bootstrap interval for it, and the best single threshold."""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Callable, Sequence


def auc(scores: Sequence[float], labels: Sequence[bool]) -> float | None:
    """ROC AUC as the Mann-Whitney probability P(s+ > s-) + 0.5 P(s+ = s-).

    Computed from mid-ranks: AUC = (R+ - n+(n+ + 1)/2) / (n+ n-), where R+ is the
    sum of the mid-ranks of the positive items. None if either class is empty.
    """
    n = len(scores)
    if n != len(labels):
        raise ValueError("scores and labels differ in length")
    order = sorted(range(n), key=lambda i: scores[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        mid = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = mid
        i = j + 1
    n_pos = sum(1 for y in labels if y)
    n_neg = n - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    r_pos = sum(r for r, y in zip(ranks, labels, strict=True) if y)
    return (r_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def clustered_bootstrap_auc(
    scores: Sequence[float],
    labels: Sequence[bool],
    clusters: Sequence[str],
    n_boot: int = 2000,
    level: float = 0.95,
    seed: int = 0,
) -> dict[str, object]:
    """Percentile bootstrap interval for AUC that resamples whole clusters.

    Each replicate draws as many clusters as there are, with replacement, and
    keeps every item of each drawn cluster, so items from the same repository
    stay together. Replicates in which one class is absent are dropped and
    counted in ``n_dropped``.
    """
    groups: dict[str, list[int]] = defaultdict(list)
    for i, c in enumerate(clusters):
        groups[c].append(i)
    keys = sorted(groups)
    rng = random.Random(seed)
    reps: list[float] = []
    dropped = 0
    for _ in range(n_boot):
        idx = [i for k in rng.choices(keys, k=len(keys)) for i in groups[k]]
        a = auc([scores[i] for i in idx], [labels[i] for i in idx])
        if a is None:
            dropped += 1
        else:
            reps.append(a)
    point = auc(scores, labels)
    if not reps:
        return {"auc": point, "low": None, "high": None, "n_boot": 0, "n_dropped": dropped}
    reps.sort()
    alpha = (1 - level) / 2
    lo = reps[int(alpha * (len(reps) - 1))]
    hi = reps[int(round((1 - alpha) * (len(reps) - 1)))]
    mean = sum(reps) / len(reps)
    se = (sum((r - mean) ** 2 for r in reps) / max(len(reps) - 1, 1)) ** 0.5
    return {
        "auc": point,
        "low": lo,
        "high": hi,
        "se": se,
        "n_boot": len(reps),
        "n_dropped": dropped,
        "n_clusters": len(keys),
    }


def cluster_bootstrap(
    stat: Callable[[list[int]], float | None],
    clusters: Sequence[str],
    n_boot: int = 2000,
    level: float = 0.95,
    seed: int = 0,
) -> dict[str, object]:
    """Percentile interval for any statistic of a list of item indices.

    ``stat`` maps a list of indices (with repeats) to a number, or None when the
    statistic is undefined on that draw; such draws are dropped and counted.
    Clusters are resampled whole, with replacement, as in
    :func:`clustered_bootstrap_auc`.
    """
    groups: dict[str, list[int]] = defaultdict(list)
    for i, c in enumerate(clusters):
        groups[c].append(i)
    keys = sorted(groups)
    rng = random.Random(seed)
    reps: list[float] = []
    dropped = 0
    for _ in range(n_boot):
        v = stat([i for k in rng.choices(keys, k=len(keys)) for i in groups[k]])
        if v is None:
            dropped += 1
        else:
            reps.append(v)
    point = stat(list(range(len(clusters))))
    out: dict[str, object] = {"value": point, "n_boot": len(reps), "n_dropped": dropped}
    if not reps:
        return {**out, "low": None, "high": None, "se": None}
    reps.sort()
    alpha = (1 - level) / 2
    mean = sum(reps) / len(reps)
    return {
        **out,
        "low": reps[int(alpha * (len(reps) - 1))],
        "high": reps[int(round((1 - alpha) * (len(reps) - 1)))],
        "se": (sum((r - mean) ** 2 for r in reps) / max(len(reps) - 1, 1)) ** 0.5,
        "n_clusters": len(keys),
    }


def best_threshold(scores: Sequence[float], labels: Sequence[bool]) -> dict[str, float | None]:
    """Best accuracy of the rule 'predict resolved when score >= t' over all t.

    Candidate thresholds are every distinct score plus +inf (predict nothing
    resolved). The majority baseline is max(p, 1 - p) for the share p resolved.
    """
    n = len(scores)
    if n == 0:
        return {"threshold": None, "accuracy": None, "majority_baseline": None}
    pairs = sorted(zip(scores, labels, strict=True), key=lambda t: -t[0])
    n_pos = sum(1 for _, y in pairs if y)
    best_acc = (n - n_pos) / n
    best_t = float("inf")
    tp = fp = 0
    i = 0
    while i < n:
        t = pairs[i][0]
        while i < n and pairs[i][0] == t:
            if pairs[i][1]:
                tp += 1
            else:
                fp += 1
            i += 1
        acc = (tp + (n - n_pos - fp)) / n
        if acc > best_acc:
            best_acc, best_t = acc, t
    return {
        "threshold": best_t,
        "accuracy": best_acc,
        "majority_baseline": max(n_pos, n - n_pos) / n,
    }


def roc_points(
    scores: Sequence[float], labels: Sequence[bool]
) -> list[tuple[float, float]]:
    """(false positive rate, true positive rate) for 'resolved when score >= t' as t
    falls through the distinct scores, from (0, 0) to (1, 1). Tied scores move
    both rates in one step, so the trapezoid area under the points equals
    :func:`auc`. Empty if either class is absent."""
    n_pos = sum(1 for y in labels if y)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return []
    pairs = sorted(zip(scores, labels, strict=True), key=lambda t: -t[0])
    pts = [(0.0, 0.0)]
    tp = fp = 0
    i = 0
    while i < len(pairs):
        t = pairs[i][0]
        while i < len(pairs) and pairs[i][0] == t:
            tp += pairs[i][1]
            fp += not pairs[i][1]
            i += 1
        pts.append((fp / n_neg, tp / n_pos))
    return pts


def repo_of(instance_id: str) -> str:
    """Repository part of a SWE-bench style id: 'owner__name-123' -> 'owner__name'."""
    head, sep, tail = instance_id.rpartition("-")
    return head if sep and tail.isdigit() else instance_id
