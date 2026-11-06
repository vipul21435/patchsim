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
    lines.append(" " + "def f(x):" if not header else "     pass_marker = 0")
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


def test_invalid_escape_in_fragment_emits_no_warning():
    import warnings

    from patchsim.astsim import node_types_from_lines

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        c = node_types_from_lines(['x = re.compile("\\d+")'])
    assert c["Assign"] == 1


CLS = (
    "class A:\n"  # 1
    "    x = 1\n"  # 2
    "\n"  # 3
    "    def f(self):\n"  # 4
    "        a = 1\n"  # 5
    "        return a\n"  # 6
    "\n"  # 7
    "\n"  # 8
    "class B:\n"  # 9
    "    def g(self):\n"  # 10
    "        b = 2\n"  # 11
    "        return b * 2\n"  # 12
)


def _post_patch(diff: str, files: dict[str, str]):
    from patchsim.diff import apply_file_patch_lines

    p = parse_diff(diff)
    return p, {f.path: apply_file_patch_lines(files[f.path], f) for f in p.files}


def test_deletion_only_patches_in_different_methods_differ():
    del_f = "--- a/m.py\n+++ b/m.py\n@@ -5,2 +5,1 @@\n-        a = 1\n         return a\n"
    del_g = "--- a/m.py\n+++ b/m.py\n@@ -11,2 +11,1 @@\n-        b = 2\n         return b * 2\n"
    c, cs = _post_patch(del_f, {"m.py": CLS})
    g, gs = _post_patch(del_g, {"m.py": CLS})
    assert cs["m.py"].removed_lines == [5] and gs["m.py"].removed_lines == [11]
    r = ast_similarity(c, g, cs, gs)
    assert r["ast_mode"] == "post_patch_source"
    # each side counts its pre-patch method, tagged '-'. f: FunctionDef, arguments, arg,
    # Assign, Name, Constant, Return, Name = 8 nodes. g adds BinOp, Mult and a second
    # Constant: 11 nodes. Shared 8, F1 = 2 * 8 / (8 + 11); before removed lines were
    # counted both multisets were empty and the value was 1.0.
    assert r["ast_similarity"] == pytest.approx(16 / 19)
    f_nodes = node_types_from_source(CLS, [5], "-")
    assert sum(f_nodes.values()) == 8 and set(f_nodes) == {
        "-FunctionDef", "-arguments", "-arg", "-Assign", "-Name", "-Constant", "-Return"
    }  # fmt: skip
    # deleting the method body line against deleting the class attribute shares nothing
    del_x = "--- a/m.py\n+++ b/m.py\n@@ -1,2 +1,1 @@\n class A:\n-    x = 1\n"
    x, xs = _post_patch(del_x, {"m.py": CLS})
    # x = 1 is {-Assign, -Name, -Constant}, all three in g: 2 * 3 / (3 + 11)
    assert ast_similarity(x, g, xs, gs)["ast_similarity"] == pytest.approx(6 / 14)


def test_deletion_only_is_not_empty_against_addition():
    del_g = "--- a/m.py\n+++ b/m.py\n@@ -11,2 +11,1 @@\n-        b = 2\n         return b * 2\n"
    add_f = "--- a/m.py\n+++ b/m.py\n@@ -5,1 +5,2 @@\n         a = 1\n+        a += 1\n"
    g, gs = _post_patch(del_g, {"m.py": CLS})
    c, cs = _post_patch(add_f, {"m.py": CLS})
    # removed side tagged '-', added side tagged '+': no shared tags
    assert ast_similarity(c, g, cs, gs)["ast_similarity"] == 0.0


def test_class_attribute_counts_one_statement():
    # a line in a class body outside any method gives that statement, not the class
    assert node_types_from_source(CLS, [2]) == Counter({"Assign": 1, "Name": 1, "Constant": 1})
    # a class header line gives the ClassDef with its bases, not the body
    src = "@dec\nclass C(Base, metaclass=M):\n    y = 2\n"
    header = Counter({"ClassDef": 1, "Name": 3, "keyword": 1})
    assert node_types_from_source(src, [2]) == header
    assert node_types_from_source(src, [1]) == header
    # a decorator line of a method gives the method
    meth = "class D:\n    @staticmethod\n    def h():\n        return 0\n"
    assert node_types_from_source(meth, [2])["FunctionDef"] == 1


def test_class_attribute_edit_against_unrelated_method_edit():
    add_attr = "--- a/m.py\n+++ b/m.py\n@@ -2,1 +2,2 @@\n     x = 1\n+    y = 2\n"
    add_meth = "--- a/m.py\n+++ b/m.py\n@@ -11,1 +11,2 @@\n         b = 2\n+        c = 3\n"
    c, cs = _post_patch(add_attr, {"m.py": CLS})
    g, gs = _post_patch(add_meth, {"m.py": CLS})
    # candidate: the new statement y = 2 -> {+Assign, +Name, +Constant} (3 nodes)
    # gold: post-patch g -> FunctionDef, arguments, arg, Assign x2, Name x3, Constant x3,
    # Return, BinOp, Mult (14 nodes); shared Assign, Name, Constant = 3; F1 = 2*3 / (3 + 14).
    # Counting the whole class for y = 2, as before, gave 0.83 here.
    assert ast_similarity(c, g, cs, gs)["ast_similarity"] == pytest.approx(6 / 17)


def test_applied_lines_follow_the_offset():
    from patchsim.diff import apply_file_patch_lines

    d = parse_diff(
        "--- a/m.py\n+++ b/m.py\n@@ -1,2 +1,2 @@\n"
        "         b = 2\n-        return b * 2\n+        return -b\n"
    )
    a = apply_file_patch_lines(CLS, d.files[0])
    assert a.removed_lines == [12] and a.added_lines == [12]
    assert a.post.splitlines()[11] == "        return -b"
