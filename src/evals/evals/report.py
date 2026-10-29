"""Turn the runs in the eval store into numbers and failure examples for a markdown report."""

import math
import random
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from priscianus.verifier.classify import Claim, Verdict, classify
from priscianus.verifier.index import MorphologyIndex

from evals.index_agreement import Agreement
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


def breakdown(rows: Sequence[Row], dimension: str) -> dict[str, Headline]:
    """Count the headline metrics within each value of `freq_band`, `pos_class` or `slice`."""
    groups: dict[str, list[Row]] = {}
    for row in rows:
        groups.setdefault(getattr(row, dimension), []).append(row)
    return {name: headline(group) for name, group in sorted(groups.items())}


@dataclass(frozen=True)
class AmbiguityHandling:
    """How often exact match was reached on forms with several index readings, and on one.

    A form is ambiguous if the index holds the gold reading and others; single if it holds the
    gold reading alone. Items whose gold reading the index lacks, or whose gold leaves a feature
    open, are in neither.
    """

    ambiguous: int
    ambiguous_right: int
    single: int
    single_right: int


def ambiguity(rows: Sequence[Row], index: MorphologyIndex) -> AmbiguityHandling:
    """Split `rows` by whether the index finds the form ambiguous, and count the gold picks."""
    counts = {Verdict.AMBIGUOUS: [0, 0], Verdict.VERIFIED: [0, 0]}
    for row in rows:
        gold = row.gold
        if any("," in value for value in gold["features"].values()):
            continue
        found = classify(Claim(gold["form"], gold["lemma"], gold["features"]), index).verdict
        if found in counts:
            counts[found][0] += 1
            counts[found][1] += bool(row.score and row.score["exact_match"])
    (ambiguous, ambiguous_right) = counts[Verdict.AMBIGUOUS]
    (single, single_right) = counts[Verdict.VERIFIED]
    return AmbiguityHandling(ambiguous, ambiguous_right, single, single_right)


def confusions(rows: Sequence[Row]) -> list[tuple[str, str, str, int]]:
    """Each wrong feature value as `(feature, gold, given, count)`, the most common first."""
    counts: Counter[tuple[str, str, str]] = Counter()
    for row in rows:
        if row.score is None or row.claim is None:
            continue
        for name, right in row.score["features"].items():
            if not right:
                given = row.claim["features"].get(name, "(none)")
                counts[(name, row.gold["features"][name], given)] += 1
    return [(*key, n) for key, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


CATEGORIES = (
    "Format failure",
    "Hallucination",
    "Index disagreement",
    "Wrong reading",
    "Wrong and unverifiable",
)


def _category(row: Row) -> str | None:
    if row.format_error is not None:
        return "Format failure"
    right = bool(row.score and row.score["exact_match"])
    if row.verdict == "contradicted":
        return "Index disagreement" if right else "Hallucination"
    if right:
        return None
    return "Wrong and unverifiable" if row.verdict == "unknown" else "Wrong reading"


def failure_samples(
    rows: Sequence[Row], *, per_category: int, seed: int
) -> dict[str, tuple[int, list[Row]]]:
    """For each category of failure, how many rows are in it and a repeatable sample of them.

    A contradicted claim that agrees with the gold is an index disagreement, not a failure of
    the model, but it is listed here so that each can be checked by hand (ADR-003).
    """
    grouped: dict[str, list[Row]] = {name: [] for name in CATEGORIES}
    for row in rows:
        category = _category(row)
        if category:
            grouped[category].append(row)
    generator = random.Random(seed)
    return {
        name: (len(members), generator.sample(members, min(per_category, len(members))))
        for name, members in grouped.items()
    }


def ceiling(rows: Sequence[Row], agreement: Mapping[str, Agreement]) -> tuple[int, int]:
    """How many of the rows covered by `agreement` the index can match to the gold, and how many."""
    covered = [agreement[r.item_id] for r in rows if r.item_id in agreement]
    return sum(a.parse_matches for a in covered), len(covered)
