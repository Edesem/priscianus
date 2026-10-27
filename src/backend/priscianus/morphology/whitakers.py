"""Map Whitaker's Words inflection codes to Universal Dependencies features and
compare Whitaker's analyses of a form with the morphology index."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from priscianus.morphology.build_index import DEFAULT_DB
from priscianus.morphology.lookup import Analysis, lookup_form

# Whitaker's code -> UD features, per field. Codes for "any" or "not applicable"
# (X, C for gender, 0 for person) are absent on purpose: they constrain nothing.
_CODE_FEATURES: dict[str, dict[str, dict[str, str]]] = {
    "case": {
        "NOM": {"Case": "Nom"},
        "GEN": {"Case": "Gen"},
        "DAT": {"Case": "Dat"},
        "ACC": {"Case": "Acc"},
        "ABL": {"Case": "Abl"},
        "VOC": {"Case": "Voc"},
        "LOC": {"Case": "Loc"},
    },
    "number": {"S": {"Number": "Sing"}, "P": {"Number": "Plur"}},
    "gender": {"M": {"Gender": "Masc"}, "F": {"Gender": "Fem"}, "N": {"Gender": "Neut"}},
    "person": {"1": {"Person": "1"}, "2": {"Person": "2"}, "3": {"Person": "3"}},
    "tense": {
        "PRES": {"Tense": "Pres"},
        "IMPF": {"Tense": "Past", "Aspect": "Imp"},
        "PERF": {"Tense": "Past", "Aspect": "Perf"},
        "FUT": {"Tense": "Fut"},
        "FUTP": {"Tense": "Fut", "Aspect": "Perf"},
        "PLUP": {"Tense": "Pqp"},
    },
    "voice": {"ACTIVE": {"Voice": "Act"}, "PASSIVE": {"Voice": "Pass"}},
    "mood": {
        "IND": {"Mood": "Ind", "VerbForm": "Fin"},
        "SUB": {"Mood": "Sub", "VerbForm": "Fin"},
        "IMP": {"Mood": "Imp", "VerbForm": "Fin"},
        "INF": {"VerbForm": "Inf"},
    },
    "comparison": {
        "POS": {"Degree": "Pos"},
        "COMP": {"Degree": "Cmp"},
        "SUPER": {"Degree": "Sup"},
    },
}
_PLACEHOLDERS = frozenset({"", "X", "C", "0"})


def whitakers_to_ud(infl: dict[str, str], verb_form: str | None = None) -> dict[str, str]:
    """Return the UD features for one Whitaker's inflection record.

    `infl` holds Whitaker's field codes by lowercase field name. Participle and
    supine records have no mood, so the caller passes their `verb_form`.
    Raises ValueError for a code that is neither mapped nor a placeholder.
    """
    features: dict[str, str] = {}
    for name, code in infl.items():
        table = _CODE_FEATURES.get(name)
        if table is None or code in _PLACEHOLDERS:
            continue
        if code not in table:
            raise ValueError(f"Unknown Whitaker's {name.upper()} code: {code!r}")
        features.update(table[code])
    if verb_form is not None:
        features["VerbForm"] = verb_form
    return features


@dataclass(frozen=True)
class Comparison:
    """How the index's analyses of `word` stand against Whitaker's.

    "agree": every Whitaker's analysis has a match in the index.
    "missing": the index has no analysis of the form at all.
    "differ": the index knows the form but lacks some of `unmatched`.
    """

    word: str
    status: Literal["agree", "missing", "differ"]
    found: list[Analysis]
    unmatched: list[dict[str, str]] = field(default_factory=list)


def compare(word: str, expected: list[dict[str, str]], db: Path = DEFAULT_DB) -> Comparison:
    """Check that the index has an analysis of `word` for each expected UD feature set.

    An index analysis matches when it carries every expected feature; any extra
    features it has are not held against it.
    """
    found = lookup_form(word, db)
    if not found:
        return Comparison(word, "missing", found, list(expected))
    unmatched = [
        features
        for features in expected
        if not any(features.items() <= analysis.features.items() for analysis in found)
    ]
    return Comparison(word, "differ" if unmatched else "agree", found, unmatched)
