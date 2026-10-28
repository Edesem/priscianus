from pathlib import Path

import pytest

from evals.__main__ import main
from evals.parse_set import ManifestExistsError, load_parse_set

PERSEUS = """\
# newdoc id = phi0959.phi006.perseus-lat1.tb.xml
# sent_id = p@1
# text = Arma virumque cano
1\tArma\tarma\tNOUN\t_\tCase=Nom|Gender=Neut|Number=Plur\t3\tobj\t_\t_
2-3\tvirumque\t_\t_\t_\t_\t_\t_\t_\t_
2\tvirum\tvir\tNOUN\t_\tCase=Acc|Gender=Masc|Number=Sing\t3\tobj\t_\t_
3\tque\tque\tCCONJ\t_\t_\t2\tcc\t_\t_
4\tcano\tcano\tVERB\t_\tMood=Ind|Number=Sing|Person=1|Tense=Pres|VerbForm=Fin|Voice=Act\t0\troot\t_\t_

# sent_id = p@2
# text = Arma cano
1\tArma\tarma\tNOUN\t_\tCase=Nom|Gender=Neut|Number=Plur\t2\tobj\t_\t_
2\tcano\tcano\tVERB\t_\tMood=Ind|Number=Sing|Person=1|Tense=Pres|VerbForm=Fin|Voice=Act\t0\troot\t_\t_

"""

TRAINS = (
    "la_perseus-ud-train.conllu",
    "la_proiel-ud-train.conllu",
    "la_ittb-ud-train.conllu",
    "la_llct-ud-train.conllu",
    "la_udante-ud-train.conllu",
    "la_circse-ud-train.conllu",
)


@pytest.fixture
def ud_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "ud"
    directory.mkdir()
    for name in TRAINS:
        (directory / name).write_text(PERSEUS, encoding="utf-8")
    (directory / "la_perseus-ud-test.conllu").write_text(PERSEUS, encoding="utf-8")
    (directory / "la_proiel-ud-test.conllu").write_text("", encoding="utf-8")
    (directory / "la_ittb-ud-test.conllu").write_text("", encoding="utf-8")
    return directory


def args(ud_dir: Path, out: Path, *extra: str) -> list[str]:
    return [
        "build-set", "--set", "parse", "--version", "v1",
        "--ud-dir", str(ud_dir), "--out-dir", str(out), *extra,
    ]  # fmt: skip


def test_build_set_writes_a_manifest_that_loads_and_prints_the_summary(ud_dir, tmp_path, capsys):
    assert main(args(ud_dir, tmp_path / "sets")) == 0

    items = load_parse_set(tmp_path / "sets" / "parse-v1.jsonl", ud_dir)
    # One item per sentence, and never a word inside a multiword token.
    assert sorted(i.token.sent_id for i in items) == ["p@1", "p@2"]
    assert not {"virum", "que"} & {i.token.form for i in items}
    assert "| Slice | Class | Band | Test | Dev |" in capsys.readouterr().out


def test_build_set_refuses_to_overwrite_a_frozen_manifest(ud_dir, tmp_path):
    main(args(ud_dir, tmp_path / "sets"))

    with pytest.raises(ManifestExistsError):
        main(args(ud_dir, tmp_path / "sets"))


def test_build_set_needs_all_six_train_splits_for_the_frequency_bands(ud_dir, tmp_path):
    (ud_dir / "la_llct-ud-train.conllu").unlink()

    with pytest.raises(FileNotFoundError, match="make eval-data"):
        main(args(ud_dir, tmp_path / "sets"))


def test_the_same_seed_builds_the_same_manifest(ud_dir, tmp_path):
    main(args(ud_dir, tmp_path / "sets", "--seed", "5"))
    main(args(ud_dir, tmp_path / "other", "--seed", "5"))

    assert (tmp_path / "sets" / "parse-v1.jsonl").read_text() == (
        tmp_path / "other" / "parse-v1.jsonl"
    ).read_text()
