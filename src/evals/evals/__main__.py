"""Command line for the evals: `uv run python -m evals build-set --set parse --version v1`."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from priscianus.morphology.lookup import lookup_form

from evals.index_agreement import evaluate, render_report, sample_disagreements
from evals.parse_set import DEFAULT_SEED, build_set, load_parse_set

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
    agreement = commands.add_parser(
        "index-agreement", help="Compare the morphology index with the parse-set gold"
    )
    agreement.add_argument("--manifest", type=Path, default=_DATA / "eval_sets" / "parse-v1.jsonl")
    agreement.add_argument("--ud-dir", type=Path, default=_DATA / "raw" / "ud")
    agreement.add_argument("--sample", type=int, default=100, help="Disagreements to sample")
    agreement.add_argument("--sample-out", type=Path, help="Write the sampled disagreements here")
    options = parser.parse_args(argv)

    if options.command == "index-agreement":
        results = evaluate(load_parse_set(options.manifest, options.ud_dir), lookup_form)
        print(render_report(results))
        if options.sample_out:
            rows = [
                {
                    "item_id": f"{i.token.treebank}/{i.token.sent_id}/{i.token.token_id}",
                    "form": i.token.form,
                    "lemma": i.token.lemma,
                    "upos": i.token.upos,
                    "features": i.token.features,
                    "stratum": [i.slice, i.pos_class, i.freq_band],
                    "level": "no form"
                    if not a.in_index
                    else "no lemma"
                    if not a.lemma_found
                    else "no parse",
                    "index": [
                        {"lemma": x.lemma, "pos": x.pos, "features": x.features}
                        for x in lookup_form(i.token.form)
                    ],
                }
                for i, a in sample_disagreements(results, k=options.sample, seed=DEFAULT_SEED + 1)
            ]
            options.sample_out.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
        return 0

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
