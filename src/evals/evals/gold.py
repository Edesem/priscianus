"""Read UD treebank files into gold tokens that can be compared with index analyses."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import product
from pathlib import Path

import conllu
from priscianus.morphology.canonical import canonicalise, relax
from priscianus.morphology.lookup import Analysis
from priscianus.morphology.normaliser import key_loose


@dataclass(frozen=True)
class GoldToken:
    """One word of a gold sentence, as the treebank annotates it.

    `features` are the treebank's own, unmapped. `mwt_form` is the surface word when the
    treebank split it into several tokens (Perseus *mecum* = *me* + *cum*; *-que*, *-ne*
    and *-ve* in Perseus and ITTB). Such a word is half of a split, so it has no surface
    form of its own to show the model (ADR-003, Decision 3).
    """

    treebank: str
    sent_id: str
    token_id: int
    form: str
    lemma: str
    upos: str
    features: dict[str, str]
    sentence: str
    mwt_form: str | None


def read_conllu(path: Path) -> list[GoldToken]:
    """Read a UD file such as `la_perseus-ud-test.conllu`; the treebank is named in the file."""
    match = re.match(r"la_(\w+)-ud-", path.name)
    treebank = match.group(1) if match else path.stem
    return parse_conllu(path.read_text(encoding="utf-8"), treebank=treebank)


def parse_conllu(text: str, *, treebank: str) -> list[GoldToken]:
    """Parse CoNLL-U text into one `GoldToken` per word, in file order.

    Multiword token lines and empty nodes are not words. A multiword token marks the words
    it spans through `mwt_form`.
    """
    tokens: list[GoldToken] = []
    for sentence in conllu.parse(text):
        mwt_forms: dict[int, str] = {}
        for token in sentence:
            token_id = token["id"]
            if isinstance(token_id, tuple) and token_id[1] == "-":
                for covered in range(token_id[0], token_id[2] + 1):
                    mwt_forms[covered] = token["form"]
        for token in sentence:
            token_id = token["id"]
            if not isinstance(token_id, int):
                continue
            tokens.append(
                GoldToken(
                    treebank=treebank,
                    sent_id=sentence.metadata["sent_id"],
                    token_id=token_id,
                    form=token["form"],
                    lemma=token["lemma"],
                    upos=token["upos"],
                    features=dict(token["feats"] or {}),
                    sentence=sentence.metadata["text"],
                    mwt_form=mwt_forms.get(token_id),
                )
            )
    return tokens


# The compared features and the values the UD Latin treebanks give them (ADR-003, Decision 2).
# Aspect is kept here only because `canonicalise` folds it into Tense.
_COMPARED_VALUES: dict[str, frozenset[str]] = {
    "Case": frozenset({"Nom", "Gen", "Dat", "Acc", "Abl", "Voc", "Loc"}),
    "Number": frozenset({"Sing", "Plur"}),
    "Gender": frozenset({"Masc", "Fem", "Neut"}),
    "Person": frozenset({"1", "2", "3"}),
    "Mood": frozenset({"Ind", "Sub", "Imp"}),
    "Tense": frozenset({"Pres", "Past", "Fut", "Pqp"}),
    "Aspect": frozenset({"Imp", "Perf", "Prosp"}),
    "Voice": frozenset({"Act", "Pass"}),
    "VerbForm": frozenset({"Fin", "Inf", "Part", "Ger", "Gdv", "Sup"}),
    "Degree": frozenset({"Pos", "Cmp", "Sup", "Abs"}),
}

# Lexical or derivational features that only some treebanks mark. They are dropped.
_NOT_COMPARED: frozenset[str] = frozenset(
    {
        "InflClass",
        "InflClass[nominal]",
        "PronType",
        "Polarity",
        "Poss",
        "Reflex",
        "Person[psor]",
        "Number[psor]",
        "NumType",
        "NumForm",
        "NumValue",
        "AdvType",
        "AdpType",
        "PartType",
        "NameType",
        "Proper",
        "Abbr",
        "Foreign",
        "Form",
        "Variant",
        "Compound",
        "ExtPos",
    }
)


class UnknownFeatureError(ValueError):
    """Raised when a gold feature, or a value of a compared feature, is not one we know."""

    def __init__(self, feature: str, value: str) -> None:
        self.feature = feature
        self.value = value
        super().__init__(f"Unknown gold feature: {feature}={value}")


def map_features(features: Mapping[str, str]) -> dict[str, str]:
    """Keep the compared subset of a treebank's features.

    Features outside the subset are dropped, as is `Degree=Dim`. A feature that is neither
    compared nor on the dropped list, or a value we have not seen for a compared feature,
    raises `UnknownFeatureError`, so that a new release cannot change the scores unnoticed.
    A multi-valued feature ("Gender=Fem,Masc") is kept whole.
    """
    mapped: dict[str, str] = {}
    for feature, value in features.items():
        if feature in _NOT_COMPARED:
            continue
        known = _COMPARED_VALUES.get(feature)
        if known is None:
            raise UnknownFeatureError(feature, value)
        if feature == "Degree" and value == "Dim":
            continue
        for member in value.split(","):
            if member not in known:
                raise UnknownFeatureError(feature, member)
        mapped[feature] = value
    return mapped


def lemma_keys(lemma: str) -> frozenset[str]:
    """The loose keys a gold lemma may match, after the treebanks' lemma quirks.

    Perseus has a stray comma (*uterque,*). PROIEL puts optional letters in brackets
    (*dext(e)ra*, *(h)arena*), so the lemma may be spelt with or without them. A homograph
    number (*sum1*) is not part of the lemma.
    """
    cleaned = re.sub(r"\d+$", "", lemma.strip().rstrip(",;:."))
    parts = re.split(r"\(([^)]*)\)", cleaned)
    # Odd items are the bracketed letters; each is either left out or kept.
    choices = [("", part) if i % 2 else (part,) for i, part in enumerate(parts)]
    return frozenset(key_loose("".join(chosen)) for chosen in product(*choices))


def matches(gold: GoldToken, analysis: Analysis) -> bool:
    """Whether an index analysis agrees with a gold parse.

    The lemmas must have the same loose key, and every compared feature the gold marks
    must be in the analysis (any member of a multi-valued gold feature will do). Features
    the gold leaves out are not held against the analysis. Both sides are in canonical form
    and the ADR-002 and spot-check relaxations are applied: gender is not compared on
    nouns, nor voice on deponents. Without the deponent flag in the index (#38), a verb
    lemma in *-or* counts as deponent (ADR-003, Decision 2).

    Raises UnknownFeatureError for a gold feature we have no mapping for.
    """
    if key_loose(analysis.lemma) not in lemma_keys(gold.lemma):
        return False
    expected = relax(
        canonicalise(map_features(gold.features)),
        noun=gold.upos in ("NOUN", "PROPN"),
        deponent=gold.upos in ("VERB", "AUX") and gold.lemma.rstrip("0123456789").endswith("or"),
    )
    actual = canonicalise(analysis.features)
    return all(actual.get(name) in value.split(",") for name, value in expected.items())
