import pytest

from priscianus.morphology.canonical import canonicalise, relax


@pytest.mark.parametrize(
    "features, expected",
    [
        # Perseus and ITTB write Aspect=Imp on a present; PROIEL and the index do not.
        (
            {"Tense": "Pres", "Aspect": "Imp", "Mood": "Ind", "VerbForm": "Fin"},
            {"Tense": "Pres", "Mood": "Ind", "VerbForm": "Fin"},
        ),
        ({"Tense": "Fut", "Aspect": "Imp"}, {"Tense": "Fut"}),
        # Aspect=Perf on a pluperfect is dropped too.
        ({"Tense": "Pqp", "Aspect": "Perf"}, {"Tense": "Pqp"}),
        # Past tenses keep Aspect, because it separates the imperfect from the perfect.
        ({"Tense": "Past", "Aspect": "Imp"}, {"Tense": "Past", "Aspect": "Imp"}),
        ({"Tense": "Past", "Aspect": "Perf"}, {"Tense": "Past", "Aspect": "Perf"}),
        # The future perfect keeps it as well.
        ({"Tense": "Fut", "Aspect": "Perf"}, {"Tense": "Fut", "Aspect": "Perf"}),
    ],
)
def test_aspect_is_kept_only_where_it_tells_tenses_apart(features, expected):
    assert canonicalise(features) == expected


@pytest.mark.parametrize(
    "aspect, tense",
    [("Imp", "Pres"), ("Perf", "Past"), ("Prosp", "Fut")],
)
def test_participle_tense_is_taken_from_aspect(aspect, tense):
    features = {"VerbForm": "Part", "Aspect": aspect, "Voice": "Act", "Case": "Nom"}
    assert canonicalise(features) == {
        "VerbForm": "Part",
        "Tense": tense,
        "Voice": "Act",
        "Case": "Nom",
    }


def test_participle_aspect_is_dropped_when_tense_is_already_there():
    features = {"VerbForm": "Part", "Tense": "Past", "Aspect": "Perf", "Voice": "Pass"}
    assert canonicalise(features) == {"VerbForm": "Part", "Tense": "Past", "Voice": "Pass"}


def test_future_passive_participle_in_perseus_form_becomes_a_gerundive():
    perseus = {"VerbForm": "Part", "Aspect": "Prosp", "Voice": "Pass", "Case": "Gen"}
    assert canonicalise(perseus) == {"VerbForm": "Gdv", "Case": "Gen"}


def test_future_passive_participle_in_index_form_becomes_a_gerundive():
    index = {"VerbForm": "Part", "Tense": "Fut", "Voice": "Pass", "Case": "Gen"}
    assert canonicalise(index) == {"VerbForm": "Gdv", "Case": "Gen"}


def test_proiel_gerundive_loses_tense_and_voice():
    proiel = {"VerbForm": "Gdv", "Tense": "Fut", "Voice": "Pass", "Case": "Gen"}
    assert canonicalise(proiel) == {"VerbForm": "Gdv", "Case": "Gen"}


def test_future_active_participle_stays_a_participle():
    features = {"VerbForm": "Part", "Aspect": "Prosp", "Voice": "Act"}
    assert canonicalise(features) == {"VerbForm": "Part", "Tense": "Fut", "Voice": "Act"}


def test_absolute_degree_is_a_superlative():
    assert canonicalise({"Degree": "Abs"}) == {"Degree": "Sup"}


def test_positive_degree_is_dropped():
    assert canonicalise({"Degree": "Pos", "Case": "Nom"}) == {"Case": "Nom"}


def test_comparative_degree_is_kept():
    assert canonicalise({"Degree": "Cmp"}) == {"Degree": "Cmp"}


def test_multi_valued_feature_stays_a_sorted_set():
    assert canonicalise({"Gender": "Neut,Masc"}) == {"Gender": "Masc,Neut"}


def test_canonicalise_does_not_change_its_argument():
    features = {"Tense": "Pres", "Aspect": "Imp"}
    canonicalise(features)
    assert features == {"Tense": "Pres", "Aspect": "Imp"}


def test_relax_drops_gender_on_nouns_only():
    features = {"Case": "Nom", "Gender": "Fem"}
    assert relax(features, noun=True, deponent=False) == {"Case": "Nom"}
    assert relax(features, noun=False, deponent=False) == features


def test_relax_drops_voice_on_deponents_only():
    features = {"Mood": "Ind", "Voice": "Pass"}
    assert relax(features, noun=False, deponent=True) == {"Mood": "Ind"}
    assert relax(features, noun=False, deponent=False) == features


def test_relax_drops_person_on_pronouns_only():
    features = {"Case": "Acc", "Person": "3"}

    assert relax(features, noun=False, deponent=False, pronoun=True) == {"Case": "Acc"}
    assert relax(features, noun=False, deponent=False) == features
