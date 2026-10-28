"""Long-term memory: a small JSON file of facts about the user that survives between sessions."""

import json
import uuid
from datetime import date
from pathlib import Path

from weather_agent.security import looks_like_secret

KINDS = ("profile", "preference", "plan", "outcome")
DEFAULT_PATH = Path.home() / ".weather_agent" / "memory.json"


class MemoryStore:
    def __init__(self, path: Path | str = DEFAULT_PATH):
        self.path = Path(path)
        self.entries: list[dict] = self._load()

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        raw = self.path.read_text(encoding="utf-8")
        try:
            return json.loads(raw)["entries"]
        except (json.JSONDecodeError, KeyError, TypeError):
            # Keep the damaged file for inspection rather than losing it
            self.path.replace(self.path.with_suffix(self.path.suffix + ".bak"))
            return []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps({"entries": self.entries}, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def remember(self, kind: str, content: str) -> dict:
        if kind not in KINDS:
            raise ValueError(f"unknown memory kind '{kind}'; expected one of {', '.join(KINDS)}")
        content = content.strip()
        if looks_like_secret(content):
            raise ValueError("refusing to store what looks like an API key")
        for entry in self.entries:
            if entry["kind"] == kind and entry["content"].lower() == content.lower():
                return entry
        entry = {"id": uuid.uuid4().hex[:8], "kind": kind, "content": content, "created": date.today().isoformat()}
        self.entries.append(entry)
        self._save()
        return entry

    def recall(self, query: str = "", kind: str | None = None) -> list[dict]:
        words = query.lower().split()
        return [
            e
            for e in self.entries
            if (kind is None or e["kind"] == kind) and (not words or any(w in e["content"].lower() for w in words))
        ]

    def forget(self, entry_id: str) -> bool:
        before = len(self.entries)
        self.entries = [e for e in self.entries if e["id"] != entry_id]
        if len(self.entries) == before:
            return False
        self._save()
        return True

    def profile_summary(self) -> str:
        return "\n".join(f"- {e['content']}" for e in self.entries if e["kind"] in ("profile", "preference"))
