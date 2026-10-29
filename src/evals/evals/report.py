"""Turn the runs in the eval store into numbers and failure examples for a markdown report."""

import math
import random
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from priscianus.morphology.canonical import canonicalise
from priscianus.morphology.lookup import Analysis
from priscianus.verifier.classify import Claim, Verdict, classify
from priscianus.verifier.index import MorphologyIndex

from evals.index_agreement import Agreement
from evals.store import Row, RunInfo


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
        wanted = canonicalise(row.gold["features"])
        given = canonicalise(row.claim["features"])
        for name, right in row.score["features"].items():
            if not right:
                counts[(name, wanted[name], given.get(name, "(none)"))] += 1
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


_DIMENSIONS = (
    ("Frequency band", "freq_band"),
    ("POS class", "pos_class"),
    ("Classical / Ecclesiastical", "slice"),
)
_MAX_READINGS = 8
_MAX_RAW = 200


def _pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f}% ({part}/{whole})" if whole else "–"


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    return [
        "| " + " | ".join(header) + " |",
        "|" + "|".join("---" if i == 0 else "---:" for i in range(len(header))) + "|",
        *("| " + " | ".join(row) + " |" for row in rows),
        "",
    ]


def _features(features: Mapping[str, str]) -> str:
    return "|".join(f"{name}={value}" for name, value in sorted(features.items())) or "–"


def _readings(analyses: Sequence[Analysis]) -> str:
    seen = dict.fromkeys(f"{a.lemma} {a.pos} {_features(a.features)}" for a in analyses)
    shown = list(seen)[:_MAX_READINGS]
    more = f"; … and {len(seen) - len(shown)} more" if len(seen) > len(shown) else ""
    return "; ".join(shown) + more if shown else "none"


def _headline_rows(
    columns: Sequence[tuple[Headline, tuple[int, int] | None]],
) -> list[list[str]]:
    def row(label: str, count: Callable[[Headline], str]) -> list[str]:
        return [label, *(count(h) for h, _ in columns)]

    rows = [
        row("Items", lambda h: str(h.n)),
        row("Parse exact match", lambda h: _pct(h.exact, h.n)),
        row("Lemma accuracy", lambda h: _pct(h.lemma, h.n)),
        row("Claim accuracy", lambda h: _pct(h.verified + h.ambiguous, h.claims)),
        row("Hallucination rate", lambda h: _pct(h.contradicted, h.claims)),
        row("Unverifiable rate", lambda h: _pct(h.unknown, h.claims)),
        row("Schema-failure rate", lambda h: _pct(h.format_failures, h.n)),
    ]
    if any(ceil for _, ceil in columns):
        rows.insert(
            2,
            [
                "Index matches gold (ceiling)",
                *(_pct(*ceil) if ceil else "–" for _, ceil in columns),
            ],
        )
    rows.append(row("Cost", lambda h: f"${h.usd:.4f}"))
    rows.append(
        row(
            "Latency p50 / p95",
            lambda h: (
                "–" if h.latency_p50_ms is None else f"{h.latency_p50_ms} / {h.latency_p95_ms} ms"
            ),
        )
    )
    return rows


def _group_rows(groups: Mapping[str, Headline]) -> list[list[str]]:
    return [
        [
            name,
            str(h.n),
            _pct(h.exact, h.n),
            _pct(h.lemma, h.n),
            _pct(h.verified + h.ambiguous, h.claims),
            _pct(h.contradicted, h.claims),
            _pct(h.unknown, h.claims),
            _pct(h.format_failures, h.n),
        ]
        for name, h in groups.items()
    ]


def _example(row: Row, index: MorphologyIndex) -> list[str]:
    gold = row.gold
    lines = [
        f"- **{row.item_id}** — {gold.get('sentence') or '(sentence not stored)'}",
        f"  - form: {gold['form']}",
        f"  - gold: {gold['lemma']} {gold['upos']} {_features(gold['features'])}",
    ]
    if row.claim:
        claim = row.claim
        lines.append(
            f"  - model: {claim['lemma']} {claim['upos']} {_features(claim['features'])}"
            + (f" ({row.verdict})" if row.verdict else "")
        )
    else:
        lines.append(f"  - model: {row.format_error}: {row.raw_text[:_MAX_RAW]!r}")
    lines.append(f"  - index: {_readings(index.analyse(gold['form']))}")
    return lines


def render_report(
    runs: Sequence[tuple[RunInfo, Sequence[Row]]],
    index: MorphologyIndex,
    *,
    agreement: Mapping[str, Agreement] | None = None,
    per_category: int = 5,
    seed: int = 0,
) -> str:
    """Write the markdown report for `runs`, side by side in the headline tables.

    `agreement` is the index-vs-gold result for the parse set (#40), shown as the ceiling on
    exact match. The failure examples need the sentence, which the store keeps with the gold,
    so the report is for the author; a committed one cites item IDs only (ADR-003).
    """
    out = ["# Eval report", ""]
    out.append(
        "The numbers are averages over a stratified sample that overweights rare lemmas and "
        "verbs compared with running text (ADR-003). Claim rates are over the items that gave "
        "a claim; exact match, lemma accuracy and the schema-failure rate are over all items; "
        "per-feature accuracy is over the answers whose gold marks the feature."
    )
    out.append("")
    heads = [headline(rows) for _, rows in runs]
    ceilings = [ceiling(rows, agreement) if agreement is not None else None for _, rows in runs]
    names = [f"#{info.run_id} {info.model} {info.split}" for info, _ in runs]
    for info, _ in runs:
        out.append(
            f"- Run {info.run_id}: {info.model}, {info.mode} mode, split {info.split}, "
            f"{info.set_name}-{info.manifest_version}, prompt {info.prompt_id}, {info.status}"
        )
    out += ["", "## Headline", ""]
    out += _table(["Metric", *names], _headline_rows(list(zip(heads, ceilings, strict=True))))
    feature_names = sorted({name for h in heads for name in h.features})
    out += ["## Accuracy by feature", ""]
    out += _table(
        ["Feature", *names],
        [
            [f, *(_pct(*h.features[f]) if f in h.features else "–" for h in heads)]
            for f in feature_names
        ],
    )
    for info, rows in runs:
        out += [f"## Run {info.run_id}: {info.model} on {info.split}", ""]
        for title, dimension in _DIMENSIONS:
            out += [f"### By {title.lower()}", ""]
            out += _table(
                [
                    title,
                    "Items",
                    "Exact",
                    "Lemma",
                    "Claim acc.",
                    "Halluc.",
                    "Unverif.",
                    "Schema fail",
                ],
                _group_rows(breakdown(rows, dimension)),
            )
        result = ambiguity(rows, index)
        out += ["### Ambiguity handling", ""]
        out += _table(
            ["Gold reading in the index", "Exact match"],
            [
                ["Ambiguous forms", _pct(result.ambiguous_right, result.ambiguous)],
                ["Single-reading forms", _pct(result.single_right, result.single)],
            ],
        )
        out += ["### Feature confusions", ""]
        out += _table(
            ["Feature: gold → given", "Items"],
            [[f"{name}: {gold} → {given}", str(n)] for name, gold, given, n in confusions(rows)],
        )
        out += ["### Failure examples", ""]
        for category, (total, sample) in failure_samples(
            rows, per_category=per_category, seed=seed
        ).items():
            out += [f"#### {category} ({total})", ""]
            for row in sample:
                out += _example(row, index)
            out.append("")
    return "\n".join(out).rstrip() + "\n"
