#!/usr/bin/env python3
"""
align_words.py — matnni ovozga so'zma-so'z bog'lash (whisper bo'lmaganda).

    python3 tools/align_words.py voice.wav lines.txt out.json [--offset 0.2]
                                 [--min-pause 0.18] [--pause-db -33.4]

lines.txt — har qatorda bitta nutq bo'lagi matni (analyze_audio.py topgan bo'laklar
soniga teng bo'lishi kerak). Har bo'lak ichida so'zlar bo'g'inlar soniga qarab
taqsimlanadi, chegaralar esa ±0.1 s ichidagi energiya chuqurligiga "yopishtiriladi".
Natija taxminiy (±0.1–0.15 s) — read-along va sinxron voqealar uchun yetarli.
"""
import argparse
import json
import re
import sys

import numpy as np

sys.path.insert(0, __import__("os").path.dirname(__file__))
from analyze_audio import envelope_db, load, speech_segments  # noqa: E402

VOW = set("aeiouAEIOU")
NUMS = {"70": 2, "1": 1, "2": 2, "3": 1, "10": 2, "100": 1, "20": 2, "30": 2, "40": 1, "50": 2}


def syllables(w):
    core = re.sub(r"[^\w]", "", w)
    if not core:
        return 0
    if core.isdigit():
        return NUMS.get(core, 2 * len(core))
    n = sum(1 for c in core if c in VOW)
    return max(1, n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("voice")
    ap.add_argument("lines")
    ap.add_argument("out")
    ap.add_argument("--offset", type=float, default=0.0)
    ap.add_argument("--min-pause", type=float, default=0.18)
    ap.add_argument("--pause-db", type=float, default=None)
    a = ap.parse_args()
    lines = [ln.strip() for ln in open(a.lines, encoding="utf-8") if ln.strip()]
    x = load(a.voice)
    db, dt = envelope_db(x)
    thr = a.pause_db if a.pause_db is not None else max(np.percentile(db, 20) + 8, db.max() - 38)
    segs = speech_segments(db, dt, thr, a.min_pause)
    if len(segs) != len(lines):
        sys.exit(f"bo'laklar soni {len(segs)} != qatorlar soni {len(lines)}")
    sm = np.convolve(db, np.ones(5) / 5, mode="same")
    out = []
    for li, ((s, e), line) in enumerate(zip(segs, lines)):
        words = line.split()
        syl = np.array([syllables(w) for w in words], float)
        # punctuation implies a tiny breath: give it 0.6 syllable of time
        syl += np.array([0.6 if re.search(r"[,.;:!?—]$", w) else 0 for w in words])
        cum = np.concatenate([[0], np.cumsum(syl)]) / syl.sum()
        prop = s + cum * (e - s)
        bounds = prop.copy()
        for k in range(1, len(words)):
            lo = max(prop[k] - 0.1, bounds[k - 1] + 0.6 * (prop[k] - prop[k - 1]))
            hi = min(prop[k] + 0.1, prop[k + 1] - 0.6 * (prop[k + 1] - prop[k]))
            i0, i1 = int(lo / dt), int(hi / dt)
            if i1 > i0:
                bounds[k] = (i0 + int(np.argmin(sm[i0:i1]))) * dt
        for k, w in enumerate(words):
            out.append({"w": w, "s": round(bounds[k] + a.offset, 3),
                        "e": round(bounds[k + 1] + a.offset, 3), "seg": li})
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=0)
    for li in range(len(lines)):
        ws = [o for o in out if o["seg"] == li]
        print(f"{li:2d} " + "  ".join(f"{o['w']}@{o['s']:.2f}" for o in ws))


if __name__ == "__main__":
    main()
