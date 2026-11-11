"""Check a claim about a Latin form against the morphology index."""

from priscianus.verifier.claims import Claim, ModelOutput, SchemaError, output_schema, parse_output
from priscianus.verifier.classify import Classification, Verdict, classify
from priscianus.verifier.index import MorphologyIndex, SqliteIndex

__all__ = [
    "Claim",
    "Classification",
    "ModelOutput",
    "MorphologyIndex",
    "SchemaError",
    "SqliteIndex",
    "Verdict",
    "classify",
    "output_schema",
    "parse_output",
]
