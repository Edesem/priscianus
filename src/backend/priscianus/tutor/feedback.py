"""Written feedback on a graded answer (ADR-005, Decision 6).

The model is told the grade and cannot change it: `Feedback` has no `correct` field, so whether
the answer was right only ever comes from `Grade`.
"""

from dataclasses import dataclass

from priscianus.llm.client import LLMClient
from priscianus.llm.config import HAIKU
from priscianus.pipeline.tools import TOOL_DEFINITIONS, execute_tool_use
from priscianus.pipeline.verify import VerifiedClaim, verify_and_repair
from priscianus.tutor.grade import Grade
from priscianus.tutor.prompts import (
    FEEDBACK_CALLS_PER_ROUND,
    FEEDBACK_MAX_TOKENS,
    FEEDBACK_PROMPT_ID,
    FEEDBACK_SYSTEM,
)
from priscianus.verifier.claims import SchemaError, output_schema
from priscianus.verifier.index import MorphologyIndex

_OUTPUT_SCHEMA = output_schema()


class FeedbackModelError(Exception):
    """The model's answer did not fit the claim schema."""


@dataclass(frozen=True)
class Feedback:
    """`text` is the model's feedback and is not checked; only `claims` are."""

    text: str
    model: str
    prompt_id: str
    claims: tuple[VerifiedClaim, ...]


def feedback(
    lemma: str,
    pos: str,
    features: dict[str, str],
    answer: str,
    grade: Grade,
    client: LLMClient,
    index: MorphologyIndex,
) -> Feedback:
    """Ask Haiku for one or two sentences on `answer`, and check its claims against `index`.

    Claims are verified and flagged, never sent back (`max_repairs=0`).
    """
    result = verify_and_repair(
        client,
        HAIKU,
        [{"role": "user", "content": _message(lemma, pos, features, answer, grade)}],
        TOOL_DEFINITIONS,
        lambda block: execute_tool_use(block, index),
        index,
        system=FEEDBACK_SYSTEM,
        output_schema=_OUTPUT_SCHEMA,
        max_repairs=0,
        max_calls_per_round=FEEDBACK_CALLS_PER_ROUND,
        max_tokens=FEEDBACK_MAX_TOKENS,
    )
    if isinstance(result.output, SchemaError):
        raise FeedbackModelError(result.output.reason)
    return Feedback(result.output.text, HAIKU, FEEDBACK_PROMPT_ID, result.claims)


def _message(lemma: str, pos: str, features: dict[str, str], answer: str, grade: Grade) -> str:
    shown = ", ".join(f"{name}={value}" for name, value in features.items() if value != "None")
    lines = [
        f"Question: give the form of the {pos} {lemma} with {shown}.",
        f"The student typed: {answer}",
        f"Grade (final): {'correct' if grade.correct else 'incorrect'}.",
        f"Accepted forms: {', '.join(grade.accepted)}.",
    ]
    for reading in grade.answer_is:
        same = "same lemma" if reading.same_lemma else "a different lemma"
        lines.append(
            f"What the typed form really is: {reading.form} ({reading.lemma}, {same}):"
            f" {reading.features}."
        )
    return "\n".join(lines)
