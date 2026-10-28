"""TASKS T2.7 tool call budget."""

from weather_agent.tools.budget import ToolBudget


def test_allows_exactly_limit_calls_then_errors():
    budget = ToolBudget(limit=2)
    assert budget.charge() is None
    assert budget.charge() is None
    error = budget.charge()
    assert error.startswith("Error: tool budget exhausted")


def test_exhausted_message_tells_model_to_wrap_up():
    budget = ToolBudget(limit=0)
    error = budget.charge()
    assert "best plan" in error
    assert "not check" in error


def test_reset_restores_full_budget():
    budget = ToolBudget(limit=1)
    budget.charge()
    assert budget.charge() is not None
    budget.reset()
    assert budget.remaining == 1
    assert budget.charge() is None


def test_default_limit_is_30(monkeypatch):
    monkeypatch.delenv("AGENT_MAX_TOOL_CALLS", raising=False)
    assert ToolBudget().limit == 30


def test_limit_from_environment(monkeypatch):
    monkeypatch.setenv("AGENT_MAX_TOOL_CALLS", "5")
    assert ToolBudget().limit == 5
