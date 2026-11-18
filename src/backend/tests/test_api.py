"""Tests for the HTTP layer (ADR-005, Decision 1): TestClient, scripted API, in-memory index."""

from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient

from priscianus.api.main import app, create_app
from priscianus.api.settings import Settings
from priscianus.morphology.lookup import Analysis
from test_pipeline_loop import ScriptedAPI, answer, make_client
from test_pipeline_verify import claim_json, reply
from test_tutor_drills import PERFECT_3PL, DrillIndex, drills_reply, item
from test_verifier_classify import FakeIndex

REGI_DAT = Analysis("rex", "rex", "noun", "regi", {"Case": "Dat", "Number": "Sing"})
REGI_LOC = Analysis("rex", "rex", "noun", "regi", {"Case": "Loc", "Number": "Sing"})
INDEX = FakeIndex([REGI_DAT, REGI_LOC])


@pytest.fixture
def make_app(tmp_path: Path) -> Iterator[Callable[..., TestClient]]:
    """Builds a started app (so its lifespan runs) over a scripted API; closes them afterwards."""
    with ExitStack() as stack:

        def build(api: Any, index: Any = INDEX, **client_options: Any) -> TestClient:
            client = make_client(tmp_path, api, **client_options)
            return stack.enter_context(TestClient(create_app(index=index, client=client)))

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

    settings = Settings.from_env()

    assert settings.allowed_origins == ("http://localhost:5173", "https://tutor.example")
    assert settings.morphology_db == Path("/data/morphology.db")
    assert settings.llm_db == Path("/data/llm.db")


def test_an_allowed_origin_may_call_the_api_and_others_may_not(tmp_path: Path) -> None:
    settings = Settings(allowed_origins=("http://localhost:5173",))
    client = TestClient(
        create_app(settings, index=INDEX, client=make_client(tmp_path, ScriptedAPI()))
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
