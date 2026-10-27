"""Map Whitaker's Words inflection codes to Universal Dependencies features."""

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
    for field, code in infl.items():
        table = _CODE_FEATURES.get(field)
        if table is None or code in _PLACEHOLDERS:
            continue
        if code not in table:
            raise ValueError(f"Unknown Whitaker's {field.upper()} code: {code!r}")
        features.update(table[code])
    if verb_form is not None:
        features["VerbForm"] = verb_form
    return features
