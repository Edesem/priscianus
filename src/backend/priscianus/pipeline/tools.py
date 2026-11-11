"""The morphology index as tools for the model: definitions and executor (ADR-004, Decision 2).

Result content is compact JSON with sorted keys, so the same lookup always gives the same
request and cache key.
"""

import json
from typing import Any

from priscianus.morphology.canonical import canonicalise
from priscianus.morphology.lookup import Analysis
from priscianus.verifier.classify import merge_readings
from priscianus.verifier.index import MorphologyIndex

MAX_RESULTS = 50

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "lookup_form",
        "description": (
            "List every reading the morphology index has for a Latin surface form: lemma, part"
            " of speech and UD features. Use it before you parse a word. The index is incomplete"
            " and holds no uninflected words (adverbs, prepositions, conjunctions), so an error"
            " or an empty result does not mean the form is wrong. A feature missing from a"
            " reading means the index does not record it there, not that the word lacks it"
            " (noun gender, pronoun person). A deponent verb shows Voice=Act: that is a"
            " convention of the index."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"form": {"type": "string", "description": "A Latin word form."}},
            "required": ["form"],
            "additionalProperties": False,
        },
    },
    {
        "name": "inflect",
        "description": (
            "List the forms of a lemma that have the given UD features, for example the third"
            " person plural perfect active indicative of amo. An error does not mean the form"
            " is wrong: the index may have a gap. Features the index does not record (noun"
            " gender, deponent Voice=Act) are ignored and named in `ignored`."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lemma": {"type": "string"},
                "features": {"type": "object", "additionalProperties": {"type": "string"}},
                "pos": {"type": "string"},
            },
            "required": ["lemma", "features"],
            "additionalProperties": False,
        },
    },
]


def execute_tool_use(block: dict[str, Any], index: MorphologyIndex) -> dict[str, Any]:
    """Run one `tool_use` block and return its `tool_result` block."""
    body = _lookup_form(block["input"]["form"], index)
    return {"type": "tool_result", "tool_use_id": block["id"], "content": _dump(body)}


def _lookup_form(form: str, index: MorphologyIndex) -> dict[str, Any]:
    readings = merge_readings(index.analyse(form))
    return {
        "form": form,
        "readings": [_reading(r) for r in readings[:MAX_RESULTS]],
        "total": len(readings),
        "truncated": len(readings) > MAX_RESULTS,
    }


def _reading(analysis: Analysis) -> dict[str, Any]:
    features = canonicalise(analysis.features)
    reading: dict[str, Any] = {
        "features": "|".join(f"{name}={features[name]}" for name in sorted(features)),
        "form": analysis.form,
        "lemma": analysis.lemma_display,
        "pos": analysis.pos,
    }
    if analysis.base_lemma is not None:
        reading["base_lemma"] = analysis.base_lemma
    if analysis.deponent:
        reading["deponent"] = True
    if analysis.variant:
        reading["variant"] = True
    return reading


def _dump(body: dict[str, Any]) -> str:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
