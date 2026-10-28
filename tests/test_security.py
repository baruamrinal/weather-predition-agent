"""TASKS T2.18 security guards (HLD §8.4)."""

import ast
from pathlib import Path

import pytest

from weather_agent import security
from weather_agent.memory.store import MemoryStore
from weather_agent.tools import geo, http, weather

REPO = Path(__file__).resolve().parent.parent
PACKAGE = REPO / "weather_agent"

# Built at runtime so this file never contains a literal key for the repo scan to find
FAKE_ANTHROPIC_KEY = "sk-" + "ant-api03-" + "A1b2C3d4E5f6G7h8I9j0" * 2
FAKE_OPENAI_KEY = "sk-" + "proj-" + "Z9y8X7w6V5u4T3s2R1q0" * 2


# --- AC1 host allow-list ---------------------------------------------------------------


@pytest.fixture
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a connection was opened")

    monkeypatch.setattr(http.urllib.request, "urlopen", refuse)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/v1/forecast",
        "https://api.open-meteo.com.evil.example/v1/forecast",
        "http://api.open-meteo.com/v1/forecast",
        "file:///etc/passwd",
    ],
)
def test_get_json_refuses_disallowed_urls_before_connecting(no_network, url):
    with pytest.raises(ValueError):
        http.get_json(url, {})


def test_get_json_allows_open_meteo(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b'{"ok": true}'

    opened = []
    monkeypatch.setattr(http.urllib.request, "urlopen", lambda url, timeout: opened.append(url) or FakeResponse())
    assert http.get_json(weather.FORECAST_URL, {"latitude": 1}) == {"ok": True}
    assert opened == [f"{weather.FORECAST_URL}?latitude=1"]


# --- AC2 every tool URL is allowed -------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [weather.GEOCODE_URL, weather.FORECAST_URL, weather.AIR_QUALITY_URL, weather.ARCHIVE_URL, geo.ELEVATION_URL],
)
def test_tool_urls_are_allowed(url):
    http.check_url(url)  # raises if not allowed


# --- AC3 only http.py and brain/ do networking ---------------------------------------------

NETWORK_MODULES = {"urllib.request", "http.client", "socket", "requests", "httpx"}


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def test_only_http_module_and_brain_import_networking():
    allowed = {PACKAGE / "tools" / "http.py"}
    offenders = [
        str(path.relative_to(REPO))
        for path in PACKAGE.rglob("*.py")
        if path not in allowed
        and "brain" not in path.relative_to(PACKAGE).parts
        and _imported_modules(path) & NETWORK_MODULES
    ]
    assert offenders == []


# --- AC4 no keys in the repo ----------------------------------------------------------------

SCANNED_SUFFIXES = {".py", ".md", ".txt", ".ini", ".toml", ".json", ".yaml", ".yml", ".html", ".cfg", ".env"}
SKIPPED_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules"}


def _repo_files():
    for path in REPO.rglob("*"):
        if path.is_file() and path.suffix in SCANNED_SUFFIXES and not SKIPPED_DIRS & set(path.relative_to(REPO).parts):
            yield path


def test_secret_detector_recognises_key_formats():
    assert security.looks_like_secret(f"key is {FAKE_ANTHROPIC_KEY}")
    assert security.looks_like_secret(FAKE_OPENAI_KEY)
    assert not security.looks_like_secret("Set ANTHROPIC_API_KEY=sk-ant-... in your shell")
    assert not security.looks_like_secret("Son has asthma: keep AQI under 100")


def test_repo_contains_no_api_keys():
    leaks = [str(p.relative_to(REPO)) for p in _repo_files() if security.looks_like_secret(p.read_text(encoding="utf-8", errors="ignore"))]
    assert leaks == []


# --- AC5 memory refuses secrets ------------------------------------------------------------


def test_memory_refuses_api_keys(tmp_path):
    store = MemoryStore(tmp_path / "memory.json")
    with pytest.raises(ValueError, match="API key"):
        store.remember("profile", f"My Anthropic key is {FAKE_ANTHROPIC_KEY}")
    assert not (tmp_path / "memory.json").exists()
