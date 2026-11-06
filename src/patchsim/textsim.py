"""Token- and character-level similarity of the changed lines of two patches."""

from __future__ import annotations

import re
from collections import Counter

from .diff import Patch

_TOKEN_RE = re.compile(r"[A-Za-z_]\w*|\d+(?:\.\d+)?|\S")


def _changed_lines(patch: Patch) -> list[tuple[str, str]]:
    """(side, text) for every added ('+') and removed ('-') line that is not blank
    and not a whole-line '#' comment."""
    out = []
    for f in patch.files:
        for side, lines in (("-", f.removed), ("+", f.added)):
            for line in lines:
                s = line.strip()
                if s and not s.startswith("#"):
                    out.append((side, s))
    return out


def tokens(patch: Patch) -> Counter:
    """Multiset of (side, token) over the changed lines.

    Tokens are identifiers, numbers and single non-space characters; whitespace
    and whole-line comments are dropped, case is kept. Tagging by side means an
    added ``x`` and a removed ``x`` do not match each other.
    """
    c: Counter = Counter()
    for side, s in _changed_lines(patch):
        c.update((side, t) for t in _TOKEN_RE.findall(s))
    return c


def multiset_f1(a: Counter, b: Counter) -> float:
    """F1 of two multisets: 2 * |A & B| / (|A| + |B|), where & takes the minimum count.

    Two empty multisets score 1.
    """
    na, nb = sum(a.values()), sum(b.values())
    if na == nb == 0:
        return 1.0
    inter = sum((a & b).values())
    return 2 * inter / (na + nb)


def token_f1(cand: Patch, gold: Patch) -> float:
    """Normalised token multiset F1 of the changed lines (see :func:`tokens`)."""
    return multiset_f1(tokens(cand), tokens(gold))


def char_ngrams(patch: Patch, n: int) -> Counter:
    """Multiset of (side, character n-gram) taken within each changed line with
    whitespace removed. N-grams never cross a line boundary."""
    c: Counter = Counter()
    for side, s in _changed_lines(patch):
        s = "".join(s.split())
        c.update((side, s[i : i + n]) for i in range(len(s) - n + 1))
    return c


def chrf(cand: Patch, gold: Patch, max_n: int = 6, beta: float = 2.0) -> float:
    """Character n-gram F-score in the style of chrF (Popovic, 2015).

    For each n in 1..max_n with matches m_n = |C_n & G_n|:
    P_n = m_n / |C_n| and R_n = m_n / |G_n| (0 when the denominator is 0); orders
    where both sides are empty are skipped. P and R are the means over the kept
    orders, and chrF = (1 + beta^2) P R / (beta^2 P + R). beta = 2 weights recall
    twice as much as precision. Two patches with no changed characters score 1.
    """
    ps, rs = [], []
    for n in range(1, max_n + 1):
        c, g = char_ngrams(cand, n), char_ngrams(gold, n)
        nc, ng = sum(c.values()), sum(g.values())
        if nc == ng == 0:
            continue
        m = sum((c & g).values())
        ps.append(m / nc if nc else 0.0)
        rs.append(m / ng if ng else 0.0)
    if not ps:
        return 1.0
    p, r = sum(ps) / len(ps), sum(rs) / len(rs)
    if p == r == 0:
        return 0.0
    b2 = beta * beta
    return (1 + b2) * p * r / (b2 * p + r)
