"""List lemmas from the morphology index, so the drill generator can pick words (ADR-005)."""

import random
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from priscianus.morphology.build_index import DEFAULT_DB

MAX_LIMIT = 50


@dataclass(frozen=True)
class LemmaInfo:
    lemma: str
    lemma_display: str
    pos: str
    infl_class: str | None
    deponent: bool
    freq_band: str | None


def list_lemmas(
    db: Path = DEFAULT_DB,
    *,
    pos: str | None = None,
    infl_class: str | None = None,
    deponent: bool | None = None,
    freq_band: str | None = None,
    limit: int = 20,
    seed: int = 0,
) -> list[LemmaInfo]:
    """Return up to `limit` lemmas that match every filter given (`None` means no filter).

    Only lemmas with at least one form in the index are returned, and participles
    (lemmas with a `base_lemma`) are skipped, so "verbs" means real verbs. `limit` is
    capped at 50. The lemmas are sampled with `seed`: the same arguments give the same list.
    """
    conditions = [
        "l.base_lemma IS NULL",
        "EXISTS (SELECT 1 FROM analyses a WHERE a.lemma_id = l.id)",
    ]
    params: list[str | int] = []
    if pos is not None:
        conditions.append("l.pos = ?")
        params.append(pos)
    if infl_class is not None:
        conditions.append("l.infl_class = ?")
        params.append(infl_class)
    if deponent is not None:
        conditions.append("l.deponent = ?")
        params.append(int(deponent))
    if freq_band is not None:
        conditions.append("l.freq_band = ?")
        params.append(freq_band)
    query = (
        "SELECT l.lemma, l.lemma_display, l.pos, l.infl_class, l.deponent, l.freq_band"
        " FROM lemmas l WHERE " + " AND ".join(conditions) + " ORDER BY l.id"
    )

    con = sqlite3.connect(db)
    try:
        rows = con.execute(query, params).fetchall()
    finally:
        con.close()

    chosen = random.Random(seed).sample(rows, min(max(limit, 0), MAX_LIMIT, len(rows)))
    return [
        LemmaInfo(lemma, display, row_pos, row_class, bool(row_deponent), row_band)
        for lemma, display, row_pos, row_class, row_deponent, row_band in chosen
    ]
