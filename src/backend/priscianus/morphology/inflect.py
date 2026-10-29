"""Generate the surface forms of a Latin lemma from UD features."""

import sqlite3
from pathlib import Path

from priscianus.morphology.assimilation import variant_keys
from priscianus.morphology.build_index import _COLUMNS, DEFAULT_DB
from priscianus.morphology.normaliser import key_loose, key_macron


class NoSuchFormError(LookupError):
    """Raised when the index has no form of the lemma with the requested features."""


def inflect(
    lemma: str,
    features: dict[str, str],
    pos: str | None = None,
    db: Path = DEFAULT_DB,
) -> list[str]:
    """Return every indexed spelling of `lemma` that has all of `features`.

    `pos` narrows the search when several lemmas share a spelling. So do length
    marks in `lemma`: "mālum" excludes "malum", while an unmarked "malum" matches both.
    If the index has no lemma spelt like `lemma`, the assimilation variants of its prefix are
    tried (*adfirmo* finds *affirmo*). Raises NoSuchFormError if nothing matches, e.g. the
    vocative of a verb.
    """
    unknown = [f for f in features if f not in _COLUMNS]
    if unknown:
        raise ValueError(f"Unknown UD feature(s): {', '.join(unknown)}")

    query = (
        "SELECT DISTINCT l.lemma_display, a.form_display"
        " FROM analyses a JOIN lemmas l ON l.id = a.lemma_id"
        " WHERE l.lemma IN ({keys})"
    )
    key = key_loose(lemma)
    params: list[str] = []
    if pos is not None:
        query += " AND l.pos = ?"
        params.append(pos)
    for feature, value in features.items():
        query += f' AND a."{_COLUMNS[feature]}" = ?'
        params.append(value)
    query += " ORDER BY a.id"
    marked = key_macron(lemma) != key_loose(lemma)

    con = sqlite3.connect(db)
    try:
        keys = [key]
        if con.execute("SELECT 1 FROM lemmas WHERE lemma = ? LIMIT 1", (key,)).fetchone() is None:
            keys = variant_keys(key) or keys
            marked = False  # the marks were written for the other spelling
        query = query.format(keys=", ".join("?" * len(keys)))
        params = [*keys, *params]
        forms = list(
            dict.fromkeys(
                form
                for lemma_display, form in con.execute(query, params)
                if not marked or key_macron(lemma_display) == key_macron(lemma)
            )
        )
    finally:
        con.close()
    if not forms:
        raise NoSuchFormError(f"No form of {lemma!r} with features {features}")
    return forms
