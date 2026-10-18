from types import SimpleNamespace

import anthropic
import pytest

import claude
import gemini
import llm
import prompts


def _msg(text='{"ok": 1}', stop="end_turn"):
    return SimpleNamespace(
        stop_reason=stop,
        content=[SimpleNamespace(type="thinking", thinking=""),
                 SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=1000, output_tokens=2000))


def _api_error(cls, message):
    """An SDK error without a live response, whatever HTTP library it uses."""
    exc = cls.__new__(cls)
    Exception.__init__(exc, message)
    exc.message = message
    return exc


class Fake:
    def __init__(self):
        self.calls, self.reply, self.raises = [], _msg(), None
        self.messages = SimpleNamespace(create=self._create("plain"))
        self.beta = SimpleNamespace(
            messages=SimpleNamespace(create=self._create("beta")))

    def _create(self, path):
        def create(**kw):
            self.calls.append((path, kw))
            if self.raises:
                raise self.raises
            return self.reply
        return create


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(claude, "_off", None)
    fake = Fake()
    monkeypatch.setattr(claude, "_client", fake)
    monkeypatch.setattr(gemini, "generate", lambda *a, **k: '{"ok": "gemini"}')
    return fake


def test_claude_answers_first_and_is_named(live):
    raw, provider = llm.generate("p")
    assert raw == '{"ok": 1}' and provider == "claude/claude-sonnet-5-5"
    path, kw = live.calls[0]
    assert path == "beta" and kw["fallbacks"] == "default"
    assert "temperature" not in kw


def test_shortlist_and_judge_prompts_run_on_haiku(live):
    llm.generate(prompts.shortlist_prompt([{"text": "a"}, {"text": "b"}], 1))
    llm.generate(prompts.judge_prompt([["a", "b", "c", "d"]]))
    assert [c[1]["model"] for c in live.calls] == ["claude-haiku-5-5"] * 2


def test_fakes_run_on_sonnet(live):
    llm.generate(prompts.fake_prompt([[{"text": "a"}, {"text": "b"},
                                       {"text": "c"}]]))
    assert live.calls[0][1]["model"] == "claude-sonnet-5-5"


def test_missing_key_falls_to_the_gemini_ladder_with_a_warning(live, monkeypatch,
                                                               capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    raw, provider = llm.generate("p")
    assert provider.startswith("gemini/") and live.calls == []
    assert "::warning::" in capsys.readouterr().out


def test_outage_turns_claude_off_for_the_run(live):
    live.raises = _api_error(anthropic.InternalServerError, "overloaded")
    assert llm.generate("p")[1].startswith("gemini/")
    llm.generate("p")
    assert len(live.calls) == 1


def test_refusal_falls_back_for_that_call_only(live):
    live.reply = _msg(stop="refusal")
    assert llm.generate("p")[1].startswith("gemini/")
    assert claude._off is None


def test_usage_and_cost_are_logged(live, capsys):
    llm.generate("p")
    assert "claude-sonnet-5-5 [write] in=1000 out=2000 US$0.0220" in \
        capsys.readouterr().out
