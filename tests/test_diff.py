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


def _fp(text):
    from patchsim.diff import parse_diff

    return parse_diff(text).files[0]


BASE = "a\nb\nc\nd\ne\n"


def test_apply_file_patch_edit_insert_and_offset():
    from patchsim.diff import apply_file_patch

    edit = "--- a/x.py\n+++ b/x.py\n@@ -2,3 +2,3 @@\n b\n-c\n+C\n d\n"
    assert apply_file_patch(BASE, _fp(edit)) == "a\nb\nC\nd\ne\n"
    # stated line is wrong by two; the nearest exact match is used
    shifted = edit.replace("@@ -2,3 +2,3 @@", "@@ -4,3 +4,3 @@")
    assert apply_file_patch(BASE, _fp(shifted)) == "a\nb\nC\nd\ne\n"
    assert apply_file_patch(BASE, _fp(shifted), max_offset=1) is None
    insert = "--- a/x.py\n+++ b/x.py\n@@ -5,0 +6,2 @@\n+f\n+g\n"
    assert apply_file_patch(BASE, _fp(insert)) == BASE + "f\ng\n"
    new = "--- /dev/null\n+++ b/n.py\n@@ -0,0 +1,2 @@\n+x = 1\n+y = 2\n"
    assert apply_file_patch("", _fp(new)) == "x = 1\ny = 2\n"
    bad = "--- a/x.py\n+++ b/x.py\n@@ -2,1 +2,1 @@\n-zzz\n+C\n"
    assert apply_file_patch(BASE, _fp(bad)) is None


def test_without_new_files():
    from patchsim.diff import parse_diff

    p = parse_diff(
        "--- /dev/null\n+++ b/reproduce.py\n@@ -0,0 +1 @@\n+print(1)\n"
        "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n"
        "--- /dev/null\n+++ b/keep.py\n@@ -0,0 +1 @@\n+k\n"
    )
    q, dropped = p.without_new_files({"keep.py"})
    assert dropped == ["reproduce.py"]
    assert q.paths == {"x.py", "keep.py"}


def test_binary_new_and_deleted_files_from_git_headers():
    from patchsim.diff import parse_diff

    p = parse_diff(
        "diff --git a/data.fits b/data.fits\nnew file mode 100644\nindex 0000000..1111111\n"
        "Binary files /dev/null and b/data.fits differ\n"
        "diff --git a/old.bin b/old.bin\ndeleted file mode 100644\n"
        "Binary files a/old.bin and /dev/null differ\n"
    )
    new, gone = p.files
    assert new.old_path is None and new.path == "data.fits" and not new.hunks
    assert gone.new_path is None and gone.path == "old.bin"
    q, dropped = p.without_new_files(set())
    assert dropped == ["data.fits"] and q.paths == {"old.bin"}


def test_hunk_with_overstated_counts_does_not_swallow_next_file():
    from patchsim.diff import parse_diff

    p = parse_diff(
        "--- a/m.py\n+++ b/m.py\n@@ -1,3 +1,5 @@\n def f(xs):\n+    if not xs:\n"
        "+        return 0\n     return xs[0]\n"
        "--- /dev/null\n+++ b/r.py\n@@ -0,0 +1 @@\n+print(1)\n"
    )
    assert [f.path for f in p.files] == ["m.py", "r.py"]
    assert p.files[0].removed == [] and len(p.files[0].added) == 2
    assert p.files[1].old_path is None
