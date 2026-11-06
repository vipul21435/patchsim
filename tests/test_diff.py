from patchsim.diff import parse_diff

DIFF = "\n".join(
    [
        "diff --git a/pkg/mod.py b/pkg/mod.py",
        "--- a/pkg/mod.py",
        "+++ b/pkg/mod.py",
        "@@ -1,6 +1,7 @@ import os",
        " def f(x):",
        "-    return x",
        "+    return x + 1",
        " ",
        " def g(y):",
        "+    y = y * 2",
        "     return y",
        " ",
        "diff --git a/README.md b/README.md",
        "--- a/README.md",
        "+++ b/README.md",
        "@@ -10,2 +10,2 @@",
        "-old line",
        "+new line",
        " tail",
        "",
    ]
)


def test_files_and_lines():
    p = parse_diff(DIFF)
    assert p.paths == {"pkg/mod.py", "README.md"}
    mod = p.by_path()["pkg/mod.py"]
    assert mod.removed == ["    return x"]
    assert mod.added == ["    return x + 1", "    y = y * 2"]
    assert p.n_added == 3 and p.n_removed == 2


def test_touched_positions():
    p = parse_diff(DIFF).by_path()
    # line 2 removed -> 4; insertion after line 4 -> gap 9
    assert p["pkg/mod.py"].touched_positions() == {4, 9}
    assert p["README.md"].touched_positions() == {20}


def test_changed_functions_from_patch():
    p = parse_diff(DIFF).by_path()
    assert p["pkg/mod.py"].changed_functions() == {"f", "g"}


def test_new_and_deleted_files():
    text = """diff --git a/new.py b/new.py
new file mode 100644
--- /dev/null
+++ b/new.py
@@ -0,0 +1,2 @@
+a = 1
+b = 2
diff --git a/old.py b/old.py
deleted file mode 100644
--- a/old.py
+++ /dev/null
@@ -1 +0,0 @@
-x = 1
"""
    p = parse_diff(text)
    files = p.by_path()
    assert set(files) == {"new.py", "old.py"}
    assert files["new.py"].old_path is None
    assert files["new.py"].touched_positions() == {1}
    assert files["old.py"].touched_positions() == {2}


def test_plain_diff_without_git_header_and_no_newline_marker():
    text = """--- a/x.py
+++ b/x.py
@@ -1,2 +1,2 @@
 keep
-a
\\ No newline at end of file
+b
\\ No newline at end of file
--- a/y.py
+++ b/y.py
@@ -3 +3 @@
-c
+d
"""
    p = parse_diff(text)
    assert p.paths == {"x.py", "y.py"}
    assert p.by_path()["x.py"].removed == ["a"]
    assert p.by_path()["y.py"].touched_positions() == {6}


def test_empty_diff():
    p = parse_diff("")
    assert p.files == [] and p.paths == set()
