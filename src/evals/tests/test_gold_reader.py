from pathlib import Path

from evals.gold import GoldToken, parse_conllu, read_conllu

PERSEUS = """\
# newdoc id = phi0690.phi003.perseus-lat1.tb.xml
# sent_id = phi0690.phi003.perseus-lat1.tb.xml@196
# text = animo mecum ante
1\tanimo\tanimus\tNOUN\tn-s---mb-\tCase=Abl|Gender=Masc|Number=Sing\t0\troot\t_\tLId=animus1
2-3\tmecum\t_\t_\t_\t_\t_\t_\t_\tLId=ego1
2\tme\tego\tPRON\tp-s---mb-\tCase=Abl|Number=Sing|Person=1|PronType=Prs\t1\tobl\t_\t_
3\tcum\tcum\tADP\t_\tAdpType=Post\t2\tcase\t_\t_
4\tante\tante\tADV\td--------\tAdvType=Tim\t1\tadvmod\t_\tSpaceAfter=No

"""

ITTB = """\
# sent_id = test-s2
# text = essetque aliquod
# reference = ittb-scg-s2102
1-2\tessetque\t_\t_\t_\t_\t_\t_\t_\t_
1\tesset\tsum\tAUX\tN3|modB\tAspect=Imp|InflClass=LatAnom|Mood=Sub|Number=Sing|Person=3|Tense=Past|VerbForm=Fin\t0\troot\t_\t_
2\tque\tque\tCCONJ\tO4\t_\t1\tcc\t_\t_
3\taliquod\taliqui\tDET\tF1\tCase=Nom|Gender=Neut|Number=Sing\t1\tnsubj\t_\t_

"""


def test_reads_a_token_with_every_field_the_issue_asks_for():
    tokens = parse_conllu(PERSEUS, treebank="perseus")

    assert tokens[0] == GoldToken(
        treebank="perseus",
        sent_id="phi0690.phi003.perseus-lat1.tb.xml@196",
        token_id=1,
        form="animo",
        lemma="animus",
        upos="NOUN",
        features={"Case": "Abl", "Gender": "Masc", "Number": "Sing"},
        sentence="animo mecum ante",
        mwt_form=None,
        source="phi0690.phi003.perseus-lat1.tb.xml",
    )


def test_token_without_features_has_an_empty_feature_dict():
    tokens = parse_conllu(ITTB, treebank="ittb")

    assert tokens[1].form == "que"
    assert tokens[1].features == {}


def test_multiword_token_line_is_not_a_token_but_marks_its_words():
    tokens = parse_conllu(PERSEUS, treebank="perseus")

    assert [t.form for t in tokens] == ["animo", "me", "cum", "ante"]
    assert [t.mwt_form for t in tokens] == [None, "mecum", "mecum", None]


def test_enclitic_split_by_the_treebank_is_marked_with_the_surface_word():
    tokens = parse_conllu(ITTB, treebank="ittb")

    assert [(t.form, t.mwt_form) for t in tokens] == [
        ("esset", "essetque"),
        ("que", "essetque"),
        ("aliquod", None),
    ]


def test_every_token_carries_the_full_sentence_text():
    tokens = parse_conllu(ITTB, treebank="ittb")

    assert {t.sentence for t in tokens} == {"essetque aliquod"}


def test_token_ids_are_integers_within_their_sentence():
    tokens = parse_conllu(PERSEUS + ITTB, treebank="mixed")

    assert [(t.sent_id, t.token_id) for t in tokens][-3:] == [
        ("test-s2", 1),
        ("test-s2", 2),
        ("test-s2", 3),
    ]


def test_read_conllu_takes_the_treebank_name_from_the_file_name(tmp_path: Path):
    path = tmp_path / "la_perseus-ud-test.conllu"
    path.write_text(PERSEUS, encoding="utf-8")

    tokens = read_conllu(path)

    assert {t.treebank for t in tokens} == {"perseus"}
    assert len(tokens) == 4


PROIEL = """\
# source = Jerome's Vulgate, Matthew 6
# text = adtendite ne
# sent_id = 12933
1\tadtendite\tattendo\tVERB\tV-\tMood=Imp\t0\troot\t_\tRef=MATT_6.1
2\tne\tne\tSCONJ\tG-\t_\t1\tmark\t_\tRef=MATT_6.1

"""

PERSEUS_TWO_SENTENCES = """\
# newdoc id = phi0959.phi006.perseus-lat1.tb.xml
# sent_id = phi0959.phi006.perseus-lat1.tb.xml@1
# text = animo
1\tanimo\tanimus\tNOUN\tn-s---mb-\tCase=Abl\t0\troot\t_\t_

# sent_id = phi0959.phi006.perseus-lat1.tb.xml@2
# text = ante
1\tante\tante\tADV\td--------\t_\t0\troot\t_\t_

"""


def test_token_source_is_the_proiel_source_comment():
    tokens = parse_conllu(PROIEL, treebank="proiel")

    assert {t.source for t in tokens} == {"Jerome's Vulgate, Matthew 6"}


def test_token_source_carries_a_perseus_newdoc_id_over_later_sentences():
    tokens = parse_conllu(PERSEUS_TWO_SENTENCES, treebank="perseus")

    assert [t.source for t in tokens] == ["phi0959.phi006.perseus-lat1.tb.xml"] * 2


def test_token_source_is_empty_when_the_treebank_gives_none():
    tokens = parse_conllu(ITTB, treebank="ittb")

    assert {t.source for t in tokens} == {""}
