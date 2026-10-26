"""Map Wiktionary inflection tags to Universal Dependencies features."""

from collections.abc import Iterable
from itertools import product

_TAG_FEATURES: dict[str, dict[str, str]] = {
    "nominative": {"Case": "Nom"},
    "genitive": {"Case": "Gen"},
    "dative": {"Case": "Dat"},
    "accusative": {"Case": "Acc"},
    "ablative": {"Case": "Abl"},
    "vocative": {"Case": "Voc"},
    "locative": {"Case": "Loc"},
    "singular": {"Number": "Sing"},
    "plural": {"Number": "Plur"},
    "masculine": {"Gender": "Masc"},
    "feminine": {"Gender": "Fem"},
    "neuter": {"Gender": "Neut"},
    "first-person": {"Person": "1"},
    "second-person": {"Person": "2"},
    "third-person": {"Person": "3"},
    "active": {"Voice": "Act"},
    "passive": {"Voice": "Pass"},
    "positive": {"Degree": "Pos"},
    "comparative": {"Degree": "Cmp"},
    "superlative": {"Degree": "Sup"},
    "present": {"Tense": "Pres"},
    "future": {"Tense": "Fut"},
    "imperfect": {"Tense": "Past", "Aspect": "Imp"},
    "perfect": {"Tense": "Past", "Aspect": "Perf"},
    "pluperfect": {"Tense": "Pqp"},
    "indicative": {"Mood": "Ind", "VerbForm": "Fin"},
    "subjunctive": {"Mood": "Sub", "VerbForm": "Fin"},
    "imperative": {"Mood": "Imp", "VerbForm": "Fin"},
    "infinitive": {"VerbForm": "Inf"},
    "participle": {"VerbForm": "Part"},
    "gerund": {"VerbForm": "Ger"},
    "supine": {"VerbForm": "Sup"},
}

# Tags that describe the table or the register of a form, not its morphology.
_IGNORED_TAGS: frozenset[str] = frozenset(
    {
        "canonical",
        "table-tags",
        "inflection-template",
        "class",
        "romanization",
        "alternative",
        "archaic",
        "obsolete",
        "rare",
        "uncommon",
        "poetic",
        "vulgar",
        "nonstandard",
        "Medieval-Latin",
        "Late-Latin",
        "Old-Latin",
        "Classical-Latin",
        "New-Latin",
        "Ecclesiastical",
    }
)


class UnknownTagError(ValueError):
    """Raised when a tag is neither mapped nor explicitly ignored."""

    def __init__(self, tags: tuple[str, ...]) -> None:
        self.tags = tags
        super().__init__(f"Unknown Wiktionary tag(s): {', '.join(tags)}")


# Wiktionary spells the future perfect as "future" + "perfect"; together they are one tense.
_FUTURE_PERFECT: dict[str, str] = {"Tense": "Fut", "Aspect": "Perf"}

# Features that ride along with another one, so a tag setting them fills that feature's slot.
_SECONDARY_FEATURES: dict[str, str] = {"Aspect": "Tense", "Mood": "VerbForm"}


def map_tags(tags: Iterable[str]) -> list[dict[str, str]]:
    """Return one UD feature dict per reading of a Wiktionary tag list.

    Several tags for the same feature mean one spelling shared by several
    readings (e.g. "eius" is genitive singular in each gender), so the result
    has one reading per combination.

    Raises UnknownTagError for any tag that is not mapped or ignored.
    """
    ordered = tuple(dict.fromkeys(tags))
    unknown = tuple(t for t in ordered if t not in _TAG_FEATURES and t not in _IGNORED_TAGS)
    if unknown:
        raise UnknownTagError(unknown)

    future_perfect = "future" in ordered and "perfect" in ordered
    slots: dict[str, list[dict[str, str]]] = {}
    for tag in ordered:
        features = _TAG_FEATURES.get(tag)
        if features is None:
            continue
        if future_perfect and tag in ("future", "perfect"):
            features = _FUTURE_PERFECT
        options = slots.setdefault(_slot(features), [])
        if features not in options:
            options.append(features)

    return [
        {feature: value for features in combination for feature, value in features.items()}
        for combination in product(*slots.values())
    ]


def _slot(features: dict[str, str]) -> str:
    return next(f for f in features if f not in _SECONDARY_FEATURES)
