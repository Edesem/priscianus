import pytest

from priscianus.morphology.ud_features import (
    ConflictingTagsError,
    UnknownTagError,
    map_tags,
)


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        (["nominative", "singular"], {"Case": "Nom", "Number": "Sing"}),
        (["genitive", "plural"], {"Case": "Gen", "Number": "Plur"}),
        (["dative"], {"Case": "Dat"}),
        (["accusative"], {"Case": "Acc"}),
        (["ablative"], {"Case": "Abl"}),
        (["vocative"], {"Case": "Voc"}),
        (["locative"], {"Case": "Loc"}),
        (["masculine"], {"Gender": "Masc"}),
        (["feminine"], {"Gender": "Fem"}),
        (["neuter"], {"Gender": "Neut"}),
        (["first-person"], {"Person": "1"}),
        (["second-person"], {"Person": "2"}),
        (["third-person"], {"Person": "3"}),
        (["active"], {"Voice": "Act"}),
        (["passive"], {"Voice": "Pass"}),
        (["positive"], {"Degree": "Pos"}),
        (["comparative"], {"Degree": "Cmp"}),
        (["superlative"], {"Degree": "Sup"}),
        (["present"], {"Tense": "Pres"}),
        (["future"], {"Tense": "Fut"}),
        (["imperfect"], {"Tense": "Past", "Aspect": "Imp"}),
        (["perfect"], {"Tense": "Past", "Aspect": "Perf"}),
        (["pluperfect"], {"Tense": "Pqp"}),
        (["indicative"], {"Mood": "Ind", "VerbForm": "Fin"}),
        (["subjunctive"], {"Mood": "Sub", "VerbForm": "Fin"}),
        (["imperative"], {"Mood": "Imp", "VerbForm": "Fin"}),
        (["infinitive"], {"VerbForm": "Inf"}),
        (["participle"], {"VerbForm": "Part"}),
        (["gerund"], {"VerbForm": "Ger"}),
        (["supine"], {"VerbForm": "Sup"}),
    ],
)
def test_single_tag_maps_to_ud_features(tags: list[str], expected: dict[str, str]) -> None:
    assert map_tags(tags) == expected


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        (
            ["first-person", "singular", "present", "active", "indicative"],
            {
                "Person": "1",
                "Number": "Sing",
                "Tense": "Pres",
                "Voice": "Act",
                "Mood": "Ind",
                "VerbForm": "Fin",
            },
        ),
        (
            ["nominative", "singular", "masculine", "perfect", "passive", "participle"],
            {
                "Case": "Nom",
                "Number": "Sing",
                "Gender": "Masc",
                "Tense": "Past",
                "Aspect": "Perf",
                "Voice": "Pass",
                "VerbForm": "Part",
            },
        ),
        # Wiktionary spells the future perfect as two tags; they must not collide on Tense.
        (
            ["third-person", "plural", "future", "perfect", "active", "indicative"],
            {
                "Person": "3",
                "Number": "Plur",
                "Tense": "Fut",
                "Aspect": "Perf",
                "Voice": "Act",
                "Mood": "Ind",
                "VerbForm": "Fin",
            },
        ),
    ],
)
def test_tag_combinations_merge_into_one_feature_dict(
    tags: list[str], expected: dict[str, str]
) -> None:
    assert map_tags(tags) == expected


@pytest.mark.parametrize(
    "tags",
    [
        ["canonical"],
        ["table-tags"],
        ["inflection-template"],
        ["class"],
        ["romanization"],
        ["archaic", "nominative", "singular"],
        ["Medieval-Latin", "alternative"],
    ],
)
def test_metadata_tags_are_ignored_not_errors(tags: list[str]) -> None:
    result = map_tags(tags)
    assert set(result) <= {"Case", "Number"}


def test_empty_tags_give_empty_features() -> None:
    assert map_tags([]) == {}


def test_unknown_tag_raises_and_names_the_tag() -> None:
    with pytest.raises(UnknownTagError, match="blorp"):
        map_tags(["nominative", "blorp"])


def test_unknown_tag_error_lists_every_unknown_tag() -> None:
    with pytest.raises(UnknownTagError) as excinfo:
        map_tags(["blorp", "nominative", "zork"])
    assert excinfo.value.tags == ("blorp", "zork")


def test_unknown_tag_error_is_a_value_error() -> None:
    assert issubclass(UnknownTagError, ValueError)


def test_conflicting_values_for_one_feature_raise() -> None:
    with pytest.raises(ConflictingTagsError, match="Case"):
        map_tags(["nominative", "accusative"])
