"""The JSON bodies of the API (ADR-005, Decision 1), converted from what `tutor` returns."""

from pydantic import BaseModel

from priscianus.morphology.lookup import Analysis
from priscianus.pipeline.verify import VerifiedClaim
from priscianus.tutor.explain import ExplainResult
from priscianus.tutor.words import WordResult

MAX_OTHER_READINGS = 50


class ExplainRequest(BaseModel):
    text: str


class ErrorBody(BaseModel):
    """The one shape of every non-2xx response."""

    error: str
    message: str


class ReadingOut(BaseModel):
    lemma: str
    pos: str
    form: str
    features: str


class ClaimOut(BaseModel):
    form: str
    lemma: str
    upos: str
    features: dict[str, str]
    state: str
    other_readings: list[ReadingOut]


class WordOut(BaseModel):
    token: str
    claim: ClaimOut | None
    note: str | None


class ExplainResponse(BaseModel):
    text: str
    model: str
    prompt_id: str
    dropped_claims: int
    words: list[WordOut]


def _reading(analysis: Analysis) -> ReadingOut:
    features = "|".join(f"{name}={value}" for name, value in sorted(analysis.features.items()))
    return ReadingOut(lemma=analysis.lemma, pos=analysis.pos, form=analysis.form, features=features)


def _claim(verified: VerifiedClaim) -> ClaimOut:
    claim = verified.claim
    # A verified claim has no other readings and an unverifiable one has none worth showing.
    shows_others = verified.state.value in ("ambiguous", "disputed")
    others = verified.classification.others[:MAX_OTHER_READINGS] if shows_others else ()
    return ClaimOut(
        form=claim.form,
        lemma=claim.lemma,
        upos=claim.upos,
        features=dict(claim.features),
        state=verified.state.value,
        other_readings=[_reading(a) for a in others],
    )


def _word(word: WordResult) -> WordOut:
    claim = _claim(word.claim) if word.claim is not None else None
    return WordOut(token=word.token, claim=claim, note=word.note)


def explain_response(result: ExplainResult) -> ExplainResponse:
    return ExplainResponse(
        text=result.text,
        model=result.model,
        prompt_id=result.prompt_id,
        dropped_claims=result.dropped_claims,
        words=[_word(w) for w in result.words],
    )
