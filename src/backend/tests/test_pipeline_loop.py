"""Tests for the tool-use loop (ADR-004, Decision 3): a real `LLMClient` over a scripted API."""

import json
from pathlib import Path
from typing import Any

import pytest
from anthropic.types import Message, TextBlock, ToolUseBlock, Usage

from priscianus.llm.client import LLMClient, SpendCapExceeded
from priscianus.llm.config import HAIKU, cost_usd
from priscianus.pipeline.loop import run_with_tools
from priscianus.pipeline.tools import TOOL_DEFINITIONS
from priscianus.verifier.claims import ModelOutput, SchemaError, output_schema

USER = [{"role": "user", "content": 'Parse "amat".'}]
SYSTEM = "You parse Latin."

ANSWER = json.dumps(
    {
        "text": "",
        "claims": [
            {
                "form": "amat",
                "lemma": "amo",
                "upos": "VERB",
                "features": {
                    "Case": "None",
                    "Number": "Sing",
                    "Gender": "None",
                    "Person": "3",
                    "Mood": "Ind",
                    "Tense": "Pres",
                    "Aspect": "None",
                    "Voice": "Act",
                    "VerbForm": "Fin",
                    "Degree": "None",
                },
            }
        ],
    }
)


def answer(text: str = ANSWER, *, input_tokens: int = 100, output_tokens: int = 20) -> Message:
    return _message([TextBlock(type="text", text=text)], "end_turn", input_tokens, output_tokens)


def tool_use(*calls: tuple[str, str, dict[str, Any]]) -> Message:
    """An assistant turn that calls tools: each call is (id, name, input)."""
    blocks = [ToolUseBlock(type="tool_use", id=i, name=n, input=a) for i, n, a in calls]
    return _message(blocks, "tool_use", 100, 20)


def _message(
    content: list[Any], stop_reason: str, input_tokens: int, output_tokens: int
) -> Message:
    return Message(
        id="msg_1",
        type="message",
        role="assistant",
        model=HAIKU,
        content=content,
        stop_reason=stop_reason,  # type: ignore[arg-type]
        stop_sequence=None,
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
    )


class ScriptedMessages:
    """Replies in order, and records every request it was sent."""

    def __init__(self, replies: list[Message]) -> None:
        self.replies = list(replies)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Message:
        # Copy, because the loop keeps appending to the history it sent.
        self.calls.append(json.loads(json.dumps(kwargs)))
        return self.replies.pop(0)


class ScriptedAPI:
    def __init__(self, *replies: Message) -> None:
        self.messages = ScriptedMessages(list(replies))


class RecordingExecutor:
    """Stands in for the index: answers every tool call, and fails those in `failing`."""

    def __init__(self, failing: tuple[str, ...] = ()) -> None:
        self.failing = failing
        self.blocks: list[dict[str, Any]] = []

    def __call__(self, block: dict[str, Any]) -> dict[str, Any]:
        self.blocks.append(block)
        result: dict[str, Any] = {"type": "tool_result", "tool_use_id": block["id"]}
        if block["name"] in self.failing:
            result["content"] = '{"error":"unknown_form","message":"no"}'
            result["is_error"] = True
        else:
            result["content"] = '{"readings":[]}'
        return result


def make_client(tmp_path: Path, api: ScriptedAPI, **kwargs: Any) -> LLMClient:
    return LLMClient(api, db_path=tmp_path / "llm.db", **kwargs)


def run(client: LLMClient, executor: RecordingExecutor | None = None, **kwargs: Any):  # type: ignore[no-untyped-def]
    return run_with_tools(
        client,
        HAIKU,
        USER,
        TOOL_DEFINITIONS,
        executor or RecordingExecutor(),
        system=SYSTEM,
        output_schema=output_schema(),
        **kwargs,
    )


LOOKUP = ("t1", "lookup_form", {"form": "amat"})


def test_zero_rounds_makes_one_call_and_returns_the_parsed_answer(tmp_path: Path) -> None:
    api = ScriptedAPI(answer())
    executor = RecordingExecutor()
    result = run(make_client(tmp_path, api), executor)
    assert len(api.messages.calls) == 1
    assert executor.blocks == []
    assert isinstance(result.output, ModelOutput)
    assert result.output.claims[0].lemma == "amo"
    assert result.tool_calls == ()
    assert result.tool_limit_hit is False


def test_several_rounds_run_the_tools_and_send_the_results_back(tmp_path: Path) -> None:
    api = ScriptedAPI(
        tool_use(LOOKUP),
        tool_use(("t2", "inflect", {"lemma": "amo", "features": {"Tense": "Pres"}})),
        answer(),
    )
    executor = RecordingExecutor()
    result = run(make_client(tmp_path, api), executor)

    assert [b["name"] for b in executor.blocks] == ["lookup_form", "inflect"]
    assert len(api.messages.calls) == 3
    third = api.messages.calls[2]["messages"]
    assert [m["role"] for m in third] == ["user", "assistant", "user", "assistant", "user"]
    # The history is append-only: the assistant turn is sent back in full, then its results.
    assert third[1]["content"][0]["type"] == "tool_use"
    assert third[2]["content"] == [
        {"type": "tool_result", "tool_use_id": "t1", "content": '{"readings":[]}'}
    ]
    assert isinstance(result.output, ModelOutput)
    assert [c.name for c in result.tool_calls] == ["lookup_form", "inflect"]
    assert [c.round for c in result.tool_calls] == [1, 2]
    # Each tool call keeps its input, result and error flag.
    first_call = result.tool_calls[0]
    assert (first_call.input, first_call.result, first_call.is_error) == (
        {"form": "amat"},
        '{"readings":[]}',
        False,
    )
    # The result holds the whole history and leaves the caller's list alone.
    assert len(USER) == 1
    roles = [m["role"] for m in result.messages]
    assert roles == ["user", "assistant", "user", "assistant", "user", "assistant"]
    assert result.messages[-1]["content"][0]["text"] == ANSWER


def test_the_trace_has_each_calls_usage_cost_latency_and_cache_hit(tmp_path: Path) -> None:
    api = ScriptedAPI(tool_use(LOOKUP), answer(input_tokens=1000, output_tokens=200))
    result = run(make_client(tmp_path, api))
    first, second = result.calls
    assert second.usage.input_tokens == 1000
    assert second.usd == pytest.approx(cost_usd(HAIKU, input_tokens=1000, output_tokens=200))
    assert first.cache_hit is False
    assert first.latency_ms >= 0
    assert first.stop_reason == "tool_use"
    assert result.response.text == ANSWER


def test_an_erroring_tool_goes_back_to_the_model_and_the_loop_goes_on(tmp_path: Path) -> None:
    api = ScriptedAPI(tool_use(LOOKUP), answer())
    result = run(make_client(tmp_path, api), RecordingExecutor(failing=("lookup_form",)))
    (call,) = result.tool_calls
    assert call.is_error is True
    assert json.loads(call.result)["error"] == "unknown_form"
    sent = api.messages.calls[1]["messages"][-1]["content"][0]
    assert sent["is_error"] is True
    assert isinstance(result.output, ModelOutput)


def test_calls_past_the_per_round_limit_get_an_error_and_are_not_run(tmp_path: Path) -> None:
    calls = tuple((f"t{i}", "lookup_form", {"form": "amat"}) for i in range(3))
    api = ScriptedAPI(tool_use(*calls), answer())
    executor = RecordingExecutor()
    result = run(make_client(tmp_path, api), executor, max_calls_per_round=2)
    assert [b["id"] for b in executor.blocks] == ["t0", "t1"]
    assert [c.is_error for c in result.tool_calls] == [False, False, True]
    assert json.loads(result.tool_calls[2].result)["error"] == "too_many_calls"
    results = api.messages.calls[1]["messages"][-1]["content"]
    assert [r["tool_use_id"] for r in results] == ["t0", "t1", "t2"]


def test_at_the_round_limit_one_last_call_forbids_tools_and_still_gets_an_answer(
    tmp_path: Path,
) -> None:
    api = ScriptedAPI(tool_use(LOOKUP), tool_use(("t2", *LOOKUP[1:])), answer())
    executor = RecordingExecutor()
    result = run(make_client(tmp_path, api), executor, max_rounds=1)

    assert len(api.messages.calls) == 3
    assert [b["id"] for b in executor.blocks] == ["t1"]  # the second round is not run
    assert result.tool_limit_hit is True
    assert isinstance(result.output, ModelOutput)
    last = api.messages.calls[2]
    assert last["tool_choice"] == {"type": "none"}
    assert last["tools"]  # the history holds tool_use blocks, so the tools stay in the request
    assert all("tool_choice" not in c for c in api.messages.calls[:2])
    # Every tool_use block still gets a tool_result, an error that says why.
    unanswered = last["messages"][-1]["content"][0]
    assert unanswered["tool_use_id"] == "t2"
    assert unanswered["is_error"] is True
    assert json.loads(unanswered["content"])["error"] == "tool_round_limit"


def test_a_model_that_still_calls_tools_after_the_last_call_is_a_schema_failure(
    tmp_path: Path,
) -> None:
    api = ScriptedAPI(tool_use(LOOKUP), tool_use(LOOKUP), tool_use(LOOKUP))
    result = run(make_client(tmp_path, api), max_rounds=1)
    assert result.tool_limit_hit is True
    assert len(api.messages.calls) == 3
    assert isinstance(result.output, SchemaError)


def test_an_invalid_final_answer_is_a_schema_failure_not_an_exception(tmp_path: Path) -> None:
    api = ScriptedAPI(answer("not json"))
    result = run(make_client(tmp_path, api))
    assert isinstance(result.output, SchemaError)
    assert result.response.text == "not json"


def test_a_tool_use_stop_without_tool_blocks_ends_the_loop(tmp_path: Path) -> None:
    api = ScriptedAPI(tool_use())
    result = run(make_client(tmp_path, api))
    assert len(api.messages.calls) == 1
    assert isinstance(result.output, SchemaError)


def test_rerunning_an_item_replays_every_call_from_the_cache(tmp_path: Path) -> None:
    api = ScriptedAPI(tool_use(LOOKUP), answer())
    client = make_client(tmp_path, api)
    first = run(client)
    second = run(client)
    assert len(api.messages.calls) == 2
    assert [c.cache_hit for c in first.calls] == [False, False]
    assert [c.cache_hit for c in second.calls] == [True, True]
    assert second.calls[0].usd == first.calls[0].usd  # list cost, not the $0 that was spent
    assert second.output == first.output


def test_every_call_carries_the_system_prompt_tools_and_schema(tmp_path: Path) -> None:
    api = ScriptedAPI(tool_use(LOOKUP), answer())
    run(make_client(tmp_path, api))
    for sent in api.messages.calls:
        assert sent["system"][0]["cache_control"] == {"type": "ephemeral"}
        assert sent["system"][0]["text"] == SYSTEM
        assert sent["tools"] == TOOL_DEFINITIONS
        assert sent["output_config"]["format"]["schema"] == output_schema()
        assert sent["max_tokens"] == 4096


def test_the_spend_cap_stops_the_loop_between_calls_of_one_item(tmp_path: Path) -> None:
    api = ScriptedAPI(tool_use(LOOKUP), answer())
    client = make_client(tmp_path, api, spend_cap_usd=0.00001)
    # The first call (about $0.00002) is allowed and crosses the cap; the second is refused.
    with pytest.raises(SpendCapExceeded):
        run(client)
    assert len(api.messages.calls) == 1
