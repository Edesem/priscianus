"""Build, freeze and load the gold parse set (ADR-003, Decisions 3 to 5)."""

import random
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

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
    totals: defaultdict[str, float] = defaultdict(float)
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


_CLASS_SHARES = {"verb": 0.35, "noun": 0.25, "adj": 0.15, "pron_det": 0.15, "uninflected": 0.10}
_BAND_SHARES = {"top1k": 0.40, "1k-10k": 0.35, "rare": 0.25}
_OPEN_CLASSES = ("verb", "noun", "adj")
# From the rarest band up, the order in which a short cell hands its places to the next band.
_BANDS_RARE_FIRST = ("rare", "1k-10k", "top1k")

Cell = tuple[str, str | None]


def allocate(total: int, shares: Mapping[str, float]) -> dict[str, int]:
    """Split `total` by `shares`, giving the places left over to the largest remainders."""
    exact = {name: total * share for name, share in shares.items()}
    given = {name: int(value) for name, value in exact.items()}
    by_remainder = sorted(exact, key=lambda name: (given[name] - exact[name], name))
    for name in by_remainder[: total - sum(given.values())]:
        given[name] += 1
    return given


def cell_quotas(per_slice: int) -> dict[Cell, int]:
    """Items per (class, band) for one slice and split; closed classes have no band."""
    quotas: dict[Cell, int] = {}
    for cls, n in allocate(per_slice, _CLASS_SHARES).items():
        if cls in _OPEN_CLASSES:
            for band, m in allocate(n, _BAND_SHARES).items():
                quotas[(cls, band)] = m
        else:
            quotas[(cls, None)] = n
    return quotas


def source_label(token: GoldToken) -> str:
    """The work a sentence comes from, without the passage."""
    if token.treebank == "proiel":
        return token.source.split(",")[0]
    return token.source if token.treebank == "perseus" else token.treebank


@dataclass(frozen=True)
class Item:
    """One sampled word with its strata."""

    split: str
    token: GoldToken
    slice: str
    source: str
    pos_class: str
    freq_band: str


@dataclass(frozen=True)
class Sample:
    """The sampled items, how many candidates each cell had, and the cells that came up short."""

    items: list[Item]
    candidate_counts: dict[str, int]
    shortfalls: dict[str, int]


def _cell_name(slice_name: str, cell: Cell, split: str | None = None) -> str:
    name = f"{slice_name}|{cell[0]}|{cell[1] or 'all'}"
    return f"{split}|{name}" if split else name


def sample_items(
    tokens: Sequence[GoldToken],
    ranks: Mapping[str, int],
    *,
    seed: int,
    sizes: Mapping[str, int],
) -> Sample:
    """Draw the stratified sample of ADR-003, Decision 3. `sizes` is items per slice and split.

    The result depends only on the candidates, the ranks and the seed. A sentence supplies at
    most one item across all splits. A cell that has fewer candidates than its quota hands the
    rest to the next more frequent band of the same class, and the smallest cells draw first.
    """
    pools: dict[tuple[str, Cell], list[Item]] = defaultdict(list)
    for token in sorted(tokens, key=lambda t: (t.treebank, t.sent_id, t.token_id)):
        cls = pos_class(token.upos)
        slice_name = slice_of(token) if is_candidate(token) else None
        if cls is None or slice_name is None:
            continue
        band = band_for_rank(rank_of(ranks, token.lemma))
        item = Item("", token, slice_name, source_label(token), cls, band)
        pools[(slice_name, (cls, band if cls in _OPEN_CLASSES else None))].append(item)

    wanted: dict[tuple[str, str, Cell], int] = {}
    shortfalls: dict[str, int] = {}
    for slice_name in ("Classical", "Ecclesiastical"):
        for split, size in sizes.items():
            quotas = cell_quotas(size)
            for cls in _CLASS_SHARES:
                cell: Cell
                if cls not in _OPEN_CLASSES:
                    cell = (cls, None)
                    wanted[(slice_name, split, cell)] = quotas[cell]
                    continue
                carry = 0
                for band in _BANDS_RARE_FIRST:
                    cell = (cls, band)
                    want = quotas[cell] + carry
                    take = min(want, len(pools[(slice_name, cell)]))
                    wanted[(slice_name, split, cell)] = take
                    carry = want - take
                if carry:
                    shortfalls[_cell_name(slice_name, (cls, None), split)] = carry

    rng = random.Random(seed)
    used: set[tuple[str, str]] = set()
    chosen: list[Item] = []
    order = sorted(
        wanted,
        key=lambda k: (len(pools[(k[0], k[2])]), k[0], k[1], k[2][0], k[2][1] or ""),
    )
    for slice_name, split, cell in order:
        pool = list(pools[(slice_name, cell)])
        rng.shuffle(pool)
        drawn = _draw(
            pool, wanted[(slice_name, split, cell)], used, balanced=slice_name == "Ecclesiastical"
        )
        if len(drawn) < wanted[(slice_name, split, cell)]:
            name = _cell_name(slice_name, cell, split)
            shortfalls[name] = (
                shortfalls.get(name, 0) + wanted[(slice_name, split, cell)] - len(drawn)
            )
        chosen.extend(replace(item, split=split) for item in drawn)

    chosen.sort(key=lambda i: (i.split, i.token.treebank, i.token.sent_id, i.token.token_id))
    counts = {
        _cell_name(sl, cell): len(pool) for (sl, cell), pool in sorted(pools.items(), key=str)
    }
    return Sample(chosen, counts, shortfalls)


def _draw(pool: list[Item], n: int, used: set[tuple[str, str]], *, balanced: bool) -> list[Item]:
    """Take up to n items from a shuffled pool, skipping sentences already used.

    When `balanced`, the treebanks supply equal shares first, and whatever one cannot supply
    is drawn from the rest of the pool.
    """
    drawn: list[Item] = []

    def take(candidates: Sequence[Item], k: int) -> None:
        taken = 0
        for item in candidates:
            if taken == k:
                return
            sentence = (item.token.treebank, item.token.sent_id)
            if sentence not in used:
                used.add(sentence)
                drawn.append(item)
                taken += 1

    if balanced:
        groups = sorted({item.token.treebank for item in pool})
        for i, group in enumerate(groups):
            share = n // len(groups) + (1 if i < n % len(groups) else 0)
            take([item for item in pool if item.token.treebank == group], share)
    take(pool, n - len(drawn))
    return drawn
