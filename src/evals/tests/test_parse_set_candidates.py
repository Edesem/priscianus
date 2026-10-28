import pytest

from evals.gold import GoldToken
from evals.parse_set import is_candidate, pos_class, slice_of


def token(
    *,
    treebank: str = "perseus",
    upos: str = "NOUN",
    features: dict[str, str] | None = None,
    mwt_form: str | None = None,
    source: str = "",
) -> GoldToken:
    return GoldToken(
        treebank=treebank,
        sent_id="s1",
        token_id=1,
        form="rosa",
        lemma="rosa",
        upos=upos,
        features=features or {},
        sentence="rosa",
        mwt_form=mwt_form,
        source=source,
    )


@pytest.mark.parametrize(
    ("upos", "expected"),
    [
        ("VERB", "verb"),
        ("AUX", "verb"),
        ("NOUN", "noun"),
        ("ADJ", "adj"),
        ("PRON", "pron_det"),
        ("DET", "pron_det"),
        ("ADV", "uninflected"),
        ("ADP", "uninflected"),
        ("CCONJ", "uninflected"),
        ("SCONJ", "uninflected"),
        ("PART", "uninflected"),
        ("INTJ", "uninflected"),
        ("PROPN", None),
        ("NUM", None),
        ("PUNCT", None),
        ("X", None),
        ("SYM", None),
    ],
)
def test_pos_class_follows_adr_003(upos, expected):
    assert pos_class(upos) == expected


def test_an_ordinary_word_is_a_candidate():
    assert is_candidate(token())


@pytest.mark.parametrize("upos", ["PUNCT", "NUM", "PROPN", "X", "SYM"])
def test_excluded_parts_of_speech_are_not_candidates(upos):
    assert not is_candidate(token(upos=upos))


@pytest.mark.parametrize("features", [{"Foreign": "Yes"}, {"Abbr": "Yes"}])
def test_foreign_and_abbreviated_words_are_not_candidates(features):
    assert not is_candidate(token(features=features))


def test_a_word_inside_a_multiword_token_is_not_a_candidate():
    assert not is_candidate(token(mwt_form="virumque"))


@pytest.mark.parametrize(
    ("treebank", "source", "expected"),
    [
        ("perseus", "phi0690.phi003.perseus-lat1.tb.xml", "Classical"),
        ("ittb", "", "Ecclesiastical"),
        ("proiel", "Jerome's Vulgate, Matthew 6", "Ecclesiastical"),
        ("proiel", "Epistulae ad Atticum, Book 1, letter 13", "Classical"),
        ("proiel", "De officiis, Book 2", "Classical"),
        ("proiel", "Commentarii belli Gallici, Caes., Gall. 3.14", "Classical"),
        ("proiel", "Opus agriculturae, V. De qualitate terrarum", None),
    ],
)
def test_slice_comes_from_the_treebank_and_the_sentence_source(treebank, source, expected):
    assert slice_of(token(treebank=treebank, source=source)) == expected


def test_an_unrecognised_proiel_work_raises_so_a_new_release_cannot_slip_by():
    with pytest.raises(ValueError, match="Unknown PROIEL work"):
        slice_of(token(treebank="proiel", source="Peregrinatio Egeriae, 3"))


def test_a_treebank_outside_the_parse_set_has_no_slice():
    with pytest.raises(ValueError, match="llct"):
        slice_of(token(treebank="llct"))
