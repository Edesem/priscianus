"""Measure how often the morphology index agrees with the gold parses, before any model runs."""

from collections import defaultdict
from collections.abc import Callable, Iterable
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
