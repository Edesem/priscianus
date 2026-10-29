import os

from evals.env import load_env


def test_sets_variables_from_the_file(tmp_path, monkeypatch):
    monkeypatch.delenv("PRISCIANUS_TEST_KEY", raising=False)
    path = tmp_path / ".env"
    path.write_text("PRISCIANUS_TEST_KEY=abc123\n", encoding="utf-8")

    load_env(path)

    assert os.environ["PRISCIANUS_TEST_KEY"] == "abc123"


def test_keeps_a_variable_that_is_already_set(tmp_path, monkeypatch):
    monkeypatch.setenv("PRISCIANUS_TEST_KEY", "from-shell")
    path = tmp_path / ".env"
    path.write_text("PRISCIANUS_TEST_KEY=from-file\n", encoding="utf-8")

    load_env(path)

    assert os.environ["PRISCIANUS_TEST_KEY"] == "from-shell"


def test_skips_comments_and_blank_lines_and_strips_quotes(tmp_path, monkeypatch):
    monkeypatch.delenv("PRISCIANUS_TEST_A", raising=False)
    monkeypatch.delenv("PRISCIANUS_TEST_B", raising=False)
    path = tmp_path / ".env"
    path.write_text(
        "# a comment\n\nPRISCIANUS_TEST_A=\"quoted value\"\nexport PRISCIANUS_TEST_B='single'\n",
        encoding="utf-8",
    )

    load_env(path)

    assert os.environ["PRISCIANUS_TEST_A"] == "quoted value"
    assert os.environ["PRISCIANUS_TEST_B"] == "single"


def test_a_missing_file_is_not_an_error(tmp_path):
    load_env(tmp_path / "absent.env")
