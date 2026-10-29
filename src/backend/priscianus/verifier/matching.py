"""The rules for comparing a parse with an index analysis, shared by the gold comparison and
the verifier so that both count the same things as a match (ADR-003, Decision 2)."""

import re
from collections.abc import Mapping
from itertools import product

from priscianus.morphology.canonical import canonicalise, relax
from priscianus.morphology.lookup import Analysis
from priscianus.morphology.normaliser import key_loose

NOUN_POS = frozenset({"noun", "name"})
PRONOUN_POS = frozenset({"pron", "det"})


def lemma_keys(lemma: str) -> frozenset[str]:
    """The loose keys a gold lemma may match, after the treebanks' lemma quirks.

    Perseus has a stray comma (*uterque,*). PROIEL puts optional letters in brackets
    (*dext(e)ra*, *(h)arena*), so the lemma may be spelt with or without them. A homograph
    number (*sum1*) is not part of the lemma.
    """
    cleaned = re.sub(r"\d+$", "", lemma.strip().rstrip(",;:."))
    parts = re.split(r"\(([^)]*)\)", cleaned)
    # Odd items are the bracketed letters; each is either left out or kept.
    choices = [("", part) if i % 2 else (part,) for i, part in enumerate(parts)]
    return frozenset(key_loose("".join(chosen)) for chosen in product(*choices))


def lemma_agrees(claimed_lemma: str, analysis: Analysis) -> bool:
    """Whether the analysis's lemma, or the lemma it is a form of, is the claimed lemma.

    The treebanks lemmatise a participle, gerund or supine as its verb and a comparative as
    its positive (ADR-003, Decision 2), so an analysis of *pauens* agrees with *paveo*.
    """
    names = {key_loose(analysis.lemma)}
    if analysis.base_lemma is not None:
        names.add(analysis.base_lemma)
    return not names.isdisjoint(lemma_keys(claimed_lemma))


def compared_features(
    features: Mapping[str, str], analysis: Analysis, *, noun: bool, pronoun: bool
) -> dict[str, str]:
    """`features` in canonical form, minus what the index cannot check on this analysis."""
    return relax(canonicalise(features), noun=noun, deponent=analysis.deponent, pronoun=pronoun)


def features_agree(
    expected: Mapping[str, str], analysis: Analysis, *, noun: bool, pronoun: bool
) -> bool:
    """Whether every compared feature in `expected` is in the analysis.

    Any member of a multi-valued expected feature will do. Features `expected` leaves out
    are not held against the analysis. `relax` drops what the index cannot check (noun
    gender, pronoun person, deponent voice).
    """
    wanted = compared_features(expected, analysis, noun=noun, pronoun=pronoun)
    actual = canonicalise(analysis.features)
    return all(actual.get(name) in value.split(",") for name, value in wanted.items())
