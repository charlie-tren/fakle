"""Where the text comes from. Gemini first, Cloudflare Workers AI if it refuses.

Copied from Ghostwriters (dystopianist/llm.py), essay-specific parsing removed.
Gemini's free tier is stingy per DAY, so one bad run must not leave the day empty.

    GEMINI_API_KEY                 Google AI Studio, free tier
    CF_ACCOUNT_ID, CF_API_TOKEN    Cloudflare Workers AI, free neurons/day
"""
from __future__ import annotations

import os

import requests

import gemini

CF_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
CF_TIMEOUT = 120


class NoProvider(RuntimeError):
    pass


def _cloudflare(prompt: str, temperature: float) -> str:
    acct, tok = os.environ.get("CF_ACCOUNT_ID"), os.environ.get("CF_API_TOKEN")
    if not (acct and tok):
        raise NoProvider("CF_ACCOUNT_ID / CF_API_TOKEN not set")
    r = requests.post(
        f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{CF_MODEL}",
        headers={"Authorization": f"Bearer {tok}"},
        json={"messages": [{"role": "user", "content": prompt}],
              "temperature": temperature, "max_tokens": 900},
        timeout=CF_TIMEOUT)
    if r.status_code != 200:
        raise NoProvider(f"cloudflare HTTP {r.status_code}: {r.text[:160]}")
    d = r.json()
    if not d.get("success"):
        raise NoProvider(f"cloudflare: {str(d.get('errors'))[:160]}")
    # Workers AI hands JSON back already parsed when the model emits it.
    res = d["result"]
    out = res.get("response")
    if out is None and res.get("choices"):
        out = res["choices"][0].get("message", {}).get("content")
    return out


def generate(prompt: str, temperature: float = 0.9, prefer: str | None = None) -> tuple[str, str]:
    """Returns (raw text, which provider produced it)."""
    order = ["gemini", "cloudflare"]
    if prefer:
        order = [prefer] + [p for p in order if p != prefer]
    problems = []
    for name in order:
        try:
            if name == "gemini":
                return gemini.generate(prompt, temperature=temperature), "gemini"
            return _cloudflare(prompt, temperature), "cloudflare"
        except Exception as exc:                     # noqa: BLE001
            problems.append(f"{name}: {type(exc).__name__} {str(exc)[:110]}")
    raise NoProvider(" | ".join(problems))


def extract_json(raw):
    return raw if isinstance(raw, (dict, list)) else gemini.extract_json(raw)
