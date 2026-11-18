"""The CI smoke eval: 50 dev items through the verified pipeline, with a pass/fail check.

See ADR-005, Decision 9 (docs/adr/ADR-005.md).
"""

import json
import random
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from priscianus.llm.client import LLMClient
from priscianus.llm.config import HAIKU
from priscianus.verifier.index import MorphologyIndex

from evals.gold import read_conllu
from evals.parse_set import DEFAULT_SEED, ManifestExistsError, cell_quotas, load_parse_set
from evals.report import Headline, headline
from evals.run import RunSummary, run_parse
from evals.store import EvalStore

MODE = "verified"
MODEL = HAIKU
PER_SLICE = 25  # 2 slices make the 50 items
_BANDS_RARE_FIRST = ("rare", "1k-10k", "top1k")


@dataclass(frozen=True)
class Thresholds:
    """The limits that fail the build."""

    max_hallucinations: int  # final claims still contradicted by the index ("disputed")
    min_exact: int  # items whose final claim matches the gold parse exactly
    max_schema_failures: int = 0


# THE THRESHOLDS: the one place they live. ADR-005, Decision 9 sets the rule:
# hallucinations may be at most baseline + 3 items, exact match at least baseline - 3 items,
# and no schema failures. The baseline is what `make eval-smoke` measured on smoke-v1 with
# Haiku in verified mode on 2026-11-18 (index build 8081e7a9): 0 disputed, 44 of 50 exact.
# When a prompt or index change moves it on purpose, update these two numbers in that PR.
BASELINE_HALLUCINATIONS = 0
BASELINE_EXACT = 44
MARGIN = 3
THRESHOLDS = Thresholds(
    max_hallucinations=BASELINE_HALLUCINATIONS + MARGIN,
    min_exact=BASELINE_EXACT - MARGIN,
)


def build_smoke_set(
    parse_manifest: Path, out_dir: Path, *, version: str, seed: int = DEFAULT_SEED
) -> Path:
    """Draw the smoke set from the dev items of a parse manifest and write `smoke-<version>.jsonl`.

    The rows are copied unchanged (IDs, strata and hashes), so no treebank text comes in. Each
    slice gives `PER_SLICE` items, split by class and band in the parse set's shares. Raises
    `ManifestExistsError` rather than overwrite a frozen set, and ValueError if a cell of the
    parse set has fewer items than the smoke set needs.
    """
    out = out_dir / f"smoke-{version}.jsonl"
    if out.exists():
        raise ManifestExistsError(f"{out} is frozen; a change makes a new version")
    rows = [json.loads(line) for line in parse_manifest.read_text(encoding="utf-8").splitlines()]
    pools: defaultdict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["split"] == "dev":
            pools[(row["slice"], row["pos_class"], row["freq_band"])].append(row)

    rng = random.Random(seed)
    quotas = cell_quotas(PER_SLICE)
    chosen: list[dict[str, Any]] = []
    for slice_name in ("Classical", "Ecclesiastical"):
        for pos_class in sorted({cls for cls, _ in quotas}):
            wanted: list[tuple[str | None, int]]
            if (pos_class, None) in quotas:  # a closed class is drawn whatever its band
                wanted = [(None, quotas[(pos_class, None)])]
            else:  # A short band hands its places to the next more frequent one, as in parse-v1
                wanted = [(band, quotas[(pos_class, band)]) for band in _BANDS_RARE_FIRST]
            carry = 0
            for band, quota in wanted:
                pool = [
                    row
                    for key, rows_in in pools.items()
                    if key[0] == slice_name and key[1] == pos_class and band in (None, key[2])
                    for row in rows_in
                ]
                take = min(quota + carry, len(pool))
                carry = quota + carry - take
                chosen.extend(rng.sample(pool, take))
            if carry:
                raise ValueError(f"{slice_name}/{pos_class}: {carry} places cannot be filled")

    order = {row["item_id"]: n for n, row in enumerate(rows)}
    chosen.sort(key=lambda row: order[row["item_id"]])
    out_dir.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(row) + "\n" for row in chosen), encoding="utf-8")
    return out


def check_smoke(counts: Headline, limits: Thresholds) -> list[str]:
    """What is wrong with a run, one message per limit crossed; empty if it passes."""
    failures = []
    if counts.contradicted > limits.max_hallucinations:
        failures.append(
            f"hallucinations (disputed claims): {counts.contradicted}, "
            f"limit {limits.max_hallucinations}"
        )
    if counts.exact < limits.min_exact:
        failures.append(f"exact match: {counts.exact} of {counts.n}, floor {limits.min_exact}")
    if counts.format_failures > limits.max_schema_failures:
        failures.append(
            f"schema failures: {counts.format_failures}, limit {limits.max_schema_failures}"
        )
    return failures


def run_smoke(
    manifest: Path,
    ud_dir: Path,
    client: LLMClient,
    index: MorphologyIndex,
    store: EvalStore,
    *,
    git_commit: str,
    index_build_hash: str,
    concurrency: int,
) -> tuple[RunSummary, Headline]:
    """Run the smoke set and count its metrics. A second run of the same set resumes the first."""
    items = load_parse_set(manifest, ud_dir)
    treebanks = sorted({i.token.treebank for i in items})
    tokens = [t for name in treebanks for t in read_conllu(ud_dir / f"la_{name}-ud-test.conllu")]
    # The whole name ("smoke-v1"), so that the run is not mistaken for one of parse-v1.
    summary = run_parse(
        items,
        tokens,
        client,
        index,
        store,
        model=MODEL,
        manifest_version=manifest.stem,
        split="dev",
        git_commit=git_commit,
        concurrency=concurrency,
        mode=MODE,
        index_build_hash=index_build_hash,
    )
    return summary, headline(store.run_rows(summary.run_id))


def render_result(
    summary: RunSummary, counts: Headline, failures: Sequence[str], limits: Thresholds
) -> str:
    lines = [
        f"Smoke eval ({MODE}, {MODEL}): {counts.n} items, "
        f"cost recorded for this run ${counts.usd:.4f}",
        f"  hallucinations (disputed claims): {counts.contradicted} "
        f"(limit {limits.max_hallucinations})",
        f"  exact match: {counts.exact} of {counts.n} (floor {limits.min_exact})",
        f"  schema failures: {counts.format_failures} (limit {limits.max_schema_failures})",
    ]
    if summary.status != "complete":
        lines.append(f"The run did not finish ({summary.status}), so the check cannot pass.")
    lines += [f"FAIL: {message}" for message in failures]
    if not failures and summary.status == "complete":
        lines.append("PASS")
    return "\n".join(lines)
