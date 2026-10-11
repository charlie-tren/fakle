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
