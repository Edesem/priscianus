from evals.gold import GoldToken
from evals.raw_prompt import Claim
from evals.score import score_claim


def gold(upos="NOUN", lemma="puella", **features):
    return GoldToken("perseus", "s1", 1, "puellae", lemma, upos, features, "puellae canunt", None)


def test_a_claim_that_matches_the_gold_is_an_exact_match():
    score = score_claim(
        gold(Case="Gen", Number="Sing", Gender="Fem"),
        Claim("puella", "NOUN", {"Case": "Gen", "Number": "Sing", "Gender": "Fem"}),
    )
    assert score.exact_match
    assert score.lemma_match
    assert score.upos_match
    assert score.features == {"Case": True, "Number": True, "Gender": True}


def test_a_wrong_feature_value_fails_that_feature_only():
    score = score_claim(
        gold(Case="Gen", Number="Sing"), Claim("puella", "NOUN", {"Case": "Dat", "Number": "Sing"})
    )
    assert score.features == {"Case": False, "Number": True}
    assert not score.exact_match
    assert score.lemma_match


def test_a_feature_the_gold_marks_and_the_model_omits_is_an_error():
    score = score_claim(gold(Case="Gen", Number="Sing"), Claim("puella", "NOUN", {"Case": "Gen"}))
    assert score.features == {"Case": True, "Number": False}


def test_a_feature_the_gold_does_not_mark_is_ignored():
    score = score_claim(
        gold(Case="Gen"), Claim("puella", "NOUN", {"Case": "Gen", "Number": "Sing"})
    )
    assert score.features == {"Case": True}
    assert score.exact_match


def test_any_member_of_a_multi_valued_gold_feature_matches():
    score = score_claim(gold(Gender="Fem,Masc"), Claim("puella", "NOUN", {"Gender": "Masc"}))
    assert score.features == {"Gender": True}


def test_features_are_compared_in_canonical_form():
    # Perseus marks the imperfect with Aspect=Imp on a present-looking tense; both sides are
    # canonicalised before the comparison.
    score = score_claim(
        gold("VERB", "amo", Tense="Pres", Aspect="Imp", Mood="Ind"),
        Claim("amo", "VERB", {"Tense": "Pres", "Mood": "Ind"}),
    )
    assert score.features == {"Tense": True, "Mood": True}


def test_verb_and_aux_are_one_class():
    score = score_claim(gold("AUX", "sum"), Claim("sum", "VERB", {}))
    assert score.upos_match


def test_different_classes_do_not_match():
    assert not score_claim(gold("NOUN"), Claim("puella", "ADJ", {})).upos_match


def test_a_lemma_is_compared_by_loose_key_and_treebank_quirks():
    score = score_claim(gold(lemma="dext(e)ra"), Claim("dextra", "NOUN", {}))
    assert score.lemma_match


def test_a_wrong_lemma_is_no_match():
    assert not score_claim(gold(), Claim("puer", "NOUN", {})).lemma_match


def test_voice_is_not_compared_on_a_deponent():
    score = score_claim(
        gold("VERB", "loquor", Voice="Pass", Mood="Ind"),
        Claim("loquor", "VERB", {"Voice": "Act", "Mood": "Ind"}),
        deponent=True,
    )
    assert score.features == {"Mood": True}
    assert score.exact_match


def test_unknown_gold_feature_raises():
    import pytest

    from evals.gold import UnknownFeatureError

    with pytest.raises(UnknownFeatureError):
        score_claim(gold(Weird="X"), Claim("puella", "NOUN", {}))


def test_a_lemma_spelt_with_an_assimilated_prefix_matches_its_variant():
    score = score_claim(gold(lemma="adfirmo"), Claim("affirmo", "NOUN", {}))
    assert score.lemma_match
