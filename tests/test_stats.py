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


def test_cluster_bootstrap_mean_covers_truth():
    from patchsim.stats import cluster_bootstrap

    rng = random.Random(11)
    hits = 0
    sims = 120
    for t in range(sims):
        vals, clus = [], []
        for j in range(25):
            u = rng.gauss(0, 1)
            for _ in range(4):
                vals.append(u + rng.gauss(0, 1))
                clus.append(f"r{j}")
        r = cluster_bootstrap(
            lambda idx, v=vals: sum(v[i] for i in idx) / len(idx), clus, n_boot=200, seed=t
        )
        hits += r["low"] <= 0.0 <= r["high"]
    # nominal 0.95; with 25 clusters the percentile interval runs a little short
    assert 0.85 <= hits / sims <= 1.0


def test_cluster_bootstrap_undefined_draws():
    from patchsim.stats import cluster_bootstrap

    r = cluster_bootstrap(lambda idx: None, ["a", "b"], n_boot=10)
    assert r["value"] is None and r["low"] is None and r["n_dropped"] == 10


def test_roc_points_area_equals_auc():
    from patchsim.stats import roc_points

    rng = random.Random(5)
    for _ in range(100):
        n = rng.randint(2, 30)
        s = [rng.choice([0.0, 0.5, 1.0, rng.random()]) for _ in range(n)]
        y = [rng.random() < 0.5 for _ in range(n)]
        pts = roc_points(s, y)
        if all(y) or not any(y):
            assert pts == []
            continue
        segs = zip(pts[:-1], pts[1:], strict=True)
        area = sum((x2 - x1) * (y1 + y2) / 2 for (x1, y1), (x2, y2) in segs)
        assert pts[0] == (0.0, 0.0) and pts[-1] == (1.0, 1.0)
        assert area == pytest.approx(auc(s, y))


def test_stratified_auc_matches_brute_force():
    from patchsim.stats import stratified_auc

    rng = random.Random(9)
    for _ in range(100):
        n = rng.randint(2, 30)
        s = [rng.choice([0.0, 0.5, 1.0, rng.random()]) for _ in range(n)]
        y = [rng.random() < 0.5 for _ in range(n)]
        g = [rng.choice("abcd") for _ in range(n)]
        num = den = 0.0
        for i in range(n):
            for j in range(n):
                if g[i] == g[j] and y[i] and not y[j]:
                    den += 1
                    num += 1.0 if s[i] > s[j] else 0.5 if s[i] == s[j] else 0.0
        got = stratified_auc(s, y, g)
        if den == 0:
            assert got is None
        else:
            assert got == pytest.approx(num / den)


def test_stratified_auc_removes_between_stratum_signal():
    from patchsim.stats import stratified_auc

    # An easy task where most candidates resolve and all are similar to gold, and a hard
    # one where few resolve and none are; inside each task the more similar candidate
    # is the unresolved one. Pooled AUC sees mostly the task effect.
    s = [0.9, 0.8, 0.8, 0.8, 0.2, 0.1, 0.1, 0.1]
    y = [False, True, True, True, False, False, False, True]
    g = ["easy"] * 4 + ["hard"] * 4
    # pooled: 3 easy positives beat 3 of 4 negatives each; the hard positive ties two
    # negatives and loses to one: (3 * 3 + 1.0) / (4 * 4)
    assert auc(s, y) == pytest.approx(10 / 16)
    # within: easy 3 pairs all lost; hard 3 pairs: 0 + 0.5 + 0.5
    assert stratified_auc(s, y, g) == pytest.approx(1 / 6)


def test_percentile_interval_uses_one_rule_for_both_ends():
    from patchsim.stats import percentile_interval

    reps = [float(i) for i in range(2000)]
    # k = floor(0.025 * 1999) = 49; the upper end mirrors it at 1999 - 49
    assert percentile_interval(reps, 0.95) == (49.0, 1950.0)
    assert percentile_interval([1.0, 2.0, 3.0], 0.5) == (1.0, 3.0)
    assert percentile_interval([5.0], 0.95) == (5.0, 5.0)


def test_clustered_bootstrap_auc_matches_generic_bootstrap():
    from patchsim.stats import auc, cluster_bootstrap

    s = [0.1, 0.4, 0.35, 0.8, 0.7, 0.2, 0.9, 0.5]
    y = [False, True, False, True, True, False, True, False]
    c = ["a", "a", "b", "b", "c", "c", "d", "d"]
    r = clustered_bootstrap_auc(s, y, c, n_boot=200, seed=3)
    g = cluster_bootstrap(
        lambda idx: auc([s[i] for i in idx], [y[i] for i in idx]), c, n_boot=200, seed=3
    )
    assert r["auc"] == g["value"] and (r["low"], r["high"]) == (g["low"], g["high"])


def test_held_out_accuracy_closed_form():
    from patchsim.stats import held_out_accuracy

    # cluster a: (0.9, T), (0.1, F); cluster b: (0.8, T), (0.2, F); cluster c: (0.3, T), (0.7, F)
    s = [0.9, 0.1, 0.8, 0.2, 0.3, 0.7]
    y = [True, False, True, False, True, False]
    c = ["a", "a", "b", "b", "c", "c"]
    # leaving out a: fit on b, c; thresholds 0.8 and 0.3 both give 3 of 4, the first
    # found (0.8, scanning from the top) is kept; on a it gets both right.
    # leaving out b: fit on a, c; t = 0.9 (3 of 4); on b: 0.8 < 0.9 is wrong, 0.2 right.
    # leaving out c: fit on a, b; t = 0.8 (4 of 4); on c 0.3 is wrong, 0.7 right.
    r = held_out_accuracy(s, y, c)
    assert r == {"held_out_accuracy": 4 / 6, "n_folds": 3}
    assert held_out_accuracy(s, y, ["a"] * 6) == {"held_out_accuracy": None, "n_folds": 1}
