#!/usr/bin/env python3
"""
ideas.py — sahna g'oyalari uchun ilhom generatori.

    python3 tools/ideas.py --catalog
    python3 tools/ideas.py --scenes 8 --mood sokin|dramatik|energiya|nostalji [--seed 3]

projects/ideas_log.json dagi oldingi videolarda ishlatilgan texnikalar kamroq
taklif qilinadi (har ishlatilish og'irlikni 0.35 marta kamaytiradi). Taklifni
ko'r-ko'rona olmang — matn ma'nosiga moslang.
"""
import argparse
import json
import os
import random

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(HERE, "projects", "ideas_log.json")

CATALOG = {
    "kompozitsiya": ["full-bleed", "split-screen (gorizontal)", "split-screen (vertikal)", "iris doira",
                     "ravoq/deraza niqobi", "polaroid", "triptix", "film lentasi", "letterbox",
                     "karta + blur fon", "so'z ichida rasm", "ekran ichida ekran",
                     "sintetik osmon kengaytmasi", "band + qora maydon"],
    "kamera": ["push-in", "pull-out", "sho'ng'ish (zoom_between)", "panorama", "punch-in zarbada",
               "whip-pan", "shake + zoom punch", "rack focus", "tilt (ko'tarilish)", "orbit",
               "parallaks / dolly-zoom", "kalit-kadrli kuzatuv (_cam_keys)", "match-cut yuz"],
    "yorug'lik/zarra": ["god_rays", "flare", "light_leak", "flash", "shockwave", "sparks",
                        "flying_glyphs", "fall: barg/qor/yomg'ir/konfetti", "flock", "steam", "bokeh",
                        "stars", "dust", "bills (pul yomg'iri)", "lightning", "hex_shield",
                        "network (tarmoq uziladi)"],
    "rang": ["sovuq -> iliq", "oq-qora -> rang", "duotone xotira", "ichkari iliq / tashqari sovuq",
             "neon glitch -> sokin", "quyosh botishi", "tun -> tong"],
    "tipografiya": ["words_in blur", "chars_in", "text_rise", "scatter_in", "typewriter", "counter",
                    "marker", "strike", "glitch_text", "outline -> solid (chiziq o'tganda)",
                    "matn bosh ortida (sky_cutout)", "futbolkaga bosilgan matn (MULTIPLY)",
                    "so'z minorasi ko'tariladi", "eriydigan matn (melt_text)", "slam", "narx yorlig'i"],
    "o'tish": ["fade", "burn", "zoom", "dissolve", "whip", "flare", "iris", "blinds", "push", "luma",
               "glitchcut", "spin", "shutter (do'kon eshigi)", "timewarp", "cut zarbada"],
    "signature": ["pul tanaga tegib portlaydi", "do'kon eshigi yopiladi", "tanishlar tarmog'i uziladi",
                  "oltin chiziq tanani o'zgartiradi", "matn osmonda bosh ortida",
                  "energiya qalqoni + chaqmoq", "so'zlar minorasi ko'tariladi", "yosh hisoblagichi + vaqt "
                  "sakrashi", "silueta atrofida uy chiziladi", "muzqaymoqdek eriydigan matn",
                  "kollaj ichiga sho'ng'ish", "harflar uchib ketadi", "polaroidlar to'kiladi",
                  "soya -> odam", "ko'zgu rack-focus"],
}

MOOD = {
    "sokin": {"o'tish": ["dissolve", "fade", "luma", "burn"], "kamera": ["push-in", "panorama", "rack focus"]},
    "dramatik": {"o'tish": ["cut zarbada", "glitchcut", "flare", "timewarp"],
                 "kamera": ["shake + zoom punch", "punch-in zarbada", "pull-out"]},
    "energiya": {"o'tish": ["whip", "push", "spin", "glitchcut", "shutter (do'kon eshigi)"],
                 "kamera": ["whip-pan", "punch-in zarbada", "shake + zoom punch"]},
    "nostalji": {"o'tish": ["burn", "dissolve", "iris"], "kamera": ["pull-out", "panorama", "tilt (ko'tarilish)"]},
}


def used_counts():
    try:
        with open(LOG, encoding="utf-8") as fh:
            log = json.load(fh)
    except (OSError, ValueError):
        return {}
    cnt = {}
    for v in log.get("videos", []):
        for k in v.get("techniques", []) + v.get("signature", []):
            cnt[k] = cnt.get(k, 0) + 1
    return cnt


def pick(r, items, cnt, prefer=()):
    w = [(0.35 ** cnt.get(i, 0)) * (2.5 if i in prefer else 1.0) for i in items]
    return r.choices(items, weights=w, k=1)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", action="store_true")
    ap.add_argument("--scenes", type=int, default=6)
    ap.add_argument("--mood", default="dramatik", choices=sorted(MOOD))
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()
    if a.catalog:
        for k, v in CATALOG.items():
            print(f"\n[{k}]")
            for i in v:
                print("  -", i)
        return
    r = random.Random(a.seed)
    cnt = used_counts()
    m = MOOD[a.mood]
    used_tr = {}
    for i in range(a.scenes):
        tr = pick(r, CATALOG["o'tish"], {**cnt, **used_tr}, m.get("o'tish", ()))
        used_tr[tr] = used_tr.get(tr, 0) + 2
        print(f"{i + 1:2d}. {pick(r, CATALOG['kompozitsiya'], cnt):28s} | "
              f"{pick(r, CATALOG['kamera'], cnt, m.get('kamera', ())):26s} | "
              f"{pick(r, CATALOG['yorug' + chr(39) + 'lik/zarra'], cnt):24s} | "
              f"{pick(r, CATALOG['tipografiya'], cnt):34s} | {tr}")
    print("\nsignature:", pick(r, CATALOG["signature"], cnt))


if __name__ == "__main__":
    main()
