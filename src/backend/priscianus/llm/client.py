"""The one place Claude is called: cached in SQLite, logged with cost, structured output."""

import hashlib
import json
import sqlite3
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anthropic

from priscianus.llm.config import cost_usd

DEFAULT_DB = Path("llm.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS response_cache (
    cache_key TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    request_json TEXT NOT NULL,
    response_json TEXT NOT NULL,
    usd REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS call_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    model TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    cache_read_tokens INTEGER NOT NULL,
    cache_write_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    usd REAL NOT NULL,
    latency_ms INTEGER NOT NULL,
    cache_hit INTEGER NOT NULL,
    error TEXT
);
"""


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass(frozen=True)
class LLMResponse:
    content: list[dict[str, Any]]
    stop_reason: str | None
    usage: Usage
    cache_hit: bool = False

    @property
    def text(self) -> str:
        return "".join(b["text"] for b in self.content if b["type"] == "text")

    def json(self) -> Any:
        return json.loads(self.text)


class SpendCapExceeded(RuntimeError):
    """Raised before a call when this client has already spent its cap."""


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, anthropic.RateLimitError):
        return True
    # 5xx (including 529 overloaded) and dropped connections are transient.
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code >= 500
    return isinstance(exc, anthropic.APIConnectionError)


class LLMClient:
    def __init__(
        self,
        api_client: Any,
        *,
        db_path: Path | str = DEFAULT_DB,
        spend_cap_usd: float | None = None,
        max_retries: int = 5,
        backoff_base: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """`api_client` is an `anthropic.Anthropic`, or a fake with `.messages.create`.

        `spend_cap_usd` limits what this client spends in its lifetime (one run). A call
        that would start after the cap is reached raises `SpendCapExceeded`; the call that
        crosses it still completes, and so do calls already in flight, so a run overshoots by at
        most as many calls as it has threads.
        """
        self._api = api_client
        self._spend_cap = spend_cap_usd
        self._spent = 0.0
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._sleep = sleep
        # Calls may come from several threads; the lock serialises the database and the tally.
        self._lock = threading.RLock()
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._db.executescript(_SCHEMA)

    @classmethod
    def from_env(cls, **options: Any) -> "LLMClient":
        """Build a client from `ANTHROPIC_API_KEY`; `options` are the constructor's keywords."""
        # The SDK's own retries are off, because ours are logged.
        return cls(anthropic.Anthropic(max_retries=0), **options)

    def complete(
        self,
        model: str,
        messages: Sequence[dict[str, Any]],
        *,
        system: str | None = None,
        tools: Sequence[dict[str, Any]] | None = None,
        output_schema: dict[str, Any] | None = None,
        max_tokens: int = 1024,
        temperature: float | None = None,
        sample: int = 0,
    ) -> LLMResponse:
        request: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": list(messages),
        }
        if system is not None:
            request["system"] = [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ]
        if tools:
            request["tools"] = list(tools)
        if output_schema is not None:
            request["output_config"] = {"format": {"type": "json_schema", "schema": output_schema}}
        if temperature is not None:
            request["temperature"] = temperature
        key = _cache_key(request, sample)

        started = time.monotonic()
        with self._lock:
            row = self._db.execute(
                "SELECT response_json FROM response_cache WHERE cache_key = ?", (key,)
            ).fetchone()
        if row:
            response = _from_json(row[0], cache_hit=True)
            self._log(model, key, response, 0.0, started, None)
            return response

        with self._lock:
            spent = self._spent
        if self._spend_cap is not None and spent >= self._spend_cap:
            raise SpendCapExceeded(f"spent ${spent:.4f} of ${self._spend_cap:.4f} cap")
        raw = self._create_with_retries(model, key, request)
        response = _from_message(raw)
        usd = cost_usd(
            model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cache_read_tokens=response.usage.cache_read_tokens,
            cache_write_tokens=response.usage.cache_write_tokens,
        )
        with self._lock:
            with self._db:
                self._db.execute(
                    "INSERT OR REPLACE INTO response_cache(cache_key, model, request_json,"
                    " response_json, usd) VALUES (?, ?, ?, ?, ?)",
                    (key, model, _canonical(request), _to_json(response), usd),
                )
            self._spent += usd
        self._log(model, key, response, usd, started, None)
        return response

    def _create_with_retries(self, model: str, key: str, request: dict[str, Any]) -> Any:
        for attempt in range(self._max_retries + 1):
            started = time.monotonic()
            try:
                return self._api.messages.create(**request)
            except Exception as exc:
                self._log(model, key, None, 0.0, started, f"{type(exc).__name__}: {exc}")
                if attempt == self._max_retries or not _is_retryable(exc):
                    raise
                self._sleep(self._backoff_base * 2**attempt)
        raise AssertionError("unreachable")

    def _log(
        self,
        model: str,
        key: str,
        response: LLMResponse | None,
        usd: float,
        started: float,
        error: str | None,
    ) -> None:
        usage = response.usage if response else Usage()
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO call_log(model, prompt_hash, input_tokens, cache_read_tokens,"
                " cache_write_tokens, output_tokens, usd, latency_ms, cache_hit, error)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    model,
                    key,
                    usage.input_tokens,
                    usage.cache_read_tokens,
                    usage.cache_write_tokens,
                    usage.output_tokens,
                    usd,
                    round((time.monotonic() - started) * 1000),
                    int(bool(response and response.cache_hit)),
                    error,
                ),
            )


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _cache_key(request: dict[str, Any], sample: int) -> str:
    return hashlib.sha256(_canonical({"request": request, "sample": sample}).encode()).hexdigest()


def _from_message(msg: Any) -> LLMResponse:
    u = msg.usage
    return LLMResponse(
        content=[b.model_dump(mode="json") for b in msg.content],
        stop_reason=msg.stop_reason,
        usage=Usage(
            input_tokens=u.input_tokens,
            output_tokens=u.output_tokens,
            cache_read_tokens=u.cache_read_input_tokens or 0,
            cache_write_tokens=u.cache_creation_input_tokens or 0,
        ),
    )


def _to_json(r: LLMResponse) -> str:
    return _canonical(
        {"content": r.content, "stop_reason": r.stop_reason, "usage": r.usage.__dict__}
    )


def _from_json(s: str, *, cache_hit: bool) -> LLMResponse:
    d = json.loads(s)
    return LLMResponse(d["content"], d["stop_reason"], Usage(**d["usage"]), cache_hit=cache_hit)
