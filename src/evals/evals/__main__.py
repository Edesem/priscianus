"""Command line for the evals: `uv run python -m evals build-set --set parse --version v1`."""

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from priscianus.llm.client import LLMClient
from priscianus.llm.config import HAIKU
from priscianus.morphology.lookup import lookup_form
from priscianus.verifier.index import MorphologyIndex, SqliteIndex

from evals.env import load_env
from evals.gold import read_conllu
from evals.index_agreement import Agreement, evaluate, sample_disagreements
from evals.index_agreement import render_report as render_agreement
from evals.parse_set import DEFAULT_SEED, build_set, load_parse_set
from evals.raw_prompt import PROMPT_ID
from evals.report import render_report
from evals.run import MODE, SET_NAME, item_id, run_parse
from evals.store import EvalStore, RunKey

_ROOT = Path(__file__).resolve().parents[3]
_DATA = Path(__file__).resolve().parents[2] / "data"
RELEASE = "r2.18"
_RESULTS = Path(__file__).resolve().parents[1] / "results"

MakeClient = Callable[..., LLMClient]


def _make_client(*, spend_cap_usd: float | None, db_path: Path) -> LLMClient:
    load_env(_ROOT / ".env")
    return LLMClient.from_env(spend_cap_usd=spend_cap_usd, db_path=db_path)


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=_DATA
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return out.stdout.strip()


def _positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"{text} is not a positive number")
    return value


def main(
    argv: Sequence[str] | None = None,
    *,
    make_client: MakeClient = _make_client,
    index: MorphologyIndex | None = None,
) -> int:
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
    run = commands.add_parser("run", help="Run an eval set against a model and store the results")
    run.add_argument("--mode", choices=["raw"], required=True)
    run.add_argument("--set", choices=["parse"], required=True)
    run.add_argument("--split", choices=["dev", "test"], default="dev")
    run.add_argument("--model", default=HAIKU)
    run.add_argument("--limit", type=int, help="Run only the first N items of the split")
    run.add_argument("--concurrency", type=_positive_int, default=4, help="Parallel model calls")
    run.add_argument("--max-cost", type=float, help="Stop when this many USD are spent in total")
    run.add_argument("--manifest", type=Path, default=_DATA / "eval_sets" / "parse-v1.jsonl")
    run.add_argument("--ud-dir", type=Path, default=_DATA / "raw" / "ud")
    run.add_argument("--store", type=Path, default=_RESULTS / "evals.db")
    run.add_argument("--llm-db", type=Path, default=_RESULTS / "llm.db")
    report = commands.add_parser("report", help="Write a markdown report for stored runs")
    report.add_argument("runs", nargs="+", type=int, metavar="run-id")
    report.add_argument("--out", type=Path, help="Write the report here instead of printing it")
    report.add_argument("--sample", type=int, default=5, help="Failure examples per category")
    report.add_argument("--manifest", type=Path, default=_DATA / "eval_sets" / "parse-v1.jsonl")
    report.add_argument("--ud-dir", type=Path, default=_DATA / "raw" / "ud")
    report.add_argument("--store", type=Path, default=_RESULTS / "evals.db")
    options = parser.parse_args(argv)

    if options.command == "report":
        store = EvalStore(options.store)
        try:
            runs = [(store.run_info(r), store.run_rows(r)) for r in options.runs]
        except KeyError as missing:
            print(f"no run {missing.args[0]} in {options.store}", file=sys.stderr)
            return 2
        morphology = index or SqliteIndex()
        ceiling: dict[str, Agreement] | None = None
        try:
            items = load_parse_set(options.manifest, options.ud_dir)
            ceiling = {item_id(i.token): a for i, a in evaluate(items, morphology.analyse)}
        except OSError as error:
            print(f"no ceiling: could not read the parse set ({error})", file=sys.stderr)
        text = render_report(runs, morphology, agreement=ceiling, per_category=options.sample)
        if options.out:
            options.out.parent.mkdir(parents=True, exist_ok=True)
            options.out.write_text(text, encoding="utf-8")
        else:
            print(text)
        return 0

    if options.command == "run":
        items = load_parse_set(options.manifest, options.ud_dir)
        treebanks = sorted({i.token.treebank for i in items})
        tokens = [
            t
            for name in treebanks
            for t in read_conllu(options.ud_dir / f"la_{name}-ud-test.conllu")
        ]
        store = EvalStore(options.store)
        version = options.manifest.stem.rsplit("-", 1)[-1]
        key = RunKey(SET_NAME, version, options.split, MODE, options.model, PROMPT_ID)
        cap = None if options.max_cost is None else options.max_cost - store.spent_usd_for(key)
        summary = run_parse(
            items,
            tokens,
            make_client(spend_cap_usd=cap, db_path=options.llm_db),
            index or SqliteIndex(),
            store,
            model=options.model,
            manifest_version=version,
            split=options.split,
            git_commit=_git_commit(),
            limit=options.limit,
            concurrency=options.concurrency,
        )
        print(
            f"Run {summary.run_id} {summary.status}: answered {summary.answered}, "
            f"skipped {summary.skipped}, format failures {summary.failures}"
        )
        return 0 if summary.status == "complete" else 1

    if options.command == "index-agreement":
        results = evaluate(load_parse_set(options.manifest, options.ud_dir), lookup_form)
        print(render_agreement(results))
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
