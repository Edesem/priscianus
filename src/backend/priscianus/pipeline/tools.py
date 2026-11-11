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


class _ToolError(Exception):
    """An input error, reported to the model as an `is_error` result. Never leaves this module."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def execute_tool_use(block: dict[str, Any], index: MorphologyIndex) -> dict[str, Any]:
    """Run one `tool_use` block and return its `tool_result` block.

    Input errors become a result with `is_error: true`. A failure of the index or the code is
    not an input error, so it raises and fails the run.
    """
    result: dict[str, Any] = {"type": "tool_result", "tool_use_id": block["id"]}
    try:
        result["content"] = _dump(_run(block["name"], block["input"], index))
    except _ToolError as error:
        result["content"] = _dump({"error": error.code, "message": error.message})
        result["is_error"] = True
    return result


def _run(name: str, arguments: Any, index: MorphologyIndex) -> dict[str, Any]:
    if name != "lookup_form":
        available = ", ".join(tool["name"] for tool in TOOL_DEFINITIONS)
        raise _ToolError("unknown_tool", f"There is no tool {name!r}. The tools are: {available}.")
    return _lookup_form(_form_argument(arguments), index)


def _form_argument(arguments: Any) -> str:
    if not isinstance(arguments, dict) or set(arguments) != {"form"}:
        raise _ToolError("invalid_input", 'The input must be an object with only "form".')
    form = arguments["form"]
    if not isinstance(form, str) or not any(c.isalpha() for c in form):
        raise _ToolError("invalid_input", '"form" must be a string with letters in it.')
    return form


def _lookup_form(form: str, index: MorphologyIndex) -> dict[str, Any]:
    readings = merge_readings(index.analyse(form))
    if not readings:
        raise _ToolError(
            "unknown_form",
            f"The index does not hold {form!r}. It is incomplete and holds no uninflected"
            " words, so this does not mean that the form is wrong.",
        )
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
