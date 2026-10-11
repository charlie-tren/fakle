import pytest

import gemini
import llm


def test_first_working_rung_answers_and_is_named(monkeypatch):
    asked = []

    def fake_gemini(prompt, temperature=0.9, model=gemini.MODEL):
        asked.append(model)
        if model == llm.LADDER[0][1]:
            raise gemini.GeminiError("HTTP 429 PerDay")
        return '{"ok": 1}'
    monkeypatch.setattr(gemini, "generate", fake_gemini)
    raw, provider = llm.generate("p")
    assert raw == '{"ok": 1}'
    assert provider == f"gemini/{llm.LADDER[1][1]}"
    assert asked == [llm.LADDER[0][1], llm.LADDER[1][1]]


def test_falls_through_to_groq(monkeypatch):
    monkeypatch.setattr(gemini, "generate", lambda *a, **k: (_ for _ in ()).throw(gemini.GeminiError("429")))
    monkeypatch.setattr(llm, "_groq", lambda prompt, temperature, model: '{"ok": 2}')
    raw, provider = llm.generate("p")
    assert raw == '{"ok": 2}' and provider.startswith("groq/")


def test_every_rung_failing_raises_with_each_reason(monkeypatch):
    monkeypatch.setattr(gemini, "generate", lambda *a, **k: (_ for _ in ()).throw(gemini.GeminiError("429")))
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(llm.NoProvider) as e:
        llm.generate("p")
    assert "groq" in str(e.value) and str(e.value).count("gemini") >= 2


def test_gemini_is_tried_once_per_model():
    # Failed attempts count against the daily 20, so the next rung is the retry.
    assert gemini.RETRIES == 0


def test_cloudflare_is_not_a_rung():
    # Its allowance is shared with Ghostwriters and Photocopy.
    assert all(name != "cloudflare" for name, _ in llm.LADDER)


def test_groq_asks_for_low_reasoning(monkeypatch):
    # gpt-oss in JSON mode returned an empty generation at default effort (11/10/2026).
    sent = {}

    class R:
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": "{}"}}]}

    def post(url, headers, json, timeout):
        sent.update(json)
        return R()
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setattr(llm.requests, "post", post)
    llm._groq("p", 0.9, "openai/gpt-oss-120b")
    assert sent["reasoning_effort"] == "low"



class _Resp:
    def __init__(self, code, body):
        self.status_code = code
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


def test_groq_waits_out_a_per_minute_limit_once(monkeypatch):
    replies = [_Resp(429, {"error": {"message": "Rate limit reached on tokens per minute (TPM). Please try again in 12.9s."}}),
               _Resp(200, {"choices": [{"message": {"content": "{}"}}]})]
    slept = []
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: replies.pop(0))
    monkeypatch.setattr(llm.time, "sleep", lambda s: slept.append(s))
    assert llm._groq("p", 0.9, "openai/gpt-oss-120b") == "{}"
    assert slept and 12.9 <= slept[0] <= 15


def test_groq_does_not_wait_out_a_daily_limit(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _Resp(429, {"error": {"message": "tokens per day (TPD). Please try again in 9m12s."}}))
    monkeypatch.setattr(llm.time, "sleep", lambda s: (_ for _ in ()).throw(AssertionError("slept")))
    with pytest.raises(llm.NoProvider):
        llm._groq("p", 0.9, "openai/gpt-oss-120b")


def test_groq_caps_the_reply(monkeypatch):
    sent = {}
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setattr(llm.requests, "post", lambda url, headers, json, timeout: (sent.update(json), _Resp(200, {"choices": [{"message": {"content": "{}"}}]}))[1])
    llm._groq("p", 0.9, "openai/gpt-oss-120b")
    assert sent["max_completion_tokens"] <= 1500
