"""Score one hand-made candidate against one gold patch with the library API.

Usage: python examples/pair.py
The gold patch guards a division; the candidate makes the same guard with a
different spelling and also leaves a reproduction script behind.
"""

from __future__ import annotations

from patchsim.score import score_pair

GOLD = """\
--- a/stats/mean.py
+++ b/stats/mean.py
@@ -1,2 +1,4 @@
 def mean(xs):
+    if not xs:
+        return 0.0
     return sum(xs) / len(xs)
"""

CANDIDATE = """\
--- a/stats/mean.py
+++ b/stats/mean.py
@@ -1,2 +1,4 @@
 def mean(xs):
+    if len(xs) == 0:
+        return 0.0
     return sum(xs) / len(xs)
--- /dev/null
+++ b/reproduce.py
@@ -0,0 +1,2 @@
+from stats.mean import mean
+print(mean([]))
"""

KEYS = (
    "file_precision",
    "file_recall",
    "file_f1",
    "location_jaccard",
    "token_f1",
    "chrf",
    "ast_similarity",
    "ast_mode",
    "function_jaccard",
    "same_functions",
    "edit_size_ratio",
    "extra_files",
    "dropped_files",
)


def run() -> dict[str, dict]:
    out = {}
    for label, ignore in (("all files", False), ("new files set aside", True)):
        row = score_pair(CANDIDATE, GOLD, ignore_new_files=ignore)
        out[label] = {k: row[k] for k in KEYS if k in row}
    return out


if __name__ == "__main__":
    for label, row in run().items():
        print(f"{label}:")
        for k, v in row.items():
            print(f"  {k}: {round(v, 3) if isinstance(v, float) else v}")
