"""Score candidate patches against gold patches with every metric."""

from __future__ import annotations

from pathlib import Path

from .astsim import ast_similarity, function_overlap
from .diff import AppliedFile, Patch, apply_file_patch_lines, parse_diff
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


def post_patch_sources(patch: Patch, base_dir: str | Path) -> dict[str, AppliedFile] | None:
    """Every changed Python file of ``patch`` applied to its pre-patch file under ``base_dir``.

    ``base_dir/<path>`` holds the file before the patch; a file the patch creates
    starts empty and a file it deletes ends empty. Returns None when a pre-patch
    file is missing or a hunk does not apply, so the caller falls back to the
    patch-lines AST mode.
    """
    base = Path(base_dir)
    out: dict[str, AppliedFile] = {}
    for f in patch.files:
        if not f.path.endswith(".py"):
            continue
        if f.old_path is None:
            src = ""
        else:
            p = base / f.old_path
            if not p.is_file():
                return None
            src = p.read_text(encoding="utf-8", errors="replace")
        applied = apply_file_patch_lines(src, f)
        if applied is None:
            return None
        out[f.path] = applied
    return out


def score_pair(
    candidate: str,
    gold: str,
    ignore_new_files: bool = False,
    base_dir: str | Path | None = None,
) -> dict[str, object]:
    """All metrics for one candidate diff against one gold diff.

    ``ignore_new_files`` drops files the candidate creates that the gold patch does
    not touch (listed in ``dropped_files``). ``base_dir`` holds the pre-patch files
    of the instance and switches the AST metric to post-patch source when both
    patches apply.
    """
    c, g = parse_diff(candidate), parse_diff(gold)
    row: dict[str, object] = {}
    if ignore_new_files:
        c, dropped = c.without_new_files(g.paths)
        row["dropped_files"] = dropped
    row.update(file_prf(c, g))
    row["same_files"] = c.paths == g.paths
    row["extra_files"] = sorted(c.paths - g.paths)
    row.update(location_overlap(c, g))
    row["token_f1"] = token_f1(c, g)
    row["chrf"] = chrf(c, g)
    cs = gs = None
    if base_dir is not None:
        cs, gs = post_patch_sources(c, base_dir), post_patch_sources(g, base_dir)
    row.update(ast_similarity(c, g, cs, gs))
    row.update(function_overlap(c, g))
    row.update(edit_size(c, g))
    row["empty_candidate"] = not c.files
    return row


def score_all(
    candidates: list[Candidate],
    gold: dict[str, str],
    ignore_new_files: bool = False,
    sources: str | Path | None = None,
) -> list[dict[str, object]]:
    """One row per candidate whose instance has a gold patch; others are skipped.

    ``sources`` is a directory with the pre-patch files of instance ``i`` under
    ``sources/i/`` (see :func:`post_patch_sources`).
    """
    rows = []
    for cand in candidates:
        if cand.instance_id not in gold:
            continue
        row: dict[str, object] = {
            "instance_id": cand.instance_id,
            "system": cand.system,
            "repo": repo_of(cand.instance_id),
        }
        base = Path(sources) / cand.instance_id if sources is not None else None
        row.update(score_pair(cand.patch, gold[cand.instance_id], ignore_new_files, base))
        rows.append(row)
    return rows
