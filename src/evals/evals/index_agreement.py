"""Measure how often the morphology index agrees with the gold parses, before any model runs."""

from collections.abc import Callable
from dataclasses import dataclass

from priscianus.morphology.lookup import Analysis
from priscianus.morphology.normaliser import key_loose

from evals.gold import GoldToken, lemma_keys, matches


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
