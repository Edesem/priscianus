"""Build, freeze and load the gold parse set (ADR-003, Decisions 3 to 5)."""

from collections import Counter
from collections.abc import Mapping, Sequence

from evals.gold import GoldToken, lemma_keys

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


def frequency_ranks(treebanks: Mapping[str, Sequence[GoldToken]]) -> dict[str, int]:
    """Rank lemmas by their frequency in the train splits, 1 being the most frequent.

    Each treebank's counts become relative frequencies, which are averaged over the
    treebanks, so that the largest treebank does not decide the ranking (ADR-003, Decision 3).
    Lemmas are keyed by their loose key, and the words that cannot be sampled are not counted.
    Ties are ranked alphabetically.
    """
    totals: Counter[str] = Counter()
    for tokens in treebanks.values():
        counts = Counter(min(lemma_keys(t.lemma)) for t in tokens if is_candidate(t))
        size = sum(counts.values())
        for key, count in counts.items():
            totals[key] += count / size / len(treebanks)
    ordered = sorted(totals, key=lambda key: (-totals[key], key))
    return {key: rank for rank, key in enumerate(ordered, start=1)}


def band_for_rank(rank: int | None) -> str:
    """The frequency band of a lemma rank; a lemma not seen in the train splits is rare."""
    if rank is None or rank > 10_000:
        return "rare"
    return "top1k" if rank <= 1_000 else "1k-10k"


def rank_of(ranks: Mapping[str, int], lemma: str) -> int | None:
    """A gold lemma's rank, the best one over the spellings its brackets allow."""
    found = [ranks[key] for key in lemma_keys(lemma) if key in ranks]
    return min(found) if found else None
