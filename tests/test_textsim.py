from collections import Counter

import pytest

from patchsim.diff import parse_diff
from patchsim.textsim import char_ngrams, chrf, multiset_f1, token_f1, tokens


def one_line(removed: str | None, added: str | None) -> str:
    body = []
    if removed is not None:
        body.append("-" + removed)
    if added is not None:
        body.append("+" + added)
    old = 1 if removed is not None else 0
    new = 1 if added is not None else 0
    return f"--- a/x.py\n+++ b/x.py\n@@ -1,{old} +1,{new} @@\n" + "\n".join(body) + "\n"


def test_tokens_split_and_side_tag():
    p = parse_diff(one_line("x = 1", "x = foo(y)  "))
    assert tokens(p) == Counter(
        {
            ("-", "x"): 1,
            ("-", "="): 1,
            ("-", "1"): 1,
            ("+", "x"): 1,
            ("+", "="): 1,
            ("+", "foo"): 1,
            ("+", "("): 1,
            ("+", "y"): 1,
            ("+", ")"): 1,
        }
    )


def test_comment_and_blank_lines_ignored():
    p = parse_diff(one_line("# note", "   "))
    assert tokens(p) == Counter()


def test_multiset_f1_closed_form():
    a = Counter({"a": 2, "b": 1})
    b = Counter({"a": 1, "c": 3})
    assert multiset_f1(a, b) == pytest.approx(2 * 1 / 7)
    assert multiset_f1(Counter(), Counter()) == 1.0
    assert multiset_f1(a, Counter()) == 0.0


def test_token_f1():
    c = parse_diff(one_line(None, "return a + b"))  # 4 tokens
    g = parse_diff(one_line(None, "return a - b"))  # 4 tokens, 3 shared
    assert token_f1(c, g) == pytest.approx(6 / 8)
    # the same line on the opposite side does not match
    r = parse_diff(one_line("return a + b", None))
    assert token_f1(c, r) == 0.0


def test_char_ngrams_within_lines():
    p = parse_diff(one_line(None, "ab c"))
    assert char_ngrams(p, 2) == Counter({("+", "ab"): 1, ("+", "bc"): 1})
    assert char_ngrams(p, 4) == Counter()


def test_chrf_closed_form():
    # "abcd" vs "abce": n=1: 3/4, 3/4; n=2: 2/3, 2/3; n=3: 1/2, 1/2; n=4: 0, 0
    c = parse_diff(one_line(None, "abcd"))
    g = parse_diff(one_line(None, "abce"))
    p = (3 / 4 + 2 / 3 + 1 / 2 + 0) / 4
    assert chrf(c, g) == pytest.approx(p)  # P == R so chrF == P for any beta
    assert chrf(c, c) == 1.0


def test_chrf_asymmetric_beta():
    # candidate "ab", gold "abab": n=1 m=2, P=1, R=1/2; n=2 m=1, P=1, R=1/3;
    # n=3 C empty, G has 2 -> P=0, R=0; n=4 G has 1 -> 0, 0
    c = parse_diff(one_line(None, "ab"))
    g = parse_diff(one_line(None, "abab"))
    p = (1 + 1 + 0 + 0) / 4
    r = (1 / 2 + 1 / 3 + 0 + 0) / 4
    assert chrf(c, g, max_n=6) == pytest.approx(5 * p * r / (4 * p + r))


def test_chrf_empty():
    e = parse_diff("")
    assert chrf(e, e) == 1.0
    assert chrf(parse_diff(one_line(None, "abc")), e) == 0.0


def _one(path, old, new):
    from patchsim.diff import parse_diff

    return parse_diff(f"--- a/{path}\n+++ b/{path}\n@@ -1,1 +1,1 @@\n-{old}\n+{new}\n")


def test_hash_lines_are_code_outside_hash_comment_languages():
    from patchsim.textsim import chrf, token_f1

    c = _one("m.c", "#include <a.h>", "#include <b.h>")
    g = _one("m.c", "#define X 1", "#define X 2")
    assert token_f1(c, g) < 0.5 and chrf(c, g) < 0.5
    assert token_f1(c, c) == chrf(c, c) == 1.0


def test_python_comments_dropped_but_compared_when_nothing_else_changes():
    from patchsim.diff import parse_diff
    from patchsim.textsim import chrf, token_f1

    c = _one("m.py", "# old note", "# a comment about caching")
    g = _one("m.py", "# old note", "# unrelated text here")
    assert token_f1(c, g) < 1.0 and chrf(c, g) < 1.0
    assert token_f1(c, c) == chrf(c, c) == 1.0
    code = "--- a/m.py\n+++ b/m.py\n@@ -1,2 +1,2 @@\n-x = 1\n-# note\n+x = 2\n+# other\n"
    plain = "--- a/m.py\n+++ b/m.py\n@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n"
    assert token_f1(parse_diff(code), parse_diff(plain)) == 1.0


def test_chrf_short_line_counts_missing_orders_as_zero():
    from patchsim.diff import parse_diff
    from patchsim.textsim import chrf

    # 'ab' against 'abcdefgh': orders 3 to 6 have no candidate n-grams, so
    # P_n = R_n = 0 there and P = 2/6, R = (2/8 + 1/7)/6 (the paper's formula;
    # sacrebleu's default effective order would drop those orders instead).
    p, r = 2 / 6, (2 / 8 + 1 / 7) / 6

    c = parse_diff("--- /dev/null\n+++ b/t.txt\n@@ -0,0 +1 @@\n+ab\n")
    g = parse_diff("--- /dev/null\n+++ b/t.txt\n@@ -0,0 +1 @@\n+abcdefgh\n")
    assert abs(chrf(c, g) - 5 * p * r / (4 * p + r)) < 1e-12
    assert round(chrf(c, g), 3) == 0.078
