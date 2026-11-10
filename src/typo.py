"""Kinetik tipografiya: so'zma-so'z chiqadigan, ovozga sinxron matnlar (Reels xavfsiz zonasida)."""
import math
import os
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from fx import W, H, WHITE, GOLD, GOLD_HI, GOLD_DEEP, ease, hexbgr

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")
FONTS = {
    "black": "Montserrat-Black.ttf",
    "xbold": "Montserrat-ExtraBold.ttf",
    "bold": "Montserrat-Bold.ttf",
    "cinzel": "Cinzel-Bold.ttf",
    "corm": "CormorantGaramond-BoldItalic.ttf",
    "corm_s": "CormorantGaramond-SemiBoldItalic.ttf",
    "amiri": "Amiri-Arabic-Bold.ttf",
}

# Reels xavfsiz zonasi: o'ngdagi tugmalar (x>930, y>1050) va pastki izoh (y>1480) ga matn tushmasin
SAFE_CX = 522
SAFE_MAXW = 800


@lru_cache(maxsize=None)
def font(key, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, FONTS[key]), size)


class Sprite:
    __slots__ = ("premul", "alpha", "add", "ox", "oy", "adv", "asc")


@lru_cache(maxsize=None)
def sprite(text, fkey, size, color=None, grad=None, tracking=0, halo=0.62, glow=None):
    """Matnni RGBA sprite qilib chizish. color/grad -- hex satr(lar), glow -- (hex, kuch)."""
    f = font(fkey, size)
    asc, desc = f.getmetrics()
    if tracking:
        adv = sum(f.getlength(c) for c in text) + tracking * (len(text) - 1)
    else:
        adv = f.getlength(text)
    pad = int(size * 0.6) + 8
    w = int(math.ceil(adv)) + 2 * pad
    h = asc + desc + 2 * pad
    im = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(im)
    ox, oy = pad, pad + asc
    if tracking:
        x = ox
        for c in text:
            d.text((x, oy), c, font=f, fill=255, anchor="ls")
            x += f.getlength(c) + tracking
    else:
        d.text((ox, oy), text, font=f, fill=255, anchor="ls")
    A = np.asarray(im, np.float32) / 255.0
    if grad:
        top, bot = hexbgr(grad[0]), hexbgr(grad[1])
        y = np.arange(h, dtype=np.float32)
        k = np.clip((y - (oy - asc * 0.75)) / (asc * 0.95), 0, 1)[:, None, None]
        col = top * (1 - k) + bot * k
    else:
        col = hexbgr(color) if color else WHITE
    premul = A[..., None] * col
    alpha = A
    if halo > 0:
        sh = cv2.GaussianBlur(cv2.dilate(A, np.ones((3, 3), np.uint8)), (0, 0), max(2.0, size * 0.13))
        sh = np.roll(sh, max(1, int(size * 0.04)), axis=0)
        sh2 = cv2.GaussianBlur(A, (0, 0), max(4.0, size * 0.42))
        sh = np.clip(sh * 1.7 * halo + sh2 * 0.9 * halo, 0, 0.92)
        alpha = A + sh * (1 - A)
    add = None
    if glow:
        g = cv2.GaussianBlur(A, (0, 0), size * 0.32) * glow[1]
        add = g[..., None] * hexbgr(glow[0])
    s = Sprite()
    s.premul = premul.astype(np.float32)
    s.alpha = alpha.astype(np.float32)
    s.add = None if add is None else add.astype(np.float32)
    s.ox, s.oy, s.adv, s.asc = ox, oy, adv, asc
    return s


def blit(frame, premul, alpha, add, x0f, y0f, a=1.0):
    h, w = alpha.shape
    x0, y0 = int(round(x0f)), int(round(y0f))
    fx0, fy0, fx1, fy1 = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if fx1 <= fx0 or fy1 <= fy0 or a <= 0.003:
        return
    sx0, sy0 = fx0 - x0, fy0 - y0
    sx1, sy1 = sx0 + (fx1 - fx0), sy0 + (fy1 - fy0)
    reg = frame[fy0:fy1, fx0:fx1]
    al = alpha[sy0:sy1, sx0:sx1, None] * a
    reg *= 1 - al
    reg += premul[sy0:sy1, sx0:sx1] * a
    if add is not None:
        reg += add[sy0:sy1, sx0:sx1] * a * (1 - reg)


def draw_sprite(frame, spr, x, ybase, a=1.0, sc=1.0, blur=0.0, mix_spr=None, mix=0.0, sx=1.0):
    """x -- matn boshlanishi, ybase -- tayanch chiziq. Masshtab matn markazi atrofida."""
    if a <= 0.003:
        return
    pm, al, ad = spr.premul, spr.alpha, spr.add
    if mix_spr is not None and mix > 0.001:
        pm = pm * (1 - mix) + mix_spr.premul * mix
        if mix_spr.add is not None:
            ad = mix_spr.add * mix if ad is None else ad * (1 - mix) + mix_spr.add * mix
    if blur > 0.4:
        pm = cv2.GaussianBlur(pm, (0, 0), blur)
        al = cv2.GaussianBlur(al, (0, 0), blur)
        if ad is not None:
            ad = cv2.GaussianBlur(ad, (0, 0), blur)
    ax, ay = spr.ox + spr.adv / 2.0, spr.oy - spr.asc * 0.36
    scx, scy = sc * sx, sc
    if abs(scx - 1) > 1e-3 or abs(scy - 1) > 1e-3:
        hh, ww = al.shape
        nw, nh = max(1, int(ww * scx)), max(1, int(hh * scy))
        pm = cv2.resize(pm, (nw, nh), interpolation=cv2.INTER_LINEAR)
        al = cv2.resize(al, (nw, nh), interpolation=cv2.INTER_LINEAR)
        if ad is not None:
            ad = cv2.resize(ad, (nw, nh), interpolation=cv2.INTER_LINEAR)
        ax, ay = ax * nw / ww, ay * nh / hh
    tx, ty = x + spr.adv / 2.0, ybase - spr.asc * 0.36
    blit(frame, pm, al, ad, tx - ax, ty - ay, a)


# ------------------------------------------------------------------ uslublar
STYLES = {
    # oddiy subtitr: Montserrat, so'zma-so'z "pop"
    "cap": dict(font="xbold", size=60, color="FFFDF6", key="FFCC5C", hi="FFE49A", key_scale=1.12, lh=1.22,
                anim="pop", halo=0.66),
    # iqtibos (Alloh / Jabroil so'zlari): nafis kursiv serif, yumshoq paydo bo'lish
    "quote": dict(font="corm", size=80, color="FFFDF6", key="FFCC5C", lh=1.06, anim="soft", halo=0.7,
                  glow=("FFD27A", 0.22)),
    "quote_s": dict(font="corm_s", size=60, color="FFFDF6", key="FFCC5C", lh=1.15, anim="soft", halo=0.7),
    "cinzel": dict(font="cinzel", size=66, grad=("FFF2C4", "E3A63E"), lh=1.25, anim="title", tracking=5,
                   halo=0.7, glow=("FFC870", 0.35)),
    "hook_s": dict(font="bold", size=48, color="FFFDF6", lh=1.35, anim="soft_fast", halo=0.75, tracking=1),
    "hook_w": dict(font="black", size=122, color="FFFDF6", lh=1.0, anim="slam", halo=0.8),
    "hook_g": dict(font="black", size=122, grad=("FFF0B8", "E09C2E"), lh=1.0, anim="slam", halo=0.8,
                   glow=("FFB648", 0.45)),
    "hook_q": dict(font="black", size=110, color="FFFDF6", lh=1.25, anim="slam", halo=0.85, glow=("FFC45A", 0.55)),
    "impact": dict(font="cinzel", size=190, grad=("FFF6D2", "DE9A2C"), lh=1.0, anim="impact", tracking=18,
                   halo=0.55, glow=("FFC24E", 0.75)),
    "omin": dict(font="cinzel", size=70, grad=("FFF2C4", "E3A63E"), lh=1.3, anim="title", tracking=14,
                 halo=0.7, glow=("FFC870", 0.45)),
}


class Word:
    def __init__(self, text, t0, t1, key=False, color=None, glue=False, font=None, scale=1.0, dy=0.0):
        self.text, self.t0, self.t1 = text, t0, t1
        self.key, self.color, self.glue, self.font, self.scale, self.dy = key, color, glue, font, scale, dy


class Line:
    def __init__(self, words, style, ornament=False):
        self.words, self.style, self.ornament = words, STYLES[style], ornament


class Card:
    def __init__(self, lines, t_in, t_out, cx=SAFE_CX, cy=1290, maxw=SAFE_MAXW, exit="fade", shake=(), hold=False):
        self.lines, self.t_in, self.t_out = lines, t_in, t_out
        self.cx, self.cy, self.maxw, self.exit, self.shake, self.hold = cx, cy, maxw, exit, shake, hold
        self.exit_dur = 0.3
        self._layout = None

    def first_t(self):
        return min(w.t0 for ln in self.lines for w in ln.words)

    # -- sprite yaratish va joylashtirish (har bir jarayonda bir marta)
    def _word_sprites(self, w, st, size):
        fkey = w.font or st["font"]
        sz = int(round(size * (st.get("key_scale", 1.0) if w.key else 1.0) * w.scale))
        common = dict(tracking=st.get("tracking", 0), halo=st.get("halo", 0.62), glow=st.get("glow"))
        if w.color:
            base = sprite(w.text, fkey, sz, color=w.color, **common)
        elif w.key and st.get("key"):
            base = sprite(w.text, fkey, sz, color=st["key"], **common)
        elif st.get("grad"):
            base = sprite(w.text, fkey, sz, grad=st["grad"], **common)
        else:
            base = sprite(w.text, fkey, sz, color=st.get("color"), **common)
        hi = None
        if st.get("hi") and not w.key and not w.color:
            hi = sprite(w.text, fkey, sz, color=st["hi"], **common)
        return base, hi, sz

    def layout(self):
        if self._layout is not None:
            return self._layout
        rows = []
        for ln in self.lines:
            st = ln.style
            size = st["size"]
            for _ in range(6):
                items, x = [], 0.0
                sp = font(st["font"], size).getlength(" ") + st.get("tracking", 0)
                for w in ln.words:
                    base, hi, sz = self._word_sprites(w, st, size)
                    items.append([w, base, hi, x])
                    x += base.adv + (0 if w.glue else sp)
                width = x - (0 if ln.words[-1].glue else sp)
                if width <= self.maxw:
                    break
                size = int(size * self.maxw / width * 0.98)
            rows.append(dict(line=ln, st=st, size=size, items=items, width=width))
        total = sum(r["size"] * r["st"]["lh"] for r in rows)
        y = self.cy - total / 2.0
        for r in rows:
            lh = r["size"] * r["st"]["lh"]
            r["base"] = y + lh * 0.5 + r["size"] * 0.34
            r["x0"] = self.cx - r["width"] / 2.0
            y += lh
        self._layout = rows
        return rows

    def active(self, t):
        return self.t_in - 0.2 <= t <= self.t_out + self.exit_dur + 0.05

    def draw(self, frame, t):
        if not self.active(t):
            return
        rows = self.layout()
        # chiqish animatsiyasi
        ex = 0.0 if self.hold else ease((t - self.t_out) / self.exit_dur, "i2") if t > self.t_out else 0.0
        if ex >= 1:
            return
        sdx = sdy = 0.0
        for (te, amp, dur) in self.shake:
            if 0 <= t - te < dur:
                k = (1 - (t - te) / dur) ** 2
                sdx += amp * k * math.sin(2 * math.pi * 21 * (t - te))
                sdy += amp * k * math.cos(2 * math.pi * 17 * (t - te) + 0.7)
        for r in rows:
            st, anim = r["st"], r["st"]["anim"]
            if r["line"].ornament:
                self._ornament(frame, t, r, ex)
            for w, base, hi, xo in r["items"]:
                ta = w.t0 - 0.05
                if t < ta:
                    continue
                x = r["x0"] + xo + sdx
                yb = r["base"] + sdy + w.dy
                a, sc, blur, dy, sx = 1.0, 1.0, 0.0, 0.0, 1.0
                if anim == "pop":
                    p = (t - ta) / 0.2
                    a = ease(p * 1.6, "o2")
                    sc = 0.72 + 0.28 * ease(p, "back_o")
                    dy = 24 * (1 - ease(p, "o"))
                elif anim in ("soft", "soft_fast"):
                    d = 0.38 if anim == "soft" else 0.2
                    p = (t - ta) / d
                    a = ease(p, "o2")
                    blur = 7 * (1 - ease(p, "o"))
                    dy = 16 * (1 - ease(p, "o"))
                elif anim == "title":
                    p = (t - ta) / 0.6
                    a = ease(p, "o2")
                    sx = 1.18 - 0.18 * ease(p, "expo_o")
                    blur = 6 * (1 - ease(p, "o"))
                elif anim == "slam":
                    p = (t - ta) / 0.17
                    a = ease(p * 2.2, "o2")
                    sc = 1.0 + 0.9 * (1 - ease(p, "expo_o"))
                    blur = 5 * (1 - ease(p, "o"))
                elif anim == "impact":
                    p = (t - ta) / 0.35
                    a = ease(p * 1.8, "o2")
                    sc = 1.0 + 0.45 * (1 - ease(p, "expo_o")) + 0.05 * max(0.0, t - ta - 0.35)
                    blur = 8 * (1 - ease(p, "o"))
                mix = 0.0
                if hi is not None:
                    if w.t0 - 0.03 <= t <= w.t1 + 0.02:
                        mix = 1.0
                    elif t > w.t1 + 0.02:
                        mix = max(0.0, 1 - (t - w.t1 - 0.02) / 0.18)
                if ex > 0:
                    a *= 1 - ex
                    dy -= 18 * ex
                    blur += 5 * ex
                    if self.exit == "zoom":
                        sc *= 1 + 0.25 * ex
                draw_sprite(frame, base, x, yb + dy, a=a, sc=sc, blur=blur, mix_spr=hi, mix=mix, sx=sx)

    def _ornament(self, frame, t, r, ex):
        """Sarlavha yonidagi nozik oltin chiziqlar va olmos shakllari."""
        t0 = r["items"][0][0].t0
        p = ease((t - t0) / 0.8, "o")
        if p <= 0:
            return
        a = (1 - ex) * p
        y = int(r["base"] - r["size"] * 0.36)
        gap = 22
        L = int(150 * p)
        xl = int(r["x0"] - gap)
        xr = int(r["x0"] + r["width"] + gap)
        col = GOLD
        for (xa, xb) in ((max(10, xl - L), xl), (xr, min(W - 10, xr + L))):
            if xb <= xa:
                continue
            seg = frame[y - 1:y + 2, xa:xb]
            ramp = np.linspace(0, 1, xb - xa, dtype=np.float32)
            if xa < xl:  # chap chiziq o'ngga qarab kuchayadi
                pass
            else:
                ramp = ramp[::-1]
            al = (ramp * a * 0.9)[None, :, None] * np.array([0.6, 1.0, 0.6], np.float32)[:, None, None]
            seg *= 1 - al
            seg += al * col
        for xc in (xl - L - 10, xr + L + 10):
            if 10 < xc < W - 10:
                m = np.zeros((19, 19), np.uint8)
                pts = np.array([[9, 2], [16, 9], [9, 16], [2, 9]], np.int32)
                cv2.fillConvexPoly(m, pts, 255, cv2.LINE_AA)
                ys, xs = slice(y - 9, y + 10), slice(xc - 9, xc + 10)
                al = (m.astype(np.float32) / 255 * a)[..., None]
                frame[ys, xs] = frame[ys, xs] * (1 - al) + al * col
