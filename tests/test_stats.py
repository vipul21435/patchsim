import math
import random

import pytest

from patchsim.stats import auc, best_threshold, clustered_bootstrap_auc, repo_of


def brute_auc(s, y):
    pos = [a for a, b in zip(s, y, strict=True) if b]
    neg = [a for a, b in zip(s, y, strict=True) if not b]
    tot = sum(1.0 if p > q else 0.5 if p == q else 0.0 for p in pos for q in neg)
    return tot / (len(pos) * len(neg))


def test_auc_matches_pairwise_count():
    rng = random.Random(1)
    for _ in range(200):
        n = rng.randint(2, 40)
        s = [rng.choice([0.0, 0.25, 0.5, 0.75, 1.0, rng.random()]) for _ in range(n)]
        y = [rng.random() < 0.4 for _ in range(n)]
        if all(y) or not any(y):
            assert auc(s, y) is None
            continue
        assert auc(s, y) == pytest.approx(brute_auc(s, y))


def test_auc_simple_and_errors():
    assert auc([0.1, 0.9], [False, True]) == 1.0
    assert auc([0.5, 0.5], [False, True]) == 0.5
    with pytest.raises(ValueError):
        auc([1.0], [True, False])


def test_best_threshold():
    s = [0.1, 0.2, 0.3, 0.8, 0.9, 0.4]
    y = [False, False, True, True, True, False]
    r = best_threshold(s, y)
    # t = 0.8 classifies 5 of 6 correctly; t = 0.3 also 5 of 6, the first found (higher) is kept
    assert r["accuracy"] == pytest.approx(5 / 6)
    assert r["majority_baseline"] == 0.5
    assert r["threshold"] == 0.8
    assert best_threshold([], [])["accuracy"] is None
    # all negative: best is predicting nothing resolved
    assert best_threshold([0.3, 0.4], [False, False])["threshold"] == math.inf


def test_repo_of():
    assert repo_of("django__django-11099") == "django__django"
    assert repo_of("plainname") == "plainname"
    assert repo_of("a-b") == "a-b"


def simulate(rng, k=30, m=8, sigma_u=1.0):
    s, y, c = [], [], []
    for j in range(k):
        u = rng.gauss(0, sigma_u)
        for _ in range(m):
            z = rng.gauss(0, 1)
            s.append(z + u)
            y.append(rng.random() < 1 / (1 + math.exp(-(u + z))))
            c.append(f"r{j}")
    return s, y, c


def test_clustered_bootstrap_se_matches_simulation():
    rng = random.Random(7)
    true = [auc(*simulate(rng)[:2]) for _ in range(300)]
    mu = sum(true) / len(true)
    sd = (sum((a - mu) ** 2 for a in true) / (len(true) - 1)) ** 0.5
    ses = []
    for i in range(8):
        s, y, c = simulate(rng)
        r = clustered_bootstrap_auc(s, y, c, n_boot=300, seed=i)
        ses.append(r["se"])
        assert r["low"] <= r["auc"] <= r["high"]
    ratio = (sum(ses) / len(ses)) / sd
    assert 0.7 < ratio < 1.4


def test_clustered_wider_than_iid_under_cluster_effect():
    rng = random.Random(3)
    s, y, c = simulate(rng, k=20, m=15, sigma_u=1.5)
    clus = clustered_bootstrap_auc(s, y, c, n_boot=400, seed=1)
    iid = clustered_bootstrap_auc(s, y, [str(i) for i in range(len(s))], n_boot=400, seed=1)
    assert clus["se"] > iid["se"]


def test_bootstrap_single_class():
    r = clustered_bootstrap_auc([0.1, 0.2], [True, True], ["a", "b"], n_boot=20)
    assert r["auc"] is None and r["n_boot"] == 0 and r["n_dropped"] == 20
