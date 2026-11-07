#!/usr/bin/env python3
"""
mix_audio.py — ovoz (azvuchka) + fon musiqa miksi.

  * ovoz tozalanadi (highpass, yengil EQ/kompressor) va ko'tariladi (two-pass loudnorm);
  * musiqa kesiladi/ulanadi (--edit "0:20.0,110.76:" — choklarda equal-power crossfade),
    kerak bo'lsa takrorlanadi (loop), oxirida so'nadi;
  * nutq paytida musiqa avtomatik pasayadi (ducking), pauzalarda ko'tariladi;
  * --muffle "20.4-31.3" — shu oraliqda musiqa "bo'g'iq" (lowpass) bo'lib qoladi;
  * yakuniy master: -14 LUFS, true peak -1 dBTP (Instagram/Reels).

    python3 tools/mix_audio.py --voice v.m4a --music m.mp3 --dur 58.5 --out mix.m4a \
        [--edit "0:20.0,110.76:"] [--voice-at 0] [--muffle "20.4-31.3"] \
        [--voice-lufs -16] [--music-open -19] [--music-duck -28] [--lufs -14]
"""
import argparse
import json
import os
import subprocess
import tempfile

import numpy as np
from scipy.signal import butter, sosfiltfilt

SR = 48000


def decode(path, ch, filt=None):
    cmd = ["ffmpeg", "-v", "error", "-i", path]
    if filt:
        cmd += ["-af", filt]
    cmd += ["-ac", str(ch), "-ar", str(SR), "-f", "f32le", "-"]
    a = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32)
    return a.reshape(-1, ch).copy()


def write_wav(path, x):
    x = np.ascontiguousarray(x, np.float32)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac",
                          str(x.shape[1]), "-i", "-", "-c:a", "pcm_f32le", path], stdin=subprocess.PIPE)
    p.stdin.write(x.tobytes())
    p.stdin.close()
    assert p.wait() == 0


def measure(path, filt=""):
    chain = (filt + "," if filt else "") + "loudnorm=print_format=json"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", chain, "-f", "null", "-"],
                       capture_output=True, text=True)
    js = r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1]
    return json.loads(js)


def loudnorm_2pass(src, dst, I, TP, LRA, pre=""):
    m = measure(src, pre)
    ln = (f"loudnorm=I={I}:TP={TP}:LRA={LRA}:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
          f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
          f":offset={m['target_offset']}:linear=true")
    chain = (pre + "," if pre else "") + ln
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af", chain, "-ar", str(SR),
                    "-c:a", "pcm_f32le", dst], check=True)
    return m


def lufs(path):
    return float(measure(path)["input_i"])


def parse_edit(s):
    segs = []
    for part in s.split(","):
        a, b = part.split(":")
        segs.append((float(a), float(b) if b else None))
    return segs


def splice(music, segs, need, xf=0.04):
    """Concatenate source segments with equal-power crossfades; loop if too short."""
    n_xf = int(xf * SR)
    pieces = []
    for a, b in segs:
        ia = int(a * SR)
        ib = len(music) if b is None else int(b * SR)
        pieces.append(music[ia:ib + n_xf])
    out = pieces[0]
    k = 1
    while True:
        while k < len(pieces):
            nxt = pieces[k]
            t = np.linspace(0, 1, n_xf, dtype=np.float32)[:, None]
            head, tail = out[:-n_xf], out[-n_xf:]
            mixed = tail * np.cos(t * np.pi / 2) + nxt[:n_xf] * np.sin(t * np.pi / 2)
            out = np.concatenate([head, mixed, nxt[n_xf:]])
            k += 1
        if len(out) >= need:
            return out[:need]
        k = 0  # loop the whole edit again, crossfading into its start
        pieces = list(pieces)


def ramp(n, pts):
    """Piecewise-linear automation from [(t, v), ...] (seconds) over n samples."""
    t = np.arange(n) / SR
    ts, vs = zip(*pts)
    return np.interp(t, ts, vs).astype(np.float32)


def smooth_env(target, att, rel, hop):
    """One-pole attack/release smoothing on a per-hop envelope (in dB)."""
    a_att = np.exp(-hop / (att * SR))
    a_rel = np.exp(-hop / (rel * SR))
    out = np.empty_like(target)
    y = target[0]
    for i, v in enumerate(target):
        a = a_att if v < y else a_rel
        y = a * y + (1 - a) * v
        out[i] = y
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", required=True)
    ap.add_argument("--music", required=True)
    ap.add_argument("--dur", type=float, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--edit", default="0:")
    ap.add_argument("--voice-at", type=float, default=0.0)
    ap.add_argument("--muffle", default="")
    ap.add_argument("--muffle-hz", type=float, default=650.0)
    ap.add_argument("--voice-lufs", type=float, default=-16.0)
    ap.add_argument("--music-open", type=float, default=-19.0)
    ap.add_argument("--music-duck", type=float, default=-28.0)
    ap.add_argument("--music-fade", type=float, default=2.8)
    ap.add_argument("--lufs", type=float, default=-14.0)
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="mix_")
    n = int(round(a.dur * SR))

    # ---- voice: clean + bring up to a broadcast speech level
    vchain = ("highpass=f=75,equalizer=f=230:t=q:w=1.0:g=-1.5,equalizer=f=3300:t=q:w=1.1:g=2.5,"
              "acompressor=threshold=-30dB:ratio=2.6:attack=6:release=170:knee=6:makeup=4")
    vpath = os.path.join(tmp, "voice.wav")
    loudnorm_2pass(a.voice, vpath, a.voice_lufs, -2.0, 9, vchain)
    v = decode(vpath, 1)[:, 0]
    # soft downward expander so the boosted room noise stays out of pauses
    hop = 480
    nv = len(v) // hop
    rms = np.sqrt(np.mean(v[:nv * hop].reshape(nv, hop) ** 2, axis=1) + 1e-12)
    vdb = 20 * np.log10(rms)
    gate_t = np.where(vdb < -52, -10.0, 0.0).astype(np.float32)
    gate = 10 ** (smooth_env(gate_t, 0.08, 0.01, hop) / 20)
    v[:nv * hop] *= np.repeat(gate, hop)
    voice = np.zeros(n, np.float32)
    i0 = int(a.voice_at * SR)
    m_ = min(len(v), n - i0)
    voice[i0:i0 + m_] = v[:m_]

    # ---- music: edit / loop
    mus = decode(a.music, 2)
    mus = splice(mus, parse_edit(a.edit), n)
    # muffle (zero-phase lowpass crossfaded in => no phase smear at the blend)
    if a.muffle:
        sos = butter(4, a.muffle_hz, "low", fs=SR, output="sos")
        lp = sosfiltfilt(sos, mus, axis=0).astype(np.float32) * 1.25
        pts = [(0, 0)]
        for rng in a.muffle.split(","):
            t0, t1 = map(float, rng.split("-"))
            pts += [(t0, 0), (t0 + 1.2, 0.88), (t1 - 0.35, 0.88), (t1, 0)]
        pts.append((a.dur + 1, 0))
        m = ramp(n, pts)[:, None]
        mus = mus * (1 - m) + lp * m
    mpath = os.path.join(tmp, "music_raw.wav")
    write_wav(mpath, mus)
    m_lufs = lufs(mpath)

    # ducking envelope from voice activity
    nh = n // hop
    vr = np.sqrt(np.mean(voice[:nh * hop].reshape(nh, hop) ** 2, axis=1) + 1e-12)
    act = 20 * np.log10(vr) > -42
    pad = int(0.18 * SR / hop)
    act_d = np.convolve(act.astype(np.float32), np.ones(2 * pad + 1), "same") > 0
    open_g, duck_g = a.music_open - m_lufs, a.music_duck - m_lufs
    target = np.where(act_d, duck_g, open_g).astype(np.float32)
    env = smooth_env(target, 0.07, 0.45, hop)
    g = np.interp(np.arange(n), np.arange(nh) * hop + hop / 2, env).astype(np.float32)
    gl = 10 ** (g / 20)
    # intro fade-in + outro fade-out
    fade = ramp(n, [(0, 0.0), (0.12, 1.0), (a.dur - a.music_fade, 1.0), (a.dur, 0.0)])
    fade = np.sin(fade * np.pi / 2)
    mus = mus * (gl * fade)[:, None]

    mix = mus + voice[:, None]
    raw = os.path.join(tmp, "mix_raw.wav")
    write_wav(raw, mix)
    master = os.path.join(tmp, "master.wav")
    loudnorm_2pass(raw, master, a.lufs, -1.0, 11)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", master, "-t", f"{a.dur:.3f}",
                    "-c:a", "aac", "-b:a", "256k", "-ar", str(SR), a.out], check=True)
    fin = measure(a.out)
    print(f"musiqa (kesilgan) {m_lufs:.1f} LUFS -> ochiq {a.music_open}, nutq ostida {a.music_duck}")
    print(f"tayyor: {a.out}  {fin['input_i']} LUFS, TP {fin['input_tp']} dBTP")


if __name__ == "__main__":
    main()
