"""Daily limits (ADR-005, Decision 7): AI requests per user and per IP, and the day's $ cap.

Counters live in `limits.db`. The day's spend is read from the `llm.db` call log that `LLMClient`
already writes, so there is no second tally that could drift. Every day is a UTC day.
"""

import hashlib
import math
import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, time, timedelta
from pathlib import Path

from priscianus.llm.client import SpendCapExceeded

_SCHEMA = """
CREATE TABLE IF NOT EXISTS usage (
    day TEXT NOT NULL,
    subject TEXT NOT NULL,
    count INTEGER NOT NULL,
    PRIMARY KEY (day, subject)
);
"""


class DailyLimitExceeded(Exception):
    """This user (or this IP address) has used its AI requests for today."""

    def __init__(self, resets_at: datetime, retry_after: int) -> None:
        super().__init__(f"daily limit reached, resets at {resets_at.isoformat()}")
        self.resets_at = resets_at
        self.retry_after = retry_after


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Limits:
    def __init__(
        self,
        limits_db: Path | str,
        llm_db: Path | str,
        *,
        request_limit: int = 20,
        ip_limit: int = 20,
        spend_cap_usd: float = 0.50,
        salt: str = "",
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        """`now` returns a timezone-aware time; tests pass a fake clock."""
        self._llm_db = Path(llm_db)
        self._request_limit = request_limit
        self._ip_limit = ip_limit
        self._spend_cap = spend_cap_usd
        self._salt = salt
        self._now = now
        # Requests run in worker threads; the lock makes "check, then count" one step.
        self._lock = threading.Lock()
        self._db = sqlite3.connect(limits_db, check_same_thread=False)
        self._db.executescript(_SCHEMA)

    @contextmanager
    def counted(self, client_id: str | None, ip: str) -> Iterator[None]:
        """Wrap a model call: refuse if over a limit, and give the request back if the call fails.

        The spend cap is checked first, so a refused request is not counted against the user.
        """
        self._check_spend()
        subjects = self._take(client_id, ip)
        try:
            yield
        except BaseException:
            self._give_back(subjects)
            raise

    def _check_spend(self) -> None:
        today = self._now().date().isoformat()
        with sqlite3.connect(self._llm_db) as db:
            (spent,) = db.execute(
                "SELECT COALESCE(SUM(usd), 0) FROM call_log WHERE date(created_at) = ?", (today,)
            ).fetchone()
        if spent >= self._spend_cap:
            raise SpendCapExceeded(f"spent ${spent:.4f} of ${self._spend_cap:.4f} today")

    def _take(self, client_id: str | None, ip: str) -> list[str]:
        """Count one request against the user's ID (if sent) and the IP; refuse if one is full."""
        ip_hash = hashlib.sha256(f"{self._salt}{ip}".encode()).hexdigest()
        subjects = {f"ip:{ip_hash}": self._ip_limit}
        if client_id:
            subjects[f"id:{client_id[:64]}"] = self._request_limit
        day = self._now().date().isoformat()
        with self._lock, self._db:
            for subject, limit in subjects.items():
                row = self._db.execute(
                    "SELECT count FROM usage WHERE day = ? AND subject = ?", (day, subject)
                ).fetchone()
                if row and row[0] >= limit:
                    raise self._exceeded()
            for subject in subjects:
                self._db.execute(
                    "INSERT INTO usage(day, subject, count) VALUES (?, ?, 1)"
                    " ON CONFLICT(day, subject) DO UPDATE SET count = count + 1",
                    (day, subject),
                )
        return list(subjects)

    def _give_back(self, subjects: list[str]) -> None:
        day = self._now().date().isoformat()
        with self._lock, self._db:
            for subject in subjects:
                self._db.execute(
                    "UPDATE usage SET count = count - 1 WHERE day = ? AND subject = ?",
                    (day, subject),
                )

    def _exceeded(self) -> DailyLimitExceeded:
        now = self._now()
        midnight = datetime.combine(now.date() + timedelta(days=1), time(), tzinfo=UTC)
        seconds = math.ceil((midnight - now).total_seconds())
        return DailyLimitExceeded(midnight, max(1, seconds))
