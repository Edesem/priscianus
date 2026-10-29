from evals.gold import GoldToken
from evals.index_agreement import Agreement, render_report, sample_disagreements
from evals.parse_set import Item

FULL = Agreement(in_index=True, lemma_found=True, parse_matches=True)
ABSENT = Agreement(in_index=False, lemma_found=False, parse_matches=False)
LEMMA_ONLY = Agreement(in_index=True, lemma_found=True, parse_matches=False)


def item(n: int, pos_class: str = "noun") -> Item:
    token = GoldToken(
        treebank="perseus",
        sent_id="s",
        token_id=n,
        form=f"f{n}",
        lemma="x",
        upos="NOUN",
        features={},
        sentence="x",
        mwt_form=None,
    )
    return Item(
        split="test",
        token=token,
        slice="Classical",
        source="perseus",
        pos_class=pos_class,
        freq_band="top1k",
    )


def test_sample_takes_only_disagreements_and_is_repeatable():
    results = [(item(n), ABSENT if n % 2 else FULL) for n in range(20)]

    first = sample_disagreements(results, k=4, seed=40)
    again = sample_disagreements(results, k=4, seed=40)

    assert [i.token.token_id for i, _ in first] == [i.token.token_id for i, _ in again]
    assert len(first) == 4
    assert all(not a.parse_matches for _, a in first)


def test_sample_keeps_every_disagreement_when_fewer_than_k():
    results = [(item(1), ABSENT), (item(2), FULL)]

    assert len(sample_disagreements(results, k=10, seed=40)) == 1


def test_report_gives_the_ceiling_and_a_table_per_dimension():
    results = [(item(1), FULL), (item(2), LEMMA_ONLY), (item(3), ABSENT), (item(4), FULL)]

    report = render_report(results)

    assert "Ceiling: 50.0%" in report
    for heading in ("Treebank", "POS class", "Frequency band", "Classical / Ecclesiastical"):
        assert f"### {heading}" in report
    assert "| perseus | 4 | 75.0% | 75.0% | 50.0% |" in report


def test_report_gives_a_second_ceiling_without_uninflected_words():
    results = [
        (item(1), FULL),
        (item(2), ABSENT),
        (item(3, "uninflected"), ABSENT),
        (item(4, "uninflected"), ABSENT),
    ]

    report = render_report(results)

    assert "Ceiling: 25.0% of 4 items." in report
    assert "Ceiling on inflected classes: 50.0% of 2 items." in report


def test_report_counts_the_items_that_match_only_through_a_variant_spelling():
    via_variant = Agreement(in_index=True, lemma_found=True, parse_matches=True, variant=True)
    results = [(item(0), FULL), (item(1), via_variant), (item(2), ABSENT), (item(3), ABSENT)]

    report = render_report(results)

    assert "Ceiling: 50.0% of 4 items." in report
    assert "1 items match only through a variant spelling" in report
    assert "without the fallback it is 25.0%" in report
