import pytest

from evals.gold import GoldToken
from evals.parse_set import band_for_rank, frequency_ranks, rank_of


def word(lemma: str, *, upos: str = "NOUN", treebank: str = "perseus") -> GoldToken:
    return GoldToken(
        treebank=treebank,
        sent_id="s",
        token_id=1,
        form=lemma,
        lemma=lemma,
        upos=upos,
        features={},
        sentence=lemma,
        mwt_form=None,
    )


def test_ranks_average_each_treebanks_relative_frequency_not_raw_counts():
    big = [word("rosa")] * 99 + [word("lupus")]
    small = [word("lupus")] * 2

    ranks = frequency_ranks({"ittb": big, "perseus": small})

    # rosa: (0.99 + 0) / 2 = 0.495; lupus: (0.01 + 1) / 2 = 0.505. Raw counts would say rosa.
    assert ranks == {"lupus": 1, "rosa": 2}


def test_words_that_cannot_be_sampled_are_not_counted():
    tokens = [word("rosa"), word(",", upos="PUNCT"), word("Roma", upos="PROPN")]

    assert frequency_ranks({"perseus": tokens}) == {"rosa": 1}


def test_a_homograph_number_and_case_do_not_split_a_lemma():
    tokens = [word("sum1", upos="AUX"), word("sum", upos="AUX"), word("rosa")]

    assert frequency_ranks({"perseus": tokens}) == {"sum": 1, "rosa": 2}


def test_equal_frequencies_are_ranked_alphabetically():
    tokens = [word("rosa"), word("lupus")]

    assert frequency_ranks({"perseus": tokens}) == {"lupus": 1, "rosa": 2}


@pytest.mark.parametrize(
    ("rank", "expected"),
    [
        (1, "top1k"),
        (1000, "top1k"),
        (1001, "1k-10k"),
        (10000, "1k-10k"),
        (10001, "rare"),
        (None, "rare"),
    ],
)
def test_band_boundaries(rank, expected):
    assert band_for_rank(rank) == expected


def test_a_gold_lemma_takes_its_best_rank_over_the_spellings_it_may_have():
    ranks = {"dextera": 7, "dextra": 3}

    assert rank_of(ranks, "dext(e)ra") == 3
    assert rank_of(ranks, "ignotus") is None
