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
    assert len(res["disagreements"]["high_similarity_unresolved"]) == 2
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
