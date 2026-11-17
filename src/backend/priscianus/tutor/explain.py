"""Explain a Latin word or sentence, with one verified claim for each word (ADR-005, Decision 2)."""

from dataclasses import dataclass

from priscianus.llm.client import LLMClient
from priscianus.llm.config import HAIKU, SONNET
from priscianus.pipeline.tools import TOOL_DEFINITIONS, execute_tool_use
from priscianus.pipeline.verify import verify_and_repair
from priscianus.tutor.prompts import (
    EXPLAIN_CALLS_PER_ROUND,
    EXPLAIN_MAX_TOKENS,
    EXPLAIN_PROMPT_ID,
    EXPLAIN_SYSTEM,
)
from priscianus.tutor.words import WordResult, line_up, tokenise
from priscianus.verifier.claims import SchemaError, output_schema
from priscianus.verifier.index import MorphologyIndex

MAX_WORDS = 25
MAX_CHARS = 300

_OUTPUT_SCHEMA = output_schema()


class ExplainInputError(ValueError):
    """The text is empty or over the limit. Raised before any API call."""


class ExplainModelError(Exception):
    """The model's answer did not fit the claim schema."""


@dataclass(frozen=True)
class ExplainResult:
    """`text` is the model's explanation and is not checked; only the claims in `words` are.
    `dropped_claims` counts claims about a word that is not in the input.
    """

    text: str
    model: str
    prompt_id: str
    dropped_claims: int
    words: tuple[WordResult, ...]


def explain(text: str, client: LLMClient, index: MorphologyIndex) -> ExplainResult:
    """Explain `text` and check each word's claim against `index`.

    One word goes to Haiku and more to Sonnet. Claims are verified and flagged, never sent back
    (`max_repairs=0`).
    """
    tokens = tokenise(text)
    if not tokens:
        raise ExplainInputError("Type a Latin word or sentence.")
    if len(tokens) > MAX_WORDS or len(text) > MAX_CHARS:
        raise ExplainInputError(f"Use at most {MAX_WORDS} words and {MAX_CHARS} characters.")
    model = HAIKU if len(tokens) == 1 else SONNET
    result = verify_and_repair(
        client,
        model,
        [{"role": "user", "content": text}],
        TOOL_DEFINITIONS,
        lambda block: execute_tool_use(block, index),
        index,
        system=EXPLAIN_SYSTEM,
        output_schema=_OUTPUT_SCHEMA,
        max_repairs=0,
        max_calls_per_round=EXPLAIN_CALLS_PER_ROUND,
        max_tokens=EXPLAIN_MAX_TOKENS,
    )
    if isinstance(result.output, SchemaError):
        raise ExplainModelError(result.output.reason)
    words, dropped = line_up(tokens, result.claims)
    return ExplainResult(result.output.text, model, EXPLAIN_PROMPT_ID, dropped, tuple(words))
