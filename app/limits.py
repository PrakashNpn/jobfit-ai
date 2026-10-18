"""Daily usage limits, so a public demo can't run up the Claude API bill.

Counts are kept in memory: they reset at midnight UTC or when the server restarts,
which is enough for a demo. Use Redis or the database if you need them to persist.
"""

import threading
from datetime import date, datetime, timezone

from fastapi import Request


class LimitExceeded(Exception):
    pass


class DailyLimiter:
    def __init__(self, per_visitor: int, total: int) -> None:
        self.per_visitor = per_visitor  # 0 = unlimited
        self.total = total  # 0 = unlimited
        self._day: date | None = None
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def _reset_if_new_day(self) -> None:
        today = datetime.now(timezone.utc).date()
        if self._day != today:
            self._day, self._counts = today, {}

    def used(self, visitor: str) -> int:
        with self._lock:
            self._reset_if_new_day()
            return self._counts.get(visitor, 0)

    def consume(self, visitor: str) -> None:
        """Count one use, or raise LimitExceeded if a limit is reached."""
        with self._lock:
            self._reset_if_new_day()
            if self.total and sum(self._counts.values()) >= self.total:
                raise LimitExceeded(
                    "The demo has reached today's overall limit. Please try again tomorrow."
                )
            if self.per_visitor and self._counts.get(visitor, 0) >= self.per_visitor:
                raise LimitExceeded(
                    f"You've used all {self.per_visitor} free analyses for today. Please come back tomorrow."
                )
            self._counts[visitor] = self._counts.get(visitor, 0) + 1


def visitor_id(request: Request) -> str:
    # Behind a hosting proxy (Render, Railway, ...) the real IP is the first X-Forwarded-For entry.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
