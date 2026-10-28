"""Single HTTP entry point for all tools, so tests can fake it in one place.

Only HTTPS requests to Open-Meteo are allowed (HLD §8.4).
"""

import json
import urllib.parse
import urllib.request

ALLOWED_HOSTS = frozenset(
    {
        "geocoding-api.open-meteo.com",
        "api.open-meteo.com",
        "air-quality-api.open-meteo.com",
        "archive-api.open-meteo.com",
    }
)


def check_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"outbound request to {parsed.scheme}://{parsed.hostname} is not allowed")


def get_json(url: str, params: dict) -> dict:
    check_url(url)
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(full_url, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))
