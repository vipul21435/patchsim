#!/usr/bin/env bash
# Reproduce the README results from the data written by scripts/fetch_swebench.py --sources.
# Usage: bash scripts/run_real.sh [DATA_DIR] [OUT_DIR]
set -euo pipefail
D=${1:-$HOME/oss/_data/patchsim}
OUT=${2:-results}
mkdir -p "$OUT"
IN=(--candidates "$D/candidates.jsonl" --gold "$D/gold.jsonl")
Y=(--outcomes "$D/outcomes.jsonl" --n-boot 2000 --seed 0)

# 1. every file of every candidate, AST metric on patch lines
uv run patchsim analyze "${IN[@]}" "${Y[@]}" \
  --json "$OUT/analysis_all_files.json" --markdown "$OUT/analysis_all_files.md" > /dev/null
# 2. files a candidate creates outside the gold patch set aside
uv run patchsim analyze "${IN[@]}" "${Y[@]}" --ignore-new-files \
  --json "$OUT/analysis_ignore_new.json" --markdown "$OUT/analysis_ignore_new.md" > /dev/null
# 3. as 2, with the AST metric on post-patch source
uv run patchsim analyze "${IN[@]}" "${Y[@]}" --ignore-new-files --sources "$D/sources" \
  --json "$OUT/analysis_post_patch.json" --markdown "$OUT/analysis_post_patch.md" > /dev/null
# 4. one system at a time, as 2
for s in $(uv run python -c "import json,sys
print(' '.join(sorted({json.loads(l)['model'] for l in open(sys.argv[1])})))" "$D/candidates.jsonl"); do
  uv run patchsim analyze "${IN[@]}" "${Y[@]}" --ignore-new-files --include-system "$s" \
    --json "$OUT/system_$s.json" --markdown /dev/null > /dev/null
done
# 5. two systems with the same agent scaffold and different models, as 2
uv run patchsim compare "${IN[@]}" "${Y[@]}" --ignore-new-files \
  --a 20240728_sweagent_gpt4o --b 20250225_sweagent_claude-3-7-sonnet \
  --json "$OUT/compare_sweagent.json" --markdown "$OUT/compare_sweagent.md" > /dev/null
# 6. ROC chart and per-system table
uv run patchsim score "${IN[@]}" --ignore-new-files --out "$D/rows_ignore_new.jsonl" > /dev/null
uv run --with matplotlib python scripts/plot_roc.py "$D/rows_ignore_new.jsonl" \
  "$D/outcomes.jsonl" "$OUT/roc.png"
uv run python scripts/system_table.py "$OUT" > "$OUT/systems.md"
