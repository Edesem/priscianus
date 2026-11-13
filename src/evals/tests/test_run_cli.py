import hashlib
import json
import sqlite3

import pytest

from evals.__main__ import main
from evals.tools_prompt import PROMPT_ID as TOOLS_PROMPT_ID
from tests.test_run import CONLLU, FakeIndex, FakeMessages, client_for
from tests.test_run_tools import ToolCallingMessages


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
    # One call at a time: with parallel calls all of them can start before the first one's
    # cost is recorded, and then the cap is never reached.
    code, _, _ = run_cli(workspace, "--max-cost", "0.0001", "--concurrency", "1")
    assert code == 1
    assert "stopped: max cost" in capsys.readouterr().out


def test_cli_runs_tools_mode_with_the_same_options_as_raw(workspace, capsys):
    tmp_path, manifest, ud = workspace
    api = type("Api", (), {"messages": ToolCallingMessages()})()
    code = main(
        [
            "run",
            "--mode",
            "tools",
            "--set",
            "parse",
            "--limit",
            "2",
            "--max-cost",
            "5",
            "--concurrency",
            "2",
            "--manifest",
            str(manifest),
            "--ud-dir",
            str(ud),
            "--store",
            str(tmp_path / "evals.db"),
            "--llm-db",
            str(tmp_path / "llm.db"),
        ],
        make_client=lambda *, spend_cap_usd, db_path: client_for(
            tmp_path, api, spend_cap_usd=spend_cap_usd
        ),
        index=FakeIndex(),
    )
    assert code == 0
    assert "answered 2" in capsys.readouterr().out
    assert len(api.messages.calls) == 4
    assert sqlite3.connect(tmp_path / "evals.db").execute(
        "SELECT mode, prompt_id FROM runs"
    ).fetchall() == [("tools", TOOLS_PROMPT_ID)]


def test_run_rejects_a_mode_that_does_not_exist_yet(workspace):
    with pytest.raises(SystemExit):
        main(["run", "--mode", "verified", "--set", "parse"])


@pytest.mark.parametrize("value", ["0", "-2"])
def test_concurrency_must_be_positive_and_no_run_is_opened(workspace, value):
    with pytest.raises(SystemExit):
        run_cli(workspace, "--concurrency", value)
    assert not (workspace[0] / "evals.db").exists()


def report_cli(workspace, *args, **kwargs):
    tmp_path, manifest, ud = workspace
    return main(
        [
            "report",
            *args,
            "--store",
            str(tmp_path / "evals.db"),
            "--manifest",
            str(kwargs.get("manifest", manifest)),
            "--ud-dir",
            str(ud),
        ],
        index=FakeIndex(),
    )


def test_report_prints_the_markdown_for_a_run(workspace, capsys):
    run_cli(workspace)
    capsys.readouterr()
    assert report_cli(workspace, "1") == 0
    out = capsys.readouterr().out
    assert out.startswith("# Eval report")
    assert "| Items | 4 |" in out


def test_report_shows_the_index_ceiling_from_the_manifest(workspace, capsys):
    run_cli(workspace)
    capsys.readouterr()
    report_cli(workspace, "1")
    assert "| Index matches gold (ceiling) |" in capsys.readouterr().out


def test_report_without_a_manifest_leaves_the_ceiling_out_and_says_so(workspace, capsys):
    tmp_path, _, _ = workspace
    run_cli(workspace)
    capsys.readouterr()
    assert report_cli(workspace, "1", manifest=tmp_path / "missing.jsonl") == 0
    captured = capsys.readouterr()
    assert "Index matches gold" not in captured.out
    assert "no ceiling" in captured.err


def test_report_can_write_to_a_file(workspace, capsys):
    tmp_path, _, _ = workspace
    run_cli(workspace)
    capsys.readouterr()
    target = tmp_path / "out" / "report.md"
    assert report_cli(workspace, "1", "--out", str(target)) == 0
    assert target.read_text(encoding="utf-8").startswith("# Eval report")
    assert capsys.readouterr().out == ""


def test_report_for_a_run_that_does_not_exist_fails(workspace, capsys):
    run_cli(workspace)
    capsys.readouterr()
    assert report_cli(workspace, "99") == 2
    assert "no run 99" in capsys.readouterr().err
