"""Token- and character-level similarity of the changed lines of two patches."""

from __future__ import annotations

import re
from collections import Counter

from .diff import Patch

_TOKEN_RE = re.compile(r"[A-Za-z_]\w*|\d+(?:\.\d+)?|\S")


# Files in which a line starting with '#' is a comment. Elsewhere (C and C++
# preprocessor lines, Markdown headings) it is content and is kept.
HASH_COMMENT_SUFFIXES = frozenset(
    ".py .pyi .pyx .pxd .sh .bash .zsh .yml .yaml .toml .cfg .ini .conf .r .rb .pl .pm "
    ".tcl .cmake .mk .gitignore .dockerignore .coveragerc .flake8 .pylintrc".split()
)
HASH_COMMENT_NAMES = frozenset({"Makefile", "Dockerfile", "CMakeLists.txt", "setup.cfg"})


def hash_comments(path: str) -> bool:
    """True when whole-line '#' comments are dropped for this file (see
    :data:`HASH_COMMENT_SUFFIXES`)."""
    name = path.rsplit("/", 1)[-1]
    if name in HASH_COMMENT_NAMES:
        return True
    dot = name.rfind(".")
    return dot >= 0 and name[dot:].lower() in HASH_COMMENT_SUFFIXES


def _changed_lines(patch: Patch, keep_comments: bool = False) -> list[tuple[str, str]]:
    """(side, text) for every added ('+') and removed ('-') line that is not blank
    and, unless ``keep_comments``, not a whole-line '#' comment in a file type where
    '#' starts a comment."""
    out = []
    for f in patch.files:
        drop = not keep_comments and hash_comments(f.path)
        for side, lines in (("-", f.removed), ("+", f.added)):
            for line in lines:
                s = line.strip()
                if s and not (drop and s.startswith("#")):
                    out.append((side, s))
    return out


def _lines_pair(cand: Patch, gold: Patch) -> tuple[list, list]:
    """Changed lines of both patches with comments dropped, or kept when dropping
    them leaves both patches empty, so two patches that change only comments are
    compared by those comments instead of both scoring 1."""
    c, g = _changed_lines(cand), _changed_lines(gold)
    if not c and not g:
        c, g = _changed_lines(cand, True), _changed_lines(gold, True)
    return c, g


def _tokens(lines: list[tuple[str, str]]) -> Counter:
    c: Counter = Counter()
    for side, s in lines:
        c.update((side, t) for t in _TOKEN_RE.findall(s))
    return c


def tokens(patch: Patch, keep_comments: bool = False) -> Counter:
    """Multiset of (side, token) over the changed lines.

    Tokens are identifiers, numbers and single non-space characters; whitespace
    and whole-line comments are dropped, case is kept. Tagging by side means an
    added ``x`` and a removed ``x`` do not match each other.
    """
    return _tokens(_changed_lines(patch, keep_comments))


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
    """Normalised token multiset F1 of the changed lines (see :func:`tokens`).
    Comment lines are compared only when neither patch changes anything else."""
    c, g = _lines_pair(cand, gold)
    return multiset_f1(_tokens(c), _tokens(g))


def _ngrams(lines: list[tuple[str, str]], n: int) -> Counter:
    c: Counter = Counter()
    for side, s in lines:
        s = "".join(s.split())
        c.update((side, s[i : i + n]) for i in range(len(s) - n + 1))
    return c


def char_ngrams(patch: Patch, n: int, keep_comments: bool = False) -> Counter:
    """Multiset of (side, character n-gram) taken within each changed line with
    whitespace removed. N-grams never cross a line boundary."""
    return _ngrams(_changed_lines(patch, keep_comments), n)


def chrf(cand: Patch, gold: Patch, max_n: int = 6, beta: float = 2.0) -> float:
    """Character n-gram F-score in the style of chrF (Popovic, 2015).

    For each n in 1..max_n with matches m_n = |C_n & G_n|:
    P_n = m_n / |C_n| and R_n = m_n / |G_n| (0 when the denominator is 0); orders
    where both sides are empty are skipped. P and R are the means over the kept
    orders, and chrF = (1 + beta^2) P R / (beta^2 P + R). beta = 2 weights recall
    twice as much as precision. Two patches with no changed characters score 1.
    Comment lines are compared only when neither patch changes anything else.

    This is the formula of the paper. It equals sacrebleu's
    ``CHRF(char_order=6, word_order=0, beta=2)`` when every line is at least six
    characters long; for shorter lines the missing orders count as zero here,
    where sacrebleu's default drops them (it is close to ``eps_smoothing=True``).
    """
    cl, gl = _lines_pair(cand, gold)
    ps, rs = [], []
    for n in range(1, max_n + 1):
        c, g = _ngrams(cl, n), _ngrams(gl, n)
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
