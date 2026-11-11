import json
from typing import Any

from priscianus.morphology.ud_features import canonical_values
from priscianus.verifier.claims import (
    Claim,
    ModelOutput,
    SchemaError,
    output_schema,
    parse_output,
)

NO_FEATURES = dict.fromkeys(canonical_values(), "None")


def claim_data(**overrides: Any) -> dict[str, Any]:
    features = {**NO_FEATURES, **overrides.pop("features", {})}
    return {
        "form": "loquitur",
        "lemma": "loquor",
        "upos": "VERB",
        **overrides,
        "features": features,
    }


def output_text(*claims: dict[str, Any], text: str = "") -> str:
    return json.dumps({"text": text, "claims": list(claims)})


def test_canonical_values_use_gdv_and_leave_out_pos():
    values = canonical_values()
    assert "Gdv" in values["VerbForm"]
    assert "Pos" not in values["Degree"]
    assert set(values["Degree"]) == {"Cmp", "Sup"}


def test_canonical_values_cover_the_ten_compared_features():
    assert set(canonical_values()) == {
        "Case",
        "Number",
        "Gender",
        "Person",
        "Tense",
        "Aspect",
        "Mood",
        "Voice",
        "VerbForm",
        "Degree",
    }


def test_schema_allows_exactly_the_canonical_values_and_none():
    schema = output_schema()
    features = schema["properties"]["claims"]["items"]["properties"]["features"]
    for name, values in canonical_values().items():
        assert set(features["properties"][name]["enum"]) == {*values, "None"}


def test_schema_requires_every_feature_and_forbids_extras():
    schema = output_schema()
    item = schema["properties"]["claims"]["items"]
    features = item["properties"]["features"]
    assert features["required"] == list(features["properties"])
    assert features["additionalProperties"] is False
    assert item["required"] == ["form", "lemma", "upos", "features"]
    assert item["additionalProperties"] is False
    assert schema["required"] == ["text", "claims"]
    assert schema["additionalProperties"] is False


def test_schema_is_json_serialisable():
    json.dumps(output_schema())


def test_parses_a_valid_output():
    data = claim_data(features={"Person": "3", "Number": "Sing", "Voice": "Pass"})
    result = parse_output(output_text(data, text="why"))
    assert result == ModelOutput(
        "why",
        (Claim("loquitur", "loquor", "VERB", {"Person": "3", "Number": "Sing", "Voice": "Pass"}),),
    )


def test_none_is_removed_from_the_features():
    result = parse_output(output_text(claim_data(form="et", lemma="et", upos="CCONJ")))
    assert isinstance(result, ModelOutput)
    assert result.claims[0].features == {}


def test_an_output_may_have_no_claims():
    assert parse_output(output_text()) == ModelOutput("", ())


def test_an_output_may_have_several_claims():
    result = parse_output(output_text(claim_data(), claim_data(form="et", lemma="et")))
    assert isinstance(result, ModelOutput)
    assert [c.form for c in result.claims] == ["loquitur", "et"]


def test_invalid_json_is_returned_as_a_value():
    result = parse_output("not json")
    assert isinstance(result, SchemaError)
    assert result.reason.startswith("invalid JSON")


def test_output_that_is_not_an_object_is_an_error():
    assert isinstance(parse_output("[]"), SchemaError)


def test_a_missing_top_level_field_is_an_error():
    result = parse_output(json.dumps({"claims": []}))
    assert isinstance(result, SchemaError)
    assert "text" in result.reason


def test_an_extra_top_level_field_is_an_error():
    assert isinstance(parse_output(json.dumps({"text": "", "claims": [], "x": 1})), SchemaError)


def test_text_must_be_a_string():
    assert isinstance(parse_output(json.dumps({"text": 3, "claims": []})), SchemaError)


def test_claims_must_be_a_list():
    assert isinstance(parse_output(json.dumps({"text": "", "claims": {}})), SchemaError)


def test_a_claim_must_be_an_object():
    assert isinstance(parse_output(json.dumps({"text": "", "claims": ["x"]})), SchemaError)


def test_a_claim_with_a_missing_field_is_an_error():
    data = claim_data()
    del data["lemma"]
    result = parse_output(output_text(data))
    assert isinstance(result, SchemaError)
    assert "lemma" in result.reason


def test_an_empty_form_is_an_error():
    assert isinstance(parse_output(output_text(claim_data(form=" "))), SchemaError)


def test_an_empty_lemma_is_an_error():
    assert isinstance(parse_output(output_text(claim_data(lemma=""))), SchemaError)


def test_an_unknown_upos_is_an_error():
    result = parse_output(output_text(claim_data(upos="VERBISH")))
    assert isinstance(result, SchemaError)
    assert "VERBISH" in result.reason


def test_a_feature_left_out_is_an_error():
    data = claim_data()
    del data["features"]["Degree"]
    result = parse_output(output_text(data))
    assert isinstance(result, SchemaError)
    assert "Degree" in result.reason


def test_an_invented_feature_is_an_error():
    result = parse_output(output_text(claim_data(features={"Flavour": "Sweet"})))
    assert isinstance(result, SchemaError)
    assert "Flavour" in result.reason


def test_a_value_outside_the_allowed_list_is_an_error():
    result = parse_output(output_text(claim_data(features={"Case": "Nominative"})))
    assert isinstance(result, SchemaError)
    assert "Case" in result.reason


def test_features_must_be_an_object():
    data = {**claim_data(), "features": []}
    assert isinstance(parse_output(output_text(data)), SchemaError)


def test_the_verifier_package_exports_the_shared_claim():
    import priscianus.verifier as verifier

    assert verifier.Claim is Claim
