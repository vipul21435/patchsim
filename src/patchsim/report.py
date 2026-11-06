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
        f"| metric | n | AUC | {pct}% interval | within-instance AUC "
        "| best accuracy (in-sample) | threshold | held-out accuracy | majority |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for m, r in res["metrics"].items():
        w = r.get("within_instance")
        out.append(
            f"| {m} | {r['n']} | {_f(r['auc'])} | [{_f(r['low'])}, {_f(r['high'])}] | "
            f"{_iv(w)} | "
            f"{_f(r['accuracy'])} | {_f(r['threshold'])} | {_f(r.get('held_out_accuracy'))} | "
            f"{_f(r['majority_baseline'])} |"
        )
    w0 = next(iter(res["metrics"].values()), {}).get("within_instance")
    if w0:
        out += [
            "",
            f"Within-instance AUC uses only pairs of candidates for the same instance, "
            f"one resolved and one not ({w0['n_instances']} instances, {w0['n_pairs']} pairs "
            f"for the first metric).",
        ]
    out += [
        "",
        "Best accuracy is in-sample: the threshold is chosen and scored on the same "
        "candidates. Held-out accuracy chooses it on all repositories but one and scores "
        "the one left out, in turn.",
    ]
    vs = res.get("vs_metric")
    if vs:
        out += [
            "",
            f"## AUC of {vs['metric']} minus AUC of each other metric",
            "",
            "Paired: both AUCs on the same candidates and the same bootstrap draws.",
            "",
            f"| metric | n | AUC {vs['metric']} - AUC metric | {pct}% interval |",
            "|---|---|---|---|",
        ]
        for m, r in vs["differences"].items():
            out.append(f"| {m} | {r['n']} | {_f(r['value'])} | [{_f(r['low'])}, {_f(r['high'])}] |")
    out += ["", "## File sets", ""]
    for k, v in res["shares"].items():
        out.append(f"- {k.replace('_', ' ')}: {v['count']} of {v['of']} ({_f(v['share'])})")
    d = res["disagreements"]
    out += [
        "",
        f"## Disagreements ({d['metric']})",
        "",
        f"Against the best threshold t = {_f(d.get('threshold'))}: unresolved candidates "
        f"scoring at least t, and resolved candidates scoring below t.",
        "",
    ]
    for key in ("high_similarity_unresolved", "low_similarity_resolved"):
        n_key = d.get("n_" + key)
        count = f" {n_key}" if n_key is not None else ""
        out.append(f"{key.replace('_', ' ')}:{count}")
        for e in d[key]:
            out.append(f"- {e['instance_id']} ({e['system']}): {_f(e[d['metric']])}")
        if not d[key]:
            out.append("- none")
        out.append("")
    n_diff = d.get("n_different_files_resolved")
    out.append("different files, resolved:" + (f" {n_diff}" if n_diff is not None else ""))
    for e in d["different_files_resolved"]:
        extra = ", ".join(e["extra_files"]) or "(missing gold files)"
        out.append(f"- {e['instance_id']} ({e['system']}): {extra}")
    if not d["different_files_resolved"]:
        out.append("- none")
    return "\n".join(out) + "\n"


def _iv(b: dict | None) -> str:
    if not b:
        return "-"
    return f"{_f(b['value'])} [{_f(b['low'])}, {_f(b['high'])}]"


def compare_markdown(res: dict) -> str:
    pct = int(round(res["level"] * 100))
    a, b = res["a"], res["b"]
    out = [
        "# patchsim comparison",
        "",
        f"A = {a}, B = {b}. {res['n_shared']} shared instances over {res['n_repos']} "
        f"repositories ({res['n_only_a']} only in A, {res['n_only_b']} only in B); "
        f"{res['n_boot']} cluster-bootstrap replicates, seed {res['seed']}, {pct}% intervals.",
        "",
    ]
    o = res["outcomes"]
    if o:
        out += [
            f"Resolved: A {o['resolved_a']}, B {o['resolved_b']}; both {o['both']}, "
            f"only A {o['only_a']}, only B {o['only_b']}, neither {o['neither']}. "
            f"Rate difference B - A: {_iv(o['rate_diff'])}.",
            "",
        ]
    head = "| metric | n | mean A | mean B | B - A |"
    sep = "|---|---|---|---|---|"
    if o:
        head += " AUC A | AUC B | AUC B - A |"
        sep += "---|---|---|"
    out += [head, sep]
    for m, r in res["metrics"].items():
        line = f"| {m} | {r['n']} | {_f(r['mean_a'])} | {_f(r['mean_b'])} | {_iv(r['diff'])} |"
        if o:
            line += f" {_iv(r['auc_a'])} | {_iv(r['auc_b'])} | {_iv(r['auc_diff'])} |"
        out.append(line)
    return "\n".join(out) + "\n"
