"""A diff that names the same file in several sections is one file patch."""

import random

from patchsim.diff import parse_diff
from patchsim.score import post_patch_sources, score_pair

ONE = (
    "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
    "@@ -1,1 +1,1 @@\n-a = 1\n+a = 2\n@@ -10,1 +10,1 @@\n-b = 1\n+b = 2\n"
)
SPLIT = (
    "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1,1 +1,1 @@\n-a = 1\n+a = 2\n"
    "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -10,1 +10,1 @@\n-b = 1\n+b = 2\n"
)


def test_split_sections_merge_into_one_file():
    p = parse_diff(SPLIT)
    assert len(p.files) == 1
    assert [h.old_start for h in p.files[0].hunks] == [1, 10]
    r = score_pair(SPLIT, ONE)
    assert r["location_jaccard"] == 1.0
    assert r["token_f1"] == r["chrf"] == 1.0


def test_split_sections_out_of_order_are_sorted():
    a, b = SPLIT.split("diff --git")[1:]
    p = parse_diff("diff --git" + b + "diff --git" + a)
    assert [h.old_start for h in p.files[0].hunks] == [1, 10]


def test_split_sections_apply_once_in_post_patch_mode(tmp_path):
    src = "".join(
        "a = 1\n" if i == 1 else "b = 1\n" if i == 10 else f"x{i} = 0\n" for i in range(1, 13)
    )
    (tmp_path / "x.py").write_text(src)
    applied = post_patch_sources(parse_diff(SPLIT), tmp_path)
    assert list(applied) == ["x.py"]
    post = applied["x.py"].post.splitlines()
    assert post[0] == "a = 2" and post[9] == "b = 2"
    r = score_pair(SPLIT, ONE, base_dir=tmp_path)
    assert r["ast_mode"] == "post_patch_source" and r["ast_similarity"] == 1.0


def test_random_split_does_not_change_any_metric():
    rng = random.Random(3)
    for _ in range(50):
        starts = sorted(rng.sample(range(1, 200, 5), rng.randint(2, 5)))
        hunks = [f"@@ -{s},1 +{s},1 @@\n-v{s} = 0\n+v{s} = {rng.randint(1, 9)}\n" for s in starts]
        head = "diff --git a/m.py b/m.py\n--- a/m.py\n+++ b/m.py\n"
        whole = head + "".join(hunks)
        order = hunks[:]
        rng.shuffle(order)
        split = "".join(head + h for h in order)
        a, b = score_pair(split, whole), score_pair(whole, whole)
        for k in ("location_jaccard", "token_f1", "chrf", "ast_similarity", "edit_size_balance"):
            assert a[k] == b[k], k


def test_sources_path_outside_the_instance_directory_is_not_read(tmp_path):
    base = tmp_path / "srcs" / "i"
    base.mkdir(parents=True)
    (tmp_path / "outside.py").write_text("a = 1\n")
    d = "--- a/../../outside.py\n+++ b/../../outside.py\n@@ -1 +1 @@\n-a = 1\n+a = 2\n"
    assert post_patch_sources(parse_diff(d), base) is None
    d = f"--- a/{tmp_path}/outside.py\n+++ b/{tmp_path}/outside.py\n@@ -1 +1 @@\n-a = 1\n+a = 2\n"
    assert post_patch_sources(parse_diff(d), base) is None
