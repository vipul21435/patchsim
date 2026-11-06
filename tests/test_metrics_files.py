import pytest

from patchsim.diff import parse_diff
from patchsim.metrics import edit_size, file_prf, jaccard, location_overlap, prf


def mk(files: dict[str, list[tuple[int, int]]]) -> str:
    """Build a diff that replaces line n of each file with a new line, for each (n, k)
    replacing k consecutive lines starting at n."""
    out = []
    for path, edits in files.items():
        out += [f"diff --git a/{path} b/{path}", f"--- a/{path}", f"+++ b/{path}"]
        for n, k in edits:
            out.append(f"@@ -{n},{k} +{n},{k} @@")
            out += [f"-old {path} {n + j}" for j in range(k)]
            out += [f"+new {path} {n + j}" for j in range(k)]
    return "\n".join(out) + "\n"


def test_prf_closed_form():
    assert prf({1, 2, 3}, {2, 3, 4, 5}) == pytest.approx(
        (2 / 3, 2 / 4, 2 * (2 / 3) * 0.5 / (2 / 3 + 0.5))
    )
    assert prf(set(), set()) == (1.0, 1.0, 1.0)
    assert prf(set(), {1}) == (0.0, 0.0, 0.0)
    assert prf({1}, {2}) == (0.0, 0.0, 0.0)


def test_jaccard():
    assert jaccard({1, 2}, {2, 3}) == pytest.approx(1 / 3)
    assert jaccard(set(), set()) == 1.0


def test_file_prf():
    c = parse_diff(mk({"a.py": [(1, 1)], "b.py": [(1, 1)]}))
    g = parse_diff(mk({"a.py": [(1, 1)], "c.py": [(1, 1)], "d.py": [(1, 1)]}))
    r = file_prf(c, g)
    assert r["file_precision"] == pytest.approx(0.5)
    assert r["file_recall"] == pytest.approx(1 / 3)
    assert r["file_f1"] == pytest.approx(0.4)


def test_location_overlap_closed_form():
    # candidate replaces lines 10-13 of a.py, gold replaces 12-15: overlap {12,13}, union 10..15
    c = parse_diff(mk({"a.py": [(10, 4)]}))
    g = parse_diff(mk({"a.py": [(12, 4)], "b.py": [(1, 2)]}))
    r = location_overlap(c, g)
    assert r["location_jaccard_per_file"]["a.py"] == pytest.approx(2 / 6)
    assert r["location_jaccard_per_file"]["b.py"] == 0.0
    assert r["location_jaccard"] == pytest.approx(2 / 8)


def test_identical_patch_scores_one():
    d = parse_diff(mk({"a.py": [(3, 2), (20, 1)]}))
    assert location_overlap(d, d)["location_jaccard"] == 1.0
    assert file_prf(d, d)["file_f1"] == 1.0
    assert edit_size(d, d) == {"edit_size_ratio": 1.0, "edit_size_balance": 1.0}


def test_edit_size():
    c = parse_diff(mk({"a.py": [(1, 1)]}))  # 2 changed lines
    g = parse_diff(mk({"a.py": [(1, 3)]}))  # 6 changed lines
    assert edit_size(c, g) == {
        "edit_size_ratio": pytest.approx(1 / 3),
        "edit_size_balance": pytest.approx(1 / 3),
    }
    empty = parse_diff("")
    assert edit_size(c, empty) == {"edit_size_ratio": None, "edit_size_balance": 0.0}
    assert edit_size(empty, empty)["edit_size_balance"] == 1.0
