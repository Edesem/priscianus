"""The tool-use loop on the Claude client (ADR-004, Decision 3).

Every API call goes through `LLMClient.complete`, so each one is cached and logged on its own,
and the client's spend cap counts them all.
"""

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from priscianus.llm.client import LLMClient, LLMResponse, Usage
from priscianus.llm.config import cost_usd
from priscianus.verifier.claims import ModelOutput, SchemaError, parse_output

ToolExecutor = Callable[[dict[str, Any]], dict[str, Any]]

# ADR-004, Decision 3: three tool rounds on a first pass, and five calls in a round.
MAX_ROUNDS = 3
MAX_CALLS_PER_ROUND = 5


@dataclass(frozen=True)
class CallTrace:
    """One API call. `usd` and `latency_ms` are what the call cost when first made."""

    usage: Usage
    usd: float
    latency_ms: int
    cache_hit: bool
    stop_reason: str | None


@dataclass(frozen=True)
class ToolCallTrace:
    """One `tool_use` block, in the round (from 1) whose assistant turn made it."""

    round: int
    name: str
    input: dict[str, Any]
    result: str
    is_error: bool


@dataclass(frozen=True)
class LoopResult:
    response: LLMResponse
    output: ModelOutput | SchemaError
    messages: tuple[dict[str, Any], ...]
    calls: tuple[CallTrace, ...]
    tool_calls: tuple[ToolCallTrace, ...]
    tool_limit_hit: bool


def run_with_tools(
    client: LLMClient,
    model: str,
    messages: Sequence[dict[str, Any]],
    tools: Sequence[dict[str, Any]],
    executor: ToolExecutor,
    *,
    system: str | None = None,
    output_schema: dict[str, Any] | None = None,
    max_rounds: int = MAX_ROUNDS,
    max_calls_per_round: int = MAX_CALLS_PER_ROUND,
    max_tokens: int = 4096,
    temperature: float | None = None,
    sample: int = 0,
) -> LoopResult:
    """Send the request, run the tools the model calls and send the results back, until it
    answers. `executor` takes a `tool_use` block and returns its `tool_result` block.

    A round is one assistant turn with tool calls. When the model asks for another after
    `max_rounds`, its calls are not run: each gets an error result, and one last call with
    `tool_choice: none` makes it answer from what it has (`tool_limit_hit`). If that answer is
    still not valid, `output` is a `SchemaError`, as for any other invalid answer.
    """
    history = list(messages)
    calls: list[CallTrace] = []
    tool_calls: list[ToolCallTrace] = []

    def call(tool_choice: dict[str, Any] | None = None) -> LLMResponse:
        response = client.complete(
            model,
            history,
            system=system,
            tools=tools,
            tool_choice=tool_choice,
            output_schema=output_schema,
            max_tokens=max_tokens,
            temperature=temperature,
            sample=sample,
        )
        calls.append(_trace(model, response))
        return response

    response = call()
    round_number = 0
    limit_hit = False
    while response.stop_reason == "tool_use":
        blocks = [b for b in response.content if b["type"] == "tool_use"]
        if not blocks:
            break
        history.append({"role": "assistant", "content": response.content})
        if round_number == max_rounds:
            limit_hit = True
            history.append({"role": "user", "content": [_round_limit(b) for b in blocks]})
            response = call({"type": "none"})
            break
        round_number += 1
        results = []
        for position, block in enumerate(blocks):
            if position < max_calls_per_round:
                result = executor(block)
            else:
                result = _too_many_calls(block, max_calls_per_round)
            results.append(result)
            tool_calls.append(
                ToolCallTrace(
                    round_number,
                    block["name"],
                    block["input"],
                    result["content"],
                    bool(result.get("is_error", False)),
                )
            )
        history.append({"role": "user", "content": results})
        response = call()

    history.append({"role": "assistant", "content": response.content})
    return LoopResult(
        response=response,
        output=parse_output(response.text),
        messages=tuple(history),
        calls=tuple(calls),
        tool_calls=tuple(tool_calls),
        tool_limit_hit=limit_hit,
    )


def _trace(model: str, response: LLMResponse) -> CallTrace:
    usage = response.usage
    usd = cost_usd(
        model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        cache_write_tokens=usage.cache_write_tokens,
    )
    return CallTrace(usage, usd, response.latency_ms, response.cache_hit, response.stop_reason)


def _error(block: dict[str, Any], code: str, message: str) -> dict[str, Any]:
    body = json.dumps({"error": code, "message": message}, sort_keys=True, separators=(",", ":"))
    return {"type": "tool_result", "tool_use_id": block["id"], "content": body, "is_error": True}


def _too_many_calls(block: dict[str, Any], limit: int) -> dict[str, Any]:
    return _error(
        block, "too_many_calls", f"At most {limit} tools can be called at once. Call fewer."
    )


def _round_limit(block: dict[str, Any]) -> dict[str, Any]:
    return _error(
        block,
        "tool_round_limit",
        "No more tool calls are allowed. Answer from what you already have.",
    )
