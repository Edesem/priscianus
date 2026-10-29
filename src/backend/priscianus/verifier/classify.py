"""Give a claim about a form a verdict by checking it against the morphology index (ADR-003)."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from priscianus.morphology.lookup import Analysis
from priscianus.morphology.normaliser import key_loose
from priscianus.verifier.index import MorphologyIndex
from priscianus.verifier.matching import (
    NOUN_POS,
    PRONOUN_POS,
    compared_features,
    features_agree,
    lemma_agrees,
    lemma_keys,
    uses_variant,
)


class Verdict(Enum):
    VERIFIED = "verified"
    AMBIGUOUS = "ambiguous"
    CONTRADICTED = "contradicted"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Claim:
    """A parse of one word: `features` are UD names and values."""

    form: str
    lemma: str
    features: Mapping[str, str]


@dataclass(frozen=True)
class Classification:
    """The verdict, the readings that match the claim and the form's other readings.

    `variant` is true if the claim matched only through a variant spelling of the form or
    the lemma (*adfirmo* for *affirmo*), so that reports can count it apart from an exact match.
    """

    verdict: Verdict
    matching: tuple[Analysis, ...] = ()
    others: tuple[Analysis, ...] = ()
    variant: bool = False


def classify(claim: Claim, index: MorphologyIndex) -> Classification:
    """Check `claim` against `index`.

    The form's analyses are merged into readings (analyses that agree on the lemma and on
    every compared feature are one reading). The claim is VERIFIED if it matches a reading
    and the form has no other, AMBIGUOUS if the form has others too, CONTRADICTED if no
    reading matches but the index holds the claimed lemma, and UNKNOWN if it does not.
    """
    readings = _readings(index.analyse(claim.form))
    matching = tuple(a for a in readings if _matches(claim, a))
    others = tuple(a for a in readings if a not in matching)
    if matching:
        return Classification(
            Verdict.AMBIGUOUS if others else Verdict.VERIFIED,
            matching,
            others,
            variant=all(uses_variant(claim.lemma, a) for a in matching),
        )
    if any(index.has_lemma(key) for key in lemma_keys(claim.lemma)):
        return Classification(Verdict.CONTRADICTED, others=others)
    return Classification(Verdict.UNKNOWN, others=others)


def _matches(claim: Claim, analysis: Analysis) -> bool:
    return lemma_agrees(claim.lemma, analysis) and features_agree(
        claim.features, analysis, noun=analysis.pos in NOUN_POS, pronoun=analysis.pos in PRONOUN_POS
    )


def _readings(analyses: list[Analysis]) -> list[Analysis]:
    """One analysis for each distinct reading, in index order."""
    seen: set[tuple[str, tuple[tuple[str, str], ...]]] = set()
    readings = []
    for analysis in analyses:
        compared = compared_features(
            analysis.features,
            analysis,
            noun=analysis.pos in NOUN_POS,
            pronoun=analysis.pos in PRONOUN_POS,
        )
        key = (key_loose(analysis.lemma), tuple(sorted(compared.items())))
        if key not in seen:
            seen.add(key)
            readings.append(analysis)
    return readings
