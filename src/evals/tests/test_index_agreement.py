from priscianus.morphology.lookup import Analysis
from priscianus.morphology.normaliser import key_loose

from evals.gold import GoldToken
from evals.index_agreement import Agreement, check_token


def gold(form: str, lemma: str, upos: str, features: dict[str, str]) -> GoldToken:
    return GoldToken(
        treebank="t",
        sent_id="s1",
        token_id=1,
        form=form,
        lemma=lemma,
        upos=upos,
        features=features,
        sentence="x",
        mwt_form=None,
    )


def analysis(
    lemma: str, pos: str, features: dict[str, str], base_lemma: str | None = None
) -> Analysis:
    return Analysis(
        lemma=lemma,
        lemma_display=lemma,
        pos=pos,
        form="x",
        features=features,
        base_lemma=base_lemma,
    )


def test_form_absent_from_index_is_a_gap_at_every_level():
    token = gold("rosis", "rosa", "NOUN", {"Case": "Abl", "Number": "Plur"})

    assert check_token(token, lambda form: []) == Agreement(
        in_index=False, lemma_found=False, parse_matches=False
    )


def test_form_and_lemma_present_but_features_differ():
    token = gold("rosis", "rosa", "NOUN", {"Case": "Abl", "Number": "Plur"})
    found = [analysis("rosa", "noun", {"Case": "Dat", "Number": "Plur"})]

    assert check_token(token, lambda form: found) == Agreement(
        in_index=True, lemma_found=True, parse_matches=False
    )


def test_form_present_under_another_lemma_only():
    token = gold("rosis", "rosa", "NOUN", {"Case": "Abl", "Number": "Plur"})
    found = [analysis("ros", "noun", {"Case": "Abl", "Number": "Plur"})]

    assert check_token(token, lambda form: found) == Agreement(
        in_index=True, lemma_found=False, parse_matches=False
    )


def test_matching_analysis_agrees_at_every_level():
    token = gold("rosis", "rosa", "NOUN", {"Case": "Abl", "Number": "Plur"})
    found = [analysis("rosa", "noun", {"Case": "Abl", "Number": "Plur"})]

    assert check_token(token, lambda form: found) == Agreement(
        in_index=True, lemma_found=True, parse_matches=True
    )


def test_participle_linked_to_its_verb_agrees_at_the_lemma_level():
    token = gold("paventes", "paveo", "VERB", {"Case": "Acc", "VerbForm": "Part", "Tense": "Pres"})
    found = [
        analysis(
            "pavens", "verb", {"Case": "Acc", "VerbForm": "Part"}, base_lemma=key_loose("paveo")
        )
    ]

    assert check_token(token, lambda form: found) == Agreement(
        in_index=True, lemma_found=True, parse_matches=False
    )
