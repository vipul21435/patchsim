"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .analysis import analyze, attach_outcomes
from .io import load_candidates, load_gold, load_outcomes
from .report import analysis_markdown, summary_markdown
from .score import METRICS, score_all


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="patchsim",
        description="Similarity of candidate patches to gold patches, and how well it predicts "
        "test-based resolution.",
    )
    p.add_argument("--version", action="version", version=f"patchsim {__version__}")
    sub = p.add_subparsers(dest="command")

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--candidates", required=True, help="candidate patches, JSONL")
        sp.add_argument("--gold", required=True, help="gold patches, JSONL or JSON list")
        sp.add_argument("--system", help="system name to use for every candidate")
        sp.add_argument(
            "--ignore-new-files",
            action="store_true",
            help="drop files a candidate creates that the gold patch does not touch",
        )
        sp.add_argument(
            "--sources",
            help="directory with pre-patch files at <dir>/<instance_id>/<path>; "
            "switches the AST metric to post-patch source where both patches apply",
        )

    s = sub.add_parser("score", help="score every candidate against its gold patch")
    common(s)
    s.add_argument("--out", help="write one JSON row per candidate to this file")

    a = sub.add_parser("analyze", help="how well each metric predicts resolution")
    common(a)
    a.add_argument("--outcomes", required=True, help="JSONL of resolved flags or a results JSON")
    a.add_argument("--n-boot", type=int, default=2000, help="bootstrap replicates (default 2000)")
    a.add_argument("--seed", type=int, default=0)
    a.add_argument("--level", type=float, default=0.95, help="interval level (default 0.95)")
    a.add_argument("--examples", type=int, default=5, help="disagreement examples per list")
    a.add_argument("--example-metric", default="chrf", choices=METRICS)
    a.add_argument(
        "--keep-empty", action="store_true", help="keep empty candidate patches in the analysis"
    )
    a.add_argument("--json", dest="json_out", help="write the full result as JSON")
    a.add_argument("--markdown", help="write the Markdown report to this file")
    return p


def _rows(args: argparse.Namespace) -> list[dict]:
    return score_all(
        load_candidates(args.candidates, args.system),
        load_gold(args.gold),
        ignore_new_files=args.ignore_new_files,
        sources=args.sources,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    rows = _rows(args)
    if not rows:
        print("no candidate has a matching gold patch", file=sys.stderr)
        return 1
    if args.command == "score":
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r, sort_keys=True) + "\n")
        sys.stdout.write(summary_markdown(rows, METRICS))
        return 0
    rows = attach_outcomes(rows, load_outcomes(args.outcomes))
    if not rows:
        print("no scored candidate has an outcome", file=sys.stderr)
        return 1
    res = analyze(
        rows,
        n_boot=args.n_boot,
        seed=args.seed,
        level=args.level,
        examples=args.examples,
        example_metric=args.example_metric,
        exclude_empty=not args.keep_empty,
    )
    md = analysis_markdown(res)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(res, indent=2, sort_keys=True) + "\n")
    if args.markdown:
        Path(args.markdown).write_text(md)
    sys.stdout.write(md)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
