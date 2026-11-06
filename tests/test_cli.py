import importlib.util
import json
from pathlib import Path

import pytest

from patchsim.analysis import analyze, attach_outcomes
from patchsim.cli import main
from patchsim.io import load_candidates, load_gold, load_outcomes
from patchsim.score import score_all

ROOT = Path(__file__).resolve().parents[1]


def load_demo():
    spec = importlib.util.spec_from_file_location("demo", ROOT / "examples" / "demo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def demo_dir(tmp_path):
    load_demo().write(tmp_path)
    return tmp_path


def test_analyze_shares_and_examples(demo_dir):
    rows = score_all(
        load_candidates(demo_dir / "candidates.jsonl"), load_gold(demo_dir / "gold.jsonl")
    )
    rows = attach_outcomes(rows, load_outcomes(demo_dir / "outcomes.jsonl"))
    res = analyze(rows, n_boot=200, examples=2)
    assert res["n_candidates"] == 12 and res["n_resolved"] == 7 and res["n_repos"] == 3
    sh = res["shares"]
    # resolved candidates in other files: widgets-3 is unresolved; cli-2 (sys-a) is resolved
    assert sh["resolved_touching_files_outside_gold"]["count"] == 1
    assert sh["resolved_touching_files_outside_gold"]["of"] == 7
    # every unresolved candidate except acme__widgets-3 touches exactly the gold file
    assert sh["unresolved_touching_exactly_gold_files"] == {"count": 4, "of": 5, "share": 0.8}
    assert res["disagreements"]["different_files_resolved"][0]["instance_id"] == "gamma__cli-2"
    d = res["disagreements"]
    # best chrF threshold is 1.0 (accuracy 9 of 12): no unresolved candidate reaches it,
    # and three resolved ones fall below it; examples are capped at 2, lowest first
    assert d["threshold"] == 1.0 and res["metrics"]["chrf"]["accuracy"] == 0.75
    assert d["n_high_similarity_unresolved"] == 0 and d["high_similarity_unresolved"] == []
    assert d["n_low_similarity_resolved"] == 3
    assert [e["instance_id"] for e in d["low_similarity_resolved"]] == [
        "gamma__cli-2",
        "beta__parse-3",
    ]
    # every listed example lies on the wrong side of the threshold
    assert all(e["chrf"] < d["threshold"] for e in d["low_similarity_resolved"])
    for m in res["metrics"].values():
        if m["auc"] is not None:
            assert 0.0 <= m["auc"] <= 1.0


def test_cli_score_and_analyze(demo_dir, tmp_path, capsys):
    args = [
        "--candidates",
        str(demo_dir / "candidates.jsonl"),
        "--gold",
        str(demo_dir / "gold.jsonl"),
    ]
    out = tmp_path / "rows.jsonl"
    assert main(["score", *args, "--out", str(out)]) == 0
    assert len(out.read_text().splitlines()) == 12
    assert "| sys-a | 8 |" in capsys.readouterr().out

    js, md = tmp_path / "a.json", tmp_path / "a.md"
    rc = main(
        [
            "analyze",
            *args,
            "--outcomes",
            str(demo_dir / "outcomes.jsonl"),
            "--n-boot",
            "100",
            "--json",
            str(js),
            "--markdown",
            str(md),
        ]
    )
    assert rc == 0
    text = capsys.readouterr().out
    assert "| chrf |" in text and "## Disagreements (chrf)" in text
    assert md.read_text() == text
    assert json.loads(js.read_text())["n_boot"] == 100


def test_cli_no_matches(tmp_path, capsys):
    (tmp_path / "c.jsonl").write_text('{"instance_id": "x-1", "patch": ""}\n')
    (tmp_path / "g.jsonl").write_text('{"instance_id": "y-1", "patch": ""}\n')
    assert (
        main(
            [
                "score",
                "--candidates",
                str(tmp_path / "c.jsonl"),
                "--gold",
                str(tmp_path / "g.jsonl"),
            ]
        )
        == 1
    )
    (tmp_path / "o.jsonl").write_text('{"instance_id": "z-1", "resolved": true}\n')
    (tmp_path / "g.jsonl").write_text('{"instance_id": "x-1", "patch": ""}\n')
    rc = main(
        [
            "analyze",
            "--candidates",
            str(tmp_path / "c.jsonl"),
            "--gold",
            str(tmp_path / "g.jsonl"),
            "--outcomes",
            str(tmp_path / "o.jsonl"),
        ]
    )
    assert rc == 1


def test_cli_help(capsys):
    assert main([]) == 0
    assert "analyze" in capsys.readouterr().out


def test_cli_ignore_new_files_flag(demo_dir, tmp_path):
    out = tmp_path / "rows.jsonl"
    args = [
        "--candidates",
        str(demo_dir / "candidates.jsonl"),
        "--gold",
        str(demo_dir / "gold.jsonl"),
    ]
    assert main(["score", *args, "--ignore-new-files", "--out", str(out)]) == 0
    rows = [json.loads(x) for x in out.read_text().splitlines()]
    assert all("dropped_files" in r for r in rows)


def test_empty_candidates_excluded_by_default():
    gold = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a = 1\n+a = 2\n"
    rows = []
    for i, (patch, ok) in enumerate([(gold, True), ("", False), (gold, False), (gold, True)]):
        from patchsim.score import score_pair

        rows.append(
            {"instance_id": f"o__r-{i}", "system": "s", "repo": f"r{i % 2}", "resolved": ok}
            | score_pair(patch, gold)
        )
    res = analyze(rows, n_boot=50)
    assert res["n_empty"] == 1 and res["n_candidates"] == 3
    # the three non-empty candidates are identical to gold: no separation
    assert res["metrics"]["chrf"]["auc"] == 0.5
    kept = analyze(rows, n_boot=50, exclude_empty=False)
    assert kept["n_candidates"] == 4
    # pairs: each positive beats the empty one (1) and ties the other (0.5): 3 / 4
    assert kept["metrics"]["chrf"]["auc"] == pytest.approx(0.75)


def test_cli_compare(demo_dir, tmp_path, capsys):
    base = [
        "--candidates",
        str(demo_dir / "candidates.jsonl"),
        "--gold",
        str(demo_dir / "gold.jsonl"),
    ]
    js = tmp_path / "cmp.json"
    md = tmp_path / "cmp.md"
    rc = main(
        [
            "compare",
            *base,
            "--outcomes",
            str(demo_dir / "outcomes.jsonl"),
            "--n-boot",
            "50",
            "--json",
            str(js),
            "--markdown",
            str(md),
        ]
    )
    assert rc == 0
    res = json.loads(js.read_text())
    assert (res["a"], res["b"]) == ("sys-a", "sys-b")
    assert res["n_shared"] > 0 and "auc_diff" in res["metrics"]["chrf"]
    assert "patchsim comparison" in md.read_text()
    # B given as a separate file, no outcomes
    rc = main(
        [
            "compare",
            *base,
            "--system",
            "x",
            "--candidates-b",
            str(demo_dir / "candidates.jsonl"),
            "--system-b",
            "y",
            "--n-boot",
            "20",
        ]
    )
    assert rc == 0
    assert "| chrf |" in capsys.readouterr().out
    assert main(["compare", *base, "--a", "sys-a", "--b", "sys-a"]) == 1


def test_cli_include_system(demo_dir, tmp_path):
    out = tmp_path / "rows.jsonl"
    args = [
        "--candidates",
        str(demo_dir / "candidates.jsonl"),
        "--gold",
        str(demo_dir / "gold.jsonl"),
    ]
    assert main(["score", *args, "--include-system", "sys-b", "--out", str(out)]) == 0
    assert {json.loads(x)["system"] for x in out.read_text().splitlines()} == {"sys-b"}
    assert main(["score", *args, "--include-system", "nobody"]) == 1


def test_within_instance_auc_in_analysis():
    from patchsim.analysis import within_instance_auc

    rows = [
        {"instance_id": "o__a-1", "repo": "o__a", "chrf": 0.9, "resolved": True},
        {"instance_id": "o__a-1", "repo": "o__a", "chrf": 0.4, "resolved": False},
        {"instance_id": "o__b-1", "repo": "o__b", "chrf": 0.2, "resolved": True},
        {"instance_id": "o__b-1", "repo": "o__b", "chrf": 0.3, "resolved": False},
        {"instance_id": "o__b-2", "repo": "o__b", "chrf": 0.5, "resolved": True},
    ]
    r = within_instance_auc(rows, "chrf", n_boot=100)
    assert r["n_instances"] == 2 and r["n_pairs"] == 2
    assert r["value"] == 0.5
    assert 0.0 <= r["low"] <= r["high"] <= 1.0


def test_pair_example_closed_form():
    spec = importlib.util.spec_from_file_location("pair", ROOT / "examples" / "pair.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = mod.run()
    kept, aside = out["all files"], out["new files set aside"]
    assert kept["file_precision"] == 0.5 and kept["extra_files"] == ["reproduce.py"]
    assert aside["dropped_files"] == ["reproduce.py"] and aside["file_f1"] == 1.0
    # added tokens: gold {if, not, xs, :, return, 0.0}; candidate {if, len, (, xs, ), =, =, 0,
    # :, return, 0.0}; 5 shared, so F1 = 2 * 5 / (6 + 11)
    assert aside["token_f1"] == pytest.approx(10 / 17)
