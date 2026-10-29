import pytest

from evals.report import headline
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
