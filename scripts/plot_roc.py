"""ROC curves of each similarity metric for predicting resolution, rendered headlessly.

Usage: python scripts/plot_roc.py ROWS.jsonl OUTCOMES.jsonl OUT.png
ROWS comes from `patchsim score --out`; empty candidate patches are left out, as in
`patchsim analyze`.
"""

from __future__ import annotations

import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from patchsim.io import load_outcomes, outcome_for  # noqa: E402
from patchsim.stats import auc, roc_points  # noqa: E402

SHOW = ("file_f1", "location_jaccard", "token_f1", "chrf", "ast_similarity", "edit_size_balance")


def main(rows_path: str, outcomes_path: str, out: str) -> None:
    outcomes = load_outcomes(outcomes_path)
    rows = []
    for line in open(rows_path, encoding="utf-8"):
        r = json.loads(line)
        y = outcome_for(outcomes, r["system"], r["instance_id"])
        if y is not None and not r["empty_candidate"]:
            rows.append({**r, "resolved": y})
    fig, ax = plt.subplots(figsize=(5.5, 5.0), dpi=120)
    for m in SHOW:
        sub = [r for r in rows if r.get(m) is not None]
        s = [float(r[m]) for r in sub]
        y = [bool(r["resolved"]) for r in sub]
        pts = roc_points(s, y)
        ax.plot([p[0] for p in pts], [p[1] for p in pts], lw=1.4, label=f"{m} ({auc(s, y):.3f})")
    ax.plot([0, 1], [0, 1], color="grey", lw=0.8, ls="--")
    ax.set_xlabel("false positive rate (unresolved predicted resolved)")
    ax.set_ylabel("true positive rate")
    ax.set_title(f"Similarity to gold vs resolution, {len(rows)} candidates", fontsize=10)
    ax.legend(fontsize=8, loc="lower right", title="metric (AUC)", title_fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(out)


if __name__ == "__main__":
    main(*sys.argv[1:4])
