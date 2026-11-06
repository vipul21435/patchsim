from collections import Counter

import pytest

from patchsim.astsim import (
    ast_similarity,
    function_overlap,
    node_types_from_lines,
    node_types_from_source,
)
from patchsim.diff import parse_diff


def py_diff(path: str, header: str, removed: list[str], added: list[str], start: int = 1) -> str:
    lines = [f"--- a/{path}", f"+++ b/{path}"]
    lines.append(f"@@ -{start},{len(removed) + 1} +{start},{len(added) + 1} @@ {header}")
    lines.append(" " + "def f(x):" if not header else " pass_marker = 0")
    lines += ["-" + r for r in removed] + ["+" + a for a in added]
    return "\n".join(lines) + "\n"


def test_node_types_whole_block():
    c = node_types_from_lines(["    return x + 1"])
    assert c == Counter({"Return": 1, "BinOp": 1, "Name": 1, "Add": 1, "Constant": 1})


def test_node_types_fragment_fallback():
    # "if x:" alone does not parse; it is completed with "pass"; "else:" is skipped
    c = node_types_from_lines(["if x:", "    y()", "else:"])
    assert c == Counter({"If": 1, "Name": 2, "Pass": 1, "Expr": 1, "Call": 1})
    assert node_types_from_lines(["elif y > 0:"])["Compare"] == 1
    assert node_types_from_lines(["   ", ")"]) == Counter()


def test_node_types_from_source_picks_enclosing_function():
    src = "def a():\n    return 1\n\ndef b(x):\n    return x\n\nZ = 3\n"
    c = node_types_from_source(src, [5])
    assert c == Counter({"FunctionDef": 1, "arguments": 1, "arg": 1, "Return": 1, "Name": 1})
    top = node_types_from_source(src, [7])
    assert top == Counter({"Assign": 1, "Name": 1, "Constant": 1})
    assert node_types_from_source("def (:", [1]) is None


def test_ast_similarity_patch_lines():
    g = parse_diff(py_diff("m.py", "", ["    return x"], ["    return x + 1"]))
    c = parse_diff(py_diff("m.py", "", ["    return x"], ["    return x - 1"]))
    r = ast_similarity(c, g)
    # removed sides identical (Return, Name); added sides differ only in Add vs Sub:
    # 7 tags each side, 6 shared
    assert r == {"ast_similarity": pytest.approx(12 / 14), "ast_mode": "patch_lines"}


def test_ast_similarity_with_sources_and_missing_source():
    g = parse_diff(py_diff("m.py", "", [], ["    return x + 1"]))
    c = parse_diff(py_diff("m.py", "", [], ["    return x + 1"]))
    src = {"m.py": "def f(x):\n    return x + 1\n"}
    r = ast_similarity(c, g, src, src)
    assert r == {"ast_similarity": 1.0, "ast_mode": "post_patch_source"}
    r2 = ast_similarity(c, g, {}, src)
    assert r2["ast_mode"] == "patch_lines"


def test_ast_similarity_non_python():
    d = parse_diff("--- a/r.md\n+++ b/r.md\n@@ -1 +1 @@\n-a\n+b\n")
    assert ast_similarity(d, d) == {"ast_similarity": None, "ast_mode": None}


def test_function_overlap():
    g = parse_diff(py_diff("m.py", "def f(x):", ["    a"], ["    b"]))
    c = parse_diff(py_diff("m.py", "def g(x):", ["    a"], ["    b"]))
    assert function_overlap(g, g) == {"function_jaccard": 1.0, "same_functions": True}
    assert function_overlap(c, g) == {"function_jaccard": 0.0, "same_functions": False}
    d = parse_diff("--- a/r.md\n+++ b/r.md\n@@ -1 +1 @@\n-a\n+b\n")
    assert function_overlap(d, d) == {"function_jaccard": None, "same_functions": None}


def test_added_new_lines():
    d = parse_diff("--- a/m.py\n+++ b/m.py\n@@ -3,2 +3,3 @@\n keep\n+new\n-old\n+new2\n")
    assert d.files[0].added_new_lines() == [4, 5]
