from priscianus.morphology.lookup import Analysis

from evals.gold import GoldToken
from evals.index_agreement import evaluate
from evals.parse_set import Item


def test_evaluate_pairs_each_item_with_its_agreement():
    token = GoldToken(
        treebank="perseus",
        sent_id="s",
        token_id=1,
        form="rosa",
        lemma="rosa",
        upos="NOUN",
        features={"Case": "Nom"},
        sentence="x",
        mwt_form=None,
    )
    item = Item(
        split="test",
        token=token,
        slice="Classical",
        source="perseus",
        pos_class="noun",
        freq_band="top1k",
    )
    found = [
        Analysis(
            lemma="rosa", lemma_display="rosa", pos="noun", form="rosa", features={"Case": "Nom"}
        )
    ]

    [(got, agreement)] = evaluate([item], lambda form: found if form == "rosa" else [])

    assert got is item
    assert agreement.parse_matches
