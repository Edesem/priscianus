import pytest
from priscianus.morphology.lookup import Analysis

from evals.index_agreement import Agreement
from evals.report import (
    ambiguity,
    breakdown,
    ceiling,
    confusions,
    failure_samples,
    headline,
    render_report,
)
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


def report(store, *runs, **kwargs):
    return render_report(
        [(store.run_info(r), store.run_rows(r)) for r in runs], FakeIndex(), **kwargs
    )


def line_with(text, start):
    return next(line for line in text.splitlines() if line.startswith(start))


def test_a_run_info_says_what_was_run(store):
    info = store.run_info(1)
    assert (info.run_id, info.model, info.split, info.manifest_version, info.prompt_id) == (
        1,
        "claude-haiku-5-5",
        "dev",
        "v1",
        "raw-parse-v3",
    )
    assert info.status == "complete"


def test_asking_for_a_run_that_does_not_exist_is_an_error(store):
    with pytest.raises(KeyError):
        store.run_info(99)


def test_the_report_gives_each_headline_metric_with_its_counts(store):
    text = report(store, 1)
    assert "33.3% (2/6)" in line_with(text, "| Parse exact match")
    assert "50.0% (3/6)" in line_with(text, "| Lemma accuracy")
    assert "60.0% (3/5)" in line_with(text, "| Claim accuracy")
    assert "20.0% (1/5)" in line_with(text, "| Hallucination rate")
    assert "20.0% (1/5)" in line_with(text, "| Unverifiable rate")
    assert "16.7% (1/6)" in line_with(text, "| Schema-failure rate")
    assert "$0.1500" in line_with(text, "| Cost")
    assert "300 / 500 ms" in line_with(text, "| Latency p50 / p95")


def test_the_report_says_which_split_and_prompt_it_used(store):
    text = report(store, 1)
    assert "dev" in text and "raw-parse-v3" in text and "claude-haiku-5-5" in text


def test_several_runs_are_side_by_side_in_one_table(store):
    second = store.start_run(KEY._replace(model="claude-sonnet-5-5"), git_commit="x")
    answer(
        store, second, "a", "Classical", "noun", "top1k",
        gold("rosa", Case="Nom", Number="Sing"),
        claim=claim("rosa", Case="Nom", Number="Sing"),
        verdict="verified",
        score=score(Case=True, Number=True),
    )  # fmt: skip
    row = line_with(report(store, 1, second), "| Parse exact match")
    assert "33.3% (2/6)" in row and "100.0% (1/1)" in row


def test_each_breakdown_shows_the_item_count_of_its_cells(store):
    text = report(store, 1)
    assert "| rare | 2 |" in text
    assert "| Ecclesiastical | 3 |" in text
    assert "| verb | 2 |" in text


def test_the_index_ceiling_is_shown_beside_exact_match(store):
    agreement = {"a": Agreement(True, True, True), "b": Agreement(True, True, False)}
    text = report(store, 1, agreement=agreement)
    assert "50.0% (1/2)" in line_with(text, "| Index matches gold (ceiling)")
    assert "Index matches gold" not in report(store, 1)


def test_ambiguity_handling_is_reported(store):
    text = report(store, 1)
    assert "50.0% (1/2)" in line_with(text, "| Ambiguous forms")
    assert "100.0% (1/1)" in line_with(text, "| Single-reading forms")


def test_the_feature_confusions_are_listed(store):
    assert "Case: Nom → Abl | 1" in report(store, 1)


def test_a_failure_example_shows_sentence_form_gold_answer_and_index_readings(store):
    text = report(store, 1)
    wrong_reading = text.split("### Wrong reading")[1].split("###")[0]
    assert "Sentence." in wrong_reading
    assert "rosa" in wrong_reading
    assert "gold: rosa NOUN Case=Nom|Number=Sing" in wrong_reading
    assert "model: rosa NOUN Case=Abl|Number=Sing" in wrong_reading
    assert "Case=Nom|Number=Sing" in wrong_reading.split("index:")[1]
    assert "Case=Abl|Number=Sing" in wrong_reading.split("index:")[1]


def test_a_format_failure_shows_what_the_model_sent(store):
    failure = report(store, 1).split("### Format failure")[1].split("###")[0]
    assert "invalid JSON" in failure


def test_an_empty_category_is_still_listed_with_its_count(store):
    assert "### Index disagreement (0)" in report(store, 1)


def test_the_report_says_its_numbers_are_over_a_stratified_sample(store):
    assert "stratified sample" in report(store, 1)


def test_a_participle_wrong_in_tense_is_a_confusion_whose_gold_marks_aspect(store):
    run = store.start_run(KEY._replace(split="test"), git_commit="x")
    answer(
        store, run, "g", "Classical", "verb", "top1k",
        gold("amo", "VERB", VerbForm="Part", Aspect="Perf"),
        claim=claim("amo", "VERB", VerbForm="Part", Tense="Pres"),
        verdict="verified",
        score=score(Tense=False, VerbForm=True),
    )  # fmt: skip
    assert confusions(store.run_rows(run)) == [("Tense", "Past", "Pres", 1)]
