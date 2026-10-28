import json
from pathlib import Path

import pytest

from evals.gold import parse_conllu
from evals.parse_set import (
    Item,
    ManifestExistsError,
    ManifestMismatchError,
    Sample,
    load_parse_set,
    summary_table,
    write_manifest,
)

CONLLU = """\
# newdoc id = phi0959.phi006.perseus-lat1.tb.xml
# sent_id = phi0959.phi006.perseus-lat1.tb.xml@1
# text = Arma virumque cano
1\tArma\tarma\tNOUN\tn-p---nn-\tCase=Nom|Gender=Neut|Number=Plur\t3\tobj\t_\t_
2\tvirum\tvir\tNOUN\tn-s---ma-\tCase=Acc|Gender=Masc|Number=Sing\t3\tobj\t_\t_
3\tcano\tcano\tVERB\tv1spia---\tMood=Ind|Number=Sing|Person=1|Tense=Pres|VerbForm=Fin|Voice=Act\t0\troot\t_\t_

"""


def write_ud(directory: Path, text: str = CONLLU) -> None:
    (directory / "la_perseus-ud-test.conllu").write_text(text, encoding="utf-8")


def sample_of(ud_dir: Path) -> Sample:
    tokens = parse_conllu(CONLLU, treebank="perseus")
    items = [
        Item("test", tokens[2], "Classical", tokens[2].source, "verb", "top1k"),
        Item("dev", tokens[0], "Classical", tokens[0].source, "noun", "rare"),
    ]
    return Sample(items, {"Classical|verb|top1k": 12}, {})


def build(tmp_path: Path, **overrides):
    ud = tmp_path / "ud"
    ud.mkdir(exist_ok=True)
    write_ud(ud)
    out = tmp_path / "sets"
    kwargs = dict(
        version="v1", seed=1, sizes={"test": 1, "dev": 1}, ud_dir=ud, out_dir=out, release="r2.18"
    )
    kwargs.update(overrides)
    manifest = write_manifest(sample_of(ud), **kwargs)
    return ud, out, manifest


def test_the_manifest_holds_ids_and_strata_but_no_treebank_text(tmp_path):
    _, _, manifest = build(tmp_path)

    rows = [json.loads(line) for line in manifest.read_text().splitlines()]
    assert rows[0] == {
        "item_id": "perseus/phi0959.phi006.perseus-lat1.tb.xml@1/3",
        "split": "test",
        "treebank": "perseus",
        "ud_release": "r2.18",
        "file": "la_perseus-ud-test.conllu",
        "sent_id": "phi0959.phi006.perseus-lat1.tb.xml@1",
        "word_id": 3,
        "slice": "Classical",
        "source": "phi0959.phi006.perseus-lat1.tb.xml",
        "pos_class": "verb",
        "freq_band": "top1k",
        "form_sha256": rows[0]["form_sha256"],
        "sentence_sha256": rows[0]["sentence_sha256"],
    }
    text = manifest.read_text()
    for leaked in ("Arma", "virumque", "cano", "arma"):
        assert leaked not in text


def test_the_meta_file_records_how_the_set_was_built(tmp_path):
    ud, out, manifest = build(tmp_path)

    meta = json.loads(manifest.with_name("parse-v1.meta.json").read_text())

    assert meta["seed"] == 1
    assert meta["sizes"] == {"test": 1, "dev": 1}
    assert meta["ud_release"] == "r2.18"
    assert meta["candidate_counts"] == {"Classical|verb|top1k": 12}
    assert set(meta["file_sha256"]) == {"la_perseus-ud-test.conllu"}
    assert meta["item_count"] == 2


def test_a_committed_manifest_is_never_overwritten(tmp_path):
    build(tmp_path)

    with pytest.raises(ManifestExistsError, match="parse-v2"):
        build(tmp_path)


def test_the_loader_resolves_the_manifest_against_the_treebank_files(tmp_path):
    ud, _, manifest = build(tmp_path)

    items = load_parse_set(manifest, ud)

    assert [(i.split, i.token.form, i.token.sentence, i.pos_class) for i in items] == [
        ("test", "cano", "Arma virumque cano", "verb"),
        ("dev", "Arma", "Arma virumque cano", "noun"),
    ]


def test_the_loader_fails_loudly_when_a_sentence_changed(tmp_path):
    ud, _, manifest = build(tmp_path)
    write_ud(ud, CONLLU.replace("# text = Arma virumque cano", "# text = Arma virumque canto"))

    with pytest.raises(ManifestMismatchError, match="sentence"):
        load_parse_set(manifest, ud)


def test_the_loader_fails_loudly_when_a_form_changed(tmp_path):
    ud, _, manifest = build(tmp_path)
    write_ud(ud, CONLLU.replace("3\tcano\tcano", "3\tcanto\tcano"))

    with pytest.raises(ManifestMismatchError, match="form"):
        load_parse_set(manifest, ud)


def test_the_loader_fails_loudly_when_an_item_is_gone(tmp_path):
    ud, _, manifest = build(tmp_path)
    write_ud(ud, CONLLU.replace("@1", "@9"))

    with pytest.raises(ManifestMismatchError, match="not in"):
        load_parse_set(manifest, ud)


def test_the_loader_fails_loudly_when_the_treebank_file_is_missing(tmp_path):
    ud, _, manifest = build(tmp_path)
    (ud / "la_perseus-ud-test.conllu").unlink()

    with pytest.raises(ManifestMismatchError, match="make eval-data"):
        load_parse_set(manifest, ud)


def test_the_summary_counts_items_per_stratum_and_split(tmp_path):
    ud, _, manifest = build(tmp_path)

    table = summary_table(load_parse_set(manifest, ud))

    assert "| Classical | noun | rare | 0 | 1 |" in table
    assert "| Classical | verb | top1k | 1 | 0 |" in table
    assert table.splitlines()[0] == "| Slice | Class | Band | Test | Dev |"
