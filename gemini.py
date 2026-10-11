"""Thin Gemini REST client. Lifted from The Aftertimes, which has had the retry
and JSON-extraction behaviour debugged in anger; no reason to rediscover it."""
from __future__ import annotations

import json
import os
import re
import time

import requests

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL = "gemini-3.6-flash"
TIMEOUT = 90
RETRIES = 3


class GeminiError(RuntimeError):
    pass


def _key() -> str:
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if not k:
        raise GeminiError("GEMINI_API_KEY is not set")
    return k


def extract_json(raw: str):
    if not raw:
        raise GeminiError("empty response")
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # The FIRST complete value, ignoring whatever follows it. The fallback model
    # sometimes writes its JSON and then keeps going, and the span from the first {
    # to the last } then holds two values: "Extra data", and on 01/10/2026 a run
    # that died in the Write step without a single gate being checked.
    for a in ("{", "["):
        i = text.find(a)
        if i >= 0:
            try:
                return json.JSONDecoder().raw_decode(text[i:])[0]
            except json.JSONDecodeError:
                pass
    for a, b in (("{", "}"), ("[", "]")):
        i, j = text.find(a), text.rfind(b)
        if 0 <= i < j:
            try:
                return json.loads(text[i:j + 1])
            except json.JSONDecodeError:
                continue
    raise GeminiError(f"no parseable JSON in: {raw[:200]!r}")


def generate(prompt: str, temperature: float = 0.95, model: str = MODEL) -> str:
    payload = {"contents": [{"parts": [{"text": prompt}]}],
               "generationConfig": {"temperature": temperature,
                                    "responseMimeType": "application/json"}}
    last = None
    for attempt in range(RETRIES + 1):
        try:
            r = requests.post(f"{ENDPOINT}/{model}:generateContent",
                              params={"key": _key()}, json=payload, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            last = f"HTTP {r.status_code}: {r.text[:200]}"
        except (requests.RequestException, KeyError, IndexError) as exc:
            last = f"{type(exc).__name__}: {exc}"
        if attempt < RETRIES:
            time.sleep(2 * (attempt + 1))
    raise GeminiError(last or "unknown failure")
