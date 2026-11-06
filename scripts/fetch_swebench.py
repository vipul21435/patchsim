"""Fetch SWE-bench Verified gold patches and a few public submissions into a data directory.

Writes, under --out (default ./data, which git ignores):

- gold.jsonl: instance_id, repo, base_commit, patch for the 500 Verified instances, read
  through the Hugging Face datasets-server rows API for princeton-nlp/SWE-bench_Verified;
- candidates.jsonl: instance_id, model, patch from each submission's all_preds.jsonl in the
  public bucket named by the submission's metadata.yaml in github.com/SWE-bench/experiments;
- outcomes.jsonl: instance_id, model, resolved for every Verified instance and submission,
  from evaluation/verified/<submission>/results/results.json in the same repository;
- with --sources, the pre-patch content of every Python file touched by a gold or candidate
  patch, at sources/<instance_id>/<path>, from raw.githubusercontent.com at base_commit.

Standard library only. Files already present are not fetched again.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SUBMISSIONS = (
    "20240728_sweagent_gpt4o",
    "20240628_autocoderover-v20240620",
    "20241028_agentless-1.5_gpt4o",
    "20241128_SWE-Fixer_Qwen2.5-7b-retriever_Qwen2.5-72b-editor_20241128",
    "20241029_OpenHands-CodeAct-2.1-sonnet-20241022",
    "20250225_sweagent_claude-3-7-sonnet",
)
ROWS = (
    "https://datasets-server.huggingface.co/rows?dataset=princeton-nlp/SWE-bench_Verified"
    "&config=default&split=test&offset={offset}&length=100"
)
RESULTS = (
    "https://raw.githubusercontent.com/SWE-bench/experiments/main/evaluation/verified/"
    "{sub}/results/results.json"
)
PREDS = "https://swe-bench-submissions.s3.amazonaws.com/verified/{sub}/all_preds.jsonl"
RAW = "https://raw.githubusercontent.com/{repo}/{commit}/{path}"


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "patchsim-fetch"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def cached(path: Path, url: str) -> bytes:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(get(url))
    return path.read_bytes()


def fetch_gold(out: Path) -> list[dict]:
    dest = out / "gold.jsonl"
    if dest.exists():
        return [json.loads(x) for x in dest.read_text().splitlines() if x.strip()]
    rows: list[dict] = []
    offset = 0
    while True:
        page = json.loads(get(ROWS.format(offset=offset)))
        batch = [r["row"] for r in page["rows"]]
        rows += [{k: r[k] for k in ("instance_id", "repo", "base_commit", "patch")} for r in batch]
        offset += len(batch)
        if not batch or offset >= page["num_rows_total"]:
            break
    dest.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return rows


def _preds(raw: bytes) -> list[dict]:
    text = raw.decode("utf-8")
    if text.lstrip().startswith("["):
        return json.loads(text)
    if text.lstrip().startswith("{") and "\n{" not in text.strip():
        data = json.loads(text)
        if isinstance(data, dict) and "instance_id" not in data:
            return list(data.values())
    return [json.loads(x) for x in text.splitlines() if x.strip()]


def fetch_submissions(out: Path, subs: tuple[str, ...], ids: list[str]) -> None:
    cands, outs = [], []
    for sub in subs:
        res = json.loads(cached(out / "raw" / sub / "results.json", RESULTS.format(sub=sub)))
        resolved = set(res["resolved"])
        for p in _preds(cached(out / "raw" / sub / "all_preds.jsonl", PREDS.format(sub=sub))):
            cands.append(
                {"instance_id": p["instance_id"], "model": sub, "patch": p.get("model_patch") or ""}
            )
        outs += [{"instance_id": i, "model": sub, "resolved": i in resolved} for i in ids]
        print(f"{sub}: {len(resolved)} resolved", file=sys.stderr)
    (out / "candidates.jsonl").write_text("".join(json.dumps(r) + "\n" for r in cands))
    (out / "outcomes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in outs))


def _python_paths(patch: str) -> set[str]:
    paths = set()
    for line in patch.splitlines():
        if line.startswith("--- a/") and line[6:].strip().endswith(".py"):
            paths.add(line[6:].strip())
    return paths


def fetch_sources(out: Path, gold: list[dict], workers: int) -> None:
    by_id = {g["instance_id"]: g for g in gold}
    want: set[tuple[str, str]] = set()
    for g in gold:
        want |= {(g["instance_id"], p) for p in _python_paths(g["patch"])}
    for line in (out / "candidates.jsonl").read_text().splitlines():
        c = json.loads(line)
        if c["instance_id"] in by_id:
            want |= {(c["instance_id"], p) for p in _python_paths(c["patch"])}

    def one(item: tuple[str, str]) -> str:
        iid, path = item
        dest = out / "sources" / iid / path
        if dest.exists() or (out / "sources" / iid / (path + ".missing")).exists():
            return "cached"
        g = by_id[iid]
        try:
            data = get(RAW.format(repo=g["repo"], commit=g["base_commit"], path=path))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                dest.parent.mkdir(parents=True, exist_ok=True)
                (out / "sources" / iid / (path + ".missing")).write_text("")
                return "missing"
            raise
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return "fetched"

    with ThreadPoolExecutor(workers) as ex:
        results = list(ex.map(one, sorted(want)))
    print({k: results.count(k) for k in set(results)}, file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="data", help="data directory (default ./data)")
    ap.add_argument("--submission", action="append", help="submission directory name (repeat)")
    ap.add_argument("--sources", action="store_true", help="also fetch pre-patch Python files")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    gold = fetch_gold(out)
    print(f"gold: {len(gold)} instances", file=sys.stderr)
    fetch_submissions(out, tuple(args.submission or SUBMISSIONS), [g["instance_id"] for g in gold])
    if args.sources:
        fetch_sources(out, gold, args.workers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
