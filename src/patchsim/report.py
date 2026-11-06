"""Markdown rendering of score summaries and analysis results."""

from __future__ import annotations


def _f(x: object, nd: int = 3) -> str:
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def summary_markdown(rows: list[dict], metrics: tuple[str, ...]) -> str:
    """Mean of each metric per system (None values excluded)."""
    systems = sorted({str(r["system"]) for r in rows})
    lines = ["| system | n | " + " | ".join(metrics) + " |", "|---" * (len(metrics) + 2) + "|"]
    for s in systems:
        sub = [r for r in rows if r["system"] == s]
        cells = []
        for m in metrics:
            vals = [float(r[m]) for r in sub if r.get(m) is not None]
            cells.append(_f(sum(vals) / len(vals) if vals else None))
        lines.append(f"| {s} | {len(sub)} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def analysis_markdown(res: dict) -> str:
    pct = int(round(res["level"] * 100))
    out = [
        "# patchsim analysis",
        "",
        f"{res['n_candidates']} candidates, {res['n_resolved']} resolved, "
        f"{res['n_repos']} repositories; {res['n_boot']} cluster-bootstrap replicates, "
        f"seed {res['seed']}.",
        "",
        f"Empty candidate patches: {res.get('n_empty', 0)}, "
        + ("excluded." if res.get("empty_excluded", True) else "kept."),
        "AST mode per candidate: "
        + ", ".join(f"{k} {v}" for k, v in res.get("ast_modes", {}).items())
        + ".",
        "",
        f"| metric | n | AUC | {pct}% interval | best accuracy | threshold | majority |",
        "|---|---|---|---|---|---|---|",
    ]
    for m, r in res["metrics"].items():
        out.append(
            f"| {m} | {r['n']} | {_f(r['auc'])} | [{_f(r['low'])}, {_f(r['high'])}] | "
            f"{_f(r['accuracy'])} | {_f(r['threshold'])} | {_f(r['majority_baseline'])} |"
        )
    out += ["", "## File sets", ""]
    for k, v in res["shares"].items():
        out.append(f"- {k.replace('_', ' ')}: {v['count']} of {v['of']} ({_f(v['share'])})")
    d = res["disagreements"]
    out += ["", f"## Disagreements ({d['metric']})", ""]
    for key in ("high_similarity_unresolved", "low_similarity_resolved"):
        out.append(f"{key.replace('_', ' ')}:")
        for e in d[key]:
            out.append(f"- {e['instance_id']} ({e['system']}): {_f(e[d['metric']])}")
        if not d[key]:
            out.append("- none")
        out.append("")
    out.append("different files, resolved:")
    for e in d["different_files_resolved"]:
        extra = ", ".join(e["extra_files"]) or "(missing gold files)"
        out.append(f"- {e['instance_id']} ({e['system']}): {extra}")
    if not d["different_files_resolved"]:
        out.append("- none")
    return "\n".join(out) + "\n"
