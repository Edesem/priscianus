"""Check a claim about a Latin form against the morphology index."""

from priscianus.verifier.classify import Claim, Classification, Verdict, classify
from priscianus.verifier.index import MorphologyIndex, SqliteIndex

__all__ = ["Claim", "Classification", "MorphologyIndex", "SqliteIndex", "Verdict", "classify"]
