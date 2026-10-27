"""Map Whitaker's Words inflection codes to Universal Dependencies features and
compare Whitaker's analyses of a form with the morphology index."""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

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


DEFAULT_FIXTURE = DEFAULT_DB.parent / "spot_check" / "whitakers.json"


def _expected_features(analysis: dict[str, Any]) -> dict[str, str]:
    """Whitaker's features for one analysis, minus what the index never records.

    Wiktionary tables give noun forms no gender (it belongs to the lemma) and
    leave positive adjectives without a degree, so neither can disagree. It
    also tags every form of a deponent Voice=Act where Whitaker's says passive
    (see ADR-002), so voice is not compared for deponents.
    """
    features = whitakers_to_ud(analysis["infl"], verb_form=analysis["verb_form"])
    if analysis["pos"] == "N":
        features.pop("Gender", None)
    if features.get("Degree") == "Pos":
        del features["Degree"]
    if analysis["pos"] == "V" and _is_deponent(analysis.get("entry", "")):
        features.pop("Voice", None)
    return features


def _is_deponent(entry: str) -> bool:
    """Whether a Whitaker's dictionary entry ("loquor, loqui, locutus sum") is deponent."""
    return entry.endswith(" sum")


def spot_check(fixture: Path = DEFAULT_FIXTURE, db: Path = DEFAULT_DB) -> list[Comparison]:
    """Compare every word in a Whitaker's fixture with the index.

    Words Whitaker's could not analyse are skipped: there is nothing to compare.
    """
    results = []
    for entry in json.loads(fixture.read_text()):
        if not entry["analyses"]:
            continue
        expected = [_expected_features(a) for a in entry["analyses"]]
        results.append(compare(entry["word"], expected, db))
    return results


def main() -> None:
    """Print each word where the index and Whitaker's disagree."""
    results = spot_check()
    for r in results:
        if r.status != "agree":
            print(f"{r.status:8} {r.word}: Whitaker's {r.unmatched}")
            for a in r.found:
                print(f"           index: {a.lemma_display} {a.pos} {a.features}")
    agreed = sum(r.status == "agree" for r in results)
    print(f"{agreed}/{len(results)} words agree", file=sys.stderr)


if __name__ == "__main__":
    main()
