"""Similarity metrics between a candidate patch and a gold patch.

Every function takes two parsed :class:`~patchsim.diff.Patch` objects (candidate
first) and returns plain numbers so results serialise to JSON directly.
"""

from __future__ import annotations

from .diff import Patch


def prf(pred: set, gold: set) -> tuple[float, float, float]:
    """Set precision, recall and F1.

    P = |C & G| / |C|, R = |C & G| / |G|, F1 = 2PR / (P + R).
    Two empty sets score (1, 1, 1); an empty side against a non-empty one scores 0.
    """
    if not pred and not gold:
        return 1.0, 1.0, 1.0
    inter = len(pred & gold)
    p = inter / len(pred) if pred else 0.0
    r = inter / len(gold) if gold else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def jaccard(a: set, b: set) -> float:
    """|A & B| / |A | B|, with two empty sets scoring 1."""
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def file_prf(cand: Patch, gold: Patch) -> dict[str, float]:
    """Precision, recall and F1 of the set of file paths touched."""
    p, r, f = prf(cand.paths, gold.paths)
    return {"file_precision": p, "file_recall": r, "file_f1": f}


def location_overlap(cand: Patch, gold: Patch) -> dict[str, object]:
    """Jaccard of touched original-file positions, per file and overall.

    Positions come from :meth:`FilePatch.touched_positions`. The overall value is
    the Jaccard of the sets of (path, position) pairs, so files the other patch
    does not touch count fully against the score.
    """
    cf, gf = cand.by_path(), gold.by_path()
    per_file: dict[str, float] = {}
    c_all: set[tuple[str, int]] = set()
    g_all: set[tuple[str, int]] = set()
    for path in sorted(set(cf) | set(gf)):
        cp = cf[path].touched_positions() if path in cf else set()
        gp = gf[path].touched_positions() if path in gf else set()
        per_file[path] = jaccard(cp, gp)
        c_all.update((path, x) for x in cp)
        g_all.update((path, x) for x in gp)
    return {"location_jaccard": jaccard(c_all, g_all), "location_jaccard_per_file": per_file}


def edit_size(cand: Patch, gold: Patch) -> dict[str, float | None]:
    """Edit size as changed lines (added + removed).

    ratio = size(C) / size(G) (None when the gold patch changes nothing);
    balance = min / max of the two sizes, in [0, 1], with two empty patches scoring 1.
    """
    sc = cand.n_added + cand.n_removed
    sg = gold.n_added + gold.n_removed
    ratio = sc / sg if sg else None
    balance = 1.0 if sc == sg == 0 else min(sc, sg) / max(sc, sg)
    return {"edit_size_ratio": ratio, "edit_size_balance": balance}
