from evals.gold import GoldToken
from evals.index_agreement import Agreement, Rates, breakdown
from evals.parse_set import Item

FULL = Agreement(in_index=True, lemma_found=True, parse_matches=True)
LEMMA_ONLY = Agreement(in_index=True, lemma_found=True, parse_matches=False)
ABSENT = Agreement(in_index=False, lemma_found=False, parse_matches=False)


def item(treebank: str, pos_class: str, freq_band: str, slice_name: str) -> Item:
    token = GoldToken(
        treebank=treebank,
        sent_id="s",
        token_id=1,
        form="x",
        lemma="x",
        upos="NOUN",
        features={},
        sentence="x",
        mwt_form=None,
    )
    return Item(
        split="test",
        token=token,
        slice=slice_name,
        source=treebank,
        pos_class=pos_class,
        freq_band=freq_band,
    )


def test_breakdown_counts_each_level_per_group_and_dimension():
    results = [
        (item("perseus", "noun", "top1k", "Classical"), FULL),
        (item("perseus", "verb", "rare", "Classical"), LEMMA_ONLY),
        (item("ittb", "noun", "top1k", "Ecclesiastical"), ABSENT),
        (item("ittb", "noun", "rare", "Ecclesiastical"), FULL),
    ]

    by_treebank = breakdown(results, "treebank")

    assert by_treebank == {
        "perseus": Rates(n=2, in_index=2, lemma_found=2, parse_matches=1),
        "ittb": Rates(n=2, in_index=1, lemma_found=1, parse_matches=1),
    }
    # The other groupings use the same counting.
    assert set(breakdown(results, "pos_class")) == {"noun", "verb"}
    assert set(breakdown(results, "freq_band")) == {"top1k", "rare"}
    assert breakdown(results, "slice")["Ecclesiastical"].parse_matches == 1
