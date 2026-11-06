import json

import pytest

from patchsim.io import Candidate, load_candidates, load_gold, load_outcomes, outcome_for
from patchsim.score import METRICS, score_all, score_pair

GOLD = "--- a/p/m.py\n+++ b/p/m.py\n@@ -1,2 +1,2 @@ def f(x):\n-    return x\n+    return x + 1\n"
OTHER = "--- a/p/n.py\n+++ b/p/n.py\n@@ -5 +5 @@\n-a = 1\n+a = 2\n"


def test_score_pair_identical_and_disjoint():
    r = score_pair(GOLD, GOLD)
    for m in METRICS:
        assert r[m] == 1.0, m
    assert r["same_files"] and r["extra_files"] == []
    d = score_pair(OTHER, GOLD)
    assert d["file_f1"] == 0.0 and d["extra_files"] == ["p/n.py"]
    assert d["location_jaccard"] == 0.0
    assert d["function_jaccard"] == 0.0


def test_score_pair_empty_candidate():
    r = score_pair("", GOLD)
    assert r["empty_candidate"] and r["file_recall"] == 0.0 and r["chrf"] == 0.0


def test_score_all_skips_missing_gold():
    rows = score_all(
        [Candidate("o__r-1", "s", GOLD), Candidate("o__r-2", "s", GOLD)], {"o__r-1": GOLD}
    )
    assert len(rows) == 1 and rows[0]["repo"] == "o__r"


def test_loaders(tmp_path):
    c = tmp_path / "c.jsonl"
    c.write_text(
        json.dumps({"instance_id": "a-1", "model_name_or_path": "sys", "model_patch": GOLD})
        + "\n\n"
        + json.dumps({"instance_id": "a-2", "model": "sys2", "patch": ""})
        + "\n"
    )
    cands = load_candidates(c)
    assert [(x.instance_id, x.system) for x in cands] == [("a-1", "sys"), ("a-2", "sys2")]
    assert load_candidates(c, system="X")[0].system == "X"

    g = tmp_path / "g.json"
    g.write_text(json.dumps([{"instance_id": "a-1", "patch": GOLD, "repo": "a"}]))
    assert load_gold(g) == {"a-1": GOLD}

    o = tmp_path / "o.jsonl"
    o.write_text('{"instance_id": "a-1", "resolved": true, "model": "sys"}\n')
    out = load_outcomes(o)
    assert outcome_for(out, "sys", "a-1") is True
    assert outcome_for(out, "sys", "a-2") is None

    r = tmp_path / "results.json"
    r.write_text(json.dumps({"resolved": ["a-1"], "no_generation": []}))
    out = load_outcomes(r)
    assert outcome_for(out, "any", "a-1") is True
    assert outcome_for(out, "any", "a-9") is False


def test_bad_jsonl(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text("{not json}\n")
    with pytest.raises(ValueError, match="bad.jsonl:1"):
        load_gold(p)
    q = tmp_path / "bad.json"
    q.write_text("[1, 2]")
    with pytest.raises(ValueError):
        load_gold(q)


def test_score_pair_ignore_new_files_and_post_patch_source(tmp_path):
    from patchsim.score import post_patch_sources, score_pair

    base = tmp_path / "base"
    (base / "pkg").mkdir(parents=True)
    (base / "pkg" / "m.py").write_text("def f(x):\n    return x\n\n\ndef g():\n    pass\n")
    gold = (
        "--- a/pkg/m.py\n+++ b/pkg/m.py\n@@ -1,2 +1,2 @@\n"
        " def f(x):\n-    return x\n+    return x + 1\n"
    )
    cand = gold + "--- /dev/null\n+++ b/reproduce.py\n@@ -0,0 +1 @@\n+print(1)\n"
    plain = score_pair(cand, gold)
    assert plain["file_precision"] == 0.5 and plain["extra_files"] == ["reproduce.py"]
    r = score_pair(cand, gold, ignore_new_files=True, base_dir=base)
    assert r["dropped_files"] == ["reproduce.py"]
    assert r["file_f1"] == 1.0 and r["same_files"] is True
    assert r["ast_mode"] == "post_patch_source" and r["ast_similarity"] == 1.0
    # missing pre-patch file: fall back to patch lines
    r2 = score_pair(cand, gold, ignore_new_files=True, base_dir=tmp_path / "nowhere")
    assert r2["ast_mode"] == "patch_lines"
    # a hunk that does not apply also falls back
    bad = gold.replace(" def f(x):", " def h(x):")
    assert post_patch_sources(parse_diff(bad), base) is None


def parse_diff(text):
    from patchsim.diff import parse_diff as p

    return p(text)
