"""The JSON bodies of the API (ADR-005, Decision 1), converted from what `tutor` returns."""

from pydantic import BaseModel

from priscianus.morphology.lookup import Analysis
from priscianus.pipeline.verify import VerifiedClaim
from priscianus.tutor.drills import MAX_COUNT, DrillSet
from priscianus.tutor.explain import ExplainResult
from priscianus.tutor.feedback import Feedback
from priscianus.tutor.grade import Grade
from priscianus.tutor.words import WordResult

MAX_OTHER_READINGS = 50


class ExplainRequest(BaseModel):
    text: str


class DrillsRequest(BaseModel):
    request: str
    count: int = MAX_COUNT


class GradeRequest(BaseModel):
    """An item and the learner's answer. Any other field (such as an answer key) is ignored."""

    lemma: str
    pos: str
    features: dict[str, str]
    answer: str


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


class DrillItemOut(BaseModel):
    """One question. There is no answer key: grading works the accepted forms out again."""

    lemma: str
    pos: str
    features: dict[str, str]
    prompt: str


class DrillsResponse(BaseModel):
    message: str | None
    shortfall: int
    items: list[DrillItemOut]


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


def drills_response(result: DrillSet) -> DrillsResponse:
    items = [
        DrillItemOut(lemma=i.lemma, pos=i.pos, features=dict(i.features), prompt=i.prompt)
        for i in result.items
    ]
    return DrillsResponse(message=result.message, shortfall=result.shortfall, items=items)


class AnswerIsOut(BaseModel):
    lemma: str
    form: str
    features: str
    same_lemma: bool


class GradeResponse(BaseModel):
    correct: bool
    accepted: list[str]
    answer_is: list[AnswerIsOut]


def grade_response(result: Grade) -> GradeResponse:
    answer_is = [
        AnswerIsOut(lemma=r.lemma, form=r.form, features=r.features, same_lemma=r.same_lemma)
        for r in result.answer_is
    ]
    accepted = list(result.accepted)
    return GradeResponse(correct=result.correct, accepted=accepted, answer_is=answer_is)


class FeedbackOut(BaseModel):
    """The model's text (not checked) and its claims, each with a state like explain's."""

    text: str
    model: str
    prompt_id: str
    claims: list[ClaimOut]


class FeedbackError(BaseModel):
    """Why there is no feedback. The grade is still returned."""

    error: str
    message: str
    resets_at: str | None = None


class FeedbackResponse(BaseModel):
    grade: GradeResponse
    feedback: FeedbackOut | None
    feedback_error: FeedbackError | None


def feedback_response(
    grade: Grade, result: Feedback | None, error: FeedbackError | None = None
) -> FeedbackResponse:
    out = None
    if result is not None:
        claims = [_claim(c) for c in result.claims]
        out = FeedbackOut(
            text=result.text, model=result.model, prompt_id=result.prompt_id, claims=claims
        )
    return FeedbackResponse(grade=grade_response(grade), feedback=out, feedback_error=error)
