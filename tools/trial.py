"""Builds puzzles for past dates into trial/, and prints them for reading.

Uses the real model. Resumable: a date already in trial/ is not rebuilt, because
the free tier allows 20 calls a day and seven dates can need more than that.

    python tools/trial.py [YYYY-MM-DD ...]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build  # noqa: E402
import llm  # noqa: E402
import pool  # noqa: E402

DATES = ["2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09", "2026-10-10", "2026-10-11"]
out = Path("trial")
out.mkdir(exist_ok=True)

for d in sys.argv[1:] or DATES:
    f = out / f"{d}.json"
    if not f.exists():
        h = pool.load_history(d)
        if h is None:
            print(f"{d}: no One Story history")
            continue
        p = build.build(d, h, lambda prompt: llm.generate(prompt))
        if p["normal"] is None and p["trump"] is None:
            print(f"{d}: nothing built (quota?), not saved")
            continue
        f.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    p = json.loads(f.read_text(encoding="utf-8"))
    for mode in ("normal", "trump"):
        print(f"\n== {d} {mode} ==")
        for r in p[mode] or []:
            for j, x in enumerate(r["headlines"]):
                print(("  FAKE " if j == r["fake"] else "       ") + x["text"])
            print()
