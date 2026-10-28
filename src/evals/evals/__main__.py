"""Command line for the evals: `uv run python -m evals build-set --set parse --version v1`."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from evals.parse_set import DEFAULT_SEED, build_set

_DATA = Path(__file__).resolve().parents[2] / "data"
RELEASE = "r2.18"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evals")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build-set", help="Sample and freeze an eval set")
    build.add_argument("--set", choices=["parse"], required=True)
    build.add_argument("--version", required=True, help="Manifest version, e.g. v1")
    build.add_argument("--seed", type=int, default=DEFAULT_SEED)
    build.add_argument("--ud-dir", type=Path, default=_DATA / "raw" / "ud")
    build.add_argument("--out-dir", type=Path, default=_DATA / "eval_sets")
    options = parser.parse_args(argv)

    manifest, table = build_set(
        ud_dir=options.ud_dir,
        out_dir=options.out_dir,
        version=options.version,
        seed=options.seed,
        release=RELEASE,
    )
    print(table)
    print(f"\nWrote {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
