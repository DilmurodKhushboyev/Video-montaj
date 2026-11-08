#!/usr/bin/env python3
"""
mix_audio.py — hikoya ovozi + fon nashid/musiqani bitta audio trekka yig'ish.

  python3 tools/mix_audio.py <ovoz> <musiqa> <chiqish.m4a> --dur 46.5
        [--voice-offset 0.4] [--voice-gain-db 10.8] [--music-start 145.63]
        [--bed-db -18.5] [--open-db -9.5] [--speech 0.75 43.84] [--fade-out 2.2]
        [--loop]

* Ovoz o'zgartirilmaydi (faqat balandlik + -1.5 dBTP limiter), --voice-offset ga suriladi.
* Musiqa --music-start dan --dur uzunlikda kesiladi; yetmasa --loop bilan qayta ulanadi.
* Musiqa nutq paytida --bed-db, nutqdan oldin/keyin --open-db balandlikda (silliq o'tish),
  oxirida --fade-out.
"""
import argparse
import subprocess


def db(x):
    return 10 ** (x / 20)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("voice")
    ap.add_argument("music")
    ap.add_argument("out")
    ap.add_argument("--dur", type=float, required=True)
    ap.add_argument("--voice-offset", type=float, default=0.4)
    ap.add_argument("--voice-gain-db", type=float, default=0.0)
    ap.add_argument("--music-start", type=float, default=0.0)
    ap.add_argument("--bed-db", type=float, default=-18.0)
    ap.add_argument("--open-db", type=float, default=-9.0)
    ap.add_argument("--speech", nargs=2, type=float, required=True,
                    help="nutq boshlanishi va tugashi (video vaqtida)")
    ap.add_argument("--fade-out", type=float, default=2.0)
    ap.add_argument("--loop", action="store_true")
    a = ap.parse_args()
    lo, hi = db(a.bed_db), db(a.open_db)
    s0, s1 = a.speech
    env = (f"{hi:.4f}-({hi - lo:.4f})*clip((t-{s0 - 0.35:.3f})/0.40,0,1)"
           f"+({hi - lo:.4f})*clip((t-{s1 + 0.05:.3f})/0.70,0,1)")
    off_ms = int(round(a.voice_offset * 1000))
    music_in = ["-stream_loop", "-1"] if a.loop else []
    fc = (
        f"[0:a]aresample=48000,aformat=channel_layouts=stereo,volume={a.voice_gain_db}dB,"
        f"alimiter=limit={db(-1.5):.4f}:level=disabled,adelay={off_ms}|{off_ms},"
        f"apad,atrim=0:{a.dur}[v];"
        f"[1:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{a.dur},asetpts=N/SR/TB,"
        f"afade=t=in:d=0.06,volume='{env}':eval=frame,"
        f"afade=t=out:st={a.dur - a.fade_out:.3f}:d={a.fade_out}[m];"
        f"[v][m]amix=inputs=2:normalize=0:duration=first,"
        f"alimiter=limit={db(-1.0):.4f}:level=disabled[o]"
    )
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", a.voice] + music_in + \
          ["-ss", str(a.music_start), "-i", a.music, "-filter_complex", fc, "-map", "[o]",
           "-t", str(a.dur), "-c:a", "aac", "-b:a", "256k", "-ar", "48000", a.out]
    subprocess.run(cmd, check=True)
    print("tayyor:", a.out)


if __name__ == "__main__":
    main()
