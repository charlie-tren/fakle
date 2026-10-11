"""Where the text comes from: a ladder of free providers, each tried once.

Gemini's free tier is 20 calls a day per project PER MODEL, and failed attempts count,
so a second Gemini model is a separate allowance and the next rung is the retry.
Groq is a different company's free tier. Cloudflare Workers AI is deliberately not
used: its daily allowance is shared with Ghostwriters and Photocopy.

    GEMINI_API_KEY   Google AI Studio, in its own project
    GROQ_API_KEY     console.groq.com
"""
from __future__ import annotations

import os
import re
import time

import requests

import gemini

LADDER = [
    ("gemini", "gemini-3.6-flash"),
    ("gemini", "gemini-3.7-flash"),
    ("groq", "openai/gpt-oss-120b"),
]
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
TIMEOUT = 120


class NoProvider(RuntimeError):
    pass


def _groq(prompt: str, temperature: float, model: str) -> str:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise NoProvider("GROQ_API_KEY not set")
    body = {"model": model, "temperature": temperature, "reasoning_effort": "low",
            # The reply is reserved against the per-minute token limit, so keep it small.
            "max_completion_tokens": 1200,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": prompt}]}
    for attempt in range(2):
        r = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {key}"}, json=body, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        # A per-minute limit clears in seconds and is worth one wait; a per-day one is not.
        wait = re.search(r"try again in ([0-9.]+)s", r.text)
        if attempt == 0 and r.status_code == 429 and "per minute" in r.text and wait and float(wait.group(1)) <= 60:
            time.sleep(float(wait.group(1)) + 1)
            continue
        raise NoProvider(f"HTTP {r.status_code}: {r.text}")
    raise NoProvider("unreachable")


def generate(prompt: str, temperature: float = 0.9) -> tuple[str, str]:
    """Returns (raw text, "provider/model" that produced it)."""
    problems = []
    for name, model in LADDER:
        try:
            if name == "gemini":
                return gemini.generate(prompt, temperature=temperature, model=model), f"{name}/{model}"
            return _groq(prompt, temperature, model), f"{name}/{model}"
        except Exception as exc:                     # noqa: BLE001
            problems.append(f"{name}/{model}: {type(exc).__name__} {str(exc)[:300]}")
    raise NoProvider(" | ".join(problems))


def extract_json(raw):
    return raw if isinstance(raw, (dict, list)) else gemini.extract_json(raw)
