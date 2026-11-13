"""The `tools` mode of the parse task: the model can call the morphology index, and nothing
verifies its answer (ADR-004, Decision 7)."""

from dataclasses import dataclass
from typing import Any

from priscianus.llm.client import LLMClient
from priscianus.morphology.normaliser import key_loose
from priscianus.pipeline.loop import LoopResult, run_with_tools
from priscianus.pipeline.tools import TOOL_DEFINITIONS, execute_tool_use
from priscianus.verifier.claims import Claim, SchemaError, output_schema
from priscianus.verifier.index import MorphologyIndex

from evals.gold import GoldToken
from evals.raw_prompt import ALLOWED_FEATURES, UPOS_TAGS, ParseFailure, build_messages

# Stored with every response. Change it whenever SYSTEM_PROMPT, the output schema, the tool
# definitions, the loop limits or the user message change (ADR-004, Decision 7).
PROMPT_ID = "tools-parse-v1"


def _feature_lines() -> str:
    return "\n".join(f"- {name}: {', '.join(values)}" for name, values in ALLOWED_FEATURES.items())


# The conventions are those of raw-parse-v3. Only the answer's wrapper and the tools are new.
SYSTEM_PROMPT = f"""\
You are a Latin morphologist. You are given a Latin sentence in which one word is marked \
with double square brackets, like [[this]]. Analyse that word, as it is used in that \
sentence.

You have two tools that read a morphology index built from Wiktionary. Before you answer, \
call lookup_form on the marked word to see the readings the index has for it. Use inflect \
if you need to check which forms a lemma has. The index is incomplete: it can lack a real \
reading, it holds no uninflected words (adverbs, prepositions, conjunctions), and it may give \
a participle its own lemma. It does not read the sentence. Your answer need not be one of its \
readings: choose the parse that fits the sentence.

Answer with a JSON object with two fields:

- "text": an empty string.
- "claims": a list with exactly one claim, about the marked word. The claim has four fields:
  - "form": the marked word, exactly as it is written in the sentence.
  - "lemma": the dictionary form, with macrons left out.
  - "upos": the Universal Dependencies part-of-speech tag, one of: {", ".join(UPOS_TAGS)}.
  - "features": an object of Universal Dependencies features. It has every one of the names \
below. Give each one of its values, or "None" if the feature does not apply to the word. \
Use only these values:
{_feature_lines()}

Lemma conventions:
- A participle, gerundive, gerund or supine takes the lemma of its verb.
- A comparative or superlative takes the lemma of the positive.
- A deponent verb takes its active-looking first-person form (-or), for example "loquor".
- Use the nominative singular for nouns and the masculine nominative singular for adjectives.

Feature conventions:
- Give a value only for a feature that the word has; give "None" for the rest. Do not guess.
- Personal, reflexive and possessive pronouns and determiners have Person: ego and meus are 1, \
tu and tuus are 2, is, se and suus are 3.
- Give Gender from the noun that the word agrees with or refers to, even when its form is the \
same in several genders.
- The imperfect is Tense=Past with Aspect=Imp; the perfect is Tense=Past with Aspect=Perf; \
the pluperfect is Tense=Pqp; the future perfect is Tense=Fut with Aspect=Perf. Give Aspect \
only for these.
- A participle is VerbForm=Part with a Tense and a Voice. A gerundive is VerbForm=Gdv with \
no Tense and no Voice.
- A finite verb has VerbForm=Fin together with Mood.
- A superlative has Degree=Sup; leave Degree out for the positive.

Answer with the JSON object only.
"""


@dataclass(frozen=True)
class ToolsResult:
    """One item's answer, with everything the loop did to get it.

    `outcome` is a `Claim` or a `ParseFailure`; either way the loop's calls, tool calls and
    `raw_text` are kept. Results of different `prompt_id`s must never be scored together.
    """

    prompt_id: str
    model: str
    raw_text: str
    outcome: Claim | ParseFailure
    loop: LoopResult


def run_tools(
    client: LLMClient,
    model: str,
    target: GoldToken,
    occurrence: int,
    index: MorphologyIndex,
    *,
    max_tokens: int = 4096,
    sample: int = 0,
) -> ToolsResult:
    """Ask `model` to parse `target` once, with the index as tools. A bad answer is a failure."""
    loop = run_with_tools(
        client,
        model,
        build_messages(target, occurrence),
        TOOL_DEFINITIONS,
        lambda block: execute_tool_use(block, index),
        system=SYSTEM_PROMPT,
        output_schema=_OUTPUT_SCHEMA,
        max_tokens=max_tokens,
        sample=sample,
    )
    return ToolsResult(PROMPT_ID, model, loop.response.text, _one_claim(loop, target.form), loop)


_OUTPUT_SCHEMA: dict[str, Any] = output_schema()


def _one_claim(loop: LoopResult, form: str) -> Claim | ParseFailure:
    """The parse task's rule: exactly one claim, about the target and not a corrected spelling."""
    stop = loop.response.stop_reason
    if stop in ("max_tokens", "refusal"):
        return ParseFailure(f"stopped with {stop}")
    output = loop.output
    if isinstance(output, SchemaError):
        return ParseFailure(output.reason)
    if len(output.claims) != 1:
        return ParseFailure(f"{len(output.claims)} claims, not 1")
    claim = output.claims[0]
    if key_loose(claim.form) != key_loose(form):
        return ParseFailure(f"the claim is about {claim.form!r}, not {form!r}")
    return Claim(form, claim.lemma, claim.upos, claim.features)
