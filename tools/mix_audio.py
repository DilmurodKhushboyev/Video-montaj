#!/usr/bin/env python3
"""
mix_audio.py — ovoz yozuvi (azvuchka) + fon musiqasini Reels uchun aralashtirish.

    python3 tools/mix_audio.py VOICE MUSIC OUT.m4a --dur 47 --music-start 37.01 \
        [--voice-delay 0.2] [--voice-lufs -14] [--music-lufs -19] [--duck 8.5]
        [--music-eq FILTER|none] [--fade-in 0.3] [--fade-out 2.2]

* Ovoz past bo'lsa — maqsadli balandlikka chiziqli ko'tariladi (tembr o'zgarmaydi),
  cho'qqilar limiter bilan ushlanadi. Ovoz maqsadga yaqin bo'lsa (±1.5 LU) — tegilmaydi.
* Musiqa kerakli joydan kesiladi; video uzunroq bo'lsa — musiqa sikl bo'lib
  qayta ulanadi (crossfade bilan).
* Ovoz yangraganda musiqa silliq pasayadi (ducking), pauzalarda qaytadi.
* Musiqada nutq chastotalari (0.9 va 2.5 kHz) biroz kesiladi — ovozga "joy" ochiladi.
* Natijada nutq paytida ovoz va musiqa farqi (momentary LUFS) chop etiladi:
  Reels uchun mediana ~12-13 dB (8 dB — musiqa bosadi, 16 dB — musiqa juda past).
* Aralashtirish numpy'da, namunaga aniq — vaqt belgilarida teshik bo'lmaydi.
"""
import argparse
import json
import re
import subprocess

import numpy as np

SR = 48000
MUSIC_EQ = "equalizer=f=2500:t=q:w=1.0:g=-5,equalizer=f=900:t=q:w=1.2:g=-3"


def lufs(path, filt=None):
    af = (filt + "," if filt else "") + "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json"
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", af, "-f", "null",
                          "-"], capture_output=True, text=True).stderr
    return json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", err, re.S).group(0))


def decode(path, af=None, ch=2):
    cmd = ["ffmpeg", "-v", "error", "-i", path]
    if af:
        cmd += ["-af", af]
    cmd += ["-ac", str(ch), "-ar", str(SR), "-f", "f32le", "-"]
    x = np.frombuffer(subprocess.run(cmd, check=True, capture_output=True).stdout, np.float32)
    return x.reshape(-1, ch).copy()


def smooth_env(x, att, rel):
    """One-pole attack/release follower on |x| (mono, per-sample, vectorised by blocks)."""
    blk = 240  # 5 ms
    n = len(x) // blk + 1
    pad = np.zeros(n * blk, np.float32)
    pad[:len(x)] = np.abs(x)
    lv = np.sqrt((pad.reshape(n, blk) ** 2).mean(1))
    a_att = np.exp(-blk / (SR * att))
    a_rel = np.exp(-blk / (SR * rel))
    out = np.empty_like(lv)
    e = 0.0
    for i, v in enumerate(lv):
        c = a_att if v > e else a_rel
        e = c * e + (1 - c) * v
        out[i] = e
    return np.repeat(out, blk)[:len(x)]


def momentary(x):
    """Momentary loudness (400 ms, 10 Hz) of a stereo float array via ffmpeg ebur128."""
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-v", "verbose", "-f", "f32le", "-ar",
                        str(SR), "-ac", str(x.shape[1]), "-i", "-", "-af", "ebur128=framelog=verbose",
                        "-f", "null", "-"], input=np.ascontiguousarray(x, np.float32).tobytes(),
                       capture_output=True)
    return np.array([float(v) for v in re.findall(rb"M:\s*(-?[\d.]+)", p.stderr)])


def report_balance(voice, music):
    mv, mm = momentary(voice), momentary(music)
    n = min(len(mv), len(mm))
    mv, mm = mv[:n], mm[:n]
    sp = mv > -35
    if sp.any():
        d = mv[sp] - mm[sp]
        print(f"nutq paytida: ovoz {np.median(mv[sp]):.1f}, musiqa {np.median(mm[sp]):.1f} LUFS(M) -> "
              f"farq mediana {np.median(d):.1f} dB, 10-persentil {np.percentile(d, 10):.1f} dB; "
              f"pauzalarda musiqa {np.median(mm[~sp]):.1f}")


def write_wav(path, x):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac",
                          str(x.shape[1]), "-i", "-", path], stdin=subprocess.PIPE)
    p.stdin.write(np.ascontiguousarray(x, np.float32).tobytes())
    p.stdin.close()
    p.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("voice")
    ap.add_argument("music")
    ap.add_argument("out")
    ap.add_argument("--dur", type=float, required=True)
    ap.add_argument("--music-start", type=float, default=0.0)
    ap.add_argument("--voice-delay", type=float, default=0.0)
    ap.add_argument("--voice-lufs", type=float, default=-14.0)
    ap.add_argument("--music-lufs", type=float, default=-19.0)
    ap.add_argument("--duck", type=float, default=8.5, help="ovoz paytida musiqa pasayishi (dB)")
    ap.add_argument("--music-eq", default=MUSIC_EQ,
                    help="musiqaga ffmpeg EQ filtri (nutq diapazonini bo'shatish); 'none' — o'chirish")
    ap.add_argument("--fade-in", type=float, default=0.3)
    ap.add_argument("--fade-out", type=float, default=2.2)
    a = ap.parse_args()
    N = int(round(a.dur * SR))

    # ---- voice
    v = lufs(a.voice)
    vi = float(v["input_i"])
    if abs(vi - a.voice_lufs) <= 1.5:
        vaf = None
        print(f"ovoz: {vi:.1f} LUFS — joyida, tegilmadi")
    else:
        g = a.voice_lufs - vi
        vaf = f"volume={g:.2f}dB,alimiter=limit=0.84:attack=2:release=50:level=disabled"
        print(f"ovoz: {vi:.1f} LUFS -> {a.voice_lufs} LUFS ({g:+.1f} dB, past edi — ko'tarildi)")
    vo = decode(a.voice, vaf, 2)
    voice = np.zeros((N, 2), np.float32)
    d0 = int(round(a.voice_delay * SR))
    k = min(len(vo), N - d0)
    voice[d0:d0 + k] = vo[:k]

    # ---- music section (looped if too short)
    meq = None if a.music_eq in ("", "none") else a.music_eq
    mu = decode(a.music, meq, 2)
    s0 = int(round(a.music_start * SR))
    sec = mu[s0:]
    if len(sec) < N:
        xf = int(1.5 * SR)
        print(f"musiqa qisqa ({len(sec) / SR:.1f}s < {a.dur}s) — sikl qilib ulandi")
        while len(sec) < N:
            ramp = np.linspace(0, 1, xf, dtype=np.float32)[:, None]
            head = mu[:xf] * ramp
            sec = np.concatenate([sec[:-xf], sec[-xf:] * (1 - ramp) + head, mu[xf:]])
    music = sec[:N].copy()
    m = lufs(a.music, f"atrim=start={a.music_start}:duration={a.dur}" + (f",{meq}" if meq else ""))
    mgain = a.music_lufs - float(m["input_i"])
    print(f"musiqa bo'lagi: {float(m['input_i']):.1f} LUFS -> {a.music_lufs} LUFS ({mgain:+.1f} dB)")

    # ---- ducking: voice envelope -> 0..1 -> gain reduction
    env = smooth_env(voice.mean(1), att=0.04, rel=0.45)
    thr = 10 ** (-38 / 20)
    full = 10 ** (-22 / 20)
    w = np.clip((np.log10(env + 1e-9) - np.log10(thr)) / (np.log10(full) - np.log10(thr)), 0, 1)
    w = smooth_env(w, att=0.03, rel=0.35)  # smooth the gain curve itself
    gdb = mgain - a.duck * w
    t = np.arange(N) / SR
    fade = np.clip(t / max(a.fade_in, 1e-3), 0, 1) * np.clip((a.dur - t) / a.fade_out, 0, 1)
    music *= (10 ** (gdb / 20) * fade ** 1.5)[:, None].astype(np.float32)

    report_balance(voice, music)
    mix = voice + music
    pk = np.abs(mix).max()
    lim = 0.89
    if pk > lim:  # gentle soft-clip only above the limit
        over = np.abs(mix) > lim * 0.9
        mix[over] = np.sign(mix[over]) * (lim * 0.9 + (lim * 0.1) * np.tanh(
            (np.abs(mix[over]) - lim * 0.9) / (lim * 0.1)))
    wav = a.out.rsplit(".", 1)[0] + ".wav"
    write_wav(wav, mix)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-c:a", "aac", "-b:a", "256k",
                    a.out], check=True)
    r = lufs(a.out)
    print(f"tayyor: {a.out}  {a.dur:.3f}s  {float(r['input_i']):.1f} LUFS  "
          f"TP {float(r['input_tp']):.1f} dBTP  (wav: {wav})")


if __name__ == "__main__":
    main()
