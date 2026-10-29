import hashlib
import json
import sqlite3

import pytest

from evals.__main__ import main
from tests.test_run import CONLLU, FakeIndex, FakeMessages, client_for


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.fixture
def workspace(tmp_path):
    ud = tmp_path / "ud"
    ud.mkdir()
    (ud / "la_perseus-ud-test.conllu").write_text(CONLLU, encoding="utf-8")
    sentence = "Gallia est omnis divisa in partes tres"
    forms = {1: "Gallia", 2: "est", 3: "omnis", 4: "divisa", 5: "in"}
    rows = [
        {
            "item_id": f"perseus/s1/{n}",
            "split": "dev" if n < 5 else "test",
            "treebank": "perseus",
            "ud_release": "r2.18",
            "file": "la_perseus-ud-test.conllu",
            "sent_id": "s1",
            "word_id": n,
            "slice": "Classical",
            "source": "perseus",
            "pos_class": "verb",
            "freq_band": "top1k",
            "form_sha256": sha(form),
            "sentence_sha256": sha(sentence),
        }
        for n, form in forms.items()
    ]
    manifest = tmp_path / "parse-v1.jsonl"
    manifest.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return tmp_path, manifest, ud


def run_cli(workspace, *extra, factory=None):
    tmp_path, manifest, ud = workspace
    api = type("Api", (), {"messages": FakeMessages()})()
    caps = []

    def make_client(*, spend_cap_usd, db_path):
        caps.append(spend_cap_usd)
        return client_for(tmp_path, api, spend_cap_usd=spend_cap_usd)

    code = main(
        [
            "run",
            "--mode",
            "raw",
            "--set",
            "parse",
            "--manifest",
            str(manifest),
            "--ud-dir",
            str(ud),
            "--store",
            str(tmp_path / "evals.db"),
            "--llm-db",
            str(tmp_path / "llm.db"),
            *extra,
        ],
        make_client=factory or make_client,
        index=FakeIndex(),
    )
    return code, api, caps


def test_run_answers_the_dev_split_by_default(workspace, capsys):
    code, api, _ = run_cli(workspace)
    assert code == 0
    assert len(api.messages.calls) == 4
    assert "answered 4" in capsys.readouterr().out


def test_run_takes_a_split_and_a_limit(workspace):
    _, api, _ = run_cli(workspace, "--split", "test")
    assert len(api.messages.calls) == 1
    _, api, _ = run_cli(workspace, "--split", "dev", "--limit", "2")
    assert len(api.messages.calls) == 2


def test_run_stores_the_run_with_the_model_and_commit(workspace):
    run_cli(workspace, "--model", "claude-sonnet-5-5")
    row = (
        sqlite3.connect(workspace[0] / "evals.db")
        .execute("SELECT model, mode, set_name, split, git_commit FROM runs")
        .fetchone()
    )
    assert row[:4] == ("claude-sonnet-5-5", "raw", "parse", "dev")
    assert row[4]


def test_run_reports_a_rerun_as_skipped(workspace, capsys):
    run_cli(workspace)
    capsys.readouterr()
    _, api, _ = run_cli(workspace)
    assert len(api.messages.calls) == 0
    assert "skipped 4" in capsys.readouterr().out


def test_max_cost_is_the_client_spend_cap(workspace):
    _, _, caps = run_cli(workspace, "--max-cost", "1.50")
    assert caps == [1.5]


def test_max_cost_is_what_is_left_after_an_earlier_session(workspace):
    run_cli(workspace, "--limit", "1")  # $0.00015
    _, _, caps = run_cli(workspace, "--max-cost", "1.50")
    assert caps[0] == pytest.approx(1.5 - 0.00015)


def test_without_max_cost_there_is_no_cap(workspace):
    _, _, caps = run_cli(workspace)
    assert caps == [None]


def test_run_exits_non_zero_when_stopped_by_the_cost_cap(workspace, capsys):
    code, _, _ = run_cli(workspace, "--max-cost", "0.0001")
    assert code == 1
    assert "stopped: max cost" in capsys.readouterr().out


def test_run_only_supports_the_raw_mode_on_the_parse_set(workspace):
    tmp_path, manifest, ud = workspace
    with pytest.raises(SystemExit):
        main(["run", "--mode", "tools", "--set", "parse"])


@pytest.mark.parametrize("value", ["0", "-2"])
def test_concurrency_must_be_positive_and_no_run_is_opened(workspace, value):
    with pytest.raises(SystemExit):
        run_cli(workspace, "--concurrency", value)
    assert not (workspace[0] / "evals.db").exists()
