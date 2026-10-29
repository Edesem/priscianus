import sqlite3
from pathlib import Path

import pytest
from anthropic.types import Message, TextBlock, Usage

from priscianus.llm.client import LLMClient
from priscianus.llm.config import HAIKU, SONNET


class FakeMessages:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply


class FakeAnthropic:
    def __init__(self, *replies):
        self.messages = FakeMessages(replies or [message("ok")])


def message(text="ok", *, input_tokens=100, output_tokens=20, cache_read=0, cache_write=0):
    return Message(
        id="msg_1",
        type="message",
        role="assistant",
        model=HAIKU,
        content=[TextBlock(type="text", text=text)],
        stop_reason="end_turn",
        stop_sequence=None,
        usage=Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=cache_write,
        ),
    )


def make(tmp_path: Path, fake: FakeAnthropic, **kwargs) -> LLMClient:
    return LLMClient(fake, db_path=tmp_path / "llm.db", **kwargs)


def log_rows(tmp_path: Path) -> list[sqlite3.Row]:
    con = sqlite3.connect(tmp_path / "llm.db")
    con.row_factory = sqlite3.Row
    return con.execute("SELECT * FROM call_log ORDER BY id").fetchall()


USER = [{"role": "user", "content": "parse amat"}]


def test_complete_returns_text_and_usage(tmp_path):
    client = make(tmp_path, FakeAnthropic(message("hello", input_tokens=7, output_tokens=3)))
    r = client.complete(HAIKU, USER, system="be brief")
    assert r.text == "hello"
    assert (r.usage.input_tokens, r.usage.output_tokens) == (7, 3)
    assert r.cache_hit is False


def test_identical_request_is_served_from_cache_without_an_api_call(tmp_path):
    fake = FakeAnthropic()
    client = make(tmp_path, fake)
    first = client.complete(HAIKU, USER, system="s")
    second = client.complete(HAIKU, USER, system="s")
    assert len(fake.messages.calls) == 1
    assert second.cache_hit is True
    assert second.text == first.text


def test_cache_persists_across_clients(tmp_path):
    fake = FakeAnthropic()
    make(tmp_path, fake).complete(HAIKU, USER)
    make(tmp_path, fake).complete(HAIKU, USER)
    assert len(fake.messages.calls) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"model": SONNET},
        {"system": "other"},
        {"messages": [{"role": "user", "content": "parse amant"}]},
        {"tools": [{"name": "lookup", "description": "d", "input_schema": {"type": "object"}}]},
        {"output_schema": {"type": "object"}},
        {"temperature": 0.5},
        {"max_tokens": 99},
        {"sample": 1},
    ],
)
def test_each_request_field_is_part_of_the_cache_key(tmp_path, change):
    fake = FakeAnthropic()
    client = make(tmp_path, fake)
    base = {"model": HAIKU, "messages": USER, "system": "s"}
    client.complete(**base)
    client.complete(**{**base, **change})
    assert len(fake.messages.calls) == 2


def test_every_call_is_logged_with_cost_and_cache_hit(tmp_path):
    client = make(tmp_path, FakeAnthropic(message(input_tokens=1000, output_tokens=2000)))
    client.complete(HAIKU, USER)
    client.complete(HAIKU, USER)
    miss, hit = log_rows(tmp_path)
    assert miss["model"] == HAIKU
    assert (miss["input_tokens"], miss["output_tokens"]) == (1000, 2000)
    assert miss["usd"] == pytest.approx((1000 * 0.10 + 2000 * 0.50) / 1e6)
    assert miss["cache_hit"] == 0
    assert miss["latency_ms"] >= 0
    assert miss["error"] is None
    assert len(miss["prompt_hash"]) == 64
    assert hit["cache_hit"] == 1
    assert hit["usd"] == 0
    assert hit["prompt_hash"] == miss["prompt_hash"]


def test_a_response_carries_the_latency_that_was_logged(tmp_path):
    client = make(tmp_path, FakeAnthropic())
    fresh = client.complete(HAIKU, USER)
    cached = client.complete(HAIKU, USER)
    miss, _ = log_rows(tmp_path)
    assert fresh.latency_ms == miss["latency_ms"]
    assert cached.latency_ms == 0


def test_cached_and_written_tokens_are_logged_and_priced(tmp_path):
    client = make(
        tmp_path,
        FakeAnthropic(
            message(input_tokens=0, output_tokens=0, cache_read=1_000_000, cache_write=1_000_000)
        ),
    )
    client.complete(SONNET, USER)
    (row,) = log_rows(tmp_path)
    assert (row["cache_read_tokens"], row["cache_write_tokens"]) == (1_000_000, 1_000_000)
    assert row["usd"] == pytest.approx(0.20 + 2.5)


def test_api_error_is_logged_and_raised_and_not_cached(tmp_path):
    fake = FakeAnthropic(ValueError("boom"), message("fine"))
    client = make(tmp_path, fake)
    with pytest.raises(ValueError):
        client.complete(HAIKU, USER)
    assert client.complete(HAIKU, USER).text == "fine"
    failed, ok = log_rows(tmp_path)
    assert "boom" in failed["error"]
    assert ok["error"] is None


def test_system_prompt_is_sent_with_a_cache_control_marker(tmp_path):
    fake = FakeAnthropic()
    make(tmp_path, fake).complete(HAIKU, USER, system="long prompt")
    sent = fake.messages.calls[0]["system"]
    assert sent == [{"type": "text", "text": "long prompt", "cache_control": {"type": "ephemeral"}}]


def test_output_schema_is_sent_and_parsed(tmp_path):
    schema = {"type": "object", "properties": {"lemma": {"type": "string"}}}
    fake = FakeAnthropic(message('{"lemma": "amo"}'))
    r = make(tmp_path, fake).complete(HAIKU, USER, output_schema=schema)
    assert fake.messages.calls[0]["output_config"] == {
        "format": {"type": "json_schema", "schema": schema}
    }
    assert r.json() == {"lemma": "amo"}


def test_tool_use_blocks_survive_the_cache(tmp_path):
    from anthropic.types import ToolUseBlock

    msg = message()
    msg.content = [ToolUseBlock(type="tool_use", id="t1", name="lookup", input={"form": "amat"})]
    msg.stop_reason = "tool_use"
    client = make(tmp_path, FakeAnthropic(msg))
    client.complete(HAIKU, USER)
    cached = client.complete(HAIKU, USER)
    assert cached.stop_reason == "tool_use"
    assert cached.content[0]["name"] == "lookup"
    assert cached.content[0]["input"] == {"form": "amat"}


def _status_error(cls, status):
    import httpx

    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("err", response=httpx.Response(status, request=req), body=None)


def test_rate_limit_is_retried_with_exponential_backoff(tmp_path):
    import anthropic

    err = _status_error(anthropic.RateLimitError, 429)
    fake = FakeAnthropic(err, err, message("finally"))
    sleeps: list[float] = []
    client = make(tmp_path, fake, sleep=sleeps.append, backoff_base=1.0)
    assert client.complete(HAIKU, USER).text == "finally"
    assert len(fake.messages.calls) == 3
    assert sleeps == [1.0, 2.0]


def test_overloaded_529_is_retried(tmp_path):
    import anthropic

    err = _status_error(anthropic.APIStatusError, 529)
    fake = FakeAnthropic(err, message("ok"))
    client = make(tmp_path, fake, sleep=lambda s: None)
    assert client.complete(HAIKU, USER).text == "ok"


def test_retries_give_up_and_raise(tmp_path):
    import anthropic

    err = _status_error(anthropic.RateLimitError, 429)
    fake = FakeAnthropic(err)
    client = make(tmp_path, fake, sleep=lambda s: None, max_retries=2)
    with pytest.raises(anthropic.RateLimitError):
        client.complete(HAIKU, USER)
    assert len(fake.messages.calls) == 3
    assert "RateLimitError" in log_rows(tmp_path)[-1]["error"]


def test_client_errors_are_not_retried(tmp_path):
    import anthropic

    err = _status_error(anthropic.BadRequestError, 400)
    fake = FakeAnthropic(err)
    client = make(tmp_path, fake, sleep=lambda s: None)
    with pytest.raises(anthropic.BadRequestError):
        client.complete(HAIKU, USER)
    assert len(fake.messages.calls) == 1


def test_spend_cap_aborts_before_the_next_call(tmp_path):
    from priscianus.llm.client import SpendCapExceeded

    # Each call costs $1.00 on Sonnet (500k input tokens).
    fake = FakeAnthropic(message(input_tokens=500_000, output_tokens=0))
    client = make(tmp_path, fake, spend_cap_usd=1.5)
    client.complete(SONNET, [{"role": "user", "content": "a"}])
    client.complete(SONNET, [{"role": "user", "content": "b"}])  # spent $2.00 > cap
    with pytest.raises(SpendCapExceeded):
        client.complete(SONNET, [{"role": "user", "content": "c"}])
    assert len(fake.messages.calls) == 2


def test_cache_hits_do_not_count_towards_the_spend_cap(tmp_path):
    fake = FakeAnthropic(message(input_tokens=500_000, output_tokens=0))
    client = make(tmp_path, fake, spend_cap_usd=1.5)
    for _ in range(5):
        client.complete(SONNET, USER)
    assert len(fake.messages.calls) == 1


def test_from_env_reads_the_api_key_from_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    client = LLMClient.from_env(db_path=tmp_path / "llm.db")
    assert client._api.api_key == "sk-test"


def test_from_env_passes_client_options_through(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    client = LLMClient.from_env(db_path=tmp_path / "llm.db", spend_cap_usd=0.05, max_retries=2)
    assert client._spend_cap == 0.05
    assert client._max_retries == 2


def test_complete_can_be_called_from_several_threads(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    client = make(tmp_path, FakeAnthropic(message("ok")))
    prompts = [[{"role": "user", "content": f"parse {n}"}] for n in range(20)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        texts = list(pool.map(lambda m: client.complete(HAIKU, m).text, prompts))
    assert texts == ["ok"] * 20
    assert len(log_rows(tmp_path)) == 20
