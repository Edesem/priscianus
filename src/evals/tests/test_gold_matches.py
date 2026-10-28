import pytest
from priscianus.morphology.lookup import Analysis

from evals.gold import GoldToken, UnknownFeatureError, matches


def gold(lemma: str, upos: str, features: dict[str, str], form: str = "x") -> GoldToken:
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


def analysis(lemma: str, pos: str, features: dict[str, str], deponent: bool = False) -> Analysis:
    return Analysis(
        lemma=lemma,
        lemma_display=lemma,
        pos=pos,
        form="x",
        features=features,
        deponent=deponent,
    )


def test_agrees_on_lemma_and_every_gold_feature():
    token = gold("rosa", "NOUN", {"Case": "Abl", "Number": "Sing", "Gender": "Fem"})

    assert matches(token, analysis("rosa", "noun", {"Case": "Abl", "Number": "Sing"}))


def test_different_lemma_does_not_match():
    token = gold("rosa", "NOUN", {"Case": "Abl", "Number": "Sing"})

    assert not matches(token, analysis("rota", "noun", {"Case": "Abl", "Number": "Sing"}))


def test_different_feature_value_does_not_match():
    token = gold("rosa", "NOUN", {"Case": "Abl", "Number": "Sing"})

    assert not matches(token, analysis("rosa", "noun", {"Case": "Nom", "Number": "Sing"}))


def test_feature_the_index_lacks_does_not_match():
    token = gold("rosa", "NOUN", {"Case": "Abl", "Number": "Sing"})

    assert not matches(token, analysis("rosa", "noun", {"Case": "Abl"}))


def test_feature_the_gold_does_not_mark_is_ignored():
    token = gold("rosa", "NOUN", {"Case": "Abl"})

    assert matches(token, analysis("rosa", "noun", {"Case": "Abl", "Number": "Sing"}))


def test_features_outside_the_compared_subset_are_ignored():
    token = gold("ego", "PRON", {"Case": "Abl", "PronType": "Prs", "InflClass": "LatPron"})

    assert matches(token, analysis("ego", "pron", {"Case": "Abl"}))


def test_unknown_gold_feature_value_raises():
    token = gold("rosa", "NOUN", {"Case": "Ess"})

    with pytest.raises(UnknownFeatureError):
        matches(token, analysis("rosa", "noun", {"Case": "Abl"}))


@pytest.mark.parametrize("gold_lemma", ["vinco", "Vinco", "uinco"])
def test_lemmas_are_compared_on_the_loose_key(gold_lemma: str):
    assert matches(gold(gold_lemma, "VERB", {}), analysis("uinco", "verb", {}))


def test_homograph_number_on_the_gold_lemma_is_ignored():
    assert matches(gold("sum1", "AUX", {}), analysis("sum", "verb", {}))


def test_perseus_lemma_with_a_stray_comma_matches():
    assert matches(gold("uterque,", "ADJ", {}), analysis("uterque", "adj", {}))


@pytest.mark.parametrize("index_lemma", ["dextra", "dextera"])
def test_proiel_optional_letters_in_brackets_match_with_or_without(index_lemma: str):
    assert matches(gold("dext(e)ra", "ADJ", {}), analysis(index_lemma, "adj", {}))


def test_proiel_initial_optional_letter_matches_both_spellings():
    assert matches(gold("(h)arena", "NOUN", {}), analysis("arena", "noun", {}))
    assert matches(gold("(h)arena", "NOUN", {}), analysis("harena", "noun", {}))


def test_ittb_multiword_lemma_matches_only_itself():
    assert matches(gold("in+quantum", "SCONJ", {}), analysis("in+quantum", "conj", {}))
    assert not matches(gold("in+quantum", "SCONJ", {}), analysis("in", "prep", {}))


def test_perseus_aspect_on_a_present_does_not_count():
    perseus = gold(
        "maneo",
        "VERB",
        {"Aspect": "Imp", "Mood": "Ind", "Tense": "Pres", "VerbForm": "Fin", "Voice": "Act"},
    )
    index = analysis(
        "maneo", "verb", {"Mood": "Ind", "Tense": "Pres", "VerbForm": "Fin", "Voice": "Act"}
    )

    assert matches(perseus, index)


def test_imperfect_is_still_told_from_the_perfect():
    imperfect = gold("amo", "VERB", {"Tense": "Past", "Aspect": "Imp"})

    assert not matches(imperfect, analysis("amo", "verb", {"Tense": "Past", "Aspect": "Perf"}))


def test_perseus_gerundive_matches_the_index_participle():
    perseus = gold("amo", "VERB", {"VerbForm": "Part", "Aspect": "Prosp", "Voice": "Pass"})
    index = analysis("amo", "verb", {"VerbForm": "Part", "Tense": "Fut", "Voice": "Pass"})

    assert matches(perseus, index)


def test_absolute_degree_matches_the_index_superlative():
    token = gold("altus", "ADJ", {"Degree": "Abs"})

    assert matches(token, analysis("altus", "adj", {"Degree": "Sup"}))


def test_any_member_of_a_multi_valued_gold_feature_matches():
    token = gold("felix", "ADJ", {"Gender": "Fem,Masc"})

    assert matches(token, analysis("felix", "adj", {"Gender": "Masc"}))
    assert matches(token, analysis("felix", "adj", {"Gender": "Fem"}))
    assert not matches(token, analysis("felix", "adj", {"Gender": "Neut"}))


def test_gender_is_not_compared_on_nouns():
    token = gold("rosa", "NOUN", {"Case": "Abl", "Gender": "Fem"})

    assert matches(token, analysis("rosa", "noun", {"Case": "Abl"}))


def test_gender_is_compared_on_adjectives():
    token = gold("bonus", "ADJ", {"Case": "Abl", "Gender": "Fem"})

    assert not matches(token, analysis("bonus", "adj", {"Case": "Abl", "Gender": "Masc"}))


def test_voice_is_not_compared_on_deponents():
    token = gold("loquor", "VERB", {"Mood": "Ind", "Voice": "Pass"})

    assert matches(
        token, analysis("loquor", "verb", {"Mood": "Ind", "Voice": "Act"}, deponent=True)
    )


def test_voice_is_not_compared_on_semi_deponents_whose_lemma_does_not_end_in_or():
    token = gold("audeo", "VERB", {"Mood": "Ind", "Voice": "Pass"})

    assert matches(token, analysis("audeo", "verb", {"Mood": "Ind", "Voice": "Act"}, deponent=True))


def test_the_index_flag_decides_not_the_lemma_ending():
    token = gold("ruor", "VERB", {"Mood": "Ind", "Voice": "Pass"})

    assert not matches(token, analysis("ruor", "verb", {"Mood": "Ind", "Voice": "Act"}))


def test_voice_is_compared_on_other_verbs():
    token = gold("amo", "VERB", {"Mood": "Ind", "Voice": "Pass"})

    assert not matches(token, analysis("amo", "verb", {"Mood": "Ind", "Voice": "Act"}))
