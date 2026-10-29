"""The `raw` mode of the parse task: one word in its sentence, no tools, no verifier (ADR-003)."""

import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from priscianus.llm.client import LLMClient, LLMResponse, Usage

from evals.gold import GoldToken

# Stored with every response. Change it whenever SYSTEM_PROMPT, OUTPUT_SCHEMA or the user
# message changes, so that results from different prompts are never mixed.
PROMPT_ID = "raw-parse-v3"

UPOS_TAGS: tuple[str, ...] = (
    "ADJ",
    "ADP",
    "ADV",
    "AUX",
    "CCONJ",
    "DET",
    "INTJ",
    "NOUN",
    "NUM",
    "PART",
    "PRON",
    "PROPN",
    "PUNCT",
    "SCONJ",
    "SYM",
    "VERB",
    "X",
)

# The compared features of ADR-003, Decision 2, in the canonical spelling.
ALLOWED_FEATURES: dict[str, tuple[str, ...]] = {
    "Case": ("Nom", "Gen", "Dat", "Acc", "Abl", "Voc", "Loc"),
    "Number": ("Sing", "Plur"),
    "Gender": ("Masc", "Fem", "Neut"),
    "Person": ("1", "2", "3"),
    "Tense": ("Pres", "Past", "Fut", "Pqp"),
    "Aspect": ("Imp", "Perf"),
    "Mood": ("Ind", "Sub", "Imp"),
    "Voice": ("Act", "Pass"),
    "VerbForm": ("Fin", "Inf", "Part", "Ger", "Gdv", "Sup"),
    "Degree": ("Cmp", "Sup"),
}

# Every feature is required, with "None" for one the word lacks. When all of them were
# optional, Haiku left features out and often ended on Degree (raw-parse-v1, dev).
NONE = "None"

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "lemma": {"type": "string"},
        "upos": {"type": "string", "enum": list(UPOS_TAGS)},
        "features": {
            "type": "object",
            "properties": {
                name: {"type": "string", "enum": [*values, NONE]}
                for name, values in ALLOWED_FEATURES.items()
            },
            "required": list(ALLOWED_FEATURES),
            "additionalProperties": False,
        },
    },
    "required": ["lemma", "upos", "features"],
    "additionalProperties": False,
}


def _feature_lines() -> str:
    return "\n".join(f"- {name}: {', '.join(values)}" for name, values in ALLOWED_FEATURES.items())


SYSTEM_PROMPT = f"""\
You are a Latin morphologist. You are given a Latin sentence in which one word is marked \
with double square brackets, like [[this]]. Analyse that word, as it is used in that \
sentence, and answer with a JSON object with three fields:

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


def mark_target(sentence: str, form: str, occurrence: int) -> str:
    """Put `[[...]]` around the `occurrence`-th whole-word match of `form` in `sentence`.

    Raises ValueError if the sentence has fewer than `occurrence` such matches.
    """
    matches = list(re.finditer(rf"(?<!\w){re.escape(form)}(?!\w)", sentence))
    if len(matches) < occurrence:
        raise ValueError(f"{form!r} occurs {len(matches)} time(s) in {sentence!r}")
    match = matches[occurrence - 1]
    return f"{sentence[: match.start()]}[[{form}]]{sentence[match.end() :]}"


def occurrence_of(target: GoldToken, tokens: Sequence[GoldToken]) -> int:
    """Which occurrence of its form `target` is in its sentence, counting from 1.

    `tokens` is any list of gold tokens that includes the target's sentence. The words of a
    split word (*-que*) are not in the sentence text under their own form, so they are not counted.
    """
    count = 0
    for token in tokens:
        if (token.treebank, token.sent_id) != (target.treebank, target.sent_id):
            continue
        if (
            token.form == target.form
            and token.mwt_form is None
            and token.token_id <= target.token_id
        ):
            count += 1
    return count


def build_messages(target: GoldToken, occurrence: int) -> list[dict[str, Any]]:
    """The user message for one parse item: the sentence with the target marked."""
    if target.mwt_form is not None:
        raise ValueError(f"{target.form!r} is half of a split word and has no form of its own")
    marked = mark_target(target.sentence, target.form, occurrence)
    return [
        {
            "role": "user",
            "content": f'Sentence: {marked}\nWord to analyse: "{target.form}" (marked above)',
        }
    ]


@dataclass(frozen=True)
class Claim:
    lemma: str
    upos: str
    features: dict[str, str]


@dataclass(frozen=True)
class ParseFailure:
    """A response that is not a valid claim. It is counted, never retried."""

    reason: str


def parse_claim(response: LLMResponse) -> Claim | ParseFailure:
    """Validate a response against the schema; anything that fails is a `ParseFailure`."""
    if response.stop_reason in ("max_tokens", "refusal"):
        return ParseFailure(f"stopped with {response.stop_reason}")
    try:
        data = json.loads(response.text)
    except json.JSONDecodeError as exc:
        return ParseFailure(f"invalid JSON: {exc}")
    reason = _schema_error(data)
    if reason:
        return ParseFailure(reason)
    features = {name: value for name, value in data["features"].items() if value != NONE}
    return Claim(data["lemma"], data["upos"], features)


def _schema_error(data: Any) -> str | None:
    if not isinstance(data, dict):
        return "JSON is not an object"
    if set(data) != {"lemma", "upos", "features"}:
        return f"fields are {sorted(data)}, not lemma, upos and features"
    if not isinstance(data["lemma"], str) or not data["lemma"].strip():
        return "lemma is not a non-empty string"
    if data["upos"] not in UPOS_TAGS:
        return f"unknown upos {data['upos']!r}"
    features = data["features"]
    if not isinstance(features, Mapping):
        return "features is not an object"
    for name, value in features.items():
        if name not in ALLOWED_FEATURES:
            return f"unknown feature {name!r}"
        if value != NONE and value not in ALLOWED_FEATURES[name]:
            return f"{name}={value!r} is not an allowed value"
    missing = [name for name in ALLOWED_FEATURES if name not in features]
    if missing:
        return f"features are missing {', '.join(missing)}"
    return None


@dataclass(frozen=True)
class RawResult:
    """One item's response, tagged with the prompt that produced it.

    `outcome` is a `Claim` or a `ParseFailure`; either way `raw_text` is kept, so a failure can
    be read later. `usage`, `cache_hit` and `latency_ms` are the call's, for the cost record.
    Results of different `prompt_id`s must never be scored together.
    """

    prompt_id: str
    model: str
    raw_text: str
    outcome: Claim | ParseFailure
    usage: Usage = Usage()
    cache_hit: bool = False
    latency_ms: int = 0


def run_raw(
    client: LLMClient,
    model: str,
    target: GoldToken,
    occurrence: int,
    *,
    max_tokens: int = 4096,
    sample: int = 0,
) -> RawResult:
    """Ask `model` to parse `target` once. A bad response becomes a failure and is not retried."""
    response = client.complete(
        model,
        build_messages(target, occurrence),
        system=SYSTEM_PROMPT,
        output_schema=OUTPUT_SCHEMA,
        max_tokens=max_tokens,
        sample=sample,
    )
    return RawResult(
        PROMPT_ID,
        model,
        response.text,
        parse_claim(response),
        usage=response.usage,
        cache_hit=response.cache_hit,
        latency_ms=response.latency_ms,
    )


@dataclass(frozen=True)
class FailureCounts:
    total: int
    failed: int
    by_kind: dict[str, int]

    @property
    def rate(self) -> float:
        return self.failed / self.total if self.total else 0.0


def failure_counts(results: Sequence[RawResult]) -> FailureCounts:
    """How many results are failures, and of what kind (the reason up to its first colon)."""
    kinds = Counter(
        r.outcome.reason.split(":")[0] for r in results if isinstance(r.outcome, ParseFailure)
    )
    return FailureCounts(len(results), sum(kinds.values()), dict(kinds))
