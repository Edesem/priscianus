from dataclasses import replace

from priscianus.morphology.lookup import Analysis
from priscianus.morphology.normaliser import key_loose
from priscianus.verifier import Claim, Verdict, classify


class FakeIndex:
    """An in-memory `MorphologyIndex`: no database, no `make data`."""

    def __init__(self, analyses: list[Analysis], extra_lemmas: tuple[str, ...] = ()) -> None:
        self._analyses = analyses
        self._lemmas = {key_loose(a.lemma) for a in analyses} | set(extra_lemmas)

    def analyse(self, form: str) -> list[Analysis]:
        return [a for a in self._analyses if key_loose(a.form) == key_loose(form)]

    def has_lemma(self, lemma: str) -> bool:
        return key_loose(lemma) in self._lemmas


def reading(
    form: str,
    lemma: str,
    features: dict[str, str],
    *,
    pos: str = "noun",
    deponent: bool = False,
    base_lemma: str | None = None,
) -> Analysis:
    return Analysis(
        lemma=lemma,
        lemma_display=lemma,
        pos=pos,
        form=form,
        features=features,
        deponent=deponent,
        base_lemma=base_lemma,
    )


ROSAE_GEN = reading("rosae", "rosa", {"Case": "Gen", "Number": "Sing"})
ROSAE_DAT = reading("rosae", "rosa", {"Case": "Dat", "Number": "Sing"})
ROSAM = reading("rosam", "rosa", {"Case": "Acc", "Number": "Sing"})


def test_verified_when_claim_matches_the_only_reading():
    index = FakeIndex([ROSAM])

    result = classify(Claim("rosam", "rosa", {"Case": "Acc", "Number": "Sing"}), index)

    assert result.verdict is Verdict.VERIFIED
    assert result.matching == (ROSAM,)
    assert result.others == ()


def test_ambiguous_when_claim_matches_one_of_several_readings_and_returns_the_others():
    index = FakeIndex([ROSAE_GEN, ROSAE_DAT, ROSAM])

    result = classify(Claim("rosae", "rosa", {"Case": "Dat", "Number": "Sing"}), index)

    assert result.verdict is Verdict.AMBIGUOUS
    assert result.matching == (ROSAE_DAT,)
    assert result.others == (ROSAE_GEN,)


def test_readings_that_agree_on_every_compared_feature_count_as_one():
    twin = reading("rosam", "rosa", {"Case": "Acc", "Number": "Sing"})
    index = FakeIndex([ROSAM, twin])

    result = classify(Claim("rosam", "rosa", {"Case": "Acc"}), index)

    assert result.verdict is Verdict.VERIFIED


def test_contradicted_when_lemma_is_indexed_but_no_reading_matches():
    index = FakeIndex([ROSAM])

    result = classify(Claim("rosam", "rosa", {"Case": "Abl", "Number": "Sing"}), index)

    assert result.verdict is Verdict.CONTRADICTED
    assert result.matching == ()
    assert result.others == (ROSAM,)


def test_contradicted_when_lemma_is_indexed_but_the_form_has_no_analysis():
    index = FakeIndex([ROSAM])

    result = classify(Claim("rosabus", "rosa", {"Case": "Abl"}), index)

    assert result.verdict is Verdict.CONTRADICTED
    assert result.others == ()


def test_unknown_when_lemma_is_not_indexed():
    index = FakeIndex([ROSAM])

    result = classify(Claim("flurbum", "flurbus", {"Case": "Acc"}), index)

    assert result.verdict is Verdict.UNKNOWN


def test_claiming_another_lemmas_form_is_contradicted_when_the_claimed_lemma_is_indexed():
    index = FakeIndex([ROSAM], extra_lemmas=("puella",))

    result = classify(Claim("rosam", "puella", {"Case": "Acc"}), index)

    assert result.verdict is Verdict.CONTRADICTED
    assert result.others == (ROSAM,)


def test_voice_is_not_compared_on_a_deponent_lemma():
    hortor = reading(
        "hortor",
        "hortor",
        {"Person": "1", "Number": "Sing", "Tense": "Pres", "Mood": "Ind", "Voice": "Act"},
        pos="verb",
        deponent=True,
    )
    claim = Claim(
        "hortor",
        "hortor",
        {"Person": "1", "Number": "Sing", "Tense": "Pres", "Mood": "Ind", "Voice": "Pass"},
    )

    assert classify(claim, FakeIndex([hortor])).verdict is Verdict.VERIFIED


def test_voice_is_compared_on_a_non_deponent_lemma():
    amor = reading("amor", "amo", {"Person": "1", "Voice": "Act"}, pos="verb")

    result = classify(Claim("amor", "amo", {"Person": "1", "Voice": "Pass"}), FakeIndex([amor]))

    assert result.verdict is Verdict.CONTRADICTED


def test_gender_is_not_compared_on_nouns_because_the_index_does_not_carry_it():
    result = classify(Claim("rosam", "rosa", {"Case": "Acc", "Gender": "Fem"}), FakeIndex([ROSAM]))

    assert result.verdict is Verdict.VERIFIED


def test_person_is_not_compared_on_pronouns():
    me = reading("me", "ego", {"Case": "Acc", "Number": "Sing"}, pos="pron")

    result = classify(Claim("me", "ego", {"Case": "Acc", "Person": "1"}), FakeIndex([me]))

    assert result.verdict is Verdict.VERIFIED


def test_participle_claim_matches_through_the_verb_lemma():
    amatus = reading(
        "amatus",
        "amatus",
        {"Case": "Nom", "Number": "Sing", "Gender": "Masc", "VerbForm": "Part"},
        pos="verb",
        base_lemma="amo",
    )

    result = classify(
        Claim("amatus", "amo", {"Case": "Nom", "VerbForm": "Part"}), FakeIndex([amatus])
    )

    assert result.verdict is Verdict.VERIFIED


def test_lemma_is_compared_without_macrons_or_homograph_numbers():
    result = classify(Claim("rosam", "rosā1", {"Case": "Acc"}), FakeIndex([ROSAM]))

    assert result.verdict is Verdict.VERIFIED


def test_a_feature_the_claim_leaves_out_is_not_held_against_it():
    result = classify(Claim("rosam", "rosa", {}), FakeIndex([ROSAM]))

    assert result.verdict is Verdict.VERIFIED


def test_claim_features_are_canonicalised_before_comparison():
    amatum = reading(
        "amatum",
        "amatus",
        {"Case": "Acc", "VerbForm": "Part", "Tense": "Past"},
        pos="verb",
        base_lemma="amo",
    )
    claim = Claim("amatum", "amo", {"Case": "Acc", "VerbForm": "Part", "Aspect": "Perf"})

    assert classify(claim, FakeIndex([amatum])).verdict is Verdict.VERIFIED


AFFIRMAT = reading("affirmat", "affirmo", {"Person": "3", "Number": "Sing"}, pos="verb")


def test_unassimilated_claim_is_verified_through_the_variant_and_flagged():
    index = FakeIndex([AFFIRMAT])

    result = classify(Claim("affirmat", "adfirmo", {"Person": "3"}), index)

    assert result.verdict is Verdict.VERIFIED
    assert result.variant is True


def test_variant_form_found_by_the_index_is_flagged():
    found = replace(AFFIRMAT, form="adfirmat", variant=True)
    index = FakeIndex([found])

    result = classify(Claim("adfirmat", "affirmo", {"Person": "3"}), index)

    assert result.verdict is Verdict.VERIFIED
    assert result.variant is True


def test_exact_claim_is_not_flagged():
    index = FakeIndex([AFFIRMAT])

    assert classify(Claim("affirmat", "affirmo", {"Person": "3"}), index).variant is False


def test_variant_lemma_with_wrong_features_is_still_contradicted():
    index = FakeIndex([AFFIRMAT])

    result = classify(Claim("affirmat", "adfirmo", {"Person": "1"}), index)

    assert result.verdict is Verdict.CONTRADICTED
    assert result.variant is False
