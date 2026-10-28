"""Single HTTP entry point for all tools, so tests can fake it in one place."""

import json
import urllib.parse
import urllib.request


def get_json(url: str, params: dict) -> dict:
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(full_url, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))
