"""TASKS T2.9 long-term memory store."""

from datetime import date

import pytest

from weather_agent.memory.store import MemoryStore


@pytest.fixture
def path(tmp_path):
    return tmp_path / "memory.json"


def test_remember_returns_entry_with_metadata(path):
    entry = MemoryStore(path).remember("profile", "Lives in Pune")
    assert entry["kind"] == "profile"
    assert entry["content"] == "Lives in Pune"
    assert entry["created"] == date.today().isoformat()
    assert entry["id"]


def test_entries_persist_across_instances(path):
    MemoryStore(path).remember("preference", "Doesn't run above 30 °C")
    assert [e["content"] for e in MemoryStore(path).recall("")] == ["Doesn't run above 30 °C"]


def test_same_content_and_kind_not_duplicated(path):
    store = MemoryStore(path)
    first = store.remember("profile", "Lives in Pune")
    second = store.remember("profile", "lives in pune ")
    assert second["id"] == first["id"]
    assert len(store.recall("")) == 1


def test_recall_matches_any_word_case_insensitive(path):
    store = MemoryStore(path)
    store.remember("profile", "Lives in Pune")
    store.remember("preference", "Son has asthma: keep AQI under 100")
    store.remember("plan", "Sikkim trip Nov 2-7")
    assert [e["content"] for e in store.recall("ASTHMA trip")] == [
        "Son has asthma: keep AQI under 100",
        "Sikkim trip Nov 2-7",
    ]


def test_recall_filters_by_kind(path):
    store = MemoryStore(path)
    store.remember("profile", "Lives in Pune")
    store.remember("plan", "Pune run on Sunday")
    assert [e["kind"] for e in store.recall("pune", kind="plan")] == ["plan"]


def test_forget(path):
    store = MemoryStore(path)
    entry = store.remember("profile", "Lives in Pune")
    assert store.forget(entry["id"]) is True
    assert store.forget(entry["id"]) is False
    assert MemoryStore(path).recall("") == []


def test_unknown_kind_rejected(path):
    with pytest.raises(ValueError):
        MemoryStore(path).remember("secret", "x")


def test_corrupt_file_backed_up_and_store_starts_empty(path):
    path.write_text("{not json", encoding="utf-8")
    store = MemoryStore(path)
    assert store.recall("") == []
    assert path.with_suffix(".json.bak").read_text(encoding="utf-8") == "{not json"


def test_missing_parent_directory_is_created(tmp_path):
    store = MemoryStore(tmp_path / "nested" / "memory.json")
    store.remember("profile", "Lives in Pune")
    assert (tmp_path / "nested" / "memory.json").exists()


def test_profile_summary(path):
    store = MemoryStore(path)
    assert store.profile_summary() == ""
    store.remember("profile", "Lives in Pune")
    store.remember("preference", "Prefers °F")
    store.remember("plan", "Sikkim trip Nov 2-7")
    assert store.profile_summary() == "- Lives in Pune\n- Prefers °F"
