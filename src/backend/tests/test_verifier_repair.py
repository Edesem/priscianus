"""Tests for the deterministic repair policy (ADR-004, Decision 4)."""

import pytest

from priscianus.morphology.lookup import Analysis
from priscianus.verifier.claims import Claim
from priscianus.verifier.classify import Classification, Verdict
from priscianus.verifier.repair import ClaimState, final_state, is_restated, needs_repair

ROSAM = Analysis("rosa", "rosa", "noun", "rosam", {"Case": "Acc", "Number": "Sing"})
ACC = {"Case": "Acc", "Number": "Sing"}


def claim(upos: str = "NOUN", lemma: str = "rosa", features: dict[str, str] | None = None) -> Claim:
    return Claim("rosam", lemma, upos, features if features is not None else ACC)


def test_a_contradicted_claim_whose_form_has_readings_needs_repair() -> None:
    result = Classification(Verdict.CONTRADICTED, others=(ROSAM,))
    assert needs_repair(claim(), result)


def test_an_unknown_inflected_claim_whose_form_has_readings_needs_repair() -> None:
    result = Classification(Verdict.UNKNOWN, others=(ROSAM,))
    assert needs_repair(claim(), result)


@pytest.mark.parametrize("verdict", [Verdict.VERIFIED, Verdict.AMBIGUOUS])
def test_a_confirmed_claim_never_needs_repair(verdict: Verdict) -> None:
    result = Classification(verdict, matching=(ROSAM,), others=(ROSAM,))
    assert not needs_repair(claim(), result)


@pytest.mark.parametrize("verdict", [Verdict.CONTRADICTED, Verdict.UNKNOWN])
def test_a_form_without_readings_gives_nothing_to_send_so_no_repair(verdict: Verdict) -> None:
    assert not needs_repair(claim(), Classification(verdict))


@pytest.mark.parametrize("upos", ["ADV", "ADP", "CCONJ", "SCONJ", "PART", "INTJ"])
def test_an_uninflected_claim_never_needs_repair(upos: str) -> None:
    result = Classification(Verdict.UNKNOWN, others=(ROSAM,))
    assert not needs_repair(claim(upos), result)


@pytest.mark.parametrize(
    ("verdict", "state"),
    [
        (Verdict.VERIFIED, ClaimState.VERIFIED),
        (Verdict.AMBIGUOUS, ClaimState.AMBIGUOUS),
        (Verdict.UNKNOWN, ClaimState.UNVERIFIABLE),
        (Verdict.CONTRADICTED, ClaimState.DISPUTED),
    ],
)
def test_final_state_maps_each_verdict(verdict: Verdict, state: ClaimState) -> None:
    assert final_state(verdict) is state


def test_the_same_lemma_and_features_are_a_restatement() -> None:
    assert is_restated(claim(), claim(upos="NOUN"))


def test_a_restatement_ignores_lemma_spelling_that_the_index_treats_as_one_key() -> None:
    assert is_restated(claim(lemma="rosa"), claim(lemma="Rosa"))


def test_a_different_lemma_is_not_a_restatement() -> None:
    assert not is_restated(claim(), claim(lemma="rosus"))


def test_different_features_are_not_a_restatement() -> None:
    assert not is_restated(claim(), claim(features={"Case": "Abl", "Number": "Sing"}))


def test_a_claim_about_another_form_is_not_a_restatement() -> None:
    other = Claim("rosae", "rosa", "NOUN", ACC)
    assert not is_restated(claim(), other)
