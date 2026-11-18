"""Grade a learner's answer to a drill item (ADR-005, Decision 6).

The index grades, not the model. The accepted forms are worked out again from the lemma and
features, so nothing the browser sends can change the key.
"""

from dataclasses import dataclass

from priscianus.morphology.inflect import NoSuchFormError
from priscianus.morphology.lookup import Analysis
from priscianus.morphology.normaliser import key_loose
from priscianus.morphology.ud_features import canonical_values
from priscianus.pipeline.tools import accepted_forms, reading_dict
from priscianus.tutor.drills import _names_one_form
from priscianus.verifier.classify import merge_readings
from priscianus.verifier.index import MorphologyIndex
from priscianus.verifier.matching import lemma_agrees


class GradeInputError(ValueError):
    """The item is not one the index can grade: bad features, or no accepted form."""


@dataclass(frozen=True)
class Reading:
    """What a wrong answer really is, from the index."""

    lemma: str
    form: str
    features: str
    same_lemma: bool


@dataclass(frozen=True)
class Grade:
    correct: bool
    accepted: tuple[str, ...]
    answer_is: tuple[Reading, ...]


def grade(
    lemma: str, pos: str, features: dict[str, str], answer: str, index: MorphologyIndex
) -> Grade:
    """Whether `answer` is an accepted form of `lemma` with `features`.

    Macrons, case and u/v, i/j are ignored (`key_loose`). A wrong answer that is in the index
    comes back with what it is. Raises `GradeInputError` if the item has no accepted form.
    """
    allowed = canonical_values()
    for name, value in features.items():
        if name not in allowed or value not in allowed[name]:
            raise GradeInputError(f"{name}={value!r} is not a feature the tutor uses.")
    if not _names_one_form(pos, features):
        raise GradeInputError("That item does not ask for one form.")
    try:
        accepted = accepted_forms(lemma, features, pos, index)
    except NoSuchFormError:
        raise GradeInputError("The index has no such form, so it cannot grade this item.") from None
    if key_loose(answer) in {key_loose(form) for form in accepted}:
        return Grade(True, tuple(accepted), ())
    readings = tuple(_reading(a, lemma) for a in merge_readings(index.analyse(answer)))
    return Grade(False, tuple(accepted), readings)


def _reading(analysis: Analysis, lemma: str) -> Reading:
    shown = reading_dict(analysis)
    return Reading(shown["lemma"], shown["form"], shown["features"], lemma_agrees(lemma, analysis))
