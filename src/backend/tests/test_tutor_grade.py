"""Tests for grading (ADR-005, Decision 6): an in-memory index, no model."""

import pytest

from priscianus.morphology.lookup import Analysis
from priscianus.morphology.normaliser import key_loose
from priscianus.tutor.grade import GradeInputError, grade
from test_tutor_drills import PERFECT_3PL, DrillIndex

PERFECT_3SG = {**PERFECT_3PL, "Number": "Sing"}


class GradeIndex(DrillIndex):
    """`DrillIndex` plus a table of what typed forms really are."""

    def analyse(self, form: str) -> list[Analysis]:
        key = key_loose(form)  # like the real index, which looks forms up by this key
        if key == "amauit":
            return [Analysis("amo", "amō", "verb", "amāvit", PERFECT_3SG)]
        if key == "reges":
            return [Analysis("rex", "rēx", "noun", "rēgēs", {"Case": "Nom", "Number": "Plur"})]
        return []


@pytest.mark.parametrize("answer", ["amāvērunt", "amaverunt", "AMAVERUNT", " amavērunt "])
def test_the_right_form_is_correct_with_or_without_macrons_and_case(answer: str) -> None:
    result = grade("amo", "verb", PERFECT_3PL, answer, GradeIndex())

    assert result.correct is True
    assert result.accepted == ("amāvērunt", "amārunt", "amāvēre")
    assert result.answer_is == ()


def test_a_wrong_form_of_the_same_lemma_says_what_it_is() -> None:
    result = grade("amo", "verb", PERFECT_3PL, "amāvit", GradeIndex())

    assert result.correct is False
    [reading] = result.answer_is
    assert (reading.lemma, reading.form, reading.same_lemma) == ("amō", "amāvit", True)
    assert "Number=Sing" in reading.features and "Person=3" in reading.features


def test_a_real_form_of_another_lemma_is_wrong_and_not_the_same_lemma() -> None:
    result = grade("amo", "verb", PERFECT_3PL, "reges", GradeIndex())

    assert result.correct is False
    assert [r.same_lemma for r in result.answer_is] == [False]


def test_a_nonsense_answer_is_wrong_and_identifies_nothing() -> None:
    result = grade("amo", "verb", PERFECT_3PL, "blorp", GradeIndex())

    assert (result.correct, result.answer_is) == (False, ())


def test_an_item_the_index_cannot_answer_is_refused_not_graded() -> None:
    with pytest.raises(GradeInputError):
        grade("amo", "verb", {"Person": "3"}, "amat", GradeIndex())
    with pytest.raises(GradeInputError):
        grade("amo", "verb", {"Colour": "Red"}, "amat", GradeIndex())
