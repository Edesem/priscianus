"""Judge the claims stored in a run again, against the index as it is now. No API calls (ADR-004,
Decision 9).

The claims are the model's, so this gives the verdicts an index rebuild would give. It cannot
replay what repair would have done: a different index would have sent other claims back, and
only a new run can say what the model would have answered.
"""

from dataclasses import dataclass

from priscianus.pipeline.tools import reading_dict
from priscianus.verifier.claims import Claim
from priscianus.verifier.classify import classify
from priscianus.verifier.index import MorphologyIndex

from evals.store import EvalStore


@dataclass(frozen=True)
class ReverifySummary:
    """How many claims were judged again, and how many got another verdict than the one stored
    with the run."""

    claims: int
    changed: int


def reverify_run(
    store: EvalStore, run_id: int, index: MorphologyIndex, index_build_hash: str
) -> ReverifySummary:
    """Store a verdict, under `index_build_hash`, for every claim of every attempt of the run.

    The verdicts stored with the run are kept. A run judged under this build before gets its
    verdicts replaced, which changes nothing unless the index file changed without its hash.
    """
    stored = store.claims_to_verify(run_id)
    changed = 0
    for claim_id, claim, before in stored:
        classification = classify(Claim(**claim), index)
        store.save_verdict(
            claim_id,
            classification.verdict.value,
            index_build_hash,
            {
                "matching": [reading_dict(a) for a in classification.matching],
                "others": [reading_dict(a) for a in classification.others],
            },
        )
        changed += before != classification.verdict.value
    return ReverifySummary(len(stored), changed)
