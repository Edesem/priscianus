"""Measure how often the morphology index agrees with the gold parses, before any model runs."""

import random
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from priscianus.morphology.lookup import Analysis
from priscianus.morphology.normaliser import key_loose

from evals.gold import GoldToken, lemma_keys, matches
from evals.parse_set import Item


@dataclass(frozen=True)
class Agreement:
    """How far the index goes towards a gold parse: each level implies the one before."""

    in_index: bool
    lemma_found: bool
    parse_matches: bool


def check_token(token: GoldToken, lookup: Callable[[str], list[Analysis]]) -> Agreement:
    """Whether the index has the form, the gold lemma for it, and an analysis that `matches`."""
    analyses = lookup(token.form)
    keys = lemma_keys(token.lemma)
    return Agreement(
        in_index=bool(analyses),
        lemma_found=any(key_loose(a.lemma) in keys for a in analyses),
        parse_matches=any(matches(token, a) for a in analyses),
    )


@dataclass(frozen=True)
class Rates:
    """Counts of items reaching each level of agreement within one group."""

    n: int
    in_index: int
    lemma_found: int
    parse_matches: int

    @property
    def parse_rate(self) -> float:
        return self.parse_matches / self.n


def _group_key(item: Item, dimension: str) -> str:
    if dimension == "treebank":
        return item.token.treebank
    return str(getattr(item, dimension))


def breakdown(results: Iterable[tuple[Item, Agreement]], dimension: str) -> dict[str, Rates]:
    """Group results by `treebank`, `pos_class`, `freq_band` or `slice` and count each level."""
    counts: defaultdict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for item, agreement in results:
        row = counts[_group_key(item, dimension)]
        row[0] += 1
        row[1] += agreement.in_index
        row[2] += agreement.lemma_found
        row[3] += agreement.parse_matches
    return {group: Rates(*row) for group, row in counts.items()}


def sample_disagreements(
    results: Sequence[tuple[Item, Agreement]], *, k: int, seed: int
) -> list[tuple[Item, Agreement]]:
    """Up to `k` results whose parse the index does not match, drawn repeatably."""
    missed = [r for r in results if not r[1].parse_matches]
    return random.Random(seed).sample(missed, min(k, len(missed)))


_DIMENSIONS = (
    ("Treebank", "treebank"),
    ("POS class", "pos_class"),
    ("Frequency band", "freq_band"),
    ("Classical / Ecclesiastical", "slice"),
)


def _pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f}%"


def render_report(results: Sequence[tuple[Item, Agreement]]) -> str:
    """Markdown tables of the agreement rates, overall and per stratum."""
    total = Rates(
        n=len(results),
        in_index=sum(a.in_index for _, a in results),
        lemma_found=sum(a.lemma_found for _, a in results),
        parse_matches=sum(a.parse_matches for _, a in results),
    )
    inflected = [a for i, a in results if i.pos_class != "uninflected"]
    matched = sum(a.parse_matches for a in inflected)
    lines = [
        f"Ceiling: {_pct(total.parse_matches, total.n)} of {total.n} items.",
        "",
        f"Ceiling on inflected classes: {_pct(matched, len(inflected))} of {len(inflected)} items.",
    ]
    for heading, dimension in _DIMENSIONS:
        lines += [
            "",
            f"### {heading}",
            "",
            "| Group | Items | Form in index | Gold lemma found | Parse matches |",
            "|---|---|---|---|---|",
        ]
        for group, rates in sorted(breakdown(results, dimension).items()):
            lines.append(
                f"| {group} | {rates.n} | {_pct(rates.in_index, rates.n)}"
                f" | {_pct(rates.lemma_found, rates.n)} | {_pct(rates.parse_matches, rates.n)} |"
            )
    return "\n".join(lines)


def evaluate(
    items: Iterable[Item], lookup: Callable[[str], list[Analysis]]
) -> list[tuple[Item, Agreement]]:
    """Check every parse-set item against the index."""
    return [(item, check_token(item.token, lookup)) for item in items]
