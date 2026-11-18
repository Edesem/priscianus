"""Make drills from a learner's request (ADR-005, Decision 3).

The model chooses lemmas and features. Code writes the prompt text of each item and takes the
accepted forms from the index, so the model never writes an answer key.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from priscianus.llm.client import LLMClient
from priscianus.llm.config import HAIKU
from priscianus.morphology.inflect import NoSuchFormError
from priscianus.morphology.ud_features import canonical_values
from priscianus.pipeline.loop import run_with_tools
from priscianus.pipeline.tools import TOOL_DEFINITIONS, accepted_forms, execute_tool_use
from priscianus.tutor.prompts import (
    DRILLS_CALLS_PER_ROUND,
    DRILLS_EXTRA_ITEMS,
    DRILLS_MAX_TOKENS,
    DRILLS_PROMPT_ID,
    DRILLS_SYSTEM,
    LIST_LEMMAS_TOOL,
)
from priscianus.verifier.claims import NONE
from priscianus.verifier.index import MorphologyIndex

MAX_REQUEST_CHARS = 200
MAX_COUNT = 10

NO_ITEMS_MESSAGE = (
    "I could not make any drills from that request. Try naming a Latin word or a form, for"
    " example 'the perfect tense of amo'."
)

_ALLOWED = canonical_values()
_TOOLS = [*TOOL_DEFINITIONS, LIST_LEMMAS_TOOL]

# The features an item must name to pick out one cell of the paradigm. Without them, the accepted
# forms would be a whole row ("perfect indicative of tego" would accept every person).
_FINITE = {"Person", "Number", "Tense", "Voice", "Mood"}
_NOMINAL = {"Case", "Number"}
_ADJECTIVE = {"Case", "Number", "Gender"}

_TENSES = {
    ("Pres", None): "present",
    ("Past", "Imp"): "imperfect",
    ("Past", "Perf"): "perfect",
    ("Past", None): "past",
    ("Pqp", None): "pluperfect",
    ("Fut", None): "future",
    ("Fut", "Perf"): "future perfect",
}
_WORDS = {
    "Degree": {"Cmp": "comparative", "Sup": "superlative"},
    "Case": {
        "Nom": "nominative",
        "Gen": "genitive",
        "Dat": "dative",
        "Acc": "accusative",
        "Abl": "ablative",
        "Voc": "vocative",
        "Loc": "locative",
    },
    "Gender": {"Masc": "masculine", "Fem": "feminine", "Neut": "neuter"},
    "Person": {"1": "1st person", "2": "2nd person", "3": "3rd person"},
    "Number": {"Sing": "singular", "Plur": "plural"},
    "Voice": {"Act": "active", "Pass": "passive"},
    "Mood": {"Ind": "indicative", "Sub": "subjunctive", "Imp": "imperative"},
    "VerbForm": {
        "Inf": "infinitive",
        "Part": "participle",
        "Ger": "gerund",
        "Sup": "supine",
        "Gdv": "gerundive",
    },
}


class DrillInputError(ValueError):
    """The request is empty or over the limit. Raised before any API call."""


class DrillModelError(Exception):
    """The model's answer was not the JSON object the drills schema asks for."""


@dataclass(frozen=True)
class DrillItem:
    """One "give the form" item. `accepted` comes from the index and is never sent to the
    learner before they answer.
    """

    lemma: str
    pos: str
    features: dict[str, str]
    accepted: tuple[str, ...]
    prompt: str


@dataclass(frozen=True)
class DrillSet:
    """`shortfall` is how many items fewer than `count` there are. `message` explains why when
    there are no items.
    """

    items: tuple[DrillItem, ...]
    message: str | None
    shortfall: int
    model: str
    prompt_id: str


def drills_output_schema() -> dict[str, Any]:
    """The JSON schema of the model's answer: a message and items of lemma, pos and features."""
    # Every feature is required, with "None" for one that does not apply: when they were optional,
    # Haiku gave only VerbForm=Fin and every verb item was too vague (as raw-parse-v3, ADR-004).
    features = {
        name: {"type": "string", "enum": [*values, NONE]} for name, values in _ALLOWED.items()
    }
    item = {
        "type": "object",
        "properties": {
            "lemma": {"type": "string"},
            "pos": {"type": "string"},
            "features": {
                "type": "object",
                "properties": features,
                "required": list(features),
                "additionalProperties": False,
            },
        },
        "required": ["lemma", "pos", "features"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"message": {"type": "string"}, "items": {"type": "array", "items": item}},
        "required": ["message", "items"],
        "additionalProperties": False,
    }


def make_drills(
    request: str, client: LLMClient, index: MorphologyIndex, count: int = MAX_COUNT
) -> DrillSet:
    """Turn `request` into up to `count` drill items whose accepted forms come from `index`.

    The model is asked for a few more items than `count`. Items with no index form and
    duplicates are dropped, and the first `count` that remain are kept.
    """
    if not request.strip():
        raise DrillInputError("Say what you want to practise.")
    if len(request) > MAX_REQUEST_CHARS:
        raise DrillInputError(f"Use at most {MAX_REQUEST_CHARS} characters.")
    if not 1 <= count <= MAX_COUNT:
        raise DrillInputError(f"Ask for between 1 and {MAX_COUNT} items.")
    seed = int.from_bytes(hashlib.sha256(request.encode()).digest()[:4], "big")
    content = f"Request: {request}\nGive {count + DRILLS_EXTRA_ITEMS} items."
    result = run_with_tools(
        client,
        HAIKU,
        [{"role": "user", "content": content}],
        _TOOLS,
        lambda block: _execute(block, index, seed),
        system=DRILLS_SYSTEM,
        output_schema=drills_output_schema(),
        max_calls_per_round=DRILLS_CALLS_PER_ROUND,
        max_tokens=DRILLS_MAX_TOKENS,
    )
    message, raw_items = _parse(result.response.text)
    items = _keep_valid(raw_items, index)[:count]
    if not items:
        # The model's message is kept only if it gave no items. If it gave items that were all
        # dropped, its message ("I have given you six items") would be false.
        message = message if not raw_items and message else NO_ITEMS_MESSAGE
        return DrillSet((), message, count, HAIKU, DRILLS_PROMPT_ID)
    return DrillSet(tuple(items), None, count - len(items), HAIKU, DRILLS_PROMPT_ID)


def _parse(text: str) -> tuple[str, list[Any]]:
    try:
        data = json.loads(text)
        message, items = data["message"], data["items"]
    except (ValueError, KeyError, TypeError):
        raise DrillModelError("The answer is not a JSON object with message and items.") from None
    if not isinstance(message, str) or not isinstance(items, list):
        raise DrillModelError("The answer needs a string message and a list of items.")
    return message, items


def _keep_valid(raw_items: list[Any], index: MorphologyIndex) -> list[DrillItem]:
    kept: list[DrillItem] = []
    seen: set[tuple[str, tuple[tuple[str, str], ...]]] = set()
    for raw in raw_items:
        lemma, pos, features = _fields(raw)
        if lemma is None or pos is None or features is None:
            continue
        key = (lemma, tuple(sorted(features.items())))
        if key in seen or not _names_one_form(pos, features):
            continue
        try:
            forms = accepted_forms(lemma, features, pos, index)
        except NoSuchFormError:
            continue
        seen.add(key)
        kept.append(DrillItem(lemma, pos, features, tuple(forms), item_prompt(lemma, features)))
    return kept


def _fields(raw: Any) -> tuple[str | None, str | None, dict[str, str] | None]:
    """The lemma, pos and features of a raw item, or Nones if it is malformed."""
    if not isinstance(raw, dict):
        return None, None, None
    lemma, pos, features = raw.get("lemma"), raw.get("pos"), raw.get("features")
    if not isinstance(lemma, str) or not lemma.strip() or not isinstance(pos, str):
        return None, None, None
    if not isinstance(features, dict) or not features:
        return None, None, None
    features = {name: value for name, value in features.items() if value != NONE}
    for name, value in features.items():
        if name not in _ALLOWED or value not in _ALLOWED[name]:
            return None, None, None
    if features.get("Tense") in ("Pres", "Pqp"):
        # Haiku often writes the present as Aspect=Imp. The index has no aspect there, so the
        # item would be dropped. Removing the slip does not change which form code looks up.
        features.pop("Aspect", None)
    if pos in ("noun", "name"):
        # The index has no noun gender, so a gender here could make the prompt say something false.
        features.pop("Gender", None)
    return lemma, pos, features or None


def _names_one_form(pos: str, features: dict[str, str]) -> bool:
    """Whether `features` pick out one cell. v1 drills cover finite verbs, infinitives, nouns,
    pronouns and adjectives; a participle, gerund or supine item is dropped.
    """
    if pos == "verb":
        if features.get("VerbForm") == "Inf":
            return {"Tense", "Voice"} <= set(features)
        return features.get("VerbForm") == "Fin" and set(features) >= _FINITE
    if pos in ("adj", "det"):
        return set(features) >= _ADJECTIVE
    return pos in ("noun", "name", "pron") and set(features) >= _NOMINAL


def item_prompt(lemma: str, features: dict[str, str]) -> str:
    """The question for the learner, built from lemma and features only."""
    words = []
    for name in ("Degree", "Case", "Gender", "Person", "Number"):
        if name in features:
            words.append(_WORDS[name][features[name]])
    if "Tense" in features:
        words.append(_TENSES[(features["Tense"], features.get("Aspect"))])
    for name in ("Voice", "Mood", "VerbForm"):
        if name in features and features[name] != "Fin":
            words.append(_WORDS[name][features[name]])
    return f"Give the {' '.join(words)} of {lemma}."


def _execute(block: dict[str, Any], index: MorphologyIndex, seed: int) -> dict[str, Any]:
    if block["name"] == "list_lemmas":
        return _list_lemmas(block, index, seed)
    return execute_tool_use(block, index)


def _list_lemmas(block: dict[str, Any], index: MorphologyIndex, seed: int) -> dict[str, Any]:
    result: dict[str, Any] = {"type": "tool_result", "tool_use_id": block["id"]}
    try:
        found = index.list_lemmas(seed=seed, **block["input"])
    except TypeError:
        result["is_error"] = True
        result["content"] = json.dumps(
            {"error": "invalid_input", "message": "Use only the filters the tool lists."}
        )
        return result
    lemmas = [
        {
            "lemma": f.lemma,
            "pos": f.pos,
            "infl_class": f.infl_class,
            "deponent": f.deponent,
            "freq_band": f.freq_band,
        }
        for f in found
    ]
    result["content"] = json.dumps({"lemmas": lemmas}, sort_keys=True, ensure_ascii=False)
    return result
