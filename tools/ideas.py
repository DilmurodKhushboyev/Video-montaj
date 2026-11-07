#!/usr/bin/env python3
"""
ideas.py — g'oyalar katalogi va tasodifiy kombinatsiyalar (ilhom uchun, shablon emas).
projects/ideas_log.json dagi oldingi videolarda ishlatilgan texnikalar kamroq taklif qilinadi.

    python3 tools/ideas.py --catalog
    python3 tools/ideas.py --scenes 8 --mood sokin|dramatik|energiya|nostalji [--seed 3]
"""
import argparse
import json
import os
import random

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(HERE, "projects", "ideas_log.json")

CATALOG = {
    "kompozitsiya": ["full-bleed", "lenta + xira fon (band)", "karta / polaroid", "triptix (3 lenta)",
                     "split-screen (o'tmish / bugun)", "iris doira", "ravoq/deraza niqobi",
                     "film lentasi", "letterbox", "so'z ichida rasm", "ekran ichida ekran",
                     "vertikal stek (pastdan yuqoriga ko'tarilish)", "qorong'ida yolg'iz obyekt (cutout)"],
    "kamera": ["push-in", "pull-out", "sho'ng'ish (zoom_between)", "panorama g'arb->sharq",
               "tilt up", "punch-in", "whip", "shake + zoom punch", "rack focus", "orbit",
               "parallaks / dolly-zoom", "UI-swipe (reel o'tib ketay deydi)"],
    "yorug'lik/zarra": ["god_rays", "flare", "light_leak", "shockwave", "sparks", "flying_glyphs",
                        "gul barglari", "qor", "pufakchalar (suv osti)", "qushlar", "bokeh",
                        "yulduzlar", "chang", "fonar alangasi miltillashi", "yorug'lik to'kilishi (radial reveal)"],
    "rang": ["oltin o'tmish", "sovuq ko'k inqiroz", "duotone", "time-lapse kun/tun miltillashi",
             "skaner chizig'i rangni o'zgartiradi", "botqoq yashil", "oq-qora -> rang"],
    "tipografiya": ["words_in blur", "chars_in", "text_rise", "scatter_in (uzoqdan uchib kelish)",
                    "drop_chars (harflar yiqiladi)", "typewriter", "counter", "stamp (shtamp)",
                    "glitch_text", "zinapoya matn", "marshrut yoyi + yorliqlar", "slam", "shine"],
    "o'tish": ["fade", "burn", "zoom", "cut", "dissolve", "whip", "flare", "iris", "blinds", "push",
               "luma", "glitchcut", "spin", "heart"],
    "signature": ["EKG so'nadi -> yurak qaytadi", "chala yurak konturi -> muqova yuragi to'ldiradi",
                  "AF-ramka tomoshabinni tanlaydi", "bosmaxona skaneri", "reel swipe qilinmay qaytadi",
                  "o'tmish arvohi bugungi kadrda (double exposure)", "1000 kun-tun time-lapse"],
}

MOOD = {"sokin": ["dissolve", "fade", "luma", "push-in", "bokeh", "chang"],
        "dramatik": ["burn", "cut", "shockwave", "shake + zoom punch", "sovuq ko'k inqiroz"],
        "energiya": ["whip", "glitchcut", "slam", "punch-in", "sparks"],
        "nostalji": ["film lentasi", "duotone", "light_leak", "karta / polaroid"]}


def used():
    try:
        log = json.load(open(LOG))
    except (OSError, ValueError):
        return {}
    cnt = {}
    for v in log.get("videos", []):
        for k in v.get("techniques", []) + v.get("signatures", []):
            cnt[k] = cnt.get(k, 0) + 1
    return cnt


def pick(rng, items, cnt, bias=()):
    w = [(3.0 if i in bias else 1.0) / (1 + 2 * cnt.get(i, 0)) for i in items]
    return rng.choices(items, w)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", action="store_true")
    ap.add_argument("--scenes", type=int, default=6)
    ap.add_argument("--mood", default="sokin", choices=list(MOOD))
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()
    if a.catalog:
        for k, v in CATALOG.items():
            print(f"{k}:\n  - " + "\n  - ".join(v))
        return
    rng = random.Random(a.seed)
    cnt = used()
    bias = MOOD[a.mood]
    for i in range(a.scenes):
        row = {k: pick(rng, CATALOG[k], cnt, bias) for k in
               ("kompozitsiya", "kamera", "yorug'lik/zarra", "tipografiya", "o'tish")}
        print(f"{i + 1:02d}. " + " | ".join(f"{k}: {v}" for k, v in row.items()))
    print("signature taklifi:", pick(rng, CATALOG["signature"], cnt))


if __name__ == "__main__":
    main()
