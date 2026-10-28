"""Build, freeze and load the gold parse set (ADR-003, Decisions 3 to 5)."""

from evals.gold import GoldToken

_POS_CLASSES: dict[str, str] = {
    "VERB": "verb",
    "AUX": "verb",
    "NOUN": "noun",
    "ADJ": "adj",
    "PRON": "pron_det",
    "DET": "pron_det",
    "ADV": "uninflected",
    "ADP": "uninflected",
    "CCONJ": "uninflected",
    "SCONJ": "uninflected",
    "PART": "uninflected",
    "INTJ": "uninflected",
}

# PROIEL works by slice, matched on the start of the `# source` comment. Palladius is in neither.
_PROIEL_SLICES: dict[str, str | None] = {
    "Jerome's Vulgate": "Ecclesiastical",
    "Epistulae ad Atticum": "Classical",
    "De officiis": "Classical",
    "Commentarii belli Gallici": "Classical",
    "Opus agriculturae": None,
}


def pos_class(upos: str) -> str | None:
    """The part-of-speech class a UPOS tag is scored under, or None if the tag is excluded."""
    return _POS_CLASSES.get(upos)


def is_candidate(token: GoldToken) -> bool:
    """Whether a word may be sampled: an inflecting or function word with a surface form."""
    return (
        pos_class(token.upos) is not None
        and token.features.get("Foreign") != "Yes"
        and token.features.get("Abbr") != "Yes"
        and token.mwt_form is None
    )


def slice_of(token: GoldToken) -> str | None:
    """ "Classical" or "Ecclesiastical", or None for text that is in neither slice.

    Raises ValueError for a treebank outside the parse set or a PROIEL work we have not
    placed, so that a new release cannot add text to a slice unnoticed.
    """
    if token.treebank == "perseus":
        return "Classical"
    if token.treebank == "ittb":
        return "Ecclesiastical"
    if token.treebank != "proiel":
        raise ValueError(f"No slice for treebank {token.treebank!r}")
    for work, slice_name in _PROIEL_SLICES.items():
        if token.source.startswith(work):
            return slice_name
    raise ValueError(f"Unknown PROIEL work: {token.source!r}")
