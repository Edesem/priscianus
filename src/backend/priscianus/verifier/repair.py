"""The deterministic parts of repair: who is sent back, when to stop and the final state
(ADR-004, Decision 4). No LLM is called here.
"""

from enum import Enum

from priscianus.morphology.normaliser import key_loose
from priscianus.verifier.claims import Claim
from priscianus.verifier.classify import Classification, Verdict

# The index holds no uninflected words by design (ADR-003), so it has no evidence about them.
UNINFLECTED_UPOS = frozenset({"ADV", "ADP", "CCONJ", "SCONJ", "PART", "INTJ"})


class ClaimState(Enum):
    """What a claim's final verdict means for the learner and the report."""

    VERIFIED = "verified"
    AMBIGUOUS = "ambiguous"
    UNVERIFIABLE = "unverifiable"
    DISPUTED = "disputed"


_STATES = {
    Verdict.VERIFIED: ClaimState.VERIFIED,
    Verdict.AMBIGUOUS: ClaimState.AMBIGUOUS,
    Verdict.UNKNOWN: ClaimState.UNVERIFIABLE,
    Verdict.CONTRADICTED: ClaimState.DISPUTED,
}


def needs_repair(claim: Claim, classification: Classification) -> bool:
    """Whether the claim is sent back: CONTRADICTED or UNKNOWN, inflected, and its form has at
    least one reading to show. A VERIFIED or AMBIGUOUS claim is never sent back.
    """
    return (
        classification.verdict in (Verdict.CONTRADICTED, Verdict.UNKNOWN)
        and claim.upos not in UNINFLECTED_UPOS
        and bool(classification.others)
    )


def final_state(verdict: Verdict) -> ClaimState:
    """A claim still CONTRADICTED is flagged `disputed`, not dropped."""
    return _STATES[verdict]


def is_restated(before: Claim, after: Claim) -> bool:
    """Whether `after` makes the same claim as `before`: the same form, the same lemma key and
    the same features. `upos` is not compared, as the verifier ignores it.
    """
    return (
        key_loose(before.form) == key_loose(after.form)
        and key_loose(before.lemma) == key_loose(after.lemma)
        and dict(before.features) == dict(after.features)
    )
