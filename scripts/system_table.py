"""Markdown table of per-system AUCs from the system_*.json files of scripts/run_real.sh."""

from __future__ import annotations

import json
import sys
from pathlib import Path

COLS = ("file_f1", "location_jaccard", "token_f1", "chrf", "ast_similarity")


def main(out_dir: str) -> None:
    print("| system | n | resolved | " + " | ".join(f"AUC, {m}" for m in COLS) + " |")
    print("|---" * (len(COLS) + 3) + "|")
    for p in sorted(Path(out_dir).glob("system_*.json")):
        res = json.loads(p.read_text())
        name = p.stem[len("system_") :]
        cells = []
        for m in COLS:
            r = res["metrics"][m]
            cells.append(f"{r['auc']:.3f} [{r['low']:.3f}, {r['high']:.3f}]")
        head = f"| {name} | {res['n_candidates']} | {res['n_resolved']} | "
        print(head + " | ".join(cells) + " |")


if __name__ == "__main__":
    main(sys.argv[1])
