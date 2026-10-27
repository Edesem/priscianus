"""Command line demo: `python -m priscianus.morphology parse <word>`."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from priscianus.morphology.build_index import DEFAULT_DB
from priscianus.morphology.lookup import lookup_form

_FEATURE_ORDER = (
    "Case",
    "Gender",
    "Person",
    "Number",
    "Degree",
    "Tense",
    "Aspect",
    "Mood",
    "Voice",
    "VerbForm",
)


def _describe(features: dict[str, str]) -> str:
    ordered = sorted(features, key=lambda f: _FEATURE_ORDER.index(f) if f in _FEATURE_ORDER else 99)
    return ", ".join(f"{name}={features[name]}" for name in ordered)


def main(argv: Sequence[str] | None = None, db: Path = DEFAULT_DB) -> int:
    parser = argparse.ArgumentParser(prog="python -m priscianus.morphology")
    commands = parser.add_subparsers(dest="command", required=True)
    parse = commands.add_parser("parse", help="print every analysis of a Latin word")
    parse.add_argument("word")
    args = parser.parse_args(argv)

    if not db.exists():
        print(f"No morphology index at {db}. Build it with `make data`.", file=sys.stderr)
        return 2

    analyses = lookup_form(args.word, db)
    if not analyses:
        print(f"No analyses found for '{args.word}'.", file=sys.stderr)
        return 1

    count = len(analyses)
    print(f"{args.word}: {count} {'analysis' if count == 1 else 'analyses'}")
    for analysis in analyses:
        features = _describe(analysis.features)
        print(f"  {analysis.form}: form of {analysis.lemma_display} ({analysis.pos}): {features}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
