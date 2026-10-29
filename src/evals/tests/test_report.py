import pytest
from priscianus.morphology.lookup import Analysis

from evals.index_agreement import Agreement
from evals.report import ambiguity, breakdown, ceiling, confusions, failure_samples, headline
from evals.store import EvalStore, RunKey

KEY = RunKey("parse", "v1", "dev", "raw", "claude-haiku-5-5", "raw-parse-v3")


def gold(lemma, upos="NOUN", sentence="Sentence.", **features):
    return {"form": lemma, "lemma": lemma, "upos": upos, "features": features, "sentence": sentence}


def cost(usd=0.01, latency_ms=100, cache_hit=False):
    return {
        "model": KEY.model,
        "input_tokens": 10,
        "output_tokens": 5,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "usd": usd,
        "cache_hit": cache_hit,
        "latency_ms": latency_ms,
    }


def answer(store, run, item_id, slice, pos_class, band, gold_, *, claim, verdict, score, **extra):
    store.save_item(
        item_id,
        split="dev",
        treebank="perseus",
        sent_id=item_id,
        word_id=1,
        slice=slice,
        pos_class=pos_class,
        freq_band=band,
        gold=gold_,
    )
    store.record_response(
        run,
        item_id,
        raw_text="{}",
        format_error=None if claim else "invalid JSON",
        claim=claim,
        verdict=verdict,
        score=score,
        cost=extra.get("cost", cost()),
    )


def claim(lemma, upos="NOUN", **features):
    return {"form": lemma, "lemma": lemma, "upos": upos, "features": features}


def score(lemma=True, upos=True, **features):
    return {
        "exact_match": lemma and upos and all(features.values()),
        "lemma_match": lemma,
        "upos_match": upos,
        "features": features,
    }


@pytest.fixture
def store(tmp_path):
    """Six items. a and f are right; b has the wrong case; c is wrong and contradicted; d is
    not valid JSON; e is wrong and not in the index. f was served from the cache."""
    store = EvalStore(tmp_path / "evals.db")
    run = store.start_run(KEY, git_commit="abc")
    answer(
        store, run, "a", "Classical", "noun", "top1k",
        gold("rosa", Case="Nom", Number="Sing"),
        claim=claim("rosa", Case="Nom", Number="Sing"),
        verdict="verified",
        score=score(Case=True, Number=True),
        cost=cost(0.01, 100),
    )  # fmt: skip
    answer(
        store, run, "b", "Classical", "noun", "top1k",
        gold("rosa", Case="Nom", Number="Sing"),
        claim=claim("rosa", Case="Abl", Number="Sing"),
        verdict="ambiguous",
        score=score(Case=False, Number=True),
        cost=cost(0.02, 200),
    )  # fmt: skip
    answer(
        store, run, "c", "Classical", "verb", "rare",
        gold("amo", "VERB", Tense="Pres", Number="Sing"),
        claim=claim("amor", "VERB", Tense="Fut", Number="Sing"),
        verdict="contradicted",
        score=score(lemma=False, Tense=False, Number=True),
        cost=cost(0.03, 300),
    )  # fmt: skip
    answer(
        store, run, "d", "Ecclesiastical", "verb", "rare",
        gold("dico", "VERB", Tense="Pres"),
        claim=None, verdict=None, score=None,
        cost=cost(0.04, 400),
    )  # fmt: skip
    answer(
        store, run, "e", "Ecclesiastical", "noun", "top1k",
        gold("deus", Case="Nom"),
        claim=claim("deus2", Case="Nom"),
        verdict="unknown",
        score=score(lemma=False, Case=True),
        cost=cost(0.05, 500),
    )  # fmt: skip
    answer(
        store, run, "f", "Ecclesiastical", "noun", "top1k",
        gold("rex", Case="Nom"),
        claim=claim("rex", Case="Nom"),
        verdict="verified",
        score=score(Case=True),
        cost=cost(0.0, 0, cache_hit=True),
    )  # fmt: skip
    store.finish_run(run, "complete")
    return store


@pytest.fixture
def rows(store):
    return store.run_rows(1)


def test_exact_match_counts_a_format_failure_as_a_miss(rows):
    m = headline(rows)
    assert (m.n, m.exact) == (6, 2)  # a and f


def test_lemma_accuracy_counts_a_format_failure_as_a_miss(rows):
    assert headline(rows).lemma == 3  # a, b, f


def test_claim_rates_are_over_the_items_that_gave_a_claim(rows):
    m = headline(rows)
    assert m.claims == 5
    assert (m.verified, m.ambiguous, m.contradicted, m.unknown) == (2, 1, 1, 1)
    assert m.claim_accuracy == pytest.approx(3 / 5)
    assert m.hallucination_rate == pytest.approx(1 / 5)
    assert m.unverifiable_rate == pytest.approx(1 / 5)


def test_the_format_failure_rate_is_over_all_items(rows):
    m = headline(rows)
    assert m.format_failures == 1
    assert m.format_failure_rate == pytest.approx(1 / 6)


def test_a_feature_is_scored_over_the_answers_whose_gold_marks_it(rows):
    m = headline(rows)
    assert m.features["Case"] == (3, 4)  # a, e, f right; b wrong
    assert m.features["Number"] == (3, 3)
    assert m.features["Tense"] == (0, 1)


def test_cost_is_the_sum_and_latency_leaves_out_cache_hits(rows):
    m = headline(rows)
    assert m.usd == pytest.approx(0.15)
    assert m.latency_p50_ms == 300
    assert m.latency_p95_ms == 500


def test_a_run_with_no_answers_has_no_rates():
    m = headline([])
    assert (m.n, m.claims) == (0, 0)
    assert m.claim_accuracy is None
    assert m.latency_p50_ms is None


def test_every_metric_is_counted_again_within_a_band(rows):
    by_band = breakdown(rows, "freq_band")
    assert {band: m.n for band, m in by_band.items()} == {"top1k": 4, "rare": 2}
    assert by_band["top1k"].exact == 2
    assert by_band["rare"].format_failures == 1


def test_a_breakdown_by_pos_class_and_slice_shows_item_counts(rows):
    assert {k: m.n for k, m in breakdown(rows, "pos_class").items()} == {"noun": 4, "verb": 2}
    assert {k: m.n for k, m in breakdown(rows, "slice").items()} == {
        "Classical": 3,
        "Ecclesiastical": 3,
    }


class FakeIndex:
    """*rosa* is nominative or ablative, *rex* only nominative; the rest are not in it."""

    def analyse(self, form):
        def reading(case):
            return Analysis(form, form, "noun", form, {"Case": case, "Number": "Sing"})

        return {"rosa": [reading("Nom"), reading("Abl")], "rex": [reading("Nom")]}.get(form, [])

    def has_lemma(self, lemma):
        return lemma in {"rosa", "rex"}


def test_ambiguity_handling_asks_if_the_model_picked_the_gold_reading(rows):
    result = ambiguity(rows, FakeIndex())
    assert (result.ambiguous, result.ambiguous_right) == (2, 1)  # a right, b wrong
    assert (result.single, result.single_right) == (1, 1)  # f


def test_ambiguity_handling_skips_a_form_the_gold_leaves_open(store):
    run = store.start_run(KEY._replace(split="test"), git_commit="x")
    answer(
        store, run, "g", "Classical", "noun", "top1k",
        gold("rosa", Case="Nom,Acc", Number="Sing"),
        claim=claim("rosa", Case="Nom", Number="Sing"),
        verdict="ambiguous",
        score=score(Case=True, Number=True),
    )  # fmt: skip
    assert ambiguity(store.run_rows(run), FakeIndex()).ambiguous == 0


def test_the_feature_confusions_are_the_wrong_values_most_given(rows):
    assert confusions(rows) == [("Case", "Nom", "Abl", 1), ("Tense", "Pres", "Fut", 1)]


def test_a_missing_feature_is_a_confusion_with_none(store):
    run = store.start_run(KEY._replace(split="test"), git_commit="x")
    answer(
        store, run, "g", "Classical", "noun", "top1k",
        gold("rosa", Case="Nom"),
        claim=claim("rosa"),
        verdict="ambiguous",
        score=score(Case=False),
    )  # fmt: skip
    assert confusions(store.run_rows(run)) == [("Case", "Nom", "(none)", 1)]


def test_failures_are_sorted_into_the_categories_of_adr_003(rows):
    samples = failure_samples(rows, per_category=5, seed=0)
    assert {
        name: (total, [r.item_id for r in sample]) for name, (total, sample) in samples.items()
    } == {
        "Format failure": (1, ["d"]),
        "Hallucination": (1, ["c"]),
        "Index disagreement": (0, []),
        "Wrong reading": (1, ["b"]),
        "Wrong and unverifiable": (1, ["e"]),
    }


def test_a_category_is_sampled_down_to_the_size_asked_for_and_repeatably(store):
    run = store.start_run(KEY._replace(split="test"), git_commit="x")
    for i in range(10):
        answer(
            store, run, f"w{i}", "Classical", "noun", "top1k",
            gold("rosa", Case="Nom"),
            claim=claim("rosa", Case="Abl"),
            verdict="verified",
            score=score(Case=False),
        )  # fmt: skip
    rows = store.run_rows(run)
    total, sample = failure_samples(rows, per_category=3, seed=1)["Wrong reading"]
    assert (total, len(sample)) == (10, 3)
    again = failure_samples(rows, per_category=3, seed=1)["Wrong reading"][1]
    assert [r.item_id for r in again] == [r.item_id for r in sample]


def test_an_index_disagreement_is_a_contradiction_the_gold_would_not_make(store):
    run = store.start_run(KEY._replace(split="test"), git_commit="x")
    answer(
        store, run, "g", "Classical", "noun", "top1k",
        gold("rosa", Case="Nom"),
        claim=claim("rosa", Case="Nom"),
        verdict="contradicted",
        score=score(Case=True),
    )  # fmt: skip
    total, sample = failure_samples(store.run_rows(run), per_category=5, seed=0)[
        "Index disagreement"
    ]
    assert (total, [r.item_id for r in sample]) == (1, ["g"])


def test_the_ceiling_is_how_many_of_the_items_the_index_can_match(rows):
    by_item = {
        "a": Agreement(True, True, True),
        "b": Agreement(True, True, True),
        "c": Agreement(True, True, False),
        "d": Agreement(False, False, False),
        "e": Agreement(True, False, False),
        # no entry for f: it is not in the parse set this was computed on
    }
    assert ceiling(rows, by_item) == (2, 5)
