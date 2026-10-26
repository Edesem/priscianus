import pytest

from priscianus.morphology.ud_features import UnknownTagError, map_tags


def _as_set(readings: list[dict[str, str]]) -> set[frozenset[tuple[str, str]]]:
    return {frozenset(r.items()) for r in readings}


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
def test_single_tag_gives_one_reading(tags: list[str], expected: dict[str, str]) -> None:
    assert map_tags(tags) == [expected]


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
    ],
)
def test_tags_for_different_features_merge_into_one_reading(
    tags: list[str], expected: dict[str, str]
) -> None:
    assert map_tags(tags) == [expected]


# Wiktionary spells the future perfect as two tags. It is one tense, not a
# future reading plus a perfect reading.
@pytest.mark.parametrize(
    "tags",
    [
        ["third-person", "plural", "future", "perfect", "active", "indicative"],
        ["third-person", "plural", "perfect", "future", "active", "indicative"],
    ],
)
def test_future_perfect_is_one_reading(tags: list[str]) -> None:
    assert map_tags(tags) == [
        {
            "Person": "3",
            "Number": "Plur",
            "Tense": "Fut",
            "Aspect": "Perf",
            "Voice": "Act",
            "Mood": "Ind",
            "VerbForm": "Fin",
        }
    ]


# A form like "eius" is one spelling shared by a reading for each gender.
def test_several_genders_give_one_reading_per_gender() -> None:
    readings = map_tags(["genitive", "singular", "masculine", "feminine", "neuter"])
    assert len(readings) == 3
    assert _as_set(readings) == _as_set(
        [
            {"Case": "Gen", "Number": "Sing", "Gender": "Masc"},
            {"Case": "Gen", "Number": "Sing", "Gender": "Fem"},
            {"Case": "Gen", "Number": "Sing", "Gender": "Neut"},
        ]
    )


def test_several_cases_give_one_reading_per_case() -> None:
    readings = map_tags(["nominative", "accusative", "neuter", "singular"])
    assert _as_set(readings) == _as_set(
        [
            {"Case": "Nom", "Gender": "Neut", "Number": "Sing"},
            {"Case": "Acc", "Gender": "Neut", "Number": "Sing"},
        ]
    )


def test_several_multi_valued_features_give_every_combination() -> None:
    readings = map_tags(["nominative", "accusative", "masculine", "feminine"])
    assert _as_set(readings) == _as_set(
        [
            {"Case": "Nom", "Gender": "Masc"},
            {"Case": "Nom", "Gender": "Fem"},
            {"Case": "Acc", "Gender": "Masc"},
            {"Case": "Acc", "Gender": "Fem"},
        ]
    )


def test_repeated_tag_does_not_duplicate_readings() -> None:
    assert map_tags(["feminine", "feminine", "singular"]) == [{"Gender": "Fem", "Number": "Sing"}]


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        (["canonical"], {}),
        (["table-tags"], {}),
        (["inflection-template"], {}),
        (["class"], {}),
        (["romanization"], {}),
        (["archaic", "nominative", "singular"], {"Case": "Nom", "Number": "Sing"}),
        (["Medieval-Latin", "alternative"], {}),
    ],
)
def test_metadata_tags_are_ignored_not_errors(tags: list[str], expected: dict[str, str]) -> None:
    assert map_tags(tags) == [expected]


def test_empty_tags_give_one_reading_with_no_features() -> None:
    assert map_tags([]) == [{}]


def test_unknown_tag_raises_and_names_the_tag() -> None:
    with pytest.raises(UnknownTagError, match="blorp"):
        map_tags(["nominative", "blorp"])


def test_unknown_tag_error_lists_every_unknown_tag() -> None:
    with pytest.raises(UnknownTagError) as excinfo:
        map_tags(["blorp", "nominative", "zork"])
    assert excinfo.value.tags == ("blorp", "zork")


def test_unknown_tag_error_is_a_value_error() -> None:
    assert issubclass(UnknownTagError, ValueError)
