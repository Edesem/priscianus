import pytest

from priscianus.morphology.assimilation import variant_keys


@pytest.mark.parametrize(
    ("key", "variants"),
    [
        ("adfirmo", ["affirmo"]),
        ("affirmo", ["adfirmo"]),
        ("inpiger", ["impiger"]),
        ("inmundus", ["immundus"]),
        ("illatus", ["inlatus"]),
        ("conlatio", ["collatio"]),
        ("obcido", ["occido"]),
        ("subpono", ["suppono"]),
        ("adnuo", ["annuo"]),
        ("adquiro", ["acquiro"]),
    ],
)
def test_prefix_assimilation_is_swapped_in_both_directions(key: str, variants: list[str]) -> None:
    assert variant_keys(key) == variants


@pytest.mark.parametrize("key", ["rosa", "amo", "intro", "inde", "addo", "", "ad", "adf", "inm"])
def test_keys_without_an_assimilating_prefix_have_no_variants(key: str) -> None:
    assert variant_keys(key) == []


def test_only_the_start_of_the_key_changes() -> None:
    assert variant_keys("adfinadfin") == ["affinadfin"]
