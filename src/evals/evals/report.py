"""Turn the runs in the eval store into numbers and failure examples for a markdown report."""

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from evals.store import Row


@dataclass(frozen=True)
class Headline:
    """The counts behind a run's headline metrics. Rates are None where nothing is counted.

    Exact match and lemma accuracy are over all items, so a format failure is a miss. The claim
    rates are over the items that gave a claim. A feature is `(right, marked)` over the items
    with a score whose gold marks it.
    """

    n: int
    exact: int
    lemma: int
    format_failures: int
    verified: int
    ambiguous: int
    contradicted: int
    unknown: int
    features: dict[str, tuple[int, int]]
    usd: float
    latency_p50_ms: int | None
    latency_p95_ms: int | None

    @property
    def claims(self) -> int:
        return self.verified + self.ambiguous + self.contradicted + self.unknown

    @property
    def exact_rate(self) -> float | None:
        return _rate(self.exact, self.n)

    @property
    def lemma_rate(self) -> float | None:
        return _rate(self.lemma, self.n)

    @property
    def claim_accuracy(self) -> float | None:
        return _rate(self.verified + self.ambiguous, self.claims)

    @property
    def hallucination_rate(self) -> float | None:
        return _rate(self.contradicted, self.claims)

    @property
    def unverifiable_rate(self) -> float | None:
        return _rate(self.unknown, self.claims)

    @property
    def format_failure_rate(self) -> float | None:
        return _rate(self.format_failures, self.n)


def _rate(part: int, whole: int) -> float | None:
    return part / whole if whole else None


def _percentile(values: Sequence[int], q: float) -> int | None:
    """The nearest-rank percentile: the smallest value that `q` of the values are at or below."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(math.ceil(q * len(ordered)), 1) - 1]


def headline(rows: Sequence[Row]) -> Headline:
    """Count the headline metrics over `rows`. Latency leaves out cache hits, which took no time."""
    verdicts = Counter(r.verdict for r in rows if r.verdict)
    features: dict[str, list[int]] = {}
    for row in rows:
        if row.score is None:
            continue
        for name, right in row.score["features"].items():
            counts = features.setdefault(name, [0, 0])
            counts[0] += right
            counts[1] += 1
    latencies = [r.latency_ms for r in rows if not r.cache_hit]
    return Headline(
        n=len(rows),
        exact=sum(bool(r.score and r.score["exact_match"]) for r in rows),
        lemma=sum(bool(r.score and r.score["lemma_match"]) for r in rows),
        format_failures=sum(r.format_error is not None for r in rows),
        verified=verdicts["verified"],
        ambiguous=verdicts["ambiguous"],
        contradicted=verdicts["contradicted"],
        unknown=verdicts["unknown"],
        features={name: (right, marked) for name, (right, marked) in sorted(features.items())},
        usd=sum(r.usd for r in rows),
        latency_p50_ms=_percentile(latencies, 0.5),
        latency_p95_ms=_percentile(latencies, 0.95),
    )
