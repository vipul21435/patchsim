"""Command-line interface."""

from __future__ import annotations

import argparse
import sys

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="patchsim",
        description="Similarity of candidate patches to gold patches, and how well it predicts "
        "test-based resolution.",
    )
    p.add_argument("--version", action="version", version=f"patchsim {__version__}")
    p.add_subparsers(dest="command")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
