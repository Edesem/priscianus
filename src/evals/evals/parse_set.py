"""Build, freeze and load the gold parse set (ADR-003, Decisions 3 to 5)."""

import hashlib
import json
import random
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from priscianus.verifier.matching import lemma_keys

from evals.gold import GoldToken, read_conllu

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
    quotas = {split: cell_quotas(size) for split, size in sizes.items()}
    for slice_name in ("Classical", "Ecclesiastical"):
        for split in sizes:
            for cls in _CLASS_SHARES:
                if cls not in _OPEN_CLASSES:
                    wanted[(slice_name, split, (cls, None))] = quotas[split][(cls, None)]
        for cls in _OPEN_CLASSES:
            # Dev and test draw on the same sentences, so what is left shrinks as splits take.
            left = {
                band: len(
                    {(i.token.treebank, i.token.sent_id) for i in pools[(slice_name, (cls, band))]}
                )
                for band in _BANDS_RARE_FIRST
            }
            carry = dict.fromkeys(sizes, 0)
            for band in _BANDS_RARE_FIRST:
                for split in sizes:
                    want = quotas[split][(cls, band)] + carry[split]
                    take = min(want, left[band])
                    left[band] -= take
                    wanted[(slice_name, split, (cls, band))] = take
                    carry[split] = want - take
            for split, short in carry.items():
                if short:
                    shortfalls[_cell_name(slice_name, (cls, None), split)] = short

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


class ManifestExistsError(FileExistsError):
    """Raised when a build would overwrite a committed manifest (ADR-003, Decision 4)."""


class ManifestMismatchError(ValueError):
    """Raised when the treebank files do not match the manifest, e.g. a different UD release."""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_name(treebank: str) -> str:
    return f"la_{treebank}-ud-test.conllu"


def write_manifest(
    sample: Sample,
    *,
    version: str,
    seed: int,
    sizes: Mapping[str, int],
    ud_dir: Path,
    out_dir: Path,
    release: str,
) -> Path:
    """Write `parse-<version>.jsonl` and `parse-<version>.meta.json` and return the first.

    The rows hold IDs, strata and hashes of the form and the sentence, and no treebank text
    (ADR-003, Decision 5). Raises `ManifestExistsError` rather than overwrite a manifest.
    """
    manifest = out_dir / f"parse-{version}.jsonl"
    meta = out_dir / f"parse-{version}.meta.json"
    if manifest.exists() or meta.exists():
        number = int(version.lstrip("v")) + 1 if version.lstrip("v").isdigit() else "N"
        raise ManifestExistsError(
            f"{manifest} is frozen; a change makes a new version (parse-v{number})"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = [
        {
            "item_id": f"{i.token.treebank}/{i.token.sent_id}/{i.token.token_id}",
            "split": i.split,
            "treebank": i.token.treebank,
            "ud_release": release,
            "file": _file_name(i.token.treebank),
            "sent_id": i.token.sent_id,
            "word_id": i.token.token_id,
            "slice": i.slice,
            "source": i.source,
            "pos_class": i.pos_class,
            "freq_band": i.freq_band,
            "form_sha256": _sha256(i.token.form),
            "sentence_sha256": _sha256(i.token.sentence),
        }
        for i in sample.items
    ]
    manifest.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    files = sorted({row["file"] for row in rows})
    meta.write_text(
        json.dumps(
            {
                "version": version,
                "seed": seed,
                "sizes": dict(sizes),
                "ud_release": release,
                "item_count": len(rows),
                "file_sha256": {
                    name: hashlib.sha256((ud_dir / name).read_bytes()).hexdigest() for name in files
                },
                "candidate_counts": sample.candidate_counts,
                "shortfalls": sample.shortfalls,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def load_parse_set(manifest: Path, ud_dir: Path) -> list[Item]:
    """Resolve a manifest against the downloaded treebanks.

    Raises `ManifestMismatchError` if a file is missing, an item is not in its file, or the
    form or sentence differs from the hash in the manifest, which means a different UD release.
    """
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    words: dict[str, dict[tuple[str, int], GoldToken]] = {}
    items: list[Item] = []
    for row in rows:
        name = row["file"]
        if name not in words:
            path = ud_dir / name
            if not path.exists():
                raise ManifestMismatchError(f"{path} is missing; run `make eval-data`")
            words[name] = {(t.sent_id, t.token_id): t for t in read_conllu(path)}
        token = words[name].get((row["sent_id"], row["word_id"]))
        if token is None:
            raise ManifestMismatchError(
                f"{row['item_id']} is not in {name} ({row['ud_release']} expected)"
            )
        for field, text in (("form", token.form), ("sentence", token.sentence)):
            if _sha256(text) != row[f"{field}_sha256"]:
                raise ManifestMismatchError(
                    f"{row['item_id']}: the {field} differs from the manifest; "
                    f"is {name} from UD {row['ud_release']}?"
                )
        items.append(
            Item(
                row["split"], token, row["slice"], row["source"], row["pos_class"], row["freq_band"]
            )
        )
    return items


def summary_table(items: Sequence[Item]) -> str:
    """A markdown table of item counts per slice, class and band, by split."""
    classes = list(_CLASS_SHARES)
    bands = list(_BAND_SHARES)
    counts: Counter[tuple[str, str, str, str]] = Counter(
        (i.slice, i.pos_class, i.freq_band if i.pos_class in _OPEN_CLASSES else "all", i.split)
        for i in items
    )
    keys = sorted(
        {k[:3] for k in counts},
        key=lambda k: (k[0], classes.index(k[1]), bands.index(k[2]) if k[2] in bands else 0),
    )
    lines = ["| Slice | Class | Band | Test | Dev |", "|---|---|---|---|---|"]
    for key in keys:
        lines.append(f"| {' | '.join(key)} | {counts[(*key, 'test')]} | {counts[(*key, 'dev')]} |")
    test = sum(n for k, n in counts.items() if k[3] == "test")
    dev = sum(n for k, n in counts.items() if k[3] == "dev")
    lines.append(f"| **Total** | | | {test} | {dev} |")
    return "\n".join(lines)


TRAIN_TREEBANKS = ("perseus", "proiel", "ittb", "llct", "udante", "circse")
TEST_TREEBANKS = ("perseus", "proiel", "ittb")
DEFAULT_SEED = 39
DEFAULT_SIZES = {"test": 500, "dev": 150}


def build_set(
    *, ud_dir: Path, out_dir: Path, version: str, seed: int, release: str
) -> tuple[Path, str]:
    """Build and write a parse set from the downloaded files; return the manifest and summary.

    Raises FileNotFoundError if a treebank file is missing, and `ManifestExistsError` if the
    version is already written.
    """
    names = [f"la_{tb}-ud-train.conllu" for tb in TRAIN_TREEBANKS]
    names += [_file_name(tb) for tb in TEST_TREEBANKS]
    missing = [name for name in names if not (ud_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing {', '.join(missing)} in {ud_dir}; run `make eval-data`")
    ranks = frequency_ranks(
        {tb: read_conllu(ud_dir / f"la_{tb}-ud-train.conllu") for tb in TRAIN_TREEBANKS}
    )
    candidates = [t for tb in TEST_TREEBANKS for t in read_conllu(ud_dir / _file_name(tb))]
    sample = sample_items(candidates, ranks, seed=seed, sizes=DEFAULT_SIZES)
    manifest = write_manifest(
        sample,
        version=version,
        seed=seed,
        sizes=DEFAULT_SIZES,
        ud_dir=ud_dir,
        out_dir=out_dir,
        release=release,
    )
    return manifest, summary_table(sample.items)
