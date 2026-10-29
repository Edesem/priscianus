"""Read UD treebank files into gold tokens that can be compared with index analyses."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import conllu
from priscianus.morphology.canonical import canonicalise
from priscianus.morphology.lookup import Analysis
from priscianus.verifier.matching import features_agree, lemma_agrees


@dataclass(frozen=True)
class GoldToken:
    """One word of a gold sentence, as the treebank annotates it.

    `features` are the treebank's own, unmapped. `mwt_form` is the surface word when the
    treebank split it into several tokens (Perseus *mecum* = *me* + *cum*; *-que*, *-ne*
    and *-ve* in Perseus and ITTB). Such a word is half of a split, so it has no surface
    form of its own to show the model (ADR-003, Decision 3). `source` is where the sentence
    comes from: Perseus's `# newdoc id` (which holds for the sentences after it), PROIEL's
    `# source`, and empty for ITTB, which is all Aquinas.
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
    source: str = ""


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
    doc_id = ""
    for sentence in conllu.parse(text):
        doc_id = sentence.metadata.get("newdoc id", doc_id)
        source = sentence.metadata.get("source", doc_id)
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
                    source=source,
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


def matches(gold: GoldToken, analysis: Analysis) -> bool:
    """Whether an index analysis agrees with a gold parse.

    The lemmas must agree (see `lemma_agrees`), and every compared feature the gold marks
    must be in the analysis (any member of a multi-valued gold feature will do). Features
    the gold leaves out are not held against the analysis. Both sides are in canonical form
    and the ADR-002 and spot-check relaxations are applied: gender is not compared on
    nouns, nor person on pronouns, nor voice on deponents and semi-deponents, as the index
    flags them (ADR-002).

    Raises UnknownFeatureError for a gold feature we have no mapping for.
    """
    return lemma_agrees(gold.lemma, analysis) and features_agree(
        canonicalise(map_features(gold.features)),
        analysis,
        noun=gold.upos in ("NOUN", "PROPN"),
        pronoun=gold.upos in ("PRON", "DET"),
    )
