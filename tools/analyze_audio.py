#!/usr/bin/env python3
"""
analyze_audio.py — ovoz tahlili: pauzalar (sahna chegaralari), bass zarbalari, onsetlar,
spektrogramma. Montajda sahnalarni nutq/musiqa ritmiga bog'lash uchun.

    python3 tools/analyze_audio.py in.(mp4|m4a|mp3) [--png spec.png] [--start S --dur D]
           [--json out.json] [--pause-db -38] [--min-pause 0.25]
"""
import argparse
import json
import subprocess

import numpy as np

SR = 22050


def decode(path, start=None, dur=None, stereo=False):
    cmd = ["ffmpeg", "-v", "error"]
    if start is not None:
        cmd += ["-ss", str(start)]
    if dur is not None:
        cmd += ["-t", str(dur)]
    cmd += ["-i", path, "-ac", "2" if stereo else "1", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.float32)
    return a.reshape(-1, 2) if stereo else a


def frames(x, hop=256, win=1024):
    n = 1 + max(0, (len(x) - win) // hop)
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    return x[idx] * np.hanning(win)[None, :]


def analyze(x, hop=256, win=1024):
    fr = frames(x, hop, win)
    spec = np.abs(np.fft.rfft(fr, axis=1))
    freqs = np.fft.rfftfreq(win, 1 / SR)
    rms = np.sqrt(np.mean((fr / np.hanning(win).mean()) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms + 1e-9)
    bass = spec[:, freqs < 150].sum(1)
    flux = np.maximum(0, np.diff(np.log1p(spec), axis=0)).sum(1)
    flux = np.concatenate([[0], flux])
    t = np.arange(len(db)) * hop / SR
    return t, db, bass, flux, spec, freqs


def pauses(t, db, thr=-38.0, min_len=0.25):
    """Quiet stretches below thr dB (relative to the loudest frame)."""
    rel = db - db.max()
    q = rel < thr
    out, s = [], None
    for i, v in enumerate(q):
        if v and s is None:
            s = i
        elif not v and s is not None:
            if t[i] - t[s] >= min_len:
                out.append((round(float(t[s]), 3), round(float(t[i]), 3)))
            s = None
    if s is not None and t[-1] - t[s] >= min_len:
        out.append((round(float(t[s]), 3), round(float(t[-1]), 3)))
    return out


def peaks(t, v, k=1.6, min_gap=0.18):
    """Local maxima above mean + k*std, at least min_gap seconds apart."""
    thr = v.mean() + k * v.std()
    out = []
    for i in range(1, len(v) - 1):
        if v[i] > thr and v[i] >= v[i - 1] and v[i] >= v[i + 1]:
            if not out or t[i] - out[-1][0] >= min_gap:
                out.append((round(float(t[i]), 3), float(v[i])))
            elif v[i] > out[-1][1]:
                out[-1] = (round(float(t[i]), 3), float(v[i]))
    return out


def save_png(path, t, spec, freqs, db, marks=()):
    from PIL import Image, ImageDraw
    fmax = 6000
    s = np.log1p(spec[:, freqs < fmax]).T[::-1]
    s = (s - s.min()) / (np.ptp(s) + 1e-9)
    secs = t[-1] if len(t) else 1
    wpx = int(min(4000, max(800, secs * 40)))
    img = Image.fromarray((255 * s ** 0.7).astype(np.uint8)).resize((wpx, 400))
    img = Image.merge("RGB", (img, img.point(lambda v: v * 0.8), img.point(lambda v: 255 - v)))
    canvas = Image.new("RGB", (wpx, 560), (10, 10, 14))
    canvas.paste(img, (0, 0))
    d = ImageDraw.Draw(canvas)
    pts = [(int(i / len(db) * wpx), 400 + int(150 * (1 - (v - db.min()) / (np.ptp(db) + 1e-9))))
           for i, v in enumerate(db)]
    d.line(pts, fill=(255, 210, 120), width=1)
    for sec in range(int(secs) + 1):
        x = int(sec / secs * wpx)
        d.line([(x, 400), (x, 410 if sec % 5 else 425)], fill=(200, 200, 200))
        if sec % 5 == 0:
            d.text((x + 2, 540), str(sec), fill=(220, 220, 220))
    for m in marks:
        x = int(m / secs * wpx)
        d.line([(x, 0), (x, 400)], fill=(80, 255, 120))
    canvas.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--png")
    ap.add_argument("--json")
    ap.add_argument("--start", type=float)
    ap.add_argument("--dur", type=float)
    ap.add_argument("--pause-db", type=float, default=-38.0)
    ap.add_argument("--min-pause", type=float, default=0.25)
    a = ap.parse_args()
    x = decode(a.src, a.start, a.dur)
    t, db, bass, flux, spec, freqs = analyze(x)
    ps = pauses(t, db, a.pause_db, a.min_pause)
    bh = peaks(t, bass, 2.0, 0.25)
    on = peaks(t, flux, 1.6, 0.12)
    print(f"davomiylik: {len(x) / SR:.3f} s")
    print("pauzalar:", ", ".join(f"{s:.2f}-{e:.2f}" for s, e in ps))
    print("bass zarbalari:", ", ".join(f"{s:.2f}" for s, _ in bh[:80]))
    print("onsetlar:", ", ".join(f"{s:.2f}" for s, _ in on[:200]))
    if a.png:
        save_png(a.png, t, spec, freqs, db, [s for s, _ in bh])
    if a.json:
        json.dump({"pauses": ps, "bass": [s for s, _ in bh], "onsets": [s for s, _ in on]},
                  open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
