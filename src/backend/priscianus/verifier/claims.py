"""The claim and the JSON schema for every structured model output (ADR-004, Decision 1).

Validation errors are returned as `SchemaError` values, not raised, so that the evals can count
them as schema failures (ADR-003).
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from priscianus.morphology.ud_features import canonical_values

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

# Every feature is required, with "None" for one the word lacks (raw-parse-v3: when features
# were optional, Haiku left them out). "None" is removed when parsing.
NONE = "None"

_CLAIM_FIELDS = ("form", "lemma", "upos", "features")
_OUTPUT_FIELDS = ("text", "claims")


@dataclass(frozen=True)
class Claim:
    """A parse of one word: `features` are UD names and values, without the ones set to None."""

    form: str
    lemma: str
    upos: str
    features: Mapping[str, str]


@dataclass(frozen=True)
class ModelOutput:
    """A structured model output: prose for the learner and the claims it makes."""

    text: str
    claims: tuple[Claim, ...]


@dataclass(frozen=True)
class SchemaError:
    """An output that does not fit the schema. It is counted, never retried."""

    reason: str


def output_schema() -> dict[str, Any]:
    """The JSON schema of `ModelOutput`, built from the allowed values of the index."""
    features = canonical_values()
    return {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "form": {"type": "string"},
                        "lemma": {"type": "string"},
                        "upos": {"type": "string", "enum": list(UPOS_TAGS)},
                        "features": {
                            "type": "object",
                            "properties": {
                                name: {"type": "string", "enum": [*values, NONE]}
                                for name, values in features.items()
                            },
                            "required": list(features),
                            "additionalProperties": False,
                        },
                    },
                    "required": list(_CLAIM_FIELDS),
                    "additionalProperties": False,
                },
            },
        },
        "required": list(_OUTPUT_FIELDS),
        "additionalProperties": False,
    }


def parse_output(text: str) -> ModelOutput | SchemaError:
    """Validate the JSON `text` against the schema; anything that fails is a `SchemaError`."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return SchemaError(f"invalid JSON: {exc}")
    if not isinstance(data, dict):
        return SchemaError("JSON is not an object")
    if set(data) != set(_OUTPUT_FIELDS):
        return SchemaError(f"fields are {sorted(data)}, not text and claims")
    if not isinstance(data["text"], str):
        return SchemaError("text is not a string")
    if not isinstance(data["claims"], list):
        return SchemaError("claims is not a list")
    claims = []
    for item in data["claims"]:
        claim = parse_claim(item)
        if isinstance(claim, SchemaError):
            return claim
        claims.append(claim)
    return ModelOutput(data["text"], tuple(claims))


def parse_claim(data: Any) -> Claim | SchemaError:
    """Validate one decoded claim object against the schema."""
    if not isinstance(data, dict):
        return SchemaError("claim is not an object")
    if set(data) != set(_CLAIM_FIELDS):
        return SchemaError(f"claim fields are {sorted(data)}, not form, lemma, upos and features")
    for name in ("form", "lemma"):
        if not isinstance(data[name], str) or not data[name].strip():
            return SchemaError(f"{name} is not a non-empty string")
    if data["upos"] not in UPOS_TAGS:
        return SchemaError(f"unknown upos {data['upos']!r}")
    features = data["features"]
    if not isinstance(features, Mapping):
        return SchemaError("features is not an object")
    allowed = canonical_values()
    for name, value in features.items():
        if name not in allowed:
            return SchemaError(f"unknown feature {name!r}")
        if value != NONE and value not in allowed[name]:
            return SchemaError(f"{name}={value!r} is not an allowed value")
    missing = [name for name in allowed if name not in features]
    if missing:
        return SchemaError(f"features are missing {', '.join(missing)}")
    kept = {name: value for name, value in features.items() if value != NONE}
    return Claim(data["form"], data["lemma"], data["upos"], kept)
