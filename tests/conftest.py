import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from weather_agent.tools import http  # noqa: E402


class FakeApi:
    """Stands in for http.get_json: returns canned JSON per URL and records calls."""

    def __init__(self):
        self.responses: dict[str, dict] = {}
        self.calls: list[tuple[str, dict]] = []

    def respond(self, url: str, payload: dict) -> None:
        self.responses[url] = payload

    def __call__(self, url: str, params: dict) -> dict:
        self.calls.append((url, params))
        if url not in self.responses:
            raise AssertionError(f"unexpected request to {url}")
        return self.responses[url]

    def last_params(self, url: str) -> dict:
        return [p for u, p in self.calls if u == url][-1]


@pytest.fixture
def fake_api(monkeypatch):
    api = FakeApi()
    monkeypatch.setattr(http, "get_json", api)
    return api
