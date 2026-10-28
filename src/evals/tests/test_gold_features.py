import pytest

from evals.gold import UnknownFeatureError, map_features


def test_keeps_the_compared_features():
    features = {
        "Case": "Abl",
        "Number": "Sing",
        "Gender": "Masc",
        "Person": "3",
        "Mood": "Ind",
        "Tense": "Pres",
        "Aspect": "Imp",
        "Voice": "Act",
        "VerbForm": "Fin",
        "Degree": "Cmp",
    }
    assert map_features(features) == features


def test_drops_features_outside_the_compared_subset():
    perseus_pronoun = {
        "Case": "Abl",
        "Number": "Sing",
        "Number[psor]": "Plur",
        "Person[psor]": "1",
        "Poss": "Yes",
        "PronType": "Prs",
    }
    assert map_features(perseus_pronoun) == {"Case": "Abl", "Number": "Sing"}


def test_drops_ittb_lexical_features():
    ittb = {
        "Case": "Nom",
        "Compound": "Yes",
        "Form": "Emp",
        "InflClass": "LatPron",
        "InflClass[nominal]": "IndEurO",
        "Gender": "Neut",
    }
    assert map_features(ittb) == {"Case": "Nom", "Gender": "Neut"}


def test_drops_the_diminutive_degree_but_keeps_other_degrees():
    assert map_features({"Degree": "Dim"}) == {}
    assert map_features({"Degree": "Abs"}) == {"Degree": "Abs"}


def test_keeps_a_multi_valued_feature_whole():
    assert map_features({"Gender": "Fem,Masc"}) == {"Gender": "Fem,Masc"}


def test_unknown_value_of_a_compared_feature_raises():
    with pytest.raises(UnknownFeatureError) as raised:
        map_features({"Case": "Ess"})

    assert (raised.value.feature, raised.value.value) == ("Case", "Ess")
    assert "Case=Ess" in str(raised.value)


def test_unknown_member_of_a_multi_valued_feature_raises():
    with pytest.raises(UnknownFeatureError):
        map_features({"Gender": "Masc,Bogus"})


def test_unknown_feature_name_raises():
    with pytest.raises(UnknownFeatureError) as raised:
        map_features({"Evident": "Fh"})

    assert raised.value.feature == "Evident"
