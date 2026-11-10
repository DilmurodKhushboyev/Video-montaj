#!/usr/bin/env python3
"""Ovoz miksi: ajratilgan nutq + fon musiqasi (videoning o'zidan) + montaj SFX.

Asl videoda nutq musiqadan atigi ~1-3 LU baland edi (ba'zi joylarda musiqa ostida qolgan).
Shu sababli nutq va musiqa MDX-Net bilan ajratildi va qayta balanslandi:
  * nutq: HPF, yengil EQ (aniqlik), kompressor -> tekis va tushunarli
  * musiqa: nutqdan ~12-14 LU past, gaplar orasida biroz ko'tariladi (ducking)
  * matn tugagan joyda (46.0 s) nutq kesiladi, oxirgi so'zga reverb "dumi", musiqa yumshoq so'nadi
  * yakuniy: -14 LUFS, true-peak <= -1 dBTP (Instagram uchun)
"""
import os
import sys

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy import signal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, "build", "audio")
SR = 44100
DUR = 49.2
VOICE_END = 46.0
rng = np.random.default_rng(11)


def db(x):
    return 10 ** (x / 20.0)


def peaking(f0, gain_db, q):
    a = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * f0 / SR
    al = np.sin(w0) / (2 * q)
    b = [1 + al * a, -2 * np.cos(w0), 1 - al * a]
    aa = [1 + al / a, -2 * np.cos(w0), 1 - al / a]
    return np.array(b) / aa[0], np.array(aa) / aa[0]


def shelf_high(f0, gain_db):
    a = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * f0 / SR
    al = np.sin(w0) / 2 * np.sqrt(2)
    cs = np.cos(w0)
    b0 = a * ((a + 1) + (a - 1) * cs + 2 * np.sqrt(a) * al)
    b1 = -2 * a * ((a - 1) + (a + 1) * cs)
    b2 = a * ((a + 1) + (a - 1) * cs - 2 * np.sqrt(a) * al)
    a0 = (a + 1) - (a - 1) * cs + 2 * np.sqrt(a) * al
    a1 = 2 * ((a - 1) - (a + 1) * cs)
    a2 = (a + 1) - (a - 1) * cs - 2 * np.sqrt(a) * al
    return np.array([b0, b1, b2]) / a0, np.array([a0, a1, a2]) / a0


def filt(x, ba):
    return signal.lfilter(ba[0], ba[1], x, axis=0)


def envelope(x, att, rel):
    """Bir kanalli amplituda konverti (attack/release, soniyada)."""
    a_at = np.exp(-1 / (att * SR))
    a_rl = np.exp(-1 / (rel * SR))
    # tezlik uchun 64 namunali bloklarda
    blk = 64
    n = len(x) // blk
    r = np.sqrt((x[:n * blk].reshape(n, blk) ** 2).mean(1) + 1e-12)
    env = np.zeros(n)
    e = 0.0
    aa, ar = a_at ** blk, a_rl ** blk
    for i in range(n):
        c = aa if r[i] > e else ar
        e = c * e + (1 - c) * r[i]
        env[i] = e
    return np.repeat(env, blk)[:len(x)] if n else np.zeros(len(x))


def compress(x, thr_db=-24, ratio=3.0, att=0.008, rel=0.16, knee=6):
    mono = x.mean(1)
    env = envelope(mono, att, rel)
    env = np.pad(env, (0, len(x) - len(env)), mode="edge")
    lvl = 20 * np.log10(env + 1e-9)
    over = lvl - thr_db
    gr = np.where(over <= -knee / 2, 0.0,
                  np.where(over >= knee / 2, over * (1 - 1 / ratio),
                           (1 - 1 / ratio) * (over + knee / 2) ** 2 / (2 * knee)))
    return x * db(-gr)[:, None]


def fade(n, kind="in"):
    t = np.linspace(0, np.pi / 2, n)
    return np.sin(t) if kind == "in" else np.cos(t)


def place(buf, clip, t):
    i = int(t * SR)
    if i < 0:
        clip = clip[-i:]
        i = 0
    j = min(len(buf), i + len(clip))
    if j > i:
        buf[i:j] += clip[:j - i]


# ------------------------------------------------------------------ SFX sintezi
def bandnoise_sweep(dur, f_from, f_to, q=1.2, env=None, pan=None):
    n = int(dur * SR)
    noise = rng.normal(0, 1, n)
    bands = np.geomspace(min(f_from, f_to), max(f_from, f_to), 10)
    outs = []
    for fc in bands:
        b, a = signal.butter(2, [fc / 1.6 / (SR / 2), min(0.99, fc * 1.6 / (SR / 2))], btype="band")
        outs.append(signal.lfilter(b, a, noise))
    outs = np.array(outs)
    pos = np.linspace(0, 1, n)
    if f_from > f_to:
        pos = 1 - pos
    idx = pos * (len(bands) - 1)
    lo = np.floor(idx).astype(int)
    hi = np.minimum(lo + 1, len(bands) - 1)
    fr = idx - lo
    y = outs[lo, np.arange(n)] * (1 - fr) + outs[hi, np.arange(n)] * fr
    if env is not None:
        y *= env
    y /= np.abs(y).max() + 1e-9
    st = np.stack([y, y], 1)
    if pan is not None:  # pan: (boshlanish, tugash) -1..1
        p = np.linspace(pan[0], pan[1], n)
        st[:, 0] *= np.sqrt((1 - p) / 2)
        st[:, 1] *= np.sqrt((1 + p) / 2)
        st *= np.sqrt(2)
    return st


def whoosh(dur=0.55, peak=0.55, f0=250, f1=4500, pan=None, level=-22):
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    env = np.where(t < peak, (t / peak) ** 2.2, np.exp(-(t - peak) / (1 - peak) * 4.5))
    up = bandnoise_sweep(dur, f0, f1, env=env, pan=pan)
    return up * db(level)


def boom(level=-18, dur=1.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 32 + 40 * np.exp(-t * 6)
    ph = 2 * np.pi * np.cumsum(f) / SR
    sub = np.sin(ph) * np.exp(-t * 2.6)
    click = signal.lfilter(*signal.butter(2, 180 / (SR / 2)), rng.normal(0, 1, n)) * np.exp(-t * 25)
    click /= np.abs(click).max() + 1e-9
    y = sub * 0.9 + click * 0.35
    y /= np.abs(y).max()
    return np.stack([y, y], 1) * db(level)


def shimmer(level=-30, dur=1.4, seed=0):
    r = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.zeros((n, 2))
    hp = signal.butter(2, 5000 / (SR / 2), btype="high")
    nz = signal.lfilter(*hp, r.normal(0, 1, (n, 2)), axis=0)
    trem = 0.6 + 0.4 * np.sin(2 * np.pi * 9 * t)[:, None]
    y += nz * np.exp(-t * 3.2)[:, None] * trem * 0.5
    for _ in range(14):  # mayda "yaltirash" lar
        f = r.uniform(3000, 9000)
        t0 = r.uniform(0, dur * 0.5)
        i0 = int(t0 * SR)
        tt = np.arange(n - i0) / SR
        g = np.sin(2 * np.pi * f * tt) * np.exp(-tt * r.uniform(10, 25)) * r.uniform(0.2, 0.5)
        ch = r.uniform(0, 1)
        y[i0:, 0] += g * (1 - ch)
        y[i0:, 1] += g * ch
    y /= np.abs(y).max() + 1e-9
    return y * db(level)


def riser(dur=0.6, level=-26):
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    env = t ** 2.5
    y = bandnoise_sweep(dur, 400, 7000, env=env)
    return y * db(level)


def reverb_ir(rt60=3.2, dur=3.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    decay = np.exp(-6.91 * t / rt60)
    ir = rng.normal(0, 1, (n, 2)) * decay[:, None]
    ir = signal.lfilter(*signal.butter(2, 6500 / (SR / 2)), ir, axis=0)
    pre = int(0.03 * SR)
    ir = np.concatenate([np.zeros((pre, 2)), ir])
    return ir / np.sqrt((ir ** 2).sum(0))


def main():
    voc, sr = sf.read(os.path.join(A, "sep54_vocals.wav"), dtype="float64")
    mus, _ = sf.read(os.path.join(A, "sep54_music.wav"), dtype="float64")
    assert sr == SR
    N = int(DUR * SR)
    meter = pyln.Meter(SR)

    # ------------------------------------------------ nutq
    v = voc[:N].copy()
    ve = int(VOICE_END * SR)
    fl = int(0.15 * SR)
    v[ve - fl:ve] *= fade(fl, "out")[:, None]
    v[ve:] = 0
    # Gaplar orasida ajratilgan "vokal" stemda fondagi nashid/hum qolgan (17-23 s) --
    # uni musiqa darajasiga tushirish uchun gate (-12 dB), nutq bo'laklari words.json dan.
    import json
    segs = json.load(open(os.path.join(ROOT, "data", "words.json"), encoding="utf-8"))
    gate = np.full(N, db(-12.0))
    for k, s in enumerate(segs):
        g0 = max(0, int((s["t0"] - 0.08) * SR))
        g1 = int(((VOICE_END if k == len(segs) - 1 else s["t1"]) + 0.22) * SR)
        gate[g0:min(N, g1)] = 1.0
    win = np.hanning(int(0.06 * SR))
    gate = np.convolve(gate, win / win.sum(), mode="same")
    v *= gate[:, None]
    v = filt(v, signal.butter(2, 75 / (SR / 2), btype="high"))
    v = filt(v, peaking(280, -2.0, 1.0))
    v = filt(v, peaking(3200, 2.5, 0.9))
    v = filt(v, shelf_high(10000, 1.5))
    v = compress(v, thr_db=-26, ratio=2.8)
    lv = meter.integrated_loudness(v[:ve])
    v *= db(-17.0 - lv)
    print(f"voice: {lv:.1f} LUFS -> -17.0 LUFS")

    # oxirgi so'z uchun reverb dumi
    send = np.zeros(N)
    a0, a1 = int(44.6 * SR), int(45.4 * SR)
    send[a0:a1] = np.linspace(0, 1, a1 - a0)
    send[a1:ve] = 1
    wet_in = v * send[:, None]
    ir = reverb_ir()
    wet = np.stack([signal.fftconvolve(wet_in[:, c], ir[:, c])[:N] for c in range(2)], 1)
    wet *= db(-8)

    # ------------------------------------------------ musiqa
    m = mus[:N].copy()
    lm = meter.integrated_loudness(m[:ve])
    base = -17.0 - 9.0  # nutqdan 9 LU past, gap paytida qo'shimcha ducking bilan ~13 LU
    m *= db(base - lm)
    print(f"music: {lm:.1f} LUFS -> {base:.1f} LUFS (+ducking)")
    # ducking: nutq bo'lganda -4.5 dB
    venv = envelope(voc[:N].mean(1), 0.01, 0.05)
    venv = np.pad(venv, (0, N - len(venv)), mode="edge")
    thr = np.percentile(venv[:ve], 35)
    mask = (venv > thr).astype(float)
    mask[ve:] = 0
    # attack 80 ms / release 450 ms bilan silliqlash
    k = np.zeros(N)
    e = 0.0
    aa, ar = np.exp(-1 / (0.08 * SR / 64)), np.exp(-1 / (0.45 * SR / 64))
    for i in range(0, N, 64):
        tgt = mask[i]
        c = aa if tgt > e else ar
        e = c * e + (1 - c) * tgt
        k[i:i + 64] = e
    duck_db = -4.5 * k
    # yakun: musiqa biroz ko'tariladi, so'ng past chastotaga "suzib" so'nadi
    t = np.arange(N) / SR
    swell = 3.0 * np.clip((t - VOICE_END) / 0.8, 0, 1)
    m *= db(duck_db + swell)[:, None]
    lp = filt(m, signal.butter(2, 1400 / (SR / 2)))
    kk = np.clip((t - 46.6) / 2.2, 0, 1)[:, None] ** 1.2
    m = m * (1 - kk) + lp * kk
    fo0, fo1 = int(47.3 * SR), N
    m[fo0:fo1] *= np.cos(np.linspace(0, np.pi / 2, fo1 - fo0))[:, None] ** 1.5
    wet[fo0:fo1] *= np.cos(np.linspace(0, np.pi / 2, fo1 - fo0))[:, None]

    # ------------------------------------------------ SFX (montaj tovushlari)
    fxb = np.zeros((N, 2))
    place(fxb, boom(-27, 1.2) + shimmer(-34, 1.2, 1)[:int(1.2 * SR)], 0.0)
    place(fxb, whoosh(0.5, 0.56, 300, 5000, level=-25), 1.62 - 0.28)
    place(fxb, riser(0.45, -30), 2.40 - 0.45)
    place(fxb, boom(-19, 1.6), 2.40)
    place(fxb, shimmer(-29, 1.6, 2), 2.40)
    place(fxb, whoosh(1.0, 0.5, 200, 1500, level=-31), 3.62 - 0.5)
    for i, tt in enumerate((7.55, 17.85, 38.00, 42.70)):
        place(fxb, shimmer(-35, 1.3, 10 + i), tt - 0.25)
    for tt in (14.35, 24.80):
        place(fxb, whoosh(0.7, 0.6, 150, 2500, level=-27), tt - 0.42)
    for tt in (16.35, 28.00):
        place(fxb, boom(-27, 1.2), tt)
        place(fxb, shimmer(-33, 1.2, int(tt)), tt)
    for tt in (26.70, 30.40, 33.95, 39.95):
        place(fxb, whoosh(0.5, 0.56, 300, 5000, pan=(0.7, -0.7), level=-26), tt - 0.28)
    place(fxb, riser(0.4, -29), 41.45 - 0.4)
    place(fxb, boom(-20, 1.6), 41.45)
    place(fxb, shimmer(-29, 1.6, 41), 41.45)
    place(fxb, whoosh(1.2, 0.55, 150, 1200, level=-31), 46.40 - 0.66)

    mix = v + wet + m + fxb
    sf.write(os.path.join(A, "premaster.wav"), mix.astype(np.float32), SR, subtype="FLOAT")
    # nazorat uchun alohida stemlar
    sf.write(os.path.join(A, "stem_voice.wav"), (v + wet).astype(np.float32), SR, subtype="FLOAT")
    sf.write(os.path.join(A, "stem_music.wav"), m.astype(np.float32), SR, subtype="FLOAT")
    sf.write(os.path.join(A, "stem_sfx.wav"), fxb.astype(np.float32), SR, subtype="FLOAT")
    print("premaster loudness:", round(meter.integrated_loudness(mix), 1), "LUFS")


if __name__ == "__main__":
    main()
