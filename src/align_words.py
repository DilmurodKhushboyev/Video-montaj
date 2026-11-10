"""Matnni ovozga moslash: VAD bo'laklari + bo'g'in soni + energiya pastliklari.
Natija: data/words.json  [{seg, text, words:[{w,t0,t1}]}]"""
import json, re, sys
import numpy as np
import soundfile as sf

VOC = sys.argv[1]  # ajratilgan ovoz (16k mono)
OUT = sys.argv[2] if len(sys.argv) > 2 else "data/words.json"

SEGMENTS = [
    (0.16, 3.14, "Agar Alloh subhanahu va taolo sizni sevib qolsa, nima bo‘ladi?"),
    (3.84, 6.69, "Sahihul Buxoriyda kelgan hadisni sizga aytib beraman, yaxshilab tinglang."),
    (7.68, 9.89, "Rasululloh sollallohu alayhi vasallam aytadilarki,"),
    (10.81, 13.86, "agar Alloh subhanahu va taolo bir bandasini sevib qolsa,"),
    (14.52, 16.23, "Jabroil alayhissalomni chaqirib:"),
    (16.44, 17.16, "“Ey Jabroil,"),
    (17.88, 19.68, "men falonchi bandamni sevdim,"),
    (20.48, 21.44, "sen ham uni sevgin”, deydi."),
    (22.40, 23.97, "Jabroil alayhissalom ham uni sevadi."),
    (25.34, 28.84, "So‘ng Jabroil alayhissalom osmon ahliga nido qilib: “Ey osmon ahli,"),
    (29.08, 29.89, "ey maloikalar,"),
    (30.43, 33.06, "Alloh subhanahu va taolo falonchi bandani sevdi,"),
    (33.98, 35.43, "sizlar ham sevinglar”, deydi."),
    (36.51, 37.54, "Ular ham ma’qullashib,"),
    (37.92, 39.91, "u bandani ham sevishadi."),
    (39.96, 42.66, "So‘ng u bandaga shunaqa bir fazl beriladiki,"),
    (42.70, 45.40, "dunyoga maqbuliyatlik darajasi beriladi."),
]

def syll(w):
    n = len(re.findall(r"[aeiouAEIOU]", w))
    return max(1, n)

wav, sr = sf.read(VOC, dtype="float32")
hop = int(0.01 * sr)
frames = len(wav) // hop
env = np.array([np.sqrt((wav[i * hop:(i + 1) * hop] ** 2).mean() + 1e-12) for i in range(frames)])
env_db = 20 * np.log10(env + 1e-9)
env_db = np.convolve(env_db, np.ones(3) / 3, mode="same")

result = []
for i, (a, b, text) in enumerate(SEGMENTS):
    words = text.split()
    weights = np.array([syll(w) + 0.35 for w in words], float)
    bounds = a + np.concatenate([[0], np.cumsum(weights)]) / weights.sum() * (b - a)
    # ichki chegaralarni eng yaqin energiya pastligiga tortish
    for k in range(1, len(bounds) - 1):
        c = bounds[k]
        lo, hi = int((c - 0.09) * 100), int((c + 0.09) * 100)
        lo = max(lo, int((bounds[k - 1] + 0.12) * 100)); hi = min(hi, int((bounds[k + 1] - 0.12) * 100))
        if hi > lo:
            j = lo + int(np.argmin(env_db[lo:hi]))
            if env_db[j] < np.median(env_db[int(a * 100):int(b * 100)]) - 6:
                bounds[k] = j / 100.0
    result.append({"seg": i + 1, "t0": a, "t1": b, "text": text,
                   "words": [{"w": w, "t0": round(float(bounds[k]), 3), "t1": round(float(bounds[k + 1]), 3)}
                             for k, w in enumerate(words)]})
json.dump(result, open(OUT, "w"), ensure_ascii=False, indent=1)
for s in result:
    print(f"S{s['seg']:02d} " + " ".join(f"{w['w']}@{w['t0']:.2f}" for w in s["words"]))
