"""Look up the analyses of a Latin surface form in the morphology index."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from priscianus.morphology.assimilation import variant_keys
from priscianus.morphology.build_index import _COLUMNS, DEFAULT_DB
from priscianus.morphology.normaliser import key_loose

_SELECT = (
    "SELECT l.lemma, l.lemma_display, l.pos, l.deponent, l.base_lemma, a.form_display, "
    + ", ".join(f'a."{column}"' for column in _COLUMNS.values())
    + " FROM analyses a JOIN lemmas l ON l.id = a.lemma_id"
    " WHERE a.key_loose = ? ORDER BY a.id"
)


@dataclass(frozen=True)
class Analysis:
    lemma: str
    lemma_display: str
    pos: str
    form: str
    features: dict[str, str]
    deponent: bool = False
    base_lemma: str | None = None
    variant: bool = False


def lookup_form(form: str, db: Path = DEFAULT_DB, *, variants: bool = True) -> list[Analysis]:
    """Return every analysis of `form`, or an empty list if the index has none.

    If the exact spelling has no analysis and `variants` is true, the assimilation variants of
    its prefix are tried (*adfirmat* finds *affirmat*), and those analyses are marked
    `variant`. An exact spelling that is in the index is never replaced by a variant.
    """
    key = key_loose(form)
    con = sqlite3.connect(db)
    try:
        rows = con.execute(_SELECT, (key,)).fetchall()
        variant = False
        if not rows and variants:
            variant = True
            rows = [r for k in variant_keys(key) for r in con.execute(_SELECT, (k,)).fetchall()]
    finally:
        con.close()
    return [
        Analysis(
            lemma=lemma,
            lemma_display=lemma_display,
            pos=pos,
            form=display,
            features={f: v for f, v in zip(_COLUMNS, values, strict=True) if v is not None},
            deponent=bool(deponent),
            base_lemma=base_lemma,
            variant=variant,
        )
        for lemma, lemma_display, pos, deponent, base_lemma, display, *values in rows
    ]
