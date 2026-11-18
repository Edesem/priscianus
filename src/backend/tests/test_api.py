"""Tests for the HTTP layer (ADR-005, Decision 1): TestClient, scripted API, in-memory index."""

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient

from priscianus.api.limits import Limits
from priscianus.api.main import app, create_app
from priscianus.api.settings import Settings
from priscianus.morphology.lookup import Analysis
from test_pipeline_loop import ScriptedAPI, answer, make_client
from test_pipeline_verify import claim_json, reply
from test_tutor_drills import PERFECT_3PL, DrillIndex, drills_reply, item
from test_tutor_grade import GradeIndex
from test_verifier_classify import FakeIndex

REGI_DAT = Analysis("rex", "rex", "noun", "regi", {"Case": "Dat", "Number": "Sing"})
REGI_LOC = Analysis("rex", "rex", "noun", "regi", {"Case": "Loc", "Number": "Sing"})
INDEX = FakeIndex([REGI_DAT, REGI_LOC])


def make_limits(tmp_path: Path, **options: Any) -> Limits:
    return Limits(tmp_path / "limits.db", tmp_path / "llm.db", **options)


@pytest.fixture
def make_app(tmp_path: Path) -> Iterator[Callable[..., TestClient]]:
    """Builds a started app (so its lifespan runs) over a scripted API; closes them afterwards.

    `limits` replaces the daily limits (default: the real ones, kept in `tmp_path`).
    """
    with ExitStack() as stack:

        def build(
            api: Any, index: Any = INDEX, *, limits: Limits | None = None, **client_options: Any
        ) -> TestClient:
            client = make_client(tmp_path, api, **client_options)
            limits = limits or make_limits(tmp_path)
            app = create_app(index=index, client=client, limits=limits)
            return stack.enter_context(TestClient(app))

        yield build


class FailingMessages:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    def create(self, **kwargs: Any) -> Any:
        self.calls += 1
        raise self.error


class FailingAPI:
    def __init__(self, error: Exception) -> None:
        self.messages = FailingMessages(error)


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_explain_returns_each_word_with_its_state_and_other_readings(
    make_app: Callable[..., TestClient],
) -> None:
    claim = claim_json("regi", "rex", {"Case": "Dat", "Number": "Sing"}, "NOUN")
    api = ScriptedAPI(reply(claim, text="To the king."))

    response = make_app(api).post("/api/explain", json={"text": "regi"})

    assert response.status_code == 200
    body = response.json()
    assert (body["text"], body["prompt_id"], body["dropped_claims"]) == (
        "To the king.",
        "explain-v1",
        0,
    )
    [word] = body["words"]
    assert word["token"] == "regi"
    assert word["claim"] == {
        "form": "regi",
        "lemma": "rex",
        "upos": "NOUN",
        "features": {"Case": "Dat", "Number": "Sing"},
        "state": "ambiguous",
        "other_readings": [
            {"lemma": "rex", "pos": "noun", "form": "regi", "features": "Case=Loc|Number=Sing"}
        ],
    }


def test_a_word_without_a_claim_is_listed_as_not_explained(
    make_app: Callable[..., TestClient],
) -> None:
    api = ScriptedAPI(reply(text="Nothing."))

    body = make_app(api).post("/api/explain", json={"text": "xyzzy"}).json()

    assert body["words"] == [{"token": "xyzzy", "claim": None, "note": "not_explained"}]


def test_overlong_text_is_refused_before_any_api_call(make_app: Callable[..., TestClient]) -> None:
    api = ScriptedAPI()
    text = " ".join(["arma"] * 26)

    response = make_app(api).post("/api/explain", json={"text": text})

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "invalid_input"
    assert "25 words" in body["message"]
    assert api.messages.calls == []


def test_a_request_without_text_gets_the_same_error_shape(
    make_app: Callable[..., TestClient],
) -> None:
    response = make_app(ScriptedAPI()).post("/api/explain", json={})

    assert response.status_code == 422
    assert set(response.json()) == {"error", "message"}
    assert response.json()["error"] == "invalid_input"


def test_a_model_failure_gives_503_with_a_message(make_app: Callable[..., TestClient]) -> None:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    api = FailingAPI(anthropic.APIConnectionError(request=request))

    response = make_app(api, max_retries=0).post("/api/explain", json={"text": "regi"})

    assert response.status_code == 503
    assert response.json()["error"] == "model_error"
    assert response.json()["message"]


def test_a_reached_spend_cap_gives_503_spend_cap(make_app: Callable[..., TestClient]) -> None:
    response = make_app(ScriptedAPI(), spend_cap_usd=0.0).post(
        "/api/explain", json={"text": "regi"}
    )

    assert response.status_code == 503
    assert response.json()["error"] == "spend_cap"


def test_drills_returns_items_with_a_prompt_and_no_answer_key(
    make_app: Callable[..., TestClient],
) -> None:
    api = ScriptedAPI(drills_reply(item("amo", "verb", PERFECT_3PL)))

    response = make_app(api, DrillIndex()).post(
        "/api/drills", json={"request": "perfect tense of amo", "count": 1}
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": None,
        "shortfall": 0,
        "items": [
            {
                "lemma": "amo",
                "pos": "verb",
                "features": PERFECT_3PL,
                "prompt": "Give the 3rd person plural perfect active indicative of amo.",
            }
        ],
    }


def test_an_impossible_drill_request_returns_the_generators_message(
    make_app: Callable[..., TestClient],
) -> None:
    api = ScriptedAPI(drills_reply(message="Nouns have no person."))

    body = (
        make_app(api, DrillIndex()).post("/api/drills", json={"request": "1st person noun"}).json()
    )

    assert body["items"] == []
    assert body["message"] == "Nouns have no person."


def test_an_empty_drill_request_is_refused_before_any_api_call(
    make_app: Callable[..., TestClient],
) -> None:
    api = ScriptedAPI()

    response = make_app(api, DrillIndex()).post("/api/drills", json={"request": "  "})

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_input"
    assert response.json()["message"]
    assert api.messages.calls == []


def test_asking_for_more_than_ten_items_is_refused(make_app: Callable[..., TestClient]) -> None:
    response = make_app(ScriptedAPI(), DrillIndex()).post(
        "/api/drills", json={"request": "amo", "count": 11}
    )

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_input"


def test_a_drill_request_with_a_wrong_body_says_what_to_send(
    make_app: Callable[..., TestClient],
) -> None:
    response = make_app(ScriptedAPI(), DrillIndex()).post("/api/drills", json={"text": "amo"})

    assert response.status_code == 422
    assert set(response.json()) == {"error", "message"}
    assert "request" in response.json()["message"]


def test_a_garbled_model_answer_for_drills_gives_503_model_error(
    make_app: Callable[..., TestClient],
) -> None:
    api = ScriptedAPI(answer("not json"))

    response = make_app(api, DrillIndex()).post("/api/drills", json={"request": "amo"})

    assert response.status_code == 503
    assert response.json()["error"] == "model_error"


def test_settings_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:5173, https://tutor.example")
    monkeypatch.setenv("MORPHOLOGY_DB", "/data/morphology.db")
    monkeypatch.setenv("LLM_DB", "/data/llm.db")
    monkeypatch.setenv("LIMITS_DB", "/data/limits.db")
    monkeypatch.setenv("DAILY_REQUEST_LIMIT", "5")
    monkeypatch.setenv("IP_DAILY_LIMIT", "7")
    monkeypatch.setenv("DAILY_SPEND_CAP_USD", "1.25")
    monkeypatch.setenv("IP_HASH_SALT", "pepper")

    settings = Settings.from_env()

    assert settings.allowed_origins == ("http://localhost:5173", "https://tutor.example")
    assert settings.morphology_db == Path("/data/morphology.db")
    assert settings.llm_db == Path("/data/llm.db")
    assert settings.limits_db == Path("/data/limits.db")
    assert (settings.daily_request_limit, settings.ip_daily_limit) == (5, 7)
    assert settings.daily_spend_cap_usd == 1.25
    assert settings.ip_hash_salt == "pepper"


def test_an_allowed_origin_may_call_the_api_and_others_may_not(tmp_path: Path) -> None:
    settings = Settings(allowed_origins=("http://localhost:5173",))
    client = TestClient(
        create_app(
            settings,
            index=INDEX,
            client=make_client(tmp_path, ScriptedAPI()),
            limits=make_limits(tmp_path),
        )
    )
    preflight = {
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }

    allowed = client.options(
        "/api/explain", headers={"Origin": "http://localhost:5173", **preflight}
    )
    other = client.options("/api/explain", headers={"Origin": "https://evil.example", **preflight})

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in other.headers


def test_grade_ignores_an_answer_key_sent_by_the_browser(
    make_app: Callable[..., TestClient],
) -> None:
    body = {
        "lemma": "amo",
        "pos": "verb",
        "features": PERFECT_3PL,
        "answer": "amaverunt",
        "accepted": ["blorp"],
    }
    wrong = {**body, "answer": "blorp"}
    app_client = make_app(ScriptedAPI(), DrillIndex())

    right = app_client.post("/api/grade", json=body)
    tampered = app_client.post("/api/grade", json=wrong)

    assert right.status_code == 200
    assert right.json()["correct"] is True
    assert right.json()["accepted"] == ["amāvērunt", "amārunt", "amāvēre"]
    assert tampered.json()["correct"] is False


def test_grade_makes_no_model_call_and_refuses_an_unanswerable_item(
    make_app: Callable[..., TestClient],
) -> None:
    api = ScriptedAPI()
    app_client = make_app(api, DrillIndex())
    item_body = {"lemma": "amo", "pos": "verb", "answer": "amat"}

    good = app_client.post("/api/grade", json={**item_body, "features": PERFECT_3PL})
    bad = app_client.post("/api/grade", json={**item_body, "features": {"Person": "3"}})

    assert good.status_code == 200
    assert bad.status_code == 422
    assert bad.json()["error"] == "invalid_input"
    assert api.messages.calls == []


FEEDBACK_BODY = {"lemma": "amo", "pos": "verb", "features": PERFECT_3PL, "answer": "amavit"}


def test_feedback_cannot_flip_the_grade(make_app: Callable[..., TestClient]) -> None:
    api = ScriptedAPI(reply(text="Correct! Well done."))

    response = make_app(api, GradeIndex()).post("/api/feedback", json=FEEDBACK_BODY)

    body = response.json()
    assert response.status_code == 200
    assert body["grade"]["correct"] is False  # the index decides, whatever the text says
    assert body["feedback"]["text"] == "Correct! Well done."
    assert body["feedback_error"] is None


def test_a_failed_feedback_call_still_returns_the_grade(
    make_app: Callable[..., TestClient],
) -> None:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    api = FailingAPI(anthropic.APIConnectionError(request=request))

    response = make_app(api, GradeIndex(), max_retries=0).post("/api/feedback", json=FEEDBACK_BODY)

    body = response.json()
    assert response.status_code == 200
    assert body["grade"]["correct"] is False
    assert body["feedback"] is None
    assert body["feedback_error"]["error"] == "model_error"


def test_a_reached_spend_cap_still_returns_the_grade(make_app: Callable[..., TestClient]) -> None:
    response = make_app(ScriptedAPI(), GradeIndex(), spend_cap_usd=0.0).post(
        "/api/feedback", json=FEEDBACK_BODY
    )

    body = response.json()
    assert response.status_code == 200
    assert body["grade"]["correct"] is False
    assert body["feedback_error"]["error"] == "spend_cap"


def test_a_claim_in_feedback_that_the_index_contradicts_is_marked_disputed(
    make_app: Callable[..., TestClient],
) -> None:
    wrong = claim_json("amavit", "amo", {**PERFECT_3PL})  # the index says "amavit" is singular
    api = ScriptedAPI(reply(wrong, text="Amavit is plural."))

    response = make_app(api, GradeIndex()).post("/api/feedback", json=FEEDBACK_BODY)

    [claim] = response.json()["feedback"]["claims"]
    assert claim["state"] == "disputed"
    assert "Number=Sing" in claim["other_readings"][0]["features"]


# --- Daily limits (ADR-005, Decision 7) ---

EXPLAIN = {"text": "regi"}
ME = {"X-Client-Id": "browser-1"}
REGI_REPLY = reply(claim_json("regi", "rex", {"Case": "Dat", "Number": "Sing"}, "NOUN"))


def test_the_21st_request_is_refused_with_when_it_resets_and_the_next_day_is_allowed(
    make_app: Callable[..., TestClient], tmp_path: Path
) -> None:
    clock = [datetime(2026, 11, 18, 23, 59, tzinfo=UTC)]
    limits = make_limits(tmp_path, request_limit=20, now=lambda: clock[0])
    client = make_app(ScriptedAPI(REGI_REPLY), limits=limits)
    headers = ME

    for _ in range(20):
        assert client.post("/api/explain", json=EXPLAIN, headers=headers).status_code == 200
    refused = client.post("/api/explain", json=EXPLAIN, headers=headers)

    assert refused.status_code == 429
    assert refused.json()["error"] == "daily_limit"
    assert refused.json()["resets_at"] == "2026-11-19T00:00:00+00:00"
    assert refused.headers["Retry-After"] == "60"

    clock[0] = datetime(2026, 11, 19, 0, 1, tzinfo=UTC)
    assert client.post("/api/explain", json=EXPLAIN, headers=headers).status_code == 200


def test_each_browser_has_its_own_count_but_one_ip_address_cannot_get_past_its_own(
    make_app: Callable[..., TestClient], tmp_path: Path
) -> None:
    limits = make_limits(tmp_path, request_limit=1, ip_limit=2, salt="pepper")
    client = make_app(ScriptedAPI(REGI_REPLY), limits=limits)

    def ask(browser: str) -> int:
        headers = {"X-Client-Id": browser, "Fly-Client-IP": "203.0.113.9"}
        return client.post("/api/explain", json=EXPLAIN, headers=headers).status_code

    assert ask("a") == 200
    assert ask("a") == 429  # browser a used its one request
    assert ask("b") == 200
    assert ask("c") == 429  # a new ID does not help: the IP has used its two

    with sqlite3.connect(tmp_path / "limits.db") as db:
        stored = " ".join(row[0] for row in db.execute("SELECT subject FROM usage"))
    assert "203.0.113.9" not in stored  # only a salted hash of the IP is kept


def test_counts_survive_a_restart(make_app: Callable[..., TestClient], tmp_path: Path) -> None:
    first = make_app(ScriptedAPI(REGI_REPLY), limits=make_limits(tmp_path, request_limit=1))
    assert first.post("/api/explain", json=EXPLAIN, headers=ME).status_code == 200

    # A new app over the same limits.db, as after a restart.
    second = make_app(ScriptedAPI(REGI_REPLY), limits=make_limits(tmp_path, request_limit=1))

    assert second.post("/api/explain", json=EXPLAIN, headers=ME).status_code == 429


def test_grading_is_not_counted(make_app: Callable[..., TestClient], tmp_path: Path) -> None:
    api = ScriptedAPI(REGI_REPLY)
    client = make_app(api, GradeIndex(), limits=make_limits(tmp_path, request_limit=1))

    for _ in range(3):
        assert client.post("/api/grade", json=FEEDBACK_BODY, headers=ME).status_code == 200

    # The one request is still there.
    assert client.post("/api/explain", json=EXPLAIN, headers=ME).status_code == 200


def test_a_failed_model_call_gives_the_request_back(
    make_app: Callable[..., TestClient], tmp_path: Path
) -> None:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    api = FailingAPI(anthropic.APIConnectionError(request=request))
    limits = make_limits(tmp_path, request_limit=1)
    client = make_app(api, limits=limits, max_retries=0)

    first = client.post("/api/explain", json=EXPLAIN, headers=ME)
    second = client.post("/api/explain", json=EXPLAIN, headers=ME)

    assert (first.status_code, second.status_code) == (503, 503)  # never 429


def test_a_reached_daily_spend_cap_refuses_before_the_model_is_called(
    make_app: Callable[..., TestClient], tmp_path: Path
) -> None:
    api = ScriptedAPI(REGI_REPLY)
    client = make_app(api, limits=make_limits(tmp_path, spend_cap_usd=0.50))
    # Today's calls, as the LLMClient logs them: $0.60 already spent.
    with sqlite3.connect(tmp_path / "llm.db") as db:
        db.execute(
            "INSERT INTO call_log(model, prompt_hash, input_tokens, cache_read_tokens,"
            " cache_write_tokens, output_tokens, usd, latency_ms, cache_hit)"
            " VALUES ('m', 'h', 0, 0, 0, 0, 0.60, 0, 0)"
        )

    response = client.post("/api/explain", json=EXPLAIN, headers=ME)

    assert response.status_code == 503
    assert response.json()["error"] == "spend_cap"
    assert api.messages.calls == []


def test_feedback_over_the_daily_limit_still_returns_the_grade(
    make_app: Callable[..., TestClient], tmp_path: Path
) -> None:
    api = ScriptedAPI(reply(text="It is singular."))
    client = make_app(api, GradeIndex(), limits=make_limits(tmp_path, request_limit=1))
    client.post("/api/feedback", json=FEEDBACK_BODY, headers=ME)

    response = client.post("/api/feedback", json=FEEDBACK_BODY, headers=ME)

    body = response.json()
    assert response.status_code == 200
    assert body["grade"]["correct"] is False
    assert body["feedback"] is None
    assert body["feedback_error"]["error"] == "daily_limit"
    assert body["feedback_error"]["resets_at"]
