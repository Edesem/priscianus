"""The morphology index as tools for the model: definitions and executor (ADR-004, Decision 2).

Result content is compact JSON with sorted keys, so the same lookup always gives the same
request and cache key.
"""

import json
from typing import Any

from priscianus.morphology.canonical import canonicalise
from priscianus.morphology.inflect import NoSuchFormError
from priscianus.morphology.lookup import Analysis
from priscianus.morphology.ud_features import canonical_values
from priscianus.verifier.classify import merge_readings
from priscianus.verifier.index import MorphologyIndex
from priscianus.verifier.matching import NOUN_POS, PRONOUN_POS, lemma_agrees, lemma_keys

MAX_RESULTS = 50

# The index stores no `Gdv`: it is a future passive participle there.
_GERUNDIVE = {"VerbForm": "Part", "Tense": "Fut", "Voice": "Pass"}
# What the index cannot check (`relax`), so that `inflect` drops it when nothing fits.
_RELAXABLE = ("Gender", "Person", "Voice")
# Wiktionary's placeholder for an empty table cell.
_PLACEHOLDER = "-"

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
    if name == "lookup_form":
        return _lookup_form(_form_argument(arguments), index)
    if name == "inflect":
        return _inflect(arguments, index)
    available = ", ".join(tool["name"] for tool in TOOL_DEFINITIONS)
    raise _ToolError("unknown_tool", f"There is no tool {name!r}. The tools are: {available}.")


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


def _inflect(arguments: Any, index: MorphologyIndex) -> dict[str, Any]:
    lemma, features, pos = _inflect_arguments(arguments)
    if not any(index.has_lemma(key) for key in lemma_keys(lemma)):
        raise _ToolError(
            "unknown_lemma",
            f"The index does not hold the lemma {lemma!r}. It is incomplete and holds no"
            " uninflected words, so this does not mean that the lemma is wrong.",
        )
    try:
        forms, ignored = _forms(lemma, features, pos, index)
    except NoSuchFormError:
        raise _ToolError(
            "no_such_form",
            f"The index has no such form of {lemma!r}, which may be a gap in the index.",
        ) from None
    return {
        "forms": forms[:MAX_RESULTS],
        "ignored": ignored,
        "lemma": lemma,
        "total": len(forms),
        "truncated": len(forms) > MAX_RESULTS,
    }


def _forms(
    lemma: str, features: dict[str, str], pos: str | None, index: MorphologyIndex
) -> tuple[list[str], list[str]]:
    """The forms, and the requested features that were dropped to find them.

    A feature is dropped only if the index cannot record it on the lemma: noun gender,
    pronoun person, deponent voice. Anything else that fits nothing is a gap, not dropped.
    """
    wanted = _index_encoding(features)
    try:
        return _indexed_forms(index, lemma, wanted, pos), []
    except NoSuchFormError:
        relaxable = [name for name in _RELAXABLE if name in features]
        probe = {name: value for name, value in wanted.items() if name not in relaxable}
        if not relaxable:
            raise
        probed = _indexed_forms(index, lemma, probe, pos)
        ignored = sorted(set(relaxable) & _unrecorded(index, lemma, probed))
        if not ignored:
            raise
        kept = {name: value for name, value in wanted.items() if name not in ignored}
        return _indexed_forms(index, lemma, kept, pos), ignored


def _indexed_forms(
    index: MorphologyIndex, lemma: str, features: dict[str, str], pos: str | None
) -> list[str]:
    forms = [form for form in index.inflect(lemma, features, pos) if form != _PLACEHOLDER]
    if not forms:
        raise NoSuchFormError(f"No form of {lemma!r} with features {features}")
    return forms


def _unrecorded(index: MorphologyIndex, lemma: str, forms: list[str]) -> set[str]:
    """The features the index does not record on the lemma of `forms`."""
    unrecorded: set[str] = set()
    for form in forms[:MAX_RESULTS]:
        for analysis in index.analyse(form):
            if not lemma_agrees(lemma, analysis):
                continue
            if analysis.pos in NOUN_POS:
                unrecorded.add("Gender")
            if analysis.pos in PRONOUN_POS:
                unrecorded.add("Person")
            if analysis.deponent:
                unrecorded.add("Voice")
    return unrecorded


def _index_encoding(features: dict[str, str]) -> dict[str, str]:
    if features.get("VerbForm") == "Gdv":
        return {**features, **_GERUNDIVE}
    return features


def _inflect_arguments(arguments: Any) -> tuple[str, dict[str, str], str | None]:
    if (
        not isinstance(arguments, dict)
        or not {"lemma", "features"} <= set(arguments)
        or not set(arguments) <= {"lemma", "features", "pos"}
    ):
        raise _ToolError(
            "invalid_input", 'The input must be an object with "lemma", "features" and maybe "pos".'
        )
    lemma, features, pos = arguments["lemma"], arguments["features"], arguments.get("pos")
    if not isinstance(lemma, str) or not any(c.isalpha() for c in lemma):
        raise _ToolError("invalid_input", '"lemma" must be a string with letters in it.')
    if pos is not None and (not isinstance(pos, str) or not pos):
        raise _ToolError("invalid_input", '"pos" must be a non-empty string.')
    if not isinstance(features, dict):
        raise _ToolError("invalid_input", '"features" must be an object of UD names and values.')
    allowed = canonical_values()
    for name, value in features.items():
        if name not in allowed:
            raise _ToolError("invalid_input", f"{name!r} is not a feature: {', '.join(allowed)}.")
        if value not in allowed[name]:
            raise _ToolError(
                "invalid_input",
                f"{name}={value!r} is not a value. Use: {', '.join(allowed[name])}.",
            )
    return lemma, features, pos


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
