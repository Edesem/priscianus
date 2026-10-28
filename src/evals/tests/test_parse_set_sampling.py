from collections import Counter
from itertools import count

import pytest

from evals.gold import GoldToken
from evals.parse_set import allocate, cell_quotas, sample_items, source_label

UPOS = {"verb": "VERB", "noun": "NOUN", "adj": "ADJ", "pron_det": "PRON", "uninflected": "ADV"}
SOURCES = {
    "perseus": "phi0690.phi003.perseus-lat1.tb.xml",
    "proiel-classical": "Epistulae ad Atticum, Book 1",
    "proiel-vulgate": "Jerome's Vulgate, John 6",
    "ittb": "",
}
BAND_RANK = {"top1k": 10, "1k-10k": 2_000, "rare": None}


def make_pool(
    plan: dict[tuple[str, str, str, str], int],
) -> tuple[list[GoldToken], dict[str, int]]:
    """Tokens for {(source, class, band, _): n}, one sentence each, and the ranks to band them."""
    ids = count()
    tokens: list[GoldToken] = []
    ranks: dict[str, int] = {}
    for (source, cls, band, _), n in plan.items():
        for _ in range(n):
            i = next(ids)
            lemma = "lemma" + "".join(chr(97 + int(d)) for d in str(i))  # digits would be stripped
            if BAND_RANK[band] is not None:
                ranks[lemma] = BAND_RANK[band]
            tokens.append(
                GoldToken(
                    treebank=source.split("-")[0],
                    sent_id=f"s{i}",
                    token_id=1,
                    form=lemma,
                    lemma=lemma,
                    upos=UPOS[cls],
                    features={},
                    sentence=lemma,
                    mwt_form=None,
                    source=SOURCES[source],
                )
            )
    return tokens, ranks


def full_plan(per_cell: int) -> dict[tuple[str, str, str, str], int]:
    plan = {}
    for source in SOURCES:
        for cls in UPOS:
            for band in BAND_RANK:
                plan[(source, cls, band, "")] = per_cell
    return plan


def test_allocate_gives_the_leftover_to_the_largest_remainders():
    assert allocate(10, {"a": 0.35, "b": 0.25, "c": 0.4}) == {"a": 4, "b": 2, "c": 4}
    assert sum(allocate(500, {"a": 0.4, "b": 0.35, "c": 0.25}).values()) == 500


def test_cell_quotas_follow_adr_003_for_a_slice_of_500():
    quotas = cell_quotas(500)

    by_class = Counter()
    for (cls, _), n in quotas.items():
        by_class[cls] += n
    assert by_class == {"verb": 175, "noun": 125, "adj": 75, "pron_det": 75, "uninflected": 50}
    assert sum(quotas.values()) == 500
    assert quotas[("pron_det", None)] == 75
    assert [quotas[("noun", b)] for b in ("top1k", "1k-10k", "rare")] == [50, 44, 31]


def test_every_cell_gets_its_quota_when_there_are_enough_candidates():
    tokens, ranks = make_pool(full_plan(40))

    result = sample_items(tokens, ranks, seed=1, sizes={"test": 40, "dev": 10})

    got = Counter((i.split, i.slice) for i in result.items)
    assert got == {
        (s, sl): n for s, n in (("test", 40), ("dev", 10)) for sl in ("Classical", "Ecclesiastical")
    }
    test_classical = Counter(
        (i.pos_class, i.freq_band if i.pos_class in ("verb", "noun", "adj") else None)
        for i in result.items
        if i.split == "test" and i.slice == "Classical"
    )
    assert test_classical == cell_quotas(40)


def test_the_same_seed_gives_the_same_items_whatever_the_input_order():
    tokens, ranks = make_pool(full_plan(30))

    first = sample_items(tokens, ranks, seed=7, sizes={"test": 20, "dev": 5})
    again = sample_items(list(reversed(tokens)), ranks, seed=7, sizes={"test": 20, "dev": 5})
    other = sample_items(tokens, ranks, seed=8, sizes={"test": 20, "dev": 5})

    assert first.items == again.items
    assert first.items != other.items


def test_a_sentence_is_used_at_most_once_across_dev_and_test():
    tokens, ranks = make_pool(full_plan(30))
    # Give every token a second sentence-mate that is also a candidate.
    clones = [
        GoldToken(**{**t.__dict__, "token_id": 2, "lemma": t.lemma + "x", "form": t.lemma + "x"})
        for t in tokens
    ]
    ranks.update({t.lemma: ranks[t.lemma[:-1]] for t in clones if t.lemma[:-1] in ranks})

    result = sample_items(tokens + clones, ranks, seed=3, sizes={"test": 20, "dev": 10})

    sentences = [(i.token.treebank, i.token.sent_id) for i in result.items]
    assert len(sentences) == len(set(sentences)) == 60


def test_each_ecclesiastical_cell_is_half_vulgate_and_half_ittb():
    tokens, ranks = make_pool(full_plan(40))

    result = sample_items(tokens, ranks, seed=1, sizes={"test": 40, "dev": 0})

    verbs = Counter(
        i.token.treebank
        for i in result.items
        if i.slice == "Ecclesiastical" and i.pos_class == "verb" and i.freq_band == "top1k"
    )
    assert abs(verbs["proiel"] - verbs["ittb"]) <= 1


def test_when_one_ecclesiastical_source_runs_out_the_other_fills_the_gap():
    plan = full_plan(40)
    plan[("proiel-vulgate", "noun", "top1k", "")] = 1
    tokens, ranks = make_pool(plan)

    result = sample_items(tokens, ranks, seed=1, sizes={"test": 40, "dev": 0})

    nouns = Counter(
        i.token.treebank
        for i in result.items
        if i.slice == "Ecclesiastical" and i.pos_class == "noun" and i.freq_band == "top1k"
    )
    assert nouns["proiel"] == 1
    assert nouns["ittb"] == cell_quotas(40)[("noun", "top1k")] - 1


def test_a_short_cell_takes_all_it_has_and_the_next_more_frequent_band_makes_up_the_rest():
    plan = full_plan(40)
    plan[("ittb", "verb", "rare", "")] = 2
    plan[("proiel-vulgate", "verb", "rare", "")] = 1
    tokens, ranks = make_pool(plan)

    result = sample_items(tokens, ranks, seed=1, sizes={"test": 40, "dev": 0})

    quotas = cell_quotas(40)
    verbs = Counter(
        i.freq_band for i in result.items if i.slice == "Ecclesiastical" and i.pos_class == "verb"
    )
    assert verbs["rare"] == 3
    assert verbs["1k-10k"] == quotas[("verb", "1k-10k")] + quotas[("verb", "rare")] - 3
    assert sum(verbs.values()) == sum(v for (c, _), v in quotas.items() if c == "verb")


def test_the_result_records_candidate_counts_per_cell():
    tokens, ranks = make_pool(full_plan(5))

    result = sample_items(tokens, ranks, seed=1, sizes={"test": 4, "dev": 0})

    # Classical is Perseus plus PROIEL's Cicero and Caesar: 10 candidates in each cell.
    assert result.candidate_counts["Classical|verb|top1k"] == 10
    # Closed classes are not divided by band; their three bands count as one cell.
    assert result.candidate_counts["Ecclesiastical|pron_det|all"] == 30


def test_items_are_returned_in_a_fixed_order():
    tokens, ranks = make_pool(full_plan(30))

    items = sample_items(tokens, ranks, seed=1, sizes={"test": 20, "dev": 5}).items

    keys = [(i.split, i.token.treebank, i.token.sent_id, i.token.token_id) for i in items]
    assert keys == sorted(keys)


@pytest.mark.parametrize(
    ("treebank", "source", "label"),
    [
        ("perseus", "phi0959.phi006.perseus-lat1.tb.xml", "phi0959.phi006.perseus-lat1.tb.xml"),
        ("proiel", "Commentarii belli Gallici, Caes., Gall. 3.14", "Commentarii belli Gallici"),
        ("proiel", "Jerome's Vulgate, John 6", "Jerome's Vulgate"),
        ("ittb", "", "ittb"),
    ],
)
def test_source_label_names_the_work_not_the_passage(treebank, source, label):
    token = GoldToken(treebank, "s", 1, "f", "l", "NOUN", {}, "f", None, source)

    assert source_label(token) == label
