"""Read UD treebank files into gold tokens that can be compared with index analyses."""

import re
from dataclasses import dataclass
from pathlib import Path

import conllu


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
