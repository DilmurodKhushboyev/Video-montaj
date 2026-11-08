#!/usr/bin/env python3
"""
analyze_audio.py — ovozni montaj uchun tahlil qilish.

  python3 tools/analyze_audio.py <fayl> [--png spec.png] [--start S] [--dur D]
                                 [--min-pause 0.22] [--json out.json]

Chiqaradi:
  * pauzalar (sahna chegaralari) — RMS energiya sukunat bo'lgan oraliqlar;
  * nutq/ovoz bo'laklari (pauzalar orasidagi oraliqlar);
  * bass zarbalari (20–160 Hz energiyaning keskin o'sishi) — "katta lahzalar";
  * onsetlar (spektral oqim cho'qqilari);
  * ixtiyoriy spektrogramma PNG (vaqt o'qi soniyalarda belgilangan).
"""
import argparse
import json
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SR = 16000
HOP = 160          # 10 ms
WIN = 1024


def load(path, start=None, dur=None, sr=SR):
    cmd = ["ffmpeg", "-v", "error"]
    if start is not None:
        cmd += ["-ss", str(start)]
    if dur is not None:
        cmd += ["-t", str(dur)]
    cmd += ["-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def stft_mag(x):
    n = 1 + max(0, (len(x) - WIN) // HOP)
    idx = np.arange(WIN)[None, :] + HOP * np.arange(n)[:, None]
    fr = x[idx] * np.hanning(WIN)[None, :]
    return np.abs(np.fft.rfft(fr, axis=1)).astype(np.float32)  # (frames, bins)


def smooth(v, k):
    if k <= 1:
        return v
    ker = np.ones(k) / k
    return np.convolve(v, ker, mode="same")


def analyse(x, min_pause=0.22, sr=SR):
    t_hop = HOP / sr
    S = stft_mag(x)
    freqs = np.fft.rfftfreq(WIN, 1 / sr)
    rms = np.sqrt(np.mean((S / WIN) ** 2, axis=1))
    db = 20 * np.log10(rms + 1e-9)
    db_s = smooth(db, 5)
    ref = np.percentile(db_s, 95)
    floor = np.percentile(db_s, 5)
    thr = max(floor + 6, ref - 30)
    voiced = db_s > thr
    # pauses
    pauses = []
    i = 0
    n = len(voiced)
    while i < n:
        if not voiced[i]:
            j = i
            while j < n and not voiced[j]:
                j += 1
            if (j - i) * t_hop >= min_pause:
                pauses.append((round(i * t_hop, 3), round(j * t_hop, 3)))
            i = j
        else:
            i += 1
    # segments between pauses
    segs = []
    prev = 0.0
    for a, b in pauses:
        if a - prev > 0.05:
            segs.append((round(prev, 3), a))
        prev = b
    total = len(x) / sr
    if total - prev > 0.05:
        segs.append((round(prev, 3), round(total, 3)))
    # bass hits
    bass = S[:, (freqs >= 20) & (freqs <= 160)].sum(1)
    bd = np.diff(np.log(bass + 1e-6), prepend=0)
    bd = np.clip(bd, 0, None)
    bass_n = bass / (bass.max() + 1e-9)
    hits = []
    cand = np.argsort(-(bd * bass_n))
    for c in cand:
        if bd[c] * bass_n[c] < 0.08 or len(hits) >= 40:
            break
        if all(abs(c - h) * t_hop > 0.35 for h in hits):
            hits.append(c)
    hits = sorted(round(h * t_hop, 3) for h in hits)
    # spectral-flux onsets
    L = np.log1p(S)
    flux = np.clip(np.diff(L, axis=0, prepend=L[:1]), 0, None).sum(1)
    flux = smooth(flux, 3)
    thr_f = smooth(flux, 50) + 1.2 * flux.std()
    onsets = []
    for k in range(1, len(flux) - 1):
        if flux[k] > thr_f[k] and flux[k] >= flux[k - 1] and flux[k] >= flux[k + 1]:
            if not onsets or (k - onsets[-1]) * t_hop > 0.12:
                onsets.append(k)
    onsets = [round(k * t_hop, 3) for k in onsets]
    return dict(duration=round(total, 3), threshold_db=round(float(thr), 1), pauses=pauses,
                segments=segs, bass_hits=hits, onsets=onsets), S, db_s, freqs


def spec_png(S, db_s, freqs, path, segs, pauses, sr=SR, fmax=5000, px_per_s=60):
    t_hop = HOP / sr
    nb = int(np.searchsorted(freqs, fmax))
    M = np.log1p(S[:, :nb] * 20).T[::-1]
    M = (M - M.min()) / (np.ptp(M) + 1e-9)
    secs = S.shape[0] * t_hop
    wpx = int(secs * px_per_s)
    img = Image.fromarray((M ** 0.8 * 255).astype(np.uint8)).resize((wpx, 300))
    img = Image.merge("RGB", (img, img.point(lambda v: v * 0.8), img.point(lambda v: v * 0.4)))
    canvas = Image.new("RGB", (wpx, 300 + 110), (10, 10, 12))
    canvas.paste(img, (0, 0))
    dr = ImageDraw.Draw(canvas)
    # energy curve
    e = (db_s - db_s.min()) / (np.ptp(db_s) + 1e-9)
    pts = [(int(i * t_hop * px_per_s), 300 + 70 - int(v * 60)) for i, v in enumerate(e)]
    dr.line(pts, fill=(120, 220, 255), width=1)
    for a, b in pauses:
        dr.rectangle([a * px_per_s, 300, b * px_per_s, 380], fill=(80, 30, 30))
    try:
        f = ImageFont.load_default()
    except Exception:
        f = None
    for s in range(int(secs) + 1):
        x = s * px_per_s
        dr.line([(x, 380), (x, 392)], fill=(200, 200, 200))
        dr.text((x + 2, 393), str(s), fill=(220, 220, 220), font=f)
    canvas.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--png")
    ap.add_argument("--json")
    ap.add_argument("--start", type=float)
    ap.add_argument("--dur", type=float)
    ap.add_argument("--min-pause", type=float, default=0.22)
    a = ap.parse_args()
    x = load(a.src, a.start, a.dur)
    res, S, db_s, freqs = analyse(x, a.min_pause)
    print(f"davomiylik: {res['duration']} s, sukunat chegarasi {res['threshold_db']} dB")
    print("pauzalar:")
    for p in res["pauses"]:
        print(f"  {p[0]:7.2f} – {p[1]:7.2f}  ({p[1] - p[0]:.2f} s)")
    print("bo'laklar:")
    for s in res["segments"]:
        print(f"  {s[0]:7.2f} – {s[1]:7.2f}  ({s[1] - s[0]:.2f} s)")
    print("bass zarbalari:", ", ".join(f"{h:.2f}" for h in res["bass_hits"]))
    print("onsetlar soni:", len(res["onsets"]))
    if a.png:
        spec_png(S, db_s, freqs, a.png, res["segments"], res["pauses"])
        print("spektrogramma:", a.png)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(res, fh, indent=1)


if __name__ == "__main__":
    sys.exit(main())
