import pytest

from priscianus.morphology.normaliser import key_loose


@pytest.mark.parametrize(
    ("form", "expected"),
    [
        ("amāvērunt", "amauerunt"),
        ("RĒX", "rex"),
        ("Rēgī", "regi"),
        ("  rēx\n", "rex"),
        ("ămō", "amo"),
        ("amo\u0304", "amo"),  # combining macron (NFD input)
    ],
)
def test_key_loose_strips_length_marks_and_case(form: str, expected: str) -> None:
    assert key_loose(form) == expected


@pytest.mark.parametrize(
    ("form", "expected"),
    [
        ("vir", "uir"),
        ("uir", "uir"),
        ("Iuppiter", "iuppiter"),
        ("Juppiter", "iuppiter"),
        ("jam", "iam"),
        ("VIVO", "uiuo"),
        ("Vīvō", "uiuo"),
    ],
)
def test_key_loose_folds_consonantal_u_v_and_i_j(form: str, expected: str) -> None:
    assert key_loose(form) == expected


@pytest.mark.parametrize(
    ("form", "expected"),
    [
        ("virumque", "uirumque"),
        ("itaque", "itaque"),
        ("Arma", "arma"),
        ("caelum", "caelum"),
        ("coelum", "coelum"),
        ("rosae", "rosae"),
        ("rosæ", "rosae"),
        ("cœlum", "coelum"),
        ("Æneās", "aeneas"),
        ("Œdipūs", "oedipus"),
    ],
)
def test_key_loose_leaves_enclitics_and_spelling_variants_distinct(
    form: str, expected: str
) -> None:
    assert key_loose(form) == expected


def test_key_loose_of_empty_string_is_empty() -> None:
    assert key_loose("") == ""
