#!/usr/bin/env python3
"""Instagram Reels montaji: "Agar Alloh sizni sevib qolsa nima bo'ladi?" (1080x1920, 30 fps).

Foydalanish:
  python src/montage.py --stills 1.0,5.2,...          # sinov kadrlar
  python src/montage.py --render --workers 4          # to'liq video (ovozsiz) -> build/video_noaudio.mp4
"""
import argparse
import json
import math
import os
import subprocess
import sys
from multiprocessing import Process

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx  # noqa: E402
from fx import W, H, FPS, ease, GOLD_HI, WARM, SUN  # noqa: E402
from typo import Card, Line, Word  # noqa: E402

cv2.setNumThreads(1)
ROOT = fx.ROOT
DUR = 49.2  # ovoz 46.0 s da tugaydi + 3.2 s yakuniy kadr

# ---------------------------------------------------------------- so'z vaqtlari
_WT = json.load(open(os.path.join(ROOT, "data", "words.json"), encoding="utf-8"))


def wt(seg, idx):
    w = _WT[seg - 1]["words"][idx]
    return w["t0"], w["t1"]


def Wd(text, seg, idx, **kw):
    t0, t1 = wt(seg, idx)
    return Word(text, t0, t1, **kw)


# ---------------------------------------------------------------- kadrlar (EDL)
class Shot:
    def __init__(self, panel, t0, t1, c0, c1, e="io", grade="heaven", bloom=0.35, rays=None, flare=None,
                 parts=None, pulse=(), mblur=1, rot=(0.0, 0.0)):
        self.panel, self.t0, self.t1, self.c0, self.c1, self.e = panel, t0, t1, c0, c1, e
        self.grade, self.bloom, self.rays, self.flare, self.parts = grade, bloom, rays, flare, parts
        self.pulse, self.mblur, self.rot = pulse, mblur, rot
        self.start, self.end = t0, t1
        self._p = None
        self.seed = (sum(map(ord, panel)) % 97) * 0.37 + t0 * 0.11

    def particles(self):
        if self._p is None and self.parts:
            kind, inten, seed = self.parts
            color = GOLD_HI if kind == "gold" else fx.hexbgr("FFF6E0")
            self._p = fx.Particles(110 if kind == "gold" else 70, seed, color=color)
        return self._p

    def cam(self, t, zmul=1.0):
        p = (t - self.start) / max(1e-6, self.end - self.start)
        k = ease(p, self.e)
        cx = self.c0[0] + (self.c1[0] - self.c0[0]) * k
        cy = self.c0[1] + (self.c1[1] - self.c0[1]) * k
        z = (self.c0[2] + (self.c1[2] - self.c0[2]) * k) * zmul
        r = self.rot[0] + (self.rot[1] - self.rot[0]) * k
        return cx, cy, z, r

    def pan_speed(self, t):
        """Kadr markazining bir kadrdagi siljishi (chiqish px)."""
        img = fx.panel(self.panel)
        ph, pw = img.shape[:2]
        a = self.cam(t - 0.25 / FPS)
        c = self.cam(t + 0.25 / FPS)
        Ma = fx.cam_matrix(pw, ph, *a)
        Mc = fx.cam_matrix(pw, ph, *c)
        pa = fx.map_point(Ma, pw / 2, ph / 2)
        pc = fx.map_point(Mc, pw / 2, ph / 2)
        return abs(pc[0] - pa[0]), abs(pc[1] - pa[1])

    def render(self, t, off=(0.0, 0.0), zmul=1.0, exp_add=0.0, bloom_add=0.0):
        cx, cy, z, r = self.cam(t, zmul)
        # qo'l kamerasi kabi juda yengil "nafas"
        dx = 2.5 * math.sin(2 * math.pi * 0.23 * t + self.seed) + shake_off(t)[0]
        dy = 2.5 * math.sin(2 * math.pi * 0.17 * t + self.seed * 1.7) + shake_off(t)[1]
        img, M, pw, ph = fx.warp_panel(self.panel, cx, cy, z, r, (off[0] + dx, off[1] + dy))
        pul = 0.0
        for (tp, dur, amt) in self.pulse:
            if 0 <= t - tp < dur:
                pul += amt * math.sin(math.pi * (t - tp) / dur)
        img = fx.grade(img, fx.GRADES[self.grade], exp_add + pul * 0.08)
        small = fx.quarter(img)
        if self.rays:
            sx, sy = fx.map_point(M, self.rays[0] * pw, self.rays[1] * ph)
            img = fx.god_rays(img, small, (sx, sy), self.rays[2] * (1 + pul), tint=WARM)
        img = fx.bloom(img, small, self.bloom + bloom_add + pul * 0.3)
        if self.flare:
            fxp, fyp = fx.map_point(M, self.flare[0] * pw, self.flare[1] * ph)
            flick = 1 + 0.06 * math.sin(t * 13.0) + 0.04 * math.sin(t * 7.3)
            img = fx.lens_flare(img, (fxp, fyp), self.flare[2] * flick)
        if self.mblur > 1:
            vx, vy = self.pan_speed(t)
            L = int(vx * 2)
            if L > 2:
                img = cv2.blur(img, (L, 1))
        pt = self.particles()
        if pt is not None:
            lay = pt.layer(t, self.parts[1] * (1 + pul))
            img += lay * (1 - img)
        return img


SHAKES = [(2.43, 16, 0.45), (2.76, 9, 0.35), (41.62, 10, 0.4), (28.04, 5, 0.3)]


def shake_off(t):
    dx = dy = 0.0
    for (te, amp, dur) in SHAKES:
        if 0 <= t - te < dur:
            k = (1 - (t - te) / dur) ** 2
            dx += amp * k * math.sin(2 * math.pi * 19 * (t - te))
            dy += amp * k * math.cos(2 * math.pi * 15 * (t - te) + 0.9)
    return dx, dy


S = Shot
SHOTS = [
    # --- HOOK
    S("D1", 0.00, 1.62, (0.50, 0.45, 1.00), (0.50, 0.40, 1.13), e="o", grade="earth", bloom=0.30,
      parts=("gold", 0.55, 1), rot=(-0.8, 0.5)),
    S("C5", 1.62, 2.40, (0.50, 0.70, 1.22), (0.50, 0.42, 1.30), e="o", bloom=0.3, rays=(0.5, 0.02, 0.35),
      parts=("gold", 0.6, 2)),
    S("A6", 2.40, 3.62, (0.52, 0.40, 1.08), (0.52, 0.38, 1.26), e="o", bloom=0.5, rays=(0.5, 0.0, 0.5),
      parts=("gold", 0.9, 3)),
    # --- Sahihul Buxoriy
    S("C3", 3.62, 6.05, (0.50, 0.50, 1.06), (0.53, 0.48, 1.17), grade="interior", bloom=0.4,
      rays=(0.86, 0.22, 0.6), parts=("light", 0.35, 4)),
    S("D8", 6.05, 7.55, (0.47, 0.45, 1.12), (0.50, 0.44, 1.22), grade="interior", bloom=0.4,
      rays=(0.92, 0.25, 0.55), rot=(0.4, -0.3)),
    S("C1", 7.55, 10.55, (0.83, 0.50, 1.12), (0.60, 0.45, 1.02), grade="earth", bloom=0.3,
      flare=(0.98, 0.02, 0.35), parts=("light", 0.3, 6)),
    # --- Alloh bandasini sevsa, Jabroilni chaqiradi
    S("B1", 10.55, 12.45, (0.45, 0.45, 1.06), (0.44, 0.40, 1.20), grade="interior", bloom=0.4,
      rays=(0.86, 0.32, 0.65)),
    S("C7", 12.45, 14.35, (0.52, 0.40, 1.26), (0.52, 0.45, 1.06), bloom=0.55, rays=(0.12, 0.0, 0.6),
      parts=("gold", 0.8, 8), pulse=((13.27, 0.7, 0.8),)),
    S("C4", 14.35, 16.35, (0.60, 0.66, 1.30), (0.66, 0.40, 1.10), bloom=0.45, rays=(0.80, 0.28, 0.6),
      flare=(0.80, 0.28, 0.75), parts=("light", 0.4, 9)),
    S("C2", 16.35, 17.85, (0.50, 0.80, 1.30), (0.50, 0.63, 1.38), bloom=0.55, rays=(0.5, 0.25, 0.6),
      parts=("gold", 0.6, 10)),
    S("A1", 17.85, 19.75, (0.48, 0.50, 1.04), (0.48, 0.44, 1.16), grade="interior", bloom=0.45,
      rays=(0.12, 0.08, 0.6), parts=("gold", 0.45, 11)),
    S("B3", 19.75, 22.25, (0.60, 0.42, 1.18), (0.56, 0.40, 1.04), bloom=0.45, parts=("light", 0.4, 12)),
    S("D3", 22.25, 24.80, (0.50, 0.42, 1.04), (0.52, 0.32, 1.22), bloom=0.45, parts=("gold", 0.6, 13),
      pulse=((23.70, 0.8, 1.0),)),
    # --- Osmon ahliga nido
    S("D7", 24.80, 26.70, (0.50, 0.58, 1.00), (0.52, 0.40, 1.26), bloom=0.5, rays=(0.62, 0.12, 0.7),
      parts=("light", 0.45, 14)),
    S("B4", 26.70, 28.00, (0.45, 0.50, 1.04), (0.68, 0.50, 1.04), e="o", bloom=0.4, mblur=3,
      parts=("light", 0.35, 15)),
    S("D4", 28.00, 30.40, (0.56, 0.44, 1.25), (0.57, 0.40, 1.07), bloom=0.5, rays=(0.55, 0.0, 0.6),
      flare=(0.72, 0.13, 0.45), parts=("gold", 0.55, 16)),
    S("A4", 30.40, 32.20, (0.36, 0.66, 1.36), (0.55, 0.64, 1.40), e="o", bloom=0.3, rays=(0.5, 0.08, 0.3),
      parts=("light", 0.4, 17)),
    S("B5", 32.20, 33.95, (0.47, 0.42, 1.10), (0.47, 0.36, 1.25), bloom=0.3, parts=("gold", 0.7, 18),
      pulse=((32.78, 0.7, 0.7),)),
    S("D5", 33.95, 36.45, (0.25, 0.42, 1.12), (0.55, 0.40, 1.12), bloom=0.45, parts=("gold", 0.5, 19)),
    # --- Ular ham sevishadi
    S("A5", 36.45, 38.00, (0.20, 0.45, 1.06), (0.45, 0.42, 1.06), bloom=0.45, parts=("gold", 0.5, 20)),
    S("C6", 38.00, 39.95, (0.50, 0.45, 1.05), (0.50, 0.36, 1.22), bloom=0.5, parts=("gold", 0.7, 21),
      pulse=((39.00, 0.8, 1.0),)),
    # --- Fazl va maqbuliyat
    S("B6", 39.95, 41.45, (0.37, 0.50, 1.00), (0.50, 0.45, 1.06), e="o", bloom=0.45, mblur=3,
      parts=("light", 0.45, 22)),
    S("A6", 41.45, 42.70, (0.52, 0.30, 1.45), (0.52, 0.42, 1.05), e="o", bloom=0.4, rays=(0.5, 0.0, 0.4),
      parts=("gold", 1.0, 23), pulse=((41.62, 0.9, 1.0),)),
    S("A7", 42.70, 44.40, (0.55, 0.42, 1.12), (0.55, 0.38, 1.22), grade="earth", bloom=0.35,
      parts=("light", 0.3, 24)),
    S("D6", 44.40, 46.40, (0.50, 0.42, 1.04), (0.50, 0.36, 1.18), grade="earth", bloom=0.4,
      parts=("gold", 0.45, 25), pulse=((44.73, 1.0, 0.6),)),
    S("D9", 46.40, DUR, (0.52, 0.45, 1.25), (0.53, 0.48, 1.05), e="o", grade="dusk", bloom=0.5,
      rays=(0.62, 0.42, 0.55), flare=(0.62, 0.42, 0.6), parts=("gold", 0.45, 26)),
]

# o'tishlar: (turi, davomiylik, yo'nalish)
TRANS = [
    ("whip", 0.28, (0, 1)),      # D1 -> C5: osmonga qarab keskin burilish
    ("flash", 0.30, None),       # C5 -> A6: "nima bo'ladi?" -- oq chaqnash
    ("blur", 0.70, None),        # hook -> sokin hikoya
    ("dissolve", 0.45, None),
    ("lightwipe", 0.70, None),
    ("dissolve", 0.50, None),
    ("glow", 0.50, None),
    ("zoom", 0.40, None),
    ("flash", 0.40, None),
    ("lightwipe", 0.60, None),
    ("dissolve", 0.50, None),
    ("blur", 0.50, None),
    ("zoom", 0.45, None),
    ("whip", 0.30, (-1, 0)),
    ("flash", 0.30, None),
    ("whip", 0.30, (-1, 0)),
    ("dissolve", 0.40, None),
    ("whip", 0.30, (-1, 0)),
    ("dissolve", 0.40, None),
    ("lightwipe", 0.50, None),
    ("whip", 0.32, (-1, 0)),
    ("flash", 0.32, None),
    ("glow", 0.60, None),
    ("dissolve", 0.45, None),
    ("dissolve", 0.80, None),
]
assert len(TRANS) == len(SHOTS) - 1
for i, (kind, d, _) in enumerate(TRANS):
    SHOTS[i].end = SHOTS[i].t1 + d / 2
    SHOTS[i + 1].start = SHOTS[i + 1].t0 - d / 2


def mix(a, b, k):
    return a * (1 - k) + b * k


def render_transition(i, t):
    kind, d, dr = TRANS[i]
    A, B = SHOTS[i], SHOTS[i + 1]
    T, h = A.t1, d / 2
    q = (t - (T - h)) / d
    if kind == "dissolve":
        return mix(A.render(t), B.render(t), ease(q, "sine"))
    if kind == "glow":
        g = math.sin(math.pi * q)
        return mix(A.render(t, bloom_add=0.8 * g, exp_add=0.12 * g), B.render(t, bloom_add=0.8 * g, exp_add=0.12 * g),
                   ease(q, "sine"))
    if kind == "blur":
        a = A.render(t)
        b = B.render(t)
        a = fx.fast_blur(a, 34 * fx.smoothstep(0.0, 0.7, q))
        b = fx.fast_blur(b, 34 * (1 - fx.smoothstep(0.3, 1.0, q)))
        return mix(a, b, ease(q, "sine"))
    if kind == "flash":
        if t < T:
            k = ease((t - (T - h)) / h, "i2")
            img = A.render(t, zmul=1 + 0.05 * k)
        else:
            k = 1 - ease((t - T) / h, "o")
            img = B.render(t, zmul=1 + 0.07 * k)
        img += (1 - img) * (0.95 * k)
        img *= np.array([1 - 0.06 * k, 1.0, 1.0], np.float32)  # iliq oq
        return img
    if kind == "whip":
        amt = (W if dr[0] else H) * 0.55

        def offk(tt):
            if tt < T:
                return ease((tt - (T - h)) / h, "i")
            return -(1 - ease((tt - T) / h, "o"))

        k = offk(t)
        if t < T:
            img = A.render(t, off=(dr[0] * amt * k, dr[1] * amt * k))
        else:
            img = B.render(t, off=(dr[0] * amt * k, dr[1] * amt * k))
        # tezlikka mos uzluksiz yo'nalishli harakat xiraligi
        dt = 0.5 / FPS
        v = abs(offk(min(t + dt, T + h)) - offk(max(t - dt, T - h))) * amt
        if t - dt < T < t + dt:
            v = amt * 0.9
        L = int(min(v * 1.2, 520))
        if L > 2:
            img = cv2.blur(img, (L, 1) if dr[0] else (1, L))
        img += (1 - img) * 0.15 * abs(k)
        return img
    if kind == "zoom":
        if t < T - 0.03:
            k = ease((t - (T - h)) / h, "i")
            img = A.render(t, zmul=1 + 0.9 * k, exp_add=0.10 * k)
        elif t > T + 0.03:
            k = 1 - ease((t - T) / h, "o")
            img = B.render(t, zmul=1 + 0.55 * k, exp_add=0.10 * k)
        else:
            img = mix(A.render(t, zmul=1.9, exp_add=0.10), B.render(t, zmul=1.55, exp_add=0.10), (t - T + 0.03) / 0.06)
        return img
    if kind == "lightwipe":
        a = A.render(t)
        b = B.render(t)
        lb = cv2.GaussianBlur(fx.quarter(b).max(axis=2), (0, 0), 5)
        lb = cv2.resize(lb, (W, H), interpolation=cv2.INTER_LINEAR)
        thr = 1.12 - 1.55 * ease(q, "io")
        m = fx.smoothstep(thr, thr + 0.28, lb)[..., None]
        edge = m * (1 - m) * 4
        a += (1 - a) * 0.22 * math.sin(math.pi * q)
        img = a * (1 - m) + b * m
        img += edge * WARM * 0.55 * (1 - img)
        return img
    raise ValueError(kind)


def base_frame(t):
    for i in range(len(TRANS)):
        kind, d, _ = TRANS[i]
        T = SHOTS[i].t1
        if T - d / 2 <= t < T + d / 2:
            return render_transition(i, t)
    for s in SHOTS:
        if s.t0 <= t < s.t1 or (s is SHOTS[-1] and t >= s.t0):
            return s.render(t)
    return SHOTS[-1].render(t)


def motion_samples(t):
    for i, (kind, d, _) in enumerate(TRANS):
        T = SHOTS[i].t1
        if kind == "zoom" and T - d / 2 - 0.02 <= t < T + d / 2 + 0.02:
            return 9, 1.0 / FPS
    return 1, 0.0


def chroma_amount(t):
    k = 0.0
    for i, (kind, d, _) in enumerate(TRANS):
        T = SHOTS[i].t1
        if kind in ("whip", "flash", "zoom") and abs(t - T) < d / 2:
            k = max(k, 6 * (1 - abs(t - T) / (d / 2)))
    for (te, amp, dur) in SHAKES:
        if 0 <= t - te < dur:
            k = max(k, amp * 0.4 * (1 - (t - te) / dur))
    return k


# ---------------------------------------------------------------- matnlar
def build_cards():
    C = []
    # HOOK: savol -- kuchli, markazda, so'zma-so'z "zarba" bilan
    C.append(Card([
        Line([Wd("Agar", 1, 0), Wd("Alloh", 1, 1), Wd("subhanahu", 1, 2), Wd("va", 1, 3), Wd("taolo", 1, 4)], "hook_s"),
        Line([Wd("SIZNI", 1, 5)], "hook_w"),
        Line([Wd("SEVIB", 1, 6), Wd("QOLSA", 1, 7)], "hook_g"),
        Line([Wd("NIMA", 1, 8), Wd("BO‘LADI?", 1, 9)], "hook_q"),
    ], 0.0, 3.30, cy=1185, exit="zoom", shake=((2.43, 12, 0.45), (2.76, 7, 0.35))))
    # Sahihul Buxoriy
    C.append(Card([
        Line([Wd("Sahihul", 2, 0), Wd("Buxoriyda", 2, 1)], "cinzel", ornament=True),
        Line([Wd("kelgan", 2, 2), Wd("hadisni", 2, 3), Wd("sizga", 2, 4), Wd("aytib", 2, 5), Wd("beraman,", 2, 6)],
             "quote_s"),
    ], 3.84, 5.98))
    C.append(Card([Line([Wd("yaxshilab", 2, 7, key=True), Wd("tinglang.", 2, 8, key=True)], "cap")], 6.09, 7.40))
    # Rasululloh ﷺ
    t_saw = wt(3, 1)[0]
    C.append(Card([
        Line([Wd("Rasululloh", 3, 0), Word("ﷺ", t_saw, wt(3, 3)[1], font="amiri", scale=1.75, dy=14)], "cinzel",
             ornament=True),
        Line([Wd("aytadilarki:", 3, 4)], "quote_s"),
    ], 7.68, 10.42))
    C.append(Card([Line([Wd("agar", 4, 0), Wd("Alloh", 4, 1)], "cap"),
                   Line([Wd("subhanahu", 4, 2), Wd("va", 4, 3), Wd("taolo", 4, 4)], "cap")], 10.81, 12.42))
    C.append(Card([Line([Wd("bir", 4, 5), Wd("bandasini", 4, 6)], "cap"),
                   Line([Wd("sevib", 4, 7, key=True), Wd("qolsa,", 4, 8, key=True)], "cap")], 12.51, 14.28))
    C.append(Card([Line([Wd("Jabroil", 5, 0, key=True), Wd("alayhissalomni", 5, 1)], "cap"),
                   Line([Wd("chaqirib:", 5, 2)], "cap")], 14.52, 16.30))
    # Alloh taoloning so'zlari -- iqtibos uslubida
    q0 = wt(6, 0)[0]
    C.append(Card([
        Line([Word("“", q0, q0, color="FFCC5C", glue=True), Wd("Ey", 6, 0), Wd("Jabroil,", 6, 1)], "quote"),
        Line([Wd("men", 7, 0), Wd("falonchi", 7, 1), Wd("bandamni", 7, 2)], "quote"),
        Line([Wd("sevdim,", 7, 3, key=True)], "quote"),
    ], 16.44, 19.72))
    C.append(Card([
        Line([Wd("sen", 8, 0), Wd("ham", 8, 1), Wd("uni", 8, 2), Wd("sevgin", 8, 3, glue=True, key=True),
              Word("”,", wt(8, 3)[0], wt(8, 3)[1], color="FFCC5C")], "quote"),
        Line([Wd("deydi.", 8, 4, scale=0.8)], "quote"),
    ], 20.48, 22.22))
    C.append(Card([Line([Wd("Jabroil", 9, 0), Wd("alayhissalom", 9, 1)], "cap"),
                   Line([Wd("ham", 9, 2), Wd("uni", 9, 3), Wd("SEVADI.", 9, 4, key=True)], "cap")], 22.40, 24.72))
    C.append(Card([Line([Wd("So‘ng", 10, 0), Wd("Jabroil", 10, 1), Wd("alayhissalom", 10, 2)], "cap"),
                   Line([Wd("osmon", 10, 3, key=True), Wd("ahliga", 10, 4, key=True), Wd("nido", 10, 5),
                         Wd("qilib:", 10, 6)], "cap")], 25.34, 27.98))
    q1 = wt(10, 7)[0]
    C.append(Card([
        Line([Word("“", q1, q1, color="FFCC5C", glue=True), Wd("Ey", 10, 7), Wd("osmon", 10, 8), Wd("ahli,", 10, 9)],
             "quote"),
        Line([Wd("ey", 11, 0), Wd("maloikalar,", 11, 1, key=True)], "quote"),
    ], 28.04, 30.36))
    C.append(Card([
        Line([Wd("Alloh", 12, 0), Wd("subhanahu", 12, 1), Wd("va", 12, 2), Wd("taolo", 12, 3)], "quote"),
        Line([Wd("falonchi", 12, 4), Wd("bandani", 12, 5), Wd("sevdi,", 12, 6, key=True)], "quote"),
    ], 30.43, 33.92))
    C.append(Card([
        Line([Wd("sizlar", 13, 0), Wd("ham", 13, 1), Wd("sevinglar", 13, 2, glue=True, key=True),
              Word("”,", wt(13, 2)[0], wt(13, 2)[1], color="FFCC5C")], "quote"),
        Line([Wd("deydi.", 13, 3, scale=0.8)], "quote"),
    ], 33.98, 36.42))
    C.append(Card([Line([Wd("Ular", 14, 0), Wd("ham", 14, 1), Wd("ma’qullashib,", 14, 2)], "cap"),
                   Line([Wd("u", 15, 0), Wd("bandani", 15, 1), Wd("ham", 15, 2), Wd("sevishadi.", 15, 3, key=True)],
                        "cap")], 36.51, 39.92))
    C.append(Card([Line([Wd("So‘ng", 16, 0), Wd("u", 16, 1), Wd("bandaga", 16, 2), Wd("shunaqa", 16, 3)], "cap"),
                   Line([Wd("bir", 16, 4), Wd("fazl", 16, 5, key=True), Wd("beriladiki,", 16, 6)], "cap")],
                  39.96, 42.64))
    C.append(Card([Line([Wd("FAZL", 16, 5)], "impact")], 41.62, 42.60, cy=1000, exit="zoom"))
    C.append(Card([Line([Wd("dunyoga", 17, 0), Wd("maqbuliyatlik", 17, 1, key=True)], "cap"),
                   Line([Wd("darajasi", 17, 2, key=True), Wd("beriladi.", 17, 3)], "cap")], 42.70, 46.30))
    # Yakun: duo
    C.append(Card([
        Line([Word("Alloh", 46.80, 47.0), Word("taolo", 46.95, 47.1), Word("barchamizni", 47.10, 47.3)], "quote"),
        Line([Word("O‘zi", 47.35, 47.5), Word("sevgan", 47.5, 47.7), Word("bandalaridan", 47.65, 47.9)], "quote"),
        Line([Word("qilsin!", 47.85, 48.1)], "quote"),
        Line([Word("OMIN", 48.15, 48.6)], "omin", ornament=True),
    ], 46.80, DUR + 1, cy=470, hold=True))
    # bir zonadagi ketma-ket matnlar ustma-ust tushmasin: oldingisi keyingisi boshlanishidan oldin tez chiqadi
    band = [c for c in C if c.cy > 1000 and not c.hold]
    for a, b in zip(band, band[1:]):
        if b.lines[0].style.get("anim") == "impact" or a.lines[0].style.get("anim") == "impact":
            continue
        nxt = b.first_t() - 0.05
        if a.t_out + a.exit_dur > nxt - 0.02:
            a.exit_dur = 0.16
            a.t_out = min(a.t_out, nxt - 0.08)
    # FAZL zarbasi keyingi matn kelishidan oldin to'liq yo'qolsin
    for c in C:
        if c.lines[0].style.get("anim") == "impact":
            c.exit_dur = 0.18
            c.t_out = min(c.t_out, 42.70 - 0.05 - 0.2)
    return C


CARDS = None


def band_weight(t):
    return float(fx.smoothstep(3.35, 3.9, t))


def render_frame(t, fi=0):
    global CARDS
    if CARDS is None:
        CARDS = build_cards()
    n, shutter = motion_samples(t)
    if n > 1:
        acc = None
        for j in range(n):
            tt = t + (j / (n - 1) - 0.5) * shutter
            f = base_frame(tt)
            acc = f if acc is None else acc + f
        img = acc / n
    else:
        img = base_frame(t)
    # boshlanishdagi yengil yorug'lik "zarbasi" va light leak
    if t < 0.35:
        img += (1 - img) * 0.35 * (1 - t / 0.35)
    ll = 0.0
    if t < 1.2:
        ll = 0.35 * (1 - t / 1.2)
    for i, (kind, d, _) in enumerate(TRANS):
        if kind in ("flash", "lightwipe", "glow"):
            T = SHOTS[i].t1
            if abs(t - T) < d:
                ll = max(ll, 0.35 * (1 - abs(t - T) / d))
    if t > 46.0:
        ll = max(ll, 0.18 * fx.smoothstep(46.0, 47.0, t))
    if ll > 0:
        img += fx.light_leak(t, 3.0, ll) * (1 - img)
    img = fx.chroma(img, chroma_amount(t))
    img *= fx.VIGNETTE
    bw = band_weight(t)
    if bw > 0:
        img *= 1 - fx.BAND * bw
    tw = float(fx.smoothstep(46.5, 47.2, t))
    if tw > 0:
        img *= 1 - fx.TOPBAND * tw
    for c in CARDS:
        c.draw(img, t)
    img += fx.grain(fi) * 0.009
    if t > DUR - 0.7:
        img *= max(0.0, (DUR - t) / 0.7) ** 1.3
    np.clip(img, 0, 1, out=img)
    return (img * 255 + 0.5).astype(np.uint8)


def render_range(f0, f1, path):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
           "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-profile:v", "high", "-g", "60",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fi in range(f0, f1):
        p.stdin.write(render_frame(fi / FPS, fi).tobytes())
        if (fi - f0) % 60 == 0:
            print(f"[{os.path.basename(path)}] {fi - f0}/{f1 - f0}", flush=True)
    p.stdin.close()
    p.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", default="")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--range", default="")
    ap.add_argument("--out", default=os.path.join(ROOT, "build"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.stills:
        for s in a.stills.split(","):
            t = float(s)
            cv2.imwrite(os.path.join(a.out, f"still_{t:06.2f}.png"), render_frame(t, int(t * FPS)))
            print("still", t, flush=True)
    if a.render:
        nf = int(round(DUR * FPS))
        f0, f1 = 0, nf
        if a.range:
            f0, f1 = [int(round(float(x) * FPS)) for x in a.range.split(":")]
        bounds = np.linspace(f0, f1, a.workers + 1).astype(int)
        segs = [os.path.abspath(os.path.join(a.out, f"seg_{k}.mp4")) for k in range(a.workers)]
        procs = [Process(target=render_range, args=(bounds[k], bounds[k + 1], segs[k])) for k in range(a.workers)]
        for p in procs:
            p.start()
        for p in procs:
            p.join()
        lst = os.path.join(a.out, "segs.txt")
        with open(lst, "w") as f:
            for sname in segs:
                f.write(f"file '{sname}'\n")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                        os.path.join(a.out, "video_noaudio.mp4")], check=True)
        print("done", flush=True)


if __name__ == "__main__":
    main()
