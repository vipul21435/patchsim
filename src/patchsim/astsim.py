"""AST-level similarity for Python files and the set of changed functions."""

from __future__ import annotations

import ast
import textwrap
import warnings
from collections import Counter
from collections.abc import Mapping

from .diff import AppliedFile, FilePatch, Patch
from .textsim import multiset_f1

# Expression-context and wrapper nodes carry no information about the edit.
_SKIP = {"Module", "Load", "Store", "Del"}


def _parse(code: str) -> ast.Module:
    """ast.parse with warnings about invalid escapes in fragments silenced (a
    SyntaxWarning from Python 3.12, a DeprecationWarning before)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        warnings.simplefilter("ignore", DeprecationWarning)
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


def _span(node: ast.AST) -> tuple[int, int]:
    """First and last line of a statement, decorators included."""
    first = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    return first, getattr(node, "end_lineno", node.lineno)


_FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)


def _enclosing_nodes(tree: ast.Module, lines: set[int]) -> list[tuple[ast.AST, bool]]:
    """The node to count for each line, as (node, header_only) pairs.

    A line inside a function gives the innermost function. Otherwise the module
    body is searched for the statement containing the line, descending into class
    bodies, so a class attribute gives that one statement rather than the whole
    class. A line of a class header (decorators, bases) that is in no body
    statement gives the class with ``header_only`` set: the ClassDef node and its
    decorators, bases and keywords, without the body.
    """
    found: dict[int, tuple[ast.AST, bool]] = {}
    funcs = [n for n in ast.walk(tree) if isinstance(n, _FUNCS)]
    for ln in lines:
        best: ast.AST | None = None
        header = False
        for f in funcs:
            first, last = _span(f)
            if first <= ln <= last and (best is None or first >= _span(best)[0]):
                best = f
        if best is None:
            body = tree.body
            while True:
                stmt = next((n for n in body if _span(n)[0] <= ln <= _span(n)[1]), None)
                if stmt is None:
                    header = best is not None
                    break
                best = stmt
                if not isinstance(stmt, ast.ClassDef):
                    break
                body = stmt.body
        if best is not None:
            found[id(best)] = (best, header)
    return list(found.values())


def _count_class_header(node: ast.ClassDef, out: Counter, tag: str) -> None:
    out[tag + "ClassDef"] += 1
    for part in node.decorator_list + node.bases + node.keywords:
        _count(part, out, tag)


def node_types_from_source(source: str, changed_lines: list[int], tag: str = "") -> Counter | None:
    """Multiset of node types of the functions (or other innermost statements, see
    :func:`_enclosing_nodes`) of ``source`` that contain any of ``changed_lines``,
    each type prefixed with ``tag``. None if the source does not parse."""
    try:
        tree = _parse(source)
    except SyntaxError:
        return None
    out: Counter = Counter()
    for node, header_only in _enclosing_nodes(tree, set(changed_lines)):
        if header_only and isinstance(node, ast.ClassDef):
            _count_class_header(node, out, tag)
        else:
            _count(node, out, tag)
    return out


def _patch_node_types(fp: FilePatch) -> Counter:
    return node_types_from_lines(fp.removed, "-") + node_types_from_lines(fp.added, "+")


def ast_similarity(
    cand: Patch,
    gold: Patch,
    cand_sources: Mapping[str, str | AppliedFile] | None = None,
    gold_sources: Mapping[str, str | AppliedFile] | None = None,
) -> dict[str, object]:
    """Multiset F1 of AST node types over the changed Python code.

    With ``*_sources`` for every changed Python file of both patches, node types
    come from the source (mode ``post_patch_source``): the enclosing functions or
    statements of the added lines in the post-patch file, tagged ``+``, and, when
    a source is an :class:`AppliedFile`, those of the removed lines in the
    pre-patch file, tagged ``-``. A plain string source is the post-patch text
    alone, and removed lines are then not counted. Without sources node types come
    from the patch lines, tagged by side (mode ``patch_lines``). The value is None
    when neither patch changes a Python file.
    """
    cpy = [f for f in cand.files if _is_python(f.path)]
    gpy = [f for f in gold.files if _is_python(f.path)]
    if not cpy and not gpy:
        return {"ast_similarity": None, "ast_mode": None}

    def from_source(
        files: list[FilePatch], src: Mapping[str, str | AppliedFile] | None
    ) -> Counter | None:
        if src is None:
            return None
        total: Counter = Counter()
        for f in files:
            entry = src.get(f.path)
            if isinstance(entry, AppliedFile):
                sides = [
                    (entry.post, entry.added_lines, "+"),
                    (entry.pre, entry.removed_lines, "-"),
                ]
            elif f.new_path is None:
                continue
            elif entry is None:
                return None
            else:
                sides = [(entry, f.added_new_lines(), "+")]
            for text, lines, tag in sides:
                if not lines:
                    continue
                c = node_types_from_source(text, lines, tag)
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
