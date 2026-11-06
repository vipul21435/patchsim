"""AST-level similarity for Python files and the set of changed functions."""

from __future__ import annotations

import ast
import textwrap
import warnings
from collections import Counter

from .diff import FilePatch, Patch
from .textsim import multiset_f1

# Expression-context and wrapper nodes carry no information about the edit.
_SKIP = {"Module", "Load", "Store", "Del"}


def _parse(code: str) -> ast.Module:
    """ast.parse with SyntaxWarning (e.g. invalid escapes in fragments) silenced."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        return ast.parse(code)


def _is_python(path: str) -> bool:
    return path.endswith(".py")


def _count(tree: ast.AST, out: Counter, tag: str = "") -> None:
    for node in ast.walk(tree):
        name = type(node).__name__
        if name not in _SKIP:
            out[tag + name] += 1


def _parse_line(s: str) -> ast.AST | None:
    """Parse one stripped line of code, completing a block header with ``pass``."""
    candidates = [s]
    if s.endswith(":"):
        candidates.append(s + " pass")
        if s.startswith(("elif ",)):
            candidates.append("if " + s[5:] + " pass")
    for c in candidates:
        try:
            return _parse(c)
        except SyntaxError:
            continue
    return None


def node_types_from_lines(lines: list[str], tag: str = "") -> Counter:
    """Multiset of AST node types in a list of source lines taken from a patch.

    The lines are first dedented and parsed as one block. If that fails, as it
    usually does for fragments, each line is parsed on its own (block headers
    ending in ':' are completed with ``pass``) and lines that still do not parse
    (``else:``, a lone closing bracket, a continuation line) are skipped.
    """
    out: Counter = Counter()
    code = [ln for ln in lines if ln.strip()]
    if not code:
        return out
    try:
        _count(_parse(textwrap.dedent("\n".join(code))), out, tag)
        return out
    except SyntaxError:
        pass
    for ln in code:
        tree = _parse_line(ln.strip())
        if tree is not None:
            _count(tree, out, tag)
    return out


def _enclosing_nodes(tree: ast.Module, lines: set[int]) -> list[ast.AST]:
    """Innermost function containing each line; top-level statement otherwise."""
    found: dict[int, ast.AST] = {}
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for ln in lines:
        best = None
        for f in funcs:
            end = getattr(f, "end_lineno", f.lineno)
            if f.lineno <= ln <= end and (best is None or f.lineno >= best.lineno):
                best = f
        if best is None:
            for stmt in tree.body:
                end = getattr(stmt, "end_lineno", stmt.lineno)
                if stmt.lineno <= ln <= end:
                    best = stmt
                    break
        if best is not None:
            found[id(best)] = best
    return list(found.values())


def node_types_from_source(source: str, changed_lines: list[int]) -> Counter | None:
    """Multiset of node types of the functions (or top-level statements) of
    ``source`` that contain any of ``changed_lines``. None if the source does not parse."""
    try:
        tree = _parse(source)
    except SyntaxError:
        return None
    out: Counter = Counter()
    for node in _enclosing_nodes(tree, set(changed_lines)):
        _count(node, out)
    return out


def _patch_node_types(fp: FilePatch) -> Counter:
    return node_types_from_lines(fp.removed, "-") + node_types_from_lines(fp.added, "+")


def ast_similarity(
    cand: Patch,
    gold: Patch,
    cand_sources: dict[str, str] | None = None,
    gold_sources: dict[str, str] | None = None,
) -> dict[str, object]:
    """Multiset F1 of AST node types over the changed Python code.

    With ``*_sources`` (post-patch file contents keyed by path) for every changed
    Python file of both patches, node types come from the functions that contain
    the added lines (mode ``post_patch_source``). Otherwise they come from the
    patch lines alone, tagged by side (mode ``patch_lines``). The value is None
    when neither patch changes a Python file.
    """
    cpy = [f for f in cand.files if _is_python(f.path)]
    gpy = [f for f in gold.files if _is_python(f.path)]
    if not cpy and not gpy:
        return {"ast_similarity": None, "ast_mode": None}

    def from_source(files: list[FilePatch], src: dict[str, str] | None) -> Counter | None:
        if src is None:
            return None
        total: Counter = Counter()
        for f in files:
            if f.new_path is None:
                continue
            if f.path not in src:
                return None
            c = node_types_from_source(src[f.path], f.added_new_lines())
            if c is None:
                return None
            total += c
        return total

    cs, gs = from_source(cpy, cand_sources), from_source(gpy, gold_sources)
    if cs is not None and gs is not None:
        return {"ast_similarity": multiset_f1(cs, gs), "ast_mode": "post_patch_source"}
    cc: Counter = sum((_patch_node_types(f) for f in cpy), Counter())
    gc: Counter = sum((_patch_node_types(f) for f in gpy), Counter())
    return {"ast_similarity": multiset_f1(cc, gc), "ast_mode": "patch_lines"}


def changed_functions(patch: Patch) -> set[tuple[str, str]]:
    """(path, function name) pairs for Python files, read from the patch alone."""
    return {
        (f.path, name) for f in patch.files if _is_python(f.path) for name in f.changed_functions()
    }


def function_overlap(cand: Patch, gold: Patch) -> dict[str, object]:
    """Jaccard of the changed-function sets and whether they are equal.

    Both values are None when neither patch changes a visible Python function.
    """
    c, g = changed_functions(cand), changed_functions(gold)
    if not c and not g:
        return {"function_jaccard": None, "same_functions": None}
    return {"function_jaccard": len(c & g) / len(c | g), "same_functions": c == g}
