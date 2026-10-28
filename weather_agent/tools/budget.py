"""Caps the number of tool calls per user request (PRD R3)."""

import os

DEFAULT_LIMIT = 30

EXHAUSTED_MESSAGE = (
    "Error: tool budget exhausted ({limit} calls). Do not call more tools. Answer now with the best plan "
    "you can make from the data already gathered, and list what you did not check."
)


class ToolBudget:
    def __init__(self, limit: int | None = None):
        if limit is None:
            limit = int(os.environ.get("AGENT_MAX_TOOL_CALLS", DEFAULT_LIMIT))
        self.limit = limit
        self.used = 0

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    def charge(self) -> str | None:
        """Use one call. Returns None if allowed, or an error message once the budget is spent."""
        if self.used >= self.limit:
            return EXHAUSTED_MESSAGE.format(limit=self.limit)
        self.used += 1
        return None

    def reset(self) -> None:
        self.used = 0
