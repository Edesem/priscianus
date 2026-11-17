"""Tests for lining up the model's claims with the words the student typed (ADR-005, Decision 2)."""

from priscianus.pipeline.verify import VerifiedClaim
from priscianus.tutor.words import line_up, tokenise
from priscianus.verifier.claims import Claim
from priscianus.verifier.classify import Classification, Verdict
from priscianus.verifier.repair import ClaimState


def verified(form: str) -> VerifiedClaim:
    return VerifiedClaim(
        Claim(form, form, "NOUN", {}), Classification(Verdict.VERIFIED), ClaimState.VERIFIED
    )


def test_a_claim_matches_its_word_despite_macrons_case_and_an_enclitic() -> None:
    tokens = tokenise("Arma virumque cānō.")
    claims = [verified("arma"), verified("virum"), verified("cano")]

    words, dropped = line_up(tokens, claims)

    assert [w.token for w in words] == ["Arma", "virumque", "cānō"]
    assert [w.claim for w in words] == claims
    assert [w.note for w in words] == [None, "enclitic -que", None]
    assert dropped == 0


def test_a_word_without_a_claim_is_listed_and_a_claim_without_a_word_is_dropped() -> None:
    words, dropped = line_up(tokenise("arma xyzzy"), [verified("arma"), verified("cano")])

    assert [w.token for w in words] == ["arma", "xyzzy"]
    assert words[1].claim is None
    assert words[1].note == "not_explained"
    assert dropped == 1
