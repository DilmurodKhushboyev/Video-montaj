#!/usr/bin/env python3
"""
analyze_audio.py — ovozni montaj uchun tahlil qilish.

    python3 tools/analyze_audio.py in.mp4|in.wav [--png spec.png] [--start S] [--dur D]
                                     [--pause-db -38] [--min-pause 0.22]

Chiqaradi:
  * nutq bo'laklari va pauzalar (sahna chegaralari uchun)
  * bass zarbalari (katta lahzalar) va onsetlar (urg'ular)
  * taxminiy temp (BPM)
  * --png: spektrogramma + energiya + belgilangan pauza/zarbalar
"""
import argparse
import json
import subprocess
import sys

import numpy as np

SR = 16000


def load(path, start=None, dur=None, sr=SR):
    cmd = ["ffmpeg", "-v", "error"]
    if start is not None:
        cmd += ["-ss", str(start)]
    if dur is not None:
        cmd += ["-t", str(dur)]
    cmd += ["-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def frames(x, hop, win):
    n = 1 + max(0, (len(x) - win) // hop)
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    return x[idx]


def envelope_db(x, hop=160, win=640):
    f = frames(x, hop, win)
    rms = np.sqrt((f ** 2).mean(1) + 1e-12)
    return 20 * np.log10(rms + 1e-9), hop / SR


def speech_segments(db, dt, thr, min_pause, min_seg=0.12):
    on = db > thr
    segs, s = [], None
    for i, v in enumerate(on):
        if v and s is None:
            s = i
        elif not v and s is not None:
            segs.append([s * dt, i * dt])
            s = None
    if s is not None:
        segs.append([s * dt, len(on) * dt])
    merged = []
    for a, b in segs:
        if merged and a - merged[-1][1] < min_pause:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [m for m in merged if m[1] - m[0] >= min_seg]


def spectral_flux(x, band=None, hop=512, win=2048):
    f = frames(x, hop, win) * np.hanning(win)[None, :]
    S = np.abs(np.fft.rfft(f, axis=1))
    freqs = np.fft.rfftfreq(win, 1 / SR)
    if band:
        S = S[:, (freqs >= band[0]) & (freqs < band[1])]
    S = np.log1p(S * 10)
    fl = np.maximum(0, np.diff(S, axis=0)).sum(1)
    fl = np.concatenate([[0], fl])
    return fl, hop / SR, S


def peaks(sig, dt, k=1.6, min_gap=0.18, win_s=1.5):
    w = max(3, int(win_s / dt))
    pad = np.pad(sig, (w, w), mode="edge")
    med = np.array([np.median(pad[i:i + 2 * w]) for i in range(len(sig))])
    std = sig.std() + 1e-9
    out, last = [], -1e9
    for i in range(1, len(sig) - 1):
        if sig[i] > med[i] + k * std and sig[i] >= sig[i - 1] and sig[i] >= sig[i + 1]:
            t = i * dt
            if t - last >= min_gap:
                out.append((round(t, 3), round(float((sig[i] - med[i]) / std), 2)))
                last = t
    return out


def tempo(flux, dt):
    f = flux - flux.mean()
    ac = np.correlate(f, f, "full")[len(f) - 1:]
    lo, hi = int(60 / 180 / dt), int(60 / 50 / dt)
    lag = lo + int(np.argmax(ac[lo:hi]))
    return 60 / (lag * dt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--png")
    ap.add_argument("--start", type=float)
    ap.add_argument("--dur", type=float)
    ap.add_argument("--pause-db", type=float, default=None)
    ap.add_argument("--min-pause", type=float, default=0.22)
    ap.add_argument("--json")
    a = ap.parse_args()

    x = load(a.src, a.start, a.dur)
    dur = len(x) / SR
    db, dt = envelope_db(x)
    thr = a.pause_db if a.pause_db is not None else max(np.percentile(db, 20) + 8, db.max() - 38)
    segs = speech_segments(db, dt, thr, a.min_pause)
    pauses = [(round(segs[i][1], 3), round(segs[i + 1][0], 3), round(segs[i + 1][0] - segs[i][1], 3))
              for i in range(len(segs) - 1)]
    bflux, bdt, _ = spectral_flux(x, (30, 160))
    fflux, fdt, S = spectral_flux(x)
    bass = peaks(bflux, bdt, k=2.2, min_gap=0.25)
    onsets = peaks(fflux, fdt, k=1.4, min_gap=0.12)
    bpm = tempo(fflux, fdt)

    res = {"duration": round(dur, 3), "threshold_db": round(float(thr), 1),
           "segments": [[round(s, 3), round(e, 3)] for s, e in segs], "pauses": pauses,
           "bass_hits": bass, "onsets": onsets, "bpm": round(bpm, 1)}
    print(f"davomiylik: {dur:.3f} s   chegara: {thr:.1f} dB   temp: ~{bpm:.0f} BPM")
    print(f"\nNutq/ovoz bo'laklari ({len(segs)}):")
    for i, (s, e) in enumerate(segs):
        print(f"  {i:2d}  {s:7.3f} - {e:7.3f}  ({e - s:5.2f} s)")
    print(f"\nPauzalar (>= {a.min_pause}s):")
    for s, e, d in sorted(pauses, key=lambda p: -p[2]):
        print(f"  {s:7.3f} -> {e:7.3f}   {d:5.2f} s")
    print(f"\nBass zarbalari ({len(bass)}): " + ", ".join(f"{t:.2f}({s})" for t, s in bass[:60]))
    print(f"\nOnsetlar ({len(onsets)}): " + ", ".join(f"{t:.2f}" for t, _ in onsets[:120]))
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(res, fh, indent=1)
    if a.png:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(3, 1, figsize=(max(14, dur * 0.6), 9), sharex=True)
        ax[0].imshow(S.T, origin="lower", aspect="auto", extent=[0, len(S) * fdt, 0, SR / 2],
                     cmap="magma")
        ax[0].set_ylim(0, 5000)
        ax[0].set_ylabel("Hz")
        tt = np.arange(len(db)) * dt
        ax[1].plot(tt, db, lw=0.6)
        ax[1].axhline(thr, color="r", lw=0.8)
        for s, e in segs:
            ax[1].axvspan(s, e, color="g", alpha=0.12)
        ax[1].set_ylabel("dB")
        ax[2].plot(np.arange(len(bflux)) * bdt, bflux / (bflux.max() + 1e-9), lw=0.6, label="bass")
        ax[2].plot(np.arange(len(fflux)) * fdt, fflux / (fflux.max() + 1e-9), lw=0.4, alpha=0.6,
                   label="flux")
        for t, _ in bass:
            ax[2].axvline(t, color="r", lw=0.6, alpha=0.7)
        ax[2].legend(loc="upper right")
        ax[2].set_xlabel("s")
        ax[2].set_xticks(np.arange(0, dur + 1, 1.0 if dur < 80 else 5.0))
        for axx in ax:
            axx.grid(alpha=0.25)
        plt.tight_layout()
        plt.savefig(a.png, dpi=70)
        print("\npng:", a.png)


if __name__ == "__main__":
    sys.exit(main())
