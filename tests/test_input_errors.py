import json

import pytest

from patchsim.cli import main
from patchsim.io import load_candidates, load_gold, load_outcomes

GOLD = {"instance_id": "a__b-1", "patch": "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n"}
CAND = {"instance_id": "a__b-1", "model": "s", "patch": GOLD["patch"]}


def _jsonl(path, rows):
    path.write_text("".join((r if isinstance(r, str) else json.dumps(r)) + "\n" for r in rows))
    return str(path)


def _analyze(tmp_path, cands, gold, outs):
    return main(
        [
            "analyze",
            "--candidates", _jsonl(tmp_path / "c.jsonl", cands),
            "--gold", _jsonl(tmp_path / "g.jsonl", gold),
            "--outcomes", _jsonl(tmp_path / "o.jsonl", outs),
            "--n-boot", "10",
        ]
    )  # fmt: skip


def test_missing_file_is_one_line(tmp_path, capsys):
    rc = main(["score", "--candidates", str(tmp_path / "nope.jsonl"), "--gold", "x"])
    err = capsys.readouterr().err
    assert rc == 2
    assert err == f"patchsim: {tmp_path / 'nope.jsonl'}: no such file\n"


def test_malformed_line_names_file_and_line(tmp_path, capsys):
    rc = _analyze(tmp_path, [CAND, "{not json"], [GOLD], [{"instance_id": "a__b-1", "resolved": 1}])
    err = capsys.readouterr().err
    assert rc == 2
    assert err.startswith(f"patchsim: {tmp_path / 'c.jsonl'}:2: ")
    assert "Traceback" not in err


def test_missing_instance_id(tmp_path, capsys):
    rc = _analyze(tmp_path, [{"model": "s", "patch": "x"}], [GOLD], [])
    assert rc == 2
    assert capsys.readouterr().err == f"patchsim: {tmp_path / 'c.jsonl'}:1: missing 'instance_id'\n"


def test_missing_resolved(tmp_path, capsys):
    rc = _analyze(tmp_path, [CAND], [GOLD], [{"instance_id": "a__b-1"}])
    assert rc == 2
    assert capsys.readouterr().err == f"patchsim: {tmp_path / 'o.jsonl'}:1: missing 'resolved'\n"


def test_gold_without_patch(tmp_path):
    with pytest.raises(ValueError, match=r"g.jsonl:1: missing 'patch'"):
        load_gold(_jsonl(tmp_path / "g.jsonl", [{"instance_id": "a__b-1"}]))


def test_row_that_is_not_an_object(tmp_path):
    with pytest.raises(ValueError, match=r"c.jsonl:1: expected a JSON object"):
        load_candidates(_jsonl(tmp_path / "c.jsonl", ["5"]))


def test_malformed_json_list(tmp_path):
    p = tmp_path / "g.json"
    p.write_text('[{"instance_id": "a"},\n oops]')
    with pytest.raises(ValueError, match=r"g.json:2: "):
        load_gold(p)


def test_malformed_results_object(tmp_path):
    p = tmp_path / "r.json"
    p.write_text('{"resolved": [oops]}')
    with pytest.raises(ValueError, match=r"r.json:1: "):
        load_outcomes(p)


@pytest.mark.parametrize("value", ["false", "true", 2, None, 0.5])
def test_resolved_flag_rejects_non_booleans(tmp_path, value):
    p = _jsonl(tmp_path / "o.jsonl", [{"instance_id": "a__b-1", "resolved": value}])
    with pytest.raises(ValueError):
        load_outcomes(p)


def test_resolved_flag_accepts_bool_and_0_1(tmp_path):
    rows = [
        {"instance_id": "a", "resolved": True},
        {"instance_id": "b", "resolved": False},
        {"instance_id": "c", "resolved": 1},
        {"instance_id": "d", "resolved": 0},
    ]
    out = load_outcomes(_jsonl(tmp_path / "o.jsonl", rows))
    assert out == {(None, "a"): True, (None, "b"): False, (None, "c"): True, (None, "d"): False}


def test_key_error_fallback(tmp_path, capsys, monkeypatch):
    import patchsim.cli as cli

    def boom(args):
        raise KeyError("thing")

    monkeypatch.setattr(cli, "_run", boom)
    assert main(["score", "--candidates", "c", "--gold", "g"]) == 2
    assert capsys.readouterr().err == "patchsim: missing key 'thing'\n"


@pytest.mark.parametrize(
    "flag, value, msg",
    [
        ("--level", "95", "between 0 and 1"),
        ("--level", "0", "between 0 and 1"),
        ("--n-boot", "-5", "at least 1"),
        ("--examples", "-1", "at least 0"),
    ],
)
def test_bad_numeric_options_are_one_line(tmp_path, capsys, flag, value, msg):
    args = [
        "analyze",
        "--candidates", _jsonl(tmp_path / "c.jsonl", [CAND]),
        "--gold", _jsonl(tmp_path / "g.jsonl", [GOLD]),
        "--outcomes", _jsonl(tmp_path / "o.jsonl", [{"instance_id": "a__b-1", "resolved": True}]),
        flag, value,
    ]  # fmt: skip
    with pytest.raises(SystemExit) as e:
        main(args)
    assert e.value.code == 2
    err = capsys.readouterr().err
    assert msg in err and "Traceback" not in err
