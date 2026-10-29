"""Score a model's claim against the gold parse: exact match per feature (ADR-003, Decision 2)."""

from dataclasses import dataclass

from priscianus.morphology.canonical import canonicalise, relax
from priscianus.verifier.matching import lemma_keys

from evals.gold import GoldToken, map_features
from evals.parse_set import pos_class
from evals.raw_prompt import Claim


@dataclass(frozen=True)
class Score:
    """How one claim compares with its gold token.

    `features` has one entry for each compared feature the gold marks on the token. A feature
    the gold does not mark is not in it, whatever the model said.
    """

    lemma_match: bool
    upos_match: bool
    features: dict[str, bool]

    @property
    def exact_match(self) -> bool:
        return self.lemma_match and self.upos_match and all(self.features.values())


def score_claim(gold: GoldToken, claim: Claim, *, deponent: bool = False) -> Score:
    """Compare `claim` with `gold`.

    Both feature sets are put in canonical form first. A feature is scored only if the gold marks
    it, and a multi-valued gold feature matches any one of its members. Voice is not compared on
    a deponent, whose flag the caller takes from the index (ADR-002). Gender on nouns and person
    on pronouns are compared, unlike in the comparison with the index.

    Raises UnknownFeatureError for a gold feature we have no mapping for.
    """
    wanted = relax(
        canonicalise(map_features(gold.features)), noun=False, deponent=deponent, pronoun=False
    )
    given = canonicalise(claim.features)
    return Score(
        lemma_match=not lemma_keys(gold.lemma).isdisjoint(lemma_keys(claim.lemma)),
        upos_match=_class(gold.upos) == _class(claim.upos),
        features={name: given.get(name) in value.split(",") for name, value in wanted.items()},
    )


def _class(upos: str) -> str:
    return pos_class(upos) or upos
