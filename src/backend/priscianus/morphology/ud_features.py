"""Map Wiktionary inflection tags to Universal Dependencies features."""

from collections.abc import Iterable

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


class ConflictingTagsError(ValueError):
    """Raised when two tags give different values for the same UD feature."""

    def __init__(self, feature: str, values: tuple[str, str]) -> None:
        self.feature = feature
        self.values = values
        super().__init__(f"Conflicting values for {feature}: {values[0]} vs {values[1]}")


def map_tags(tags: Iterable[str]) -> dict[str, str]:
    """Return the UD features for a Wiktionary tag list.

    Raises UnknownTagError for any tag that is not mapped or ignored, and
    ConflictingTagsError when tags disagree on a feature's value.
    """
    ordered = tuple(dict.fromkeys(tags))
    unknown = tuple(t for t in ordered if t not in _TAG_FEATURES and t not in _IGNORED_TAGS)
    if unknown:
        raise UnknownTagError(unknown)

    features: dict[str, str] = {}
    for tag in ordered:
        for feature, value in _TAG_FEATURES.get(tag, {}).items():
            _merge(features, feature, value)
    return features


def _merge(features: dict[str, str], feature: str, value: str) -> None:
    current = features.get(feature, value)
    if current == value:
        features[feature] = value
    elif {current, value} == {"Past", "Fut"}:
        # Wiktionary spells the future perfect as "future" + "perfect".
        features[feature] = "Fut"
    else:
        raise ConflictingTagsError(feature, (current, value))
