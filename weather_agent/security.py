"""Detects API-key-like strings so they never reach memory, logs, or the repo (HLD §8.4)."""

import re

SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),  # Anthropic
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{32,}"),  # OpenAI
]


def looks_like_secret(text: str) -> bool:
    return any(p.search(text) for p in SECRET_PATTERNS)
