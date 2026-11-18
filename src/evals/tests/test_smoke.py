"""#114: the smoke set and the pass/fail check that CI runs on every PR."""

import json
from collections import Counter

import pytest

from evals import smoke
from evals.__main__ import main
from evals.parse_set import ManifestExistsError, cell_quotas
from evals.report import Headline
from evals.smoke import Thresholds, build_smoke_set, check_smoke
from tests.test_run import client_for
from tests.test_run_cli import workspace  # noqa: F401  (a pytest fixture)
from tests.test_run_verified import RepairIndex, VerifiedMessages


def parse_rows():
    """A stand-in for parse-v1, laid out as the real one is: closed classes carry a band label
    but are not drawn by it, and Ecclesiastical verbs have no rare words (their places went to
    the next band up)."""
    rows = []
    for slice_name in ("Classical", "Ecclesiastical"):
        for (pos_class, band), n in cell_quotas(75).items():
            labelled = band or "top1k"
            if (slice_name, pos_class, band) == ("Ecclesiastical", "verb", "rare"):
                labelled = "1k-10k"  # these words sit in the next band up
            for i in range(n):
                rows.append(
                    {
                        "item_id": f"x/{slice_name}/{pos_class}/{band}/{i}",
                        "split": "dev",
                        "slice": slice_name,
                        "pos_class": pos_class,
                        "freq_band": labelled,
                    }
                )
    rows.append({"item_id": "x/test/1", "split": "test", "slice": "Classical"})
    return rows


@pytest.fixture
def parse_manifest(tmp_path):
    path = tmp_path / "parse-v1.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in parse_rows()), encoding="utf-8")
    return path


def read(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_smoke_set_is_50_dev_items_stratified_like_the_parse_set(parse_manifest, tmp_path):
    out = build_smoke_set(parse_manifest, tmp_path / "out", version="v1")
    rows = read(out)
    assert out.name == "smoke-v1.jsonl"
    assert len(rows) == 50
    assert {r["split"] for r in rows} == {"dev"}
    quotas = cell_quotas(25)
    for slice_name in ("Classical", "Ecclesiastical"):
        in_slice = [r for r in rows if r["slice"] == slice_name]
        by_class = Counter(r["pos_class"] for r in in_slice)
        expected: Counter[str] = Counter()
        for (pos_class, _), n in quotas.items():
            expected[pos_class] += n
        assert by_class == expected
    # Ecclesiastical verbs have no rare words, so their 2 rare places go to the next band up.
    verbs = Counter(
        r["freq_band"] for r in rows if r["slice"] == "Ecclesiastical" and r["pos_class"] == "verb"
    )
    assert verbs == {"top1k": 4, "1k-10k": 5}
    # Rows are copied whole from the parse set, so no treebank text can come in.
    assert all(row in parse_rows() for row in rows)


def test_smoke_set_is_the_same_every_time_and_is_never_overwritten(parse_manifest, tmp_path):
    first = build_smoke_set(parse_manifest, tmp_path / "a", version="v1")
    again = build_smoke_set(parse_manifest, tmp_path / "b", version="v1")
    assert first.read_text() == again.read_text()
    with pytest.raises(ManifestExistsError):
        build_smoke_set(parse_manifest, tmp_path / "a", version="v1")


def headline(*, exact=45, contradicted=1, format_failures=0):
    return Headline(
        n=50,
        exact=exact,
        lemma=50,
        format_failures=format_failures,
        verified=0,
        ambiguous=0,
        contradicted=contradicted,
        unknown=0,
        features={},
        usd=0.0,
        latency_p50_ms=None,
        latency_p95_ms=None,
    )


LIMITS = Thresholds(max_hallucinations=4, min_exact=42)


def test_a_run_at_the_limits_passes():
    assert check_smoke(headline(contradicted=4, exact=42), LIMITS) == []


@pytest.mark.parametrize(
    ("worse", "word"),
    [
        ({"contradicted": 5}, "hallucination"),
        ({"exact": 41}, "exact match"),
        ({"format_failures": 1}, "schema"),
    ],
)
def test_crossing_any_one_limit_fails(worse, word):
    failures = check_smoke(headline(**worse), LIMITS)
    assert len(failures) == 1
    assert word in failures[0]


@pytest.fixture
def smoke_run(workspace, monkeypatch):  # noqa: F811
    """Run `smoke` on the 4 dev items of the five-item workspace with a fake model.

    The fake gets *Gallia*, *est* and *omnis* right (3 exact) and *divisa* wrong (1 disputed)."""
    tmp_path, manifest, ud = workspace
    smoke_manifest = tmp_path / "smoke-v1.jsonl"
    smoke_manifest.write_text(manifest.read_text(encoding="utf-8"), encoding="utf-8")
    api = type("Api", (), {"messages": VerifiedMessages()})()

    def run(thresholds):
        monkeypatch.setattr(smoke, "THRESHOLDS", thresholds)
        code = main(
            [
                "smoke",
                "--manifest",
                str(smoke_manifest),
                "--ud-dir",
                str(ud),
                "--store",
                str(tmp_path / "evals.db"),
                "--llm-db",
                str(tmp_path / "llm.db"),
            ],
            make_client=lambda *, spend_cap_usd, db_path: client_for(tmp_path, api),
            index=RepairIndex(),
        )
        return code

    run.api = api
    run.tmp_path = tmp_path
    return run


def test_smoke_passes_under_the_threshold(smoke_run, capsys):
    assert smoke_run(Thresholds(max_hallucinations=1, min_exact=3)) == 0
    assert "PASS" in capsys.readouterr().out


def test_smoke_exits_1_above_the_threshold(smoke_run, capsys):
    assert smoke_run(Thresholds(max_hallucinations=0, min_exact=3)) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "hallucination" in out


def test_a_second_run_with_the_same_prompts_makes_no_model_calls(smoke_run):
    limits = Thresholds(max_hallucinations=1, min_exact=3)
    smoke_run(limits)
    asked = len(smoke_run.api.messages.calls)
    assert asked > 0
    # A fresh results database (as in CI), but the same response cache.
    (smoke_run.tmp_path / "evals.db").unlink()
    smoke_run(limits)
    assert len(smoke_run.api.messages.calls) == asked
