"""Build a small synthetic benchmark and run patchsim on it.

Usage: python examples/demo.py OUTDIR
Writes gold.jsonl, candidates.jsonl and outcomes.jsonl to OUTDIR, then runs
``patchsim analyze`` on them. The patches are hand-made toy edits, not real data.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from patchsim.cli import main


def diff(path: str, func: str, old: str, new: str, line: int = 10) -> str:
    return (
        f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
        f"@@ -{line},2 +{line},2 @@ def {func}(self):\n"
        f"     value = self.load()\n-    {old}\n+    {new}\n"
    )


GOLD = {
    "acme__widgets-1": diff("widgets/core.py", "size", "return value", "return value or 0"),
    "acme__widgets-2": diff("widgets/io.py", "read", "return data", "return data.strip()"),
    "acme__widgets-3": diff("widgets/core.py", "name", "return value", "return str(value)", 40),
    "beta__parse-1": diff("parse/lex.py", "next", "i += 1", "i += len(tok)"),
    "beta__parse-2": diff("parse/ast.py", "walk", "yield node", "yield from node.children"),
    "beta__parse-3": diff("parse/lex.py", "peek", "return s[i]", "return s[i] if i < n else None"),
    "gamma__cli-1": diff("cli/main.py", "run", "exit(1)", "exit(2)"),
    "gamma__cli-2": diff("cli/args.py", "parse", "return args", "return vars(args)"),
}

# (instance, system, patch, resolved)
CANDIDATES = [
    ("acme__widgets-1", "sys-a", GOLD["acme__widgets-1"], True),
    (
        "acme__widgets-2",
        "sys-a",
        diff("widgets/io.py", "read", "return data", "return data.rstrip()"),
        True,
    ),
    (
        "acme__widgets-3",
        "sys-a",
        diff("widgets/util.py", "fmt", "return v", "return str(v)"),
        False,
    ),
    ("beta__parse-1", "sys-a", diff("parse/lex.py", "next", "i += 1", "i += 2"), False),
    ("beta__parse-2", "sys-a", GOLD["beta__parse-2"], True),
    (
        "beta__parse-3",
        "sys-a",
        diff("parse/lex.py", "peek", "return s[i]", "return s[i:i+1] or None"),
        True,
    ),
    ("gamma__cli-1", "sys-a", diff("cli/main.py", "run", "exit(1)", "exit(3)"), False),
    (
        "gamma__cli-2",
        "sys-a",
        diff("cli/compat.py", "to_dict", "return a", "return dict(vars(a))"),
        True,
    ),
    (
        "acme__widgets-1",
        "sys-b",
        diff("widgets/core.py", "size", "return value", "return value"),
        False,
    ),
    ("beta__parse-1", "sys-b", GOLD["beta__parse-1"], True),
    ("gamma__cli-1", "sys-b", GOLD["gamma__cli-1"], True),
    ("gamma__cli-2", "sys-b", diff("cli/args.py", "parse", "return args", "return args"), False),
]


def write(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "gold.jsonl", "w") as fh:
        for iid, p in GOLD.items():
            fh.write(json.dumps({"instance_id": iid, "patch": p}) + "\n")
    with open(out / "candidates.jsonl", "w") as fh, open(out / "outcomes.jsonl", "w") as fo:
        for iid, system, p, y in CANDIDATES:
            fh.write(json.dumps({"instance_id": iid, "model": system, "patch": p}) + "\n")
            fo.write(json.dumps({"instance_id": iid, "model": system, "resolved": y}) + "\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    d = Path(sys.argv[1])
    write(d)
    sys.exit(
        main(
            [
                "analyze",
                "--candidates",
                str(d / "candidates.jsonl"),
                "--gold",
                str(d / "gold.jsonl"),
                "--outcomes",
                str(d / "outcomes.jsonl"),
                "--n-boot",
                "500",
                "--examples",
                "3",
            ]
        )
    )
