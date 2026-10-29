"""What the verifier needs from a morphology index (ADR-001)."""

import sqlite3
from pathlib import Path
from typing import Protocol

from priscianus.morphology.build_index import DEFAULT_DB
from priscianus.morphology.lookup import Analysis, lookup_form
from priscianus.morphology.normaliser import key_loose


class MorphologyIndex(Protocol):
    def analyse(self, form: str) -> list[Analysis]:
        """Every analysis of `form`, or an empty list if the index has none."""
        ...

    def has_lemma(self, lemma: str) -> bool:
        """Whether the index holds the lemma (and so its whole paradigm)."""
        ...


class SqliteIndex:
    """The `MorphologyIndex` over the SQLite file `make data` builds."""

    def __init__(self, db: Path = DEFAULT_DB) -> None:
        self._db = db

    def analyse(self, form: str) -> list[Analysis]:
        return lookup_form(form, self._db)

    def has_lemma(self, lemma: str) -> bool:
        con = sqlite3.connect(self._db)
        try:
            row = con.execute("SELECT 1 FROM lemmas WHERE lemma = ? LIMIT 1", (key_loose(lemma),))
            return row.fetchone() is not None
        finally:
            con.close()
