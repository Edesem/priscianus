import json

import pytest
from priscianus.llm.client import LLMResponse, Usage

from evals.gold import parse_conllu
from evals.raw_prompt import (
    ALLOWED_FEATURES,
    OUTPUT_SCHEMA,
    PROMPT_ID,
    SYSTEM_PROMPT,
    Claim,
    ParseFailure,
    build_messages,
    mark_target,
    occurrence_of,
    parse_claim,
)

CONLLU = """\
# newdoc id = phi0959.phi006.perseus-lat1.tb.xml
# sent_id = s1
# text = arma virumque cano et arma
1\tarma\tarma\tNOUN\t_\tCase=Nom|Gender=Neut|Number=Plur\t3\tobj\t_\t_
2-3\tvirumque\t_\t_\t_\t_\t_\t_\t_\t_
2\tvirum\tvir\tNOUN\t_\tCase=Acc|Gender=Masc|Number=Sing\t4\tobj\t_\t_
3\tque\tque\tCCONJ\t_\t_\t2\tcc\t_\t_
4\tcano\tcano\tVERB\t_\tMood=Ind|Number=Sing|Person=1|Tense=Pres|VerbForm=Fin|Voice=Act\t0\troot\t_\t_
5\tet\tet\tCCONJ\t_\t_\t6\tcc\t_\t_
6\tarma\tarma\tNOUN\t_\tCase=Acc|Gender=Neut|Number=Plur\t4\tobj\t_\t_

"""


@pytest.fixture
def tokens():
    return parse_conllu(CONLLU, treebank="perseus")


def response(text: str) -> LLMResponse:
    return LLMResponse([{"type": "text", "text": text}], "end_turn", Usage())


def test_marks_the_target_word_in_the_sentence():
    assert mark_target("Arma virumque cano", "cano", 1) == "Arma virumque [[cano]]"


def test_marks_the_requested_occurrence_of_a_repeated_form():
    assert mark_target("arma et arma", "arma", 2) == "arma et [[arma]]"


def test_marks_a_form_only_where_it_is_a_whole_word():
    assert mark_target("cano canone", "cano", 1) == "[[cano]] canone"


def test_mark_target_rejects_a_form_that_is_not_in_the_sentence():
    with pytest.raises(ValueError):
        mark_target("Arma virumque cano", "regina", 1)


def test_occurrence_counts_earlier_words_with_the_same_form(tokens):
    first, last = tokens[0], tokens[-1]
    assert occurrence_of(first, tokens) == 1
    assert occurrence_of(last, tokens) == 2


def test_occurrence_ignores_other_sentences(tokens):
    other = parse_conllu(CONLLU.replace("s1", "s2"), treebank="perseus")
    assert occurrence_of(other[-1], tokens + other) == 2


def test_prompt_marks_the_target_and_names_its_form(tokens):
    messages = build_messages(tokens[3], occurrence=1)
    content = messages[0]["content"]
    assert "arma virumque [[cano]] et arma" in content
    assert "[[cano]]" in content
    assert "cano" in content


def test_prompt_does_not_leak_the_gold_or_the_index(tokens):
    text = SYSTEM_PROMPT + build_messages(tokens[3], occurrence=1)[0]["content"]
    for leaked in ("gold", "treebank", "morphology index", "token_id"):
        assert leaked not in text
    # The target's own lemma, UPOS and features appear nowhere in what the model sees but its form.
    assert "lemma: cano" not in text


def test_schema_limits_features_to_the_allowed_names_and_values():
    features = OUTPUT_SCHEMA["properties"]["features"]
    assert features["additionalProperties"] is False
    assert set(features["properties"]) == set(ALLOWED_FEATURES)
    assert features["properties"]["Case"]["enum"] == [
        "Nom",
        "Gen",
        "Dat",
        "Acc",
        "Abl",
        "Voc",
        "Loc",
    ]


def test_schema_requires_lemma_upos_and_features():
    assert OUTPUT_SCHEMA["required"] == ["lemma", "upos", "features"]


def test_system_prompt_lists_every_allowed_value():
    for name, values in ALLOWED_FEATURES.items():
        assert name in SYSTEM_PROMPT
        for value in values:
            assert value in SYSTEM_PROMPT


def test_prompt_id_is_versioned():
    assert PROMPT_ID.startswith("raw-parse-v")


def test_parses_a_valid_response():
    text = json.dumps({"lemma": "cano", "upos": "VERB", "features": {"Person": "1"}})
    assert parse_claim(response(text)) == Claim("cano", "VERB", {"Person": "1"})


def test_invalid_json_is_a_failure_not_an_exception():
    result = parse_claim(response("I think it is cano"))
    assert isinstance(result, ParseFailure)
    assert "JSON" in result.reason


def test_an_invented_feature_name_is_a_failure():
    text = json.dumps({"lemma": "cano", "upos": "VERB", "features": {"Flavour": "Sweet"}})
    result = parse_claim(response(text))
    assert isinstance(result, ParseFailure)
    assert "Flavour" in result.reason


def test_a_value_outside_the_allowed_list_is_a_failure():
    text = json.dumps({"lemma": "cano", "upos": "VERB", "features": {"Case": "Nominative"}})
    assert isinstance(parse_claim(response(text)), ParseFailure)


def test_an_unknown_upos_is_a_failure():
    text = json.dumps({"lemma": "cano", "upos": "VERBISH", "features": {}})
    assert isinstance(parse_claim(response(text)), ParseFailure)


def test_a_missing_field_is_a_failure():
    assert isinstance(parse_claim(response(json.dumps({"lemma": "cano"}))), ParseFailure)


def test_an_empty_lemma_is_a_failure():
    text = json.dumps({"lemma": "", "upos": "VERB", "features": {}})
    assert isinstance(parse_claim(response(text)), ParseFailure)


def test_a_truncated_response_is_a_failure():
    truncated = LLMResponse([{"type": "text", "text": '{"lemma": "ca'}], "max_tokens", Usage())
    result = parse_claim(truncated)
    assert isinstance(result, ParseFailure)
    assert "max_tokens" in result.reason
