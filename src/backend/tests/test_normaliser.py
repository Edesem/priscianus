import pytest

from priscianus.morphology.normaliser import key_loose


@pytest.mark.parametrize(
    ("form", "expected"),
    [
        ("amāvērunt", "amaverunt"),
        ("RĒX", "rex"),
        ("Rēgī", "regi"),
        ("  rēx\n", "rex"),
        ("ămō", "amo"),
        ("amō", "amo"),  # combining macron (NFD input)
    ],
)
def test_key_loose_strips_length_marks_and_case(form: str, expected: str) -> None:
    assert key_loose(form) == expected
