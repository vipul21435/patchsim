import pytest

from patchsim.compare import compare
from patchsim.stats import auc


def make_rows():
    rows = []
    for i in range(12):
        repo = f"r{i % 3}"
        iid = f"o__{repo}-{i}"
        # system B is uniformly 0.25 more similar than A
        sa, sb = 0.1 + 0.05 * i, 0.35 + 0.05 * i
        rows.append(
            {"instance_id": iid, "system": "A", "repo": repo, "chrf": sa, "resolved": i >= 6}
        )
        rows.append(
            {"instance_id": iid, "system": "B", "repo": repo, "chrf": sb, "resolved": i % 2 == 0}
        )
    rows.append(
        {"instance_id": "o__r0-99", "system": "A", "repo": "r0", "chrf": 0.0, "resolved": False}
    )
    return rows


def test_compare_constant_shift_and_outcomes():
    res = compare(make_rows(), "A", "B", metrics=("chrf",), n_boot=200)
    assert res["n_shared"] == 12 and res["n_only_a"] == 1 and res["n_only_b"] == 0
    d = res["metrics"]["chrf"]["diff"]
    # every paired difference is 0.25, so every bootstrap draw gives 0.25
    assert d["value"] == pytest.approx(0.25)
    assert d["low"] == pytest.approx(0.25) and d["high"] == pytest.approx(0.25)
    o = res["outcomes"]
    assert (o["resolved_a"], o["resolved_b"]) == (6, 6)
    assert o["both"] + o["only_a"] + o["only_b"] + o["neither"] == 12
    assert o["both"] == 3 and o["only_a"] == 3 and o["only_b"] == 3
    s = [0.1 + 0.05 * i for i in range(12)]
    m = res["metrics"]["chrf"]
    assert m["auc_a"]["value"] == pytest.approx(auc(s, [i >= 6 for i in range(12)])) == 1.0
    assert m["auc_b"]["value"] == pytest.approx(auc(s, [i % 2 == 0 for i in range(12)]))
    assert m["auc_diff"]["value"] == pytest.approx(m["auc_b"]["value"] - 1.0)
    assert m["auc_diff"]["low"] <= m["auc_diff"]["value"] <= m["auc_diff"]["high"]


def test_compare_without_outcomes():
    rows = [{k: v for k, v in r.items() if k != "resolved"} for r in make_rows()]
    res = compare(rows, "A", "B", metrics=("chrf",), n_boot=50)
    assert res["outcomes"] is None and "auc_a" not in res["metrics"]["chrf"]
