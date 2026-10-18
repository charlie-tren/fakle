import pytest


@pytest.fixture(autouse=True)
def _no_paid_api_calls(monkeypatch):
    """A test run must never spend Anthropic credit, key in the shell or not.
    tests/test_claude.py clears `_off` and supplies a fake client."""
    import claude
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(claude, "_off", "tests never call the API")
    monkeypatch.setattr(claude, "_client", None)
