#!/usr/bin/env python3
"""
render.py — premium animatsion montaj DVIGATELI (engine) va CLI.

Bu fayl shablon EMAS. Unda sahnalar yo'q — faqat asboblar qutisi:
matn/kinetik tipografiya, rasm-kamera, effektlar, zarralar, niqoblar, o'tishlar,
kompozitor va parallel render. Har bir video o'z faylida yoziladi:
`projects/<nom>.py` (namuna: projects/oddiy_baxt.py). Sahnalar har safar
matn ma'nosidan kelib chiqib NOLDAN o'ylab topiladi (qarang: SKILL.md).

Loyiha fayli shartnomasi (projects/<nom>.py):
    import render as R
    R.configure(size=(1080, 1920), fps=30, dur=44.766)
    from render import *            # noqa: F401,F403
    def prepare(): ...              # rasm/zaxiralarni yuklash (ixtiyoriy)
    SCENES = [(0.0, scene0), (8.55, scene1), ...]   # (boshlanish soniyasi, funksiya)
    TRANS = {1: ("burn", 0.9), 2: ("iris", 0.7, {"x": 540, "y": 600}), ...}
    OUTPUT = "output/<nom>.mp4"
    POST = {"grain": 0.10, "fade_in": 0.5, "fade_out": 0.7}   # ixtiyoriy
    def OVERLAY(ctx, t): ...        # sahnalar ustidan (kesimlardan o'tib) yashaydigan qatlam
  Sahna funksiyasi: fn(ctx, lt, t) — lt: sahna ichidagi vaqt, t: umumiy vaqt.

Ishlatish:
    python3 render.py projects/<nom>.py <asl.mp4> [chiqish.mp4]
    python3 render.py projects/<nom>.py <asl.mp4> --preview 3.5 12 20.1
    python3 render.py projects/<nom>.py <asl.mp4> --check      # barcha kadrlar, kodlashsiz
"""
import functools
import importlib.util
import math
import os
import subprocess
import sys
import tempfile
from multiprocessing import Process

import cairo
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
DUR = 10.0
HERE = os.path.dirname(os.path.abspath(__file__))
FDIR = os.path.join(HERE, "assets", "fonts")
IDIR = os.path.join(HERE, "assets", "images")
HANDLE = "@Dilmurod_Khushboyev"
PROJECT = None


def configure(size=None, fps=None, dur=None):
    """Called by a project before `from render import *`."""
    global W, H, FPS, DUR
    if size:
        W, H = size
    if fps:
        FPS = fps
    if dur:
        DUR = dur
    _rng_parts.cache_clear()


def nframes():
    return int(round(DUR * FPS))


# --------------------------------------------------------------------------
# Fonts
# --------------------------------------------------------------------------
FONTS = {
    "thin": ("Inter-Thin.otf", None),
    "xlight": ("Inter-ExtraLight.otf", None),
    "light": ("Inter-Light.otf", None),
    "reg": ("Inter-Regular.otf", None),
    "med": ("Inter-Medium.otf", None),
    "semi": ("Inter-SemiBold.otf", None),
    "bold": ("Inter-Bold.otf", None),
    "xbold": ("Inter-ExtraBold.otf", None),
    "black": ("InterDisplay-Black.otf", None),
    "serif": ("PlayfairDisplay.ttf", 700),
    "serif_it": ("PlayfairDisplay-Italic.ttf", 500),
    "serif_it_b": ("PlayfairDisplay-Italic.ttf", 700),
}


@functools.lru_cache(maxsize=None)
def font(key, size):
    fn, wght = FONTS[key]
    f = ImageFont.truetype(os.path.join(FDIR, fn), size)
    if wght is not None:
        f.set_variation_by_axes([wght])
    return f


# --------------------------------------------------------------------------
# Colours / easing
# --------------------------------------------------------------------------
def hx(s, a=1.0):
    s = s.lstrip("#")
    return (int(s[0:2], 16) / 255, int(s[2:4], 16) / 255, int(s[4:6], 16) / 255, a)


def lerp(a, b, t):
    return a + (b - a) * t


def lerp2(a, b, t):
    return (lerp(a[0], b[0], t), lerp(a[1], b[1], t))


def lerpc(c1, c2, t):
    return tuple(lerp(a, b, t) for a, b in zip(c1, c2))


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def prog(t, start, dur):
    return clamp((t - start) / dur) if dur > 0 else float(t >= start)


def e_out(p):
    return 1 - (1 - p) ** 3


def e_out5(p):
    return 1 - (1 - p) ** 5


def e_in(p):
    return p ** 3


def e_io(p):
    return 4 * p * p * p if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def e_expo(p):
    return 1.0 if p >= 1 else 1 - 2 ** (-10 * p)


def e_back(p, s=1.70158):
    if p <= 1e-3:  # avoid near-singular scale matrices
        return 0.0
    p -= 1
    return 1 + (s + 1) * p ** 3 + s * p ** 2


def e_elastic(p):
    if p <= 1e-3:
        return 0.0
    if p >= 1:
        return 1.0
    return 2 ** (-10 * p) * math.sin((p * 10 - 0.75) * (2 * math.pi) / 3) + 1


def bump(t, start, dur):
    """0 -> 1 -> 0 hump over [start, start+dur]."""
    p = prog(t, start, dur)
    return math.sin(p * math.pi) if 0 < p < 1 else 0.0


def e_bounce(p):
    """Ball-drop landing (falls, hits the floor, two small rebounds)."""
    n, d = 7.5625, 2.75
    if p < 1 / d:
        return n * p * p
    if p < 2 / d:
        p -= 1.5 / d
        return n * p * p + 0.75
    if p < 2.5 / d:
        p -= 2.25 / d
        return n * p * p + 0.9375
    p -= 2.625 / d
    return n * p * p + 0.984375


def pulse(t, hits, dur=0.22):
    """Sum of sharp attack / smooth decay pulses at `hits` [(time, strength), ...]."""
    v = 0.0
    for h in hits:
        tt, s = (h, 1.0) if not isinstance(h, (tuple, list)) else h
        d = t - tt
        if 0 <= d < dur * 3:
            v += s * math.exp(-d / dur) * min(1.0, d / 0.03)
    return v


# --------------------------------------------------------------------------
# Speech timing (approximate read-along without a transcriber)
# --------------------------------------------------------------------------
def syllables(word):
    """Uzbek (Latin) syllable count = vowels; digits must be given via overrides."""
    return max(1, sum(1 for c in word.lower() if c in "aeiouаеёиоуўэюя"))


def word_times(text, t0, t1, over=None, lead=0.05):
    """Spread the words of a spoken phrase over [t0, t1] by syllable weight.
    over: {word: syllables} for numbers etc. Returns [(word, start, end), ...]."""
    words = text.split()
    syl = [(over or {}).get(w, syllables(w)) for w in words]
    dt = (t1 - t0) / sum(syl)
    out, t = [], t0
    for w_, k in zip(words, syl):
        out.append((w_, t - lead, t + k * dt - lead))
        t += k * dt
    return out


GOLD = hx("#e3c47c")
GOLD_L = hx("#f6e3ad")
GOLD_D = hx("#a67c35")
GG = (hx("#fff4d8"), hx("#eac672"))  # bright gold text gradient (readable on dark)
WHITE = hx("#f5f1e8")
MUTED = hx("#9a958a")
AMBER = hx("#f2b860")
ROSE = hx("#ff8fa3")
NEON_P = hx("#ff4f8b")
NEON_C = hx("#55e6ff")
WARM = hx("#ffb36b")
BLACK = (0, 0, 0, 1)


# --------------------------------------------------------------------------
# Text sprites (Pillow -> Cairo surface, cached)
# --------------------------------------------------------------------------
class Sprite:
    __slots__ = ("surf", "w", "asc", "desc", "pad", "buf")


@functools.lru_cache(maxsize=8000)
def sprite(text, fkey, size, color, tracking=0.0, grad=None, blur=0, stroke=0):
    """Rendered text as a cached Cairo surface. stroke>0 -> outline only."""
    f = font(fkey, size)
    asc, desc = f.getmetrics()
    if tracking:
        adv = [f.getlength(c) for c in text]
        tw_ = sum(adv) + tracking * (len(text) - 1)
    else:
        adv = None
        tw_ = f.getlength(text)
    pad = int(size * 0.3) + blur * 3 + stroke * 2 + 4
    wd, hd = int(math.ceil(tw_)) + 2 * pad, asc + desc + 2 * pad

    def put(img, sw=0):
        dr = ImageDraw.Draw(img)
        if adv:
            x = pad
            for c, a in zip(text, adv):
                dr.text((x, pad + asc), c, font=f, fill=255, anchor="ls", stroke_width=sw,
                        stroke_fill=255)
                x += a + tracking
        else:
            dr.text((pad, pad + asc), text, font=f, fill=255, anchor="ls", stroke_width=sw,
                    stroke_fill=255)
        return img

    m = put(Image.new("L", (wd, hd), 0), stroke)
    if stroke:
        inner = put(Image.new("L", (wd, hd), 0), 0)
        m = Image.fromarray(np.clip(np.asarray(m, np.int16) - np.asarray(inner, np.int16), 0, 255)
                            .astype(np.uint8))
    if blur:
        m = m.filter(ImageFilter.GaussianBlur(blur))
    al = np.asarray(m, np.float32)[..., None] / 255.0
    if grad:
        c1, c2 = np.array(grad[0][:3]), np.array(grad[1][:3])
        ys = np.clip((np.arange(hd) - pad - asc * 0.15) / (asc * 0.95), 0, 1)[:, None, None]
        rgb = c1 * (1 - ys) + c2 * ys
        rgb = np.broadcast_to(rgb, (hd, wd, 3))
    else:
        rgb = np.broadcast_to(np.array(color[:3]), (hd, wd, 3))
    a = al[..., 0] * (color[3] if color else 1.0)
    out = np.empty((hd, wd, 4), np.uint8)
    out[..., 0] = (rgb[..., 2] * a * 255).astype(np.uint8)
    out[..., 1] = (rgb[..., 1] * a * 255).astype(np.uint8)
    out[..., 2] = (rgb[..., 0] * a * 255).astype(np.uint8)
    out[..., 3] = (a * 255).astype(np.uint8)
    buf = bytearray(out.tobytes())
    sp = Sprite()
    sp.buf = buf
    sp.surf = cairo.ImageSurface.create_for_data(buf, cairo.FORMAT_ARGB32, wd, hd, wd * 4)
    sp.w, sp.asc, sp.desc, sp.pad = tw_, asc, desc, pad
    return sp


def tw(text, fkey, size, tracking=0.0):
    f = font(fkey, size)
    if tracking:
        return sum(f.getlength(c) for c in text) + tracking * (len(text) - 1)
    return f.getlength(text)


def fit(text, fkey, size, maxw, tracking=0.0):
    """Largest size <= `size` at which the text fits `maxw`."""
    while size > 20 and tw(text, fkey, size, tracking) > maxw:
        size -= 2
    return size


def draw_sprite(ctx, sp, x, y, alpha=1.0, scale=1.0, align="l", rot=0.0, sx=None):
    """Draw sprite with its baseline at y. x is left/centre/right per align."""
    if alpha <= 0.003 or scale <= 1e-3:
        return
    ox = x - {"l": 0, "c": sp.w / 2, "r": sp.w}[align]
    ctx.save()
    if scale != 1.0 or rot or sx is not None:
        cx = ox + sp.w / 2
        cy = y - sp.asc * 0.35
        ctx.translate(cx, cy)
        if rot:
            ctx.rotate(rot)
        ctx.scale(scale if sx is None else sx, scale)
        ctx.translate(-cx, -cy)
    ctx.set_source_surface(sp.surf, ox - sp.pad, y - sp.asc - sp.pad)
    ctx.paint_with_alpha(min(1.0, alpha))
    ctx.restore()


def text(ctx, s, fkey, size, color, x, y, alpha=1.0, align="l", tracking=0.0,
         grad=None, glow=0, glow_a=0.6, scale=1.0, glow_color=None, shadow=0, shadow_a=0.55,
         rot=0.0):
    if shadow:
        g = sprite(s, fkey, size, BLACK, tracking, None, shadow)
        draw_sprite(ctx, g, x, y + shadow * 0.25, alpha * shadow_a, scale, align, rot)
    if glow:
        g = sprite(s, fkey, size, glow_color or color, tracking, None, glow)
        draw_sprite(ctx, g, x, y, alpha * glow_a, scale, align, rot)
    sp = sprite(s, fkey, size, color, tracking, grad, 0)
    draw_sprite(ctx, sp, x, y, alpha, scale, align, rot)
    return sp


def outline_text(ctx, s, fkey, size, color, x, y, alpha=1.0, align="l", width=3, tracking=0.0):
    """Giant outlined word — great as a background layer behind a subject."""
    draw_sprite(ctx, sprite(s, fkey, size, color, tracking, None, 0, width), x, y, alpha, 1.0, align)


def text_rise(ctx, s, fkey, size, color, x, y, p, align="l", dist=None, **kw):
    """Editorial mask reveal: text slides up from behind a clip line."""
    if p <= 0:
        return
    sp = sprite(s, fkey, size, color, kw.get("tracking", 0.0), kw.get("grad"), 0)
    e = e_out5(p)
    dist = dist if dist is not None else (sp.asc + sp.desc) * 1.05
    ox = x - {"l": 0, "c": sp.w / 2, "r": sp.w}[align]
    ctx.save()
    ctx.rectangle(ox - sp.pad, y - sp.asc - sp.pad * 0.6, sp.w + 2 * sp.pad,
                  sp.asc + sp.desc + sp.pad * 1.2)
    ctx.clip()
    text(ctx, s, fkey, size, color, x, y + (1 - e) * dist, alpha=clamp(p * 2.5), align=align, **kw)
    ctx.restore()


def words_in(ctx, lt, s, fkey, size, color, x, y, t0, align="c", stagger=0.08, dur=0.7,
             rise=28, blur_in=0, alpha=1.0, scale=1.0, **kw):
    """Words of one line fade/rise in one after another (optionally from blur)."""
    words = s.split(" ")
    tr = kw.get("tracking", 0.0)
    sw = (font(fkey, size).getlength(" ") + tr * 3) * scale
    ws = [tw(w_, fkey, size, tr) * scale for w_ in words]
    total = sum(ws) + sw * (len(words) - 1)
    xx = x - {"l": 0, "c": total / 2, "r": total}[align]
    for i, w_ in enumerate(words):
        p = prog(lt, t0 + i * stagger, dur)
        if p > 0:
            e = e_out(p)
            yy = y + (1 - e) * rise
            cx = xx + ws[i] / 2
            if blur_in and p < 1:
                g = sprite(w_, fkey, size, color, tr, kw.get("grad"), blur_in)
                draw_sprite(ctx, g, cx, yy, alpha * (1 - e) * 0.9, scale, "c")
                text(ctx, w_, fkey, size, color, cx, yy, alpha=alpha * e ** 1.6, align="c",
                     scale=scale, **kw)
            else:
                text(ctx, w_, fkey, size, color, cx, yy, alpha=alpha * e, align="c", scale=scale, **kw)
        xx += ws[i] + sw


def chars_in(ctx, lt, s, fkey, size, color, x, y, t0, align="c", stagger=0.05, dur=0.8,
             rise=0, blur=10, alpha=1.0, tracking=0.0, **kw):
    """Letter-by-letter reveal from soft focus."""
    f = font(fkey, size)
    adv = [f.getlength(c) for c in s]
    total = sum(adv) + tracking * (len(s) - 1)
    xx = x - {"l": 0, "c": total / 2, "r": total}[align]
    for i, c in enumerate(s):
        p = prog(lt, t0 + i * stagger, dur)
        if p > 0 and c != " ":
            e = e_out(p)
            yy = y + (1 - e) * rise
            if p < 1:
                g = sprite(c, fkey, size, color, 0.0, kw.get("grad"), blur)
                draw_sprite(ctx, g, xx, yy, alpha * (1 - e) * 0.8)
            text(ctx, c, fkey, size, color, xx, yy, alpha=alpha * e ** 1.5, **kw)
        xx += adv[i] + tracking


def scatter_in(ctx, lt, s, fkey, size, color, x, y, t0, dur=1.1, spread=420, seed=3,
               align="c", **kw):
    """Letters fly in from random places, spinning, and lock into the word."""
    f = font(fkey, size)
    adv = [f.getlength(c) for c in s]
    total = sum(adv)
    xx = x - {"l": 0, "c": total / 2, "r": total}[align]
    r = np.random.default_rng(seed)
    offs = r.uniform(-1, 1, (len(s), 3))
    for i, c in enumerate(s):
        p = prog(lt, t0 + i * 0.03, dur)
        if p > 0 and c != " ":
            e = e_out5(p)
            dx, dy, rr = offs[i] * np.array([spread, spread * 0.8, 2.5])
            text(ctx, c, fkey, size, color, xx + dx * (1 - e), y + dy * (1 - e),
                 alpha=clamp(p * 2), rot=rr * (1 - e), **kw)
        xx += adv[i]


def typewriter(ctx, lt, s, fkey, size, color, x, y, t0, cps=18, cursor=True, align="l", **kw):
    """Characters appear at `cps` per second with a blinking caret."""
    if lt < t0:
        return
    n = int(clamp((lt - t0) * cps, 0, len(s)))
    shown = s[:n]
    total = tw(s, fkey, size)
    x0 = x - {"l": 0, "c": total / 2, "r": total}[align]
    if shown:
        text(ctx, shown, fkey, size, color, x0, y, **kw)
    if cursor and (n < len(s) or int(lt * 2) % 2 == 0):
        cx = x0 + tw(shown, fkey, size) + 6
        ctx.set_source_rgba(*color[:3], 0.9)
        ctx.rectangle(cx, y - size * 0.78, max(3, size * 0.07), size * 0.95)
        ctx.fill()


def counter(ctx, lt, t0, dur, v0, v1, fkey, size, color, x, y, fmt="{:d}", ease=e_out, **kw):
    """Animated number (e.g. 0 -> 50)."""
    v = lerp(v0, v1, ease(prog(lt, t0, dur)))
    text(ctx, fmt.format(int(round(v))), fkey, size, color, x, y, **kw)


def marker(ctx, x, y, w, h, p, color=GOLD, a=0.45):
    """Highlighter stroke sweeping behind a word (draw before the word)."""
    if p <= 0:
        return
    ctx.set_source_rgba(*color[:3], a)
    round_rect(ctx, x, y - h * 0.5, w * e_io(p), h, h * 0.3)
    ctx.fill()


def strike(ctx, x0, x1, y, p, color=GOLD, width=6):
    """Gold line drawn through text left -> right (crossing something out)."""
    if p <= 0:
        return
    xe = x0 + (x1 - x0) * e_io(p)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_width(width)
    ctx.set_source_rgba(*color[:3], 0.95)
    ctx.move_to(x0, y)
    ctx.line_to(xe, y)
    ctx.stroke()
    add_glow(ctx, xe, y, 40, GOLD_L, 0.7 * (1 - p) + 0.1)


def glitch_text(ctx, s, fkey, size, x, y, alpha, amt, t, align="c", color=WHITE):
    """RGB-split jittering text."""
    if alpha <= 0:
        return
    j = amt * 14
    dx1 = j * math.sin(t * 61.0)
    dx2 = j * math.cos(t * 47.0) + 3
    text(ctx, s, fkey, size, NEON_C, x - 3 - dx1, y, alpha=alpha * 0.75, align=align)
    text(ctx, s, fkey, size, NEON_P, x + dx2, y, alpha=alpha * 0.75, align=align)
    text(ctx, s, fkey, size, color, x, y, alpha=alpha, align=align, shadow=10)


def glint_text(ctx, s, fkey, size, x, y, p, align="l", color=None, a=0.8, width=120,
               tracking=0.0):
    """A light streak sweeping across the letters only (title glint), p: 0..1."""
    if not 0 < p < 1:
        return
    sp = sprite(s, fkey, size, WHITE, tracking)
    ox = x - {"l": 0, "c": sp.w / 2, "r": sp.w}[align]
    cx = lerp(ox - 2 * width, ox + sp.w + 2 * width, e_io(p))
    y0 = y - sp.asc
    col = color or GOLD_L
    g = cairo.LinearGradient(cx - width, y0, cx + width, y0 + (sp.asc + sp.desc) * 0.6)
    g.add_color_stop_rgba(0, *col[:3], 0)
    g.add_color_stop_rgba(0.5, *col[:3], a)
    g.add_color_stop_rgba(1, *col[:3], 0)
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_ADD)
    ctx.set_source(g)
    ctx.mask_surface(sp.surf, ox - sp.pad, y - sp.asc - sp.pad)
    ctx.restore()


def drop_chars(ctx, lt, s, fkey, size, color, x, y, t0, stagger=0.035, dur=0.6, height=700,
               align="c", seed=9, tilt=0.5, **kw):
    """Letters fall from above under gravity and bounce onto the baseline (falling, sinking)."""
    f = font(fkey, size)
    adv = [f.getlength(c) for c in s]
    total = sum(adv)
    xx = x - {"l": 0, "c": total / 2, "r": total}[align]
    r = np.random.default_rng(seed)
    jit = r.uniform(-1, 1, len(s))
    for i, c in enumerate(s):
        p = prog(lt, t0 + i * stagger, dur)
        if p > 0 and c != " ":
            e = e_bounce(p)
            yy = y - (1 - e) * height * (0.8 + 0.4 * abs(jit[i]))
            text(ctx, c, fkey, size, color, xx + adv[i] / 2, yy, alpha=clamp(p * 4), align="c",
                 rot=jit[i] * tilt * (1 - e), **kw)
        xx += adv[i]


def stamp(ctx, s, x, y, p, fkey="black", size=64, color=hx("#e0283c"), rot=-0.13, seed=3,
          pad=(34, 18), alpha=1.0):
    """Rubber stamp slammed onto the frame (p: 0..1 since the hit) with ink texture."""
    if p <= 0 or alpha <= 0:
        return
    e = e_out5(clamp(p * 1.0))
    sc = lerp(2.1, 1.0, e)
    sp = sprite(s, fkey, size, color)
    bw, bh = sp.w + 2 * pad[0], sp.asc + sp.desc * 0.4 + 2 * pad[1]
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.scale(sc, sc)
    ctx.push_group()
    ctx.set_source_rgba(*color[:3], 1)
    ctx.set_line_width(7)
    round_rect(ctx, -bw / 2, -bh / 2, bw, bh, 18)
    ctx.stroke()
    ctx.set_line_width(2.5)
    round_rect(ctx, -bw / 2 + 11, -bh / 2 + 11, bw - 22, bh - 22, 11)
    ctx.stroke()
    draw_sprite(ctx, sp, 0, sp.asc * 0.5 - sp.desc * 0.15, 1.0, align="c")
    # ink texture: knock out random specks
    rr = np.random.default_rng(seed)
    ctx.set_operator(cairo.OPERATOR_DEST_OUT)
    for _ in range(140):
        px_, py_ = rr.uniform(-bw / 2, bw / 2), rr.uniform(-bh / 2, bh / 2)
        ctx.set_source_rgba(0, 0, 0, rr.uniform(0.3, 0.9))
        ctx.arc(px_, py_, rr.uniform(0.8, 3.6), 0, 2 * math.pi)
        ctx.fill()
    ctx.pop_group_to_source()
    ctx.paint_with_alpha(alpha * clamp(p * 6) * 0.92)
    ctx.restore()


def brackets(ctx, x0, y0, x1, y1, L=56, color=GOLD_L, a=1.0, width=4, dash=False):
    """Camera-autofocus corner brackets around a box (selection / choosing)."""
    if a <= 0:
        return
    ctx.save()
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.set_line_width(width)
    ctx.set_source_rgba(*color[:3], a)
    if dash:
        ctx.set_dash([10, 9])
    L = min(L, (x1 - x0) / 2.2, (y1 - y0) / 2.2)
    for (cx, cy, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        ctx.move_to(cx + dx * L, cy)
        ctx.line_to(cx, cy)
        ctx.line_to(cx, cy + dy * L)
    ctx.stroke()
    ctx.restore()


def ecg(ctx, t, x0, x1, y, beats, amp=110, color=hx("#ff6b6b"), a=1.0, sweep=2.6, width=3.5,
        trail=0.85):
    """Heart-monitor trace. A write head sweeps x0->x1 every `sweep` s; beats = [(time, strength)]
    become PQRST spikes where the head was at that time. Older trace fades out."""
    if a <= 0:
        return
    span = x1 - x0
    head = x0 + ((t / sweep) % 1.0) * span

    def val(tw):
        v = 0.0
        for tb, s in beats:
            d = tw - tb
            if -0.12 < d < 0.3:
                v += s * (0.12 * math.exp(-((d + 0.08) / 0.025) ** 2)
                          - 0.18 * math.exp(-((d - 0.0) / 0.012) ** 2)
                          + 1.0 * math.exp(-((d - 0.03) / 0.014) ** 2)
                          - 0.35 * math.exp(-((d - 0.06) / 0.014) ** 2)
                          + 0.22 * math.exp(-((d - 0.2) / 0.04) ** 2))
        return v

    ctx.save()
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    pts = []
    for k in range(0, int(span) + 1, 3):
        x = x0 + k
        back = (head - x) % span
        age = back / span
        if age > trail:
            pts.append(None)
            continue
        tw = t - age * sweep
        pts.append((x, y - amp * val(tw), 1 - age / trail))
    for i in range(1, len(pts)):
        if pts[i] is None or pts[i - 1] is None or pts[i][0] < pts[i - 1][0]:
            continue
        al = a * pts[i][2] ** 1.5
        ctx.set_line_width(width)
        ctx.set_source_rgba(*color[:3], al)
        ctx.move_to(pts[i - 1][0], pts[i - 1][1])
        ctx.line_to(pts[i][0], pts[i][1])
        ctx.stroke()
    hy = y - amp * val(t)
    add_glow(ctx, head, hy, 46, color, 0.8 * a)
    ctx.set_source_rgba(1, 1, 1, a)
    ctx.arc(head, hy, 4, 0, 2 * math.pi)
    ctx.fill()
    ctx.restore()


def layer(fn, *args):
    """Render fn(ctx, *args) into an offscreen full-frame surface (for whole-frame tricks)."""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    c = cairo.Context(surf)
    fn(c, *args)
    surf.flush()
    return surf


def motion_paint(ctx, surf, dx, dy, vx=0.0, vy=0.0, taps=14, alpha=1.0):
    """Paint a layer offset by (dx, dy) with directional motion blur of length (vx, vy)."""
    blur = math.hypot(vx, vy)
    n = 1 if blur < 2 else taps
    for k in range(n):
        f = (k / (n - 1) - 0.5) if n > 1 else 0.0
        ctx.save()
        ctx.set_source_surface(surf, dx + vx * f, dy + vy * f)
        ctx.paint_with_alpha(alpha / (k + 1) if n > 1 else alpha)
        ctx.restore()


# --------------------------------------------------------------------------
# Backgrounds, light, overlays
# --------------------------------------------------------------------------
def bg_grad(ctx, top, bottom, mid=None):
    g = cairo.LinearGradient(0, 0, 0, H)
    g.add_color_stop_rgba(0, *top)
    if mid:
        g.add_color_stop_rgba(0.55, *mid)
    g.add_color_stop_rgba(1, *bottom)
    ctx.set_source(g)
    ctx.paint()


def glow(ctx, x, y, r, color, a):
    if a <= 0 or r <= 0:
        return
    g = cairo.RadialGradient(x, y, 0, x, y, r)
    c = color[:3]
    g.add_color_stop_rgba(0, *c, a)
    g.add_color_stop_rgba(0.35, *c, a * 0.45)
    g.add_color_stop_rgba(1, *c, 0)
    ctx.set_source(g)
    ctx.arc(x, y, r, 0, 2 * math.pi)
    ctx.fill()


def add_glow(ctx, x, y, r, color, a):
    """Additive light (brightens what is under it)."""
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_ADD)
    glow(ctx, x, y, r, color, a)
    ctx.restore()


def vignette(ctx, a=0.75):
    g = cairo.RadialGradient(W / 2, H * 0.48, H * 0.22, W / 2, H * 0.48, H * 0.75)
    g.add_color_stop_rgba(0, 0, 0, 0, 0)
    g.add_color_stop_rgba(1, 0, 0, 0, a)
    ctx.set_source(g)
    ctx.paint()


def vgrad(ctx, y0, y1, a0, a1, color=(0, 0, 0)):
    """Full-frame vertical darkening: a0 above y0, a1 beyond y1, smooth in between
    (y1 < y0 is fine — use it to darken the top)."""
    g = cairo.LinearGradient(0, y0, 0, y1)
    g.add_color_stop_rgba(0, *color[:3], a0)
    g.add_color_stop_rgba(1, *color[:3], a1)
    g.set_extend(cairo.EXTEND_PAD)
    ctx.set_source(g)
    ctx.paint()


def tint(ctx, color, a, op=cairo.OPERATOR_OVERLAY):
    """Colour grade the whole layer (OVERLAY, SOFT_LIGHT, MULTIPLY, SCREEN...)."""
    if a <= 0:
        return
    ctx.save()
    ctx.set_operator(op)
    ctx.set_source_rgba(*color[:3], a)
    ctx.paint()
    ctx.restore()


def letterbox(ctx, a, bar=170, color=(0, 0, 0)):
    """Cinematic bars sliding in (a: 0..1)."""
    if a <= 0:
        return
    hb = bar * e_out(a)
    ctx.set_source_rgba(*color[:3], 1)
    ctx.rectangle(0, 0, W, hb)
    ctx.rectangle(0, H - hb, W, hb)
    ctx.fill()


def scanlines(ctx, a=0.12, gap=4):
    if a <= 0:
        return
    ctx.set_source_rgba(0, 0, 0, a)
    for y in range(0, H, gap):
        ctx.rectangle(0, y, W, 1)
    ctx.fill()


def god_rays(ctx, t, ox, oy, a, color, n=9, seed=5, ang0=1.85, ang1=2.55, length=2600):
    """Light shafts from (ox, oy) fanning between angles ang0..ang1 (radians, cairo)."""
    r = np.random.default_rng(seed)
    wd, ph, fr = r.uniform(0.012, 0.04, n), r.uniform(0, 6.28, n), r.uniform(0.3, 0.9, n)
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_ADD)
    for i in range(n):
        ang = lerp(ang0, ang1, (i + 0.5) / n) + 0.035 * math.sin(t * 0.25 + ph[i])
        al = a * (0.45 + 0.55 * (0.5 + 0.5 * math.sin(t * fr[i] + ph[i])))
        g = cairo.RadialGradient(ox, oy, 0, ox, oy, length)
        g.add_color_stop_rgba(0, *color[:3], al)
        g.add_color_stop_rgba(0.45, *color[:3], al * 0.45)
        g.add_color_stop_rgba(1, *color[:3], 0)
        ctx.set_source(g)
        ctx.move_to(ox, oy)
        ctx.arc(ox, oy, length, ang - wd[i], ang + wd[i])
        ctx.close_path()
        ctx.fill()
    ctx.restore()


def flare(ctx, x, y, a, t, streak=900):
    """Sun / lens flare: core glow, anamorphic streak, ghosts toward the centre."""
    if a <= 0:
        return
    add_glow(ctx, x, y, 520, WARM, 0.26 * a)
    add_glow(ctx, x, y, 160, GOLD_L, 0.55 * a)
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_ADD)
    ctx.translate(x, y)
    ctx.scale(1, 0.035)
    g = cairo.RadialGradient(0, 0, 0, 0, 0, streak)
    g.add_color_stop_rgba(0, *GOLD_L[:3], 0.55 * a)
    g.add_color_stop_rgba(1, *GOLD_L[:3], 0)
    ctx.set_source(g)
    ctx.arc(0, 0, streak, 0, 2 * math.pi)
    ctx.fill()
    ctx.restore()
    for f, r, c in ((0.55, 46, NEON_C), (0.95, 26, WARM), (1.35, 70, GOLD)):
        gx, gy = x + (W / 2 - x) * f * 2, y + (H * 0.45 - y) * f * 2
        add_glow(ctx, gx, gy, r, c, 0.10 * a)


def light_leak(ctx, t, a, seed=2, colors=(WARM, hx("#ff6a3c"), GOLD_L)):
    """Drifting film light leaks (additive blobs entering from the edges)."""
    if a <= 0:
        return
    r = np.random.default_rng(seed)
    for k, c in enumerate(colors):
        ph = r.uniform(0, 6.28)
        x = W * (0.5 + 0.65 * math.cos(t * 0.23 + ph))
        y = H * (0.5 + 0.6 * math.sin(t * 0.17 + ph * 1.3))
        add_glow(ctx, x, y, 900 + 200 * k, c, a * (0.16 + 0.05 * math.sin(t + k)))


def shockwave(ctx, x, y, q, color=GOLD_L, rmax=950, width=3):
    """Expanding double ring (q: 0..1 since the hit)."""
    if not 0 < q < 1:
        return
    ctx.set_line_width(width * (1 - q) + 0.5)
    ctx.set_source_rgba(*color[:3], 0.8 * (1 - q))
    ctx.arc(x, y, 50 + rmax * e_out(q), 0, 2 * math.pi)
    ctx.stroke()
    ctx.set_line_width(1.5)
    ctx.set_source_rgba(*color[:3], 0.5 * (1 - q))
    ctx.arc(x, y, 30 + rmax * 0.63 * e_out(q), 0, 2 * math.pi)
    ctx.stroke()


def flash(ctx, a, color=WHITE):
    if a > 0:
        ctx.set_source_rgba(*color[:3], min(1, a))
        ctx.paint()


# --------------------------------------------------------------------------
# Particles / living details
# --------------------------------------------------------------------------
@functools.lru_cache(maxsize=None)
def _rng_parts(seed, n):
    r = np.random.default_rng(seed)
    return (r.uniform(0, W, n), r.uniform(0, H, n), r.uniform(8, 38, n),
            r.uniform(0.8, 3.2, n), r.uniform(0, 6.28, n), r.uniform(0.6, 2.2, n),
            r.uniform(-12, 12, n))


def dust(ctx, t, color, seed=1, n=70, a=0.55, speed=1.0, size=1.0, add=False):
    """Floating dust motes rising slowly."""
    xs, ys, sp, sz, ph, fr, dx = _rng_parts(seed, n)
    c = color[:3]
    if add:
        ctx.save()
        ctx.set_operator(cairo.OPERATOR_ADD)
    for i in range(n):
        y = (ys[i] - sp[i] * t * speed) % (H + 40) - 20
        x = (xs[i] + dx[i] * math.sin(t * 0.4 + ph[i]) * 2) % W
        al = a * (0.25 + 0.75 * (0.5 + 0.5 * math.sin(ph[i] + t * fr[i])))
        ctx.set_source_rgba(*c, al)
        ctx.arc(x, y, sz[i] * size, 0, 2 * math.pi)
        ctx.fill()
    if add:
        ctx.restore()


def stars(ctx, t, seed, n, y_max, color=WHITE, a=0.9):
    """Twinkling stars with sparkle crosses."""
    xs, ys, _, sz, ph, fr, _ = _rng_parts(seed, n)
    for i in range(n):
        y = ys[i] / H * y_max
        tw_ = 0.5 + 0.5 * math.sin(ph[i] + t * fr[i] * 1.6)
        al = a * (0.15 + 0.85 * tw_ ** 2)
        r = sz[i] * 0.7
        ctx.set_source_rgba(*color[:3], al)
        ctx.arc(xs[i], y, r, 0, 2 * math.pi)
        ctx.fill()
        if sz[i] > 2.6 and tw_ > 0.6:
            L = r * 6 * tw_
            ctx.set_line_width(1.2)
            ctx.set_source_rgba(*color[:3], al * 0.6)
            ctx.move_to(xs[i] - L, y)
            ctx.line_to(xs[i] + L, y)
            ctx.move_to(xs[i], y - L)
            ctx.line_to(xs[i], y + L)
            ctx.stroke()


def fall(ctx, t, kind="petal", color=hx("#ffc4cf"), seed=4, n=40, a=0.8, speed=1.0, wind=40):
    """Falling particles: kind = 'petal' | 'snow' | 'rain' | 'confetti'."""
    xs, ys, sp, sz, ph, fr, dx = _rng_parts(seed, n)
    base = {"rain": 900, "snow": 60, "petal": 90, "confetti": 160}[kind]
    for i in range(n):
        v = base * (0.6 + sp[i] / 4) * speed
        y = (ys[i] + v * t) % (H + 80) - 40
        x = (xs[i] + wind * t * (0.5 + fr[i]) + 30 * math.sin(t * fr[i] + ph[i])) % (W + 40) - 20
        if kind == "rain":
            ctx.set_source_rgba(*color[:3], a * 0.35)
            ctx.set_line_width(1.5)
            ctx.move_to(x, y)
            ctx.line_to(x - wind * 0.05, y - 40)
            ctx.stroke()
            continue
        ctx.save()
        ctx.translate(x, y)
        ctx.rotate(ph[i] + t * fr[i] * (2 if kind != "snow" else 0))
        if kind == "snow":
            ctx.set_source_rgba(1, 1, 1, a * 0.7)
            ctx.arc(0, 0, sz[i] * 1.2, 0, 2 * math.pi)
        elif kind == "confetti":
            col = (GOLD_L, ROSE, NEON_C, WHITE)[i % 4]
            ctx.set_source_rgba(*col[:3], a)
            ctx.scale(1, abs(math.sin(t * 3 + ph[i])) + 0.2)
            ctx.rectangle(-6, -3, 12, 6)
        else:
            ctx.set_source_rgba(*color[:3], a * 0.85)
            ctx.scale(1, 0.55 + 0.45 * math.sin(t * 2 + ph[i]))
            ctx.arc(0, 0, sz[i] * 3, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()


def sparks(ctx, x, y, q, seed=1, n=26, color=GOLD_L, reach=420):
    """Radial burst of sparks (q: 0..1 since the hit)."""
    if not 0 < q < 1:
        return
    r = np.random.default_rng(seed)
    ang, sp, ln = r.uniform(0, 6.28, n), r.uniform(0.4, 1.0, n), r.uniform(10, 40, n)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for i in range(n):
        d = reach * sp[i] * e_out(q)
        x1, y1 = x + math.cos(ang[i]) * d, y + math.sin(ang[i]) * d
        ctx.set_source_rgba(*color[:3], 1 - q)
        ctx.set_line_width(3 * (1 - q) + 0.5)
        ctx.move_to(x1, y1)
        ctx.line_to(x1 - math.cos(ang[i]) * ln[i], y1 - math.sin(ang[i]) * ln[i])
        ctx.stroke()


def bokeh(ctx, t, color, seed=7, n=10, a=0.10, rmin=40, rmax=130, region=None):
    """Large soft out-of-focus light discs drifting slowly."""
    r = np.random.default_rng(seed)
    xs, ys = r.uniform(0, 1, n), r.uniform(0, 1, n)
    rs, ph = r.uniform(rmin, rmax, n), r.uniform(0, 6.28, n)
    x0, y0, x1, y1 = region or (0, 0, W, H)
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_ADD)
    for i in range(n):
        x = x0 + (xs[i] * (x1 - x0) + 30 * math.sin(t * 0.3 + ph[i]))
        y = y0 + ((ys[i] * (y1 - y0) - t * 12 * (0.5 + xs[i])) % (y1 - y0))
        al = a * (0.5 + 0.5 * math.sin(t * 0.7 + ph[i]))
        g = cairo.RadialGradient(x, y, rs[i] * 0.6, x, y, rs[i])
        g.add_color_stop_rgba(0, *color[:3], al)
        g.add_color_stop_rgba(1, *color[:3], 0)
        ctx.set_source(g)
        ctx.arc(x, y, rs[i], 0, 2 * math.pi)
        ctx.fill()
    ctx.restore()


@functools.lru_cache(maxsize=None)
def _glyph_set(seed, n, burst_t, burst_n, charset, sizes):
    r = np.random.default_rng(seed)
    ts = list(r.uniform(-0.4, 5.0, n)) + list(burst_t + r.uniform(0, 0.45, burst_n))
    m = len(ts)
    offs = r.uniform(-1, 1, (m, 2)) * np.array([170, 70])
    chars = [charset[k] for k in r.integers(0, len(charset), m)]
    ang = r.uniform(-math.pi * 1.0, -math.pi * 0.2, m)
    spd = r.uniform(110, 260, m) * np.array([1.0] * n + [1.8] * burst_n)
    size = r.choice(list(sizes), m)
    rot = r.uniform(-1.2, 1.2, m)
    life = r.uniform(1.8, 2.8, m)
    return ts, chars, ang, spd, size, rot, life, offs


def flying_glyphs(ctx, lt, ox, oy, seed=17, n=40, burst_t=99.0, burst_n=0,
                  charset="abdefghijklmnopqrstuvxyzo‘g‘shch", sizes=(44, 56, 68, 84, 100),
                  fkey="serif_it", color=GOLD_L, glow_color=AMBER, a=1.0):
    """Letters (or any symbols) lifting off a source point; optional burst at burst_t."""
    ts, chars, ang, spd, size, rot, life, offs = _glyph_set(seed, n, burst_t, burst_n, charset,
                                                            tuple(sizes))
    for i in range(len(ts)):
        age = lt - ts[i]
        if age <= 0 or age > life[i]:
            continue
        p = age / life[i]
        al = a * min(1, age / 0.35) * (1 - p) ** 1.2
        x = ox + offs[i][0] + math.cos(ang[i]) * spd[i] * age + 18 * math.sin(age * 2.4 + i)
        y = oy + offs[i][1] + math.sin(ang[i]) * spd[i] * age - 30 * age * age
        text(ctx, chars[i], fkey, int(size[i]), color, x, y, alpha=al, align="c",
             rot=rot[i] * age, glow=10, glow_a=0.7, glow_color=glow_color)


def steam(ctx, t, x, y, a, h=160):
    """Rising steam wisps (coffee, tea, food)."""
    if a <= 0:
        return
    for k in range(3):
        ph = k * 2.1
        for j in range(14):
            q = j / 14
            yy = y - q * h - ((t * 40 + k * 30) % 20)
            xx = x + (k - 1) * 22 + 18 * math.sin(t * 1.7 + q * 5 + ph) * q
            al = a * (1 - q) * q * 2.2
            ctx.set_source_rgba(1, 1, 1, 0.22 * al)
            ctx.arc(xx, yy, 7 + 10 * q, 0, 2 * math.pi)
            ctx.fill()


def bird(ctx, x, y, s, flap, a, color=(0.12, 0.08, 0.10)):
    ctx.set_source_rgba(*color[:3], a)
    ctx.set_line_width(max(2, s * 0.14))
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.move_to(x - s, y - s * 0.45 * flap)
    ctx.curve_to(x - s * 0.55, y - s * 0.55 * flap - s * 0.1, x - s * 0.2, y - s * 0.12, x, y)
    ctx.curve_to(x + s * 0.2, y - s * 0.12, x + s * 0.55, y - s * 0.55 * flap - s * 0.1,
                 x + s, y - s * 0.45 * flap)
    ctx.stroke()


def flock(ctx, lt, n=4, y0=420, dy=90, speed=70, size=30, a=0.8):
    """A few birds crossing the sky left -> right."""
    for k in range(n):
        bx = -80 + ((lt + 0.6) * (speed + 12 * k) + 260 * k) % (W + 220)
        by = y0 + dy * k + 14 * math.sin(lt * 1.2 + k)
        bird(ctx, bx, by, size - 4 * k, math.sin(lt * (8 + k) + k), a)


# --------------------------------------------------------------------------
# Vector icons
# --------------------------------------------------------------------------
def heart(ctx, x, y, r):
    ctx.move_to(x, y + r * 0.9)
    ctx.curve_to(x - r * 1.7, y - r * 0.15, x - r * 0.75, y - r * 1.35, x, y - r * 0.42)
    ctx.curve_to(x + r * 0.75, y - r * 1.35, x + r * 1.7, y - r * 0.15, x, y + r * 0.9)
    ctx.close_path()


def eye(ctx, x, y, r, color, a):
    ctx.set_source_rgba(*color[:3], a)
    ctx.set_line_width(max(2, r * 0.14))
    ctx.move_to(x - r, y)
    ctx.curve_to(x - r * 0.45, y - r * 0.72, x + r * 0.45, y - r * 0.72, x + r, y)
    ctx.curve_to(x + r * 0.45, y + r * 0.72, x - r * 0.45, y + r * 0.72, x - r, y)
    ctx.close_path()
    ctx.stroke()
    ctx.arc(x, y, r * 0.3, 0, 2 * math.pi)
    ctx.fill()


def clock_icon(ctx, x, y, r, lt, a):
    """Minimal clock whose hands spin fast then settle (time passing)."""
    if a <= 0:
        return
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_source_rgba(*GOLD[:3], 0.9 * a)
    ctx.set_line_width(2.2)
    ctx.arc(x, y, r, 0, 2 * math.pi)
    ctx.stroke()
    for k in range(12):
        an = k * math.pi / 6
        rr = r - 7
        ctx.arc(x + rr * math.cos(an), y + rr * math.sin(an), 1.6 if k % 3 else 2.6, 0, 2 * math.pi)
        ctx.fill()
    spin = e_out(prog(lt, 0.2, 2.2)) * 2 * math.pi * 3 + lt * 0.6
    for L, ang, wd in ((r * 0.72, spin, 2.2), (r * 0.48, spin / 12 + 1.2, 3.0)):
        ctx.set_line_width(wd)
        ctx.move_to(x, y)
        ctx.line_to(x + L * math.cos(ang - math.pi / 2), y + L * math.sin(ang - math.pi / 2))
        ctx.stroke()
    add_glow(ctx, x, y, r * 3, GOLD, 0.10 * a)


@functools.lru_cache(maxsize=None)
def _rand_table(seed, n, t0, t1, x0, x1, y0, y1):
    r = np.random.default_rng(seed)
    return (r.uniform(t0, t1, n), r.uniform(x0, x1, n), r.uniform(y0, y1, n), r.integers(0, 3, n),
            r.uniform(18, 34, n), r.uniform(0, 6.28, n), r.uniform(1.6, 2.4, n), r.uniform(0.6, 1, n))


def social_icons(ctx, lt, seed=51, n=22, t_range=(-0.1, 3.4), region=(110, 970, 560, 900), a=1.0):
    """Hearts, eyes and notification bubbles rising with RGB glitch — 'showing off'."""
    ts, xs, ys, kind, sz, ph, life, _ = _rand_table(seed, n, *t_range, *region)
    for i in range(n):
        age = lt - ts[i]
        if age <= 0 or age > life[i]:
            continue
        p = age / life[i]
        al = a * min(1, age / 0.25) * (1 - p)
        x = xs[i] + 22 * math.sin(age * 3 + ph[i])
        y = ys[i] - 300 * e_out(p)
        col = NEON_P if kind[i] != 1 else NEON_C
        jit = 5 * math.sin(lt * 47 + i)
        for dx, c, aa in ((-jit, NEON_C, 0.5), (jit, NEON_P, 0.5), (0, col, 1.0)):
            if kind[i] == 1:
                eye(ctx, x + dx, y, sz[i] * 1.2, c, al * aa)
            else:
                ctx.set_source_rgba(*c[:3], al * aa)
                if kind[i] == 0:
                    heart(ctx, x + dx, y, sz[i])
                    ctx.fill()
                else:
                    round_rect(ctx, x + dx - sz[i] * 1.5, y - sz[i], sz[i] * 3, sz[i] * 2, sz[i] * 0.6)
                    ctx.set_line_width(3)
                    ctx.stroke()
                    heart(ctx, x + dx, y, sz[i] * 0.45)
                    ctx.fill()


def camera_flashes(ctx, lt, seed=61, n=26, t_range=(0, 3.8), region=(60, 1020, 40, 560)):
    """Paparazzi flash pops."""
    ts, xs, ys, _, _, _, _, st = _rand_table(seed, n, *t_range, *region)
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_ADD)
    for i in range(n):
        f = bump(lt, ts[i], 0.16)
        if f <= 0:
            continue
        glow(ctx, xs[i], ys[i], 120 * st[i], WHITE, 0.55 * f)
        ctx.set_source_rgba(1, 1, 1, 0.7 * f)
        ctx.set_line_width(2)
        L = 70 * st[i] * f
        ctx.move_to(xs[i] - L, ys[i])
        ctx.line_to(xs[i] + L, ys[i])
        ctx.move_to(xs[i], ys[i] - L)
        ctx.line_to(xs[i], ys[i] + L)
        ctx.stroke()
    ctx.restore()


# --------------------------------------------------------------------------
# Paths / shapes
# --------------------------------------------------------------------------
def path_len(ctx):
    L, last, first = 0.0, None, None
    for kind, pts in ctx.copy_path_flat():
        if kind == cairo.PATH_MOVE_TO:
            last = first = pts
        elif kind == cairo.PATH_LINE_TO:
            L += math.hypot(pts[0] - last[0], pts[1] - last[1])
            last = pts
        elif kind == cairo.PATH_CLOSE_PATH and first:
            L += math.hypot(first[0] - last[0], first[1] - last[1])
            last = first
    return L


def stroke_partial(ctx, p, keep=False):
    """Stroke the current path only up to fraction p of its length (line drawing)."""
    if p <= 0:
        ctx.new_path()
        return
    if p < 1:
        L = path_len(ctx)
        ctx.set_dash([L * p, L * 2], 0)
    if keep:
        ctx.stroke_preserve()
    else:
        ctx.stroke()
    ctx.set_dash([])


def round_rect(ctx, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()


def arch_path(ctx, x0, x1, y_spring, apex, bottom):
    """Pointed arch / window shape (use as a mask or a traced outline)."""
    cx = (x0 + x1) / 2
    ctx.move_to(x0, bottom)
    ctx.line_to(x0, y_spring)
    ctx.curve_to(x0, y_spring - 230, cx - 160, apex + 70, cx, apex)
    ctx.curve_to(cx + 160, apex + 70, x1, y_spring - 230, x1, y_spring)
    ctx.line_to(x1, bottom)
    ctx.close_path()


def progress_bar(ctx, idx, n, lt, dur, a=1.0, y=118, x0=70, x1=None, gap=16):
    """Segmented story progress (for numbered lists)."""
    if a <= 0:
        return
    x1 = x1 or W - 70
    seg = (x1 - x0 - gap * (n - 1)) / n
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for i in range(n):
        sx = x0 + i * (seg + gap)
        ctx.set_line_width(5)
        ctx.set_source_rgba(1, 1, 1, 0.16 * a)
        ctx.move_to(sx, y)
        ctx.line_to(sx + seg, y)
        ctx.stroke()
        f = 1.0 if i < idx else (clamp(lt / dur) if i == idx else 0)
        if f > 0:
            g = cairo.LinearGradient(sx, 0, sx + seg, 0)
            g.add_color_stop_rgba(0, *GOLD_D[:3], a)
            g.add_color_stop_rgba(1, *GOLD_L[:3], a)
            ctx.set_source(g)
            ctx.move_to(sx, y)
            ctx.line_to(sx + seg * f, y)
            ctx.stroke()
            if i == idx:
                glow(ctx, sx + seg * f, y, 22, GOLD_L, 0.7 * a)


def handle(ctx, lt, t0, y=None):
    """Author signature with side rules — always at the end of a video."""
    hp = prog(lt, t0, 1.0)
    if hp <= 0:
        return
    y = y or H - 70
    e = e_out(hp)
    lw = 70 * e
    ctx.set_line_width(2)
    ctx.set_source_rgba(*GOLD[:3], 0.7 * e)
    hw = tw(HANDLE, "semi", 38, 2) / 2
    for sd in (-1, 1):
        ctx.move_to(W / 2 + sd * (hw + 24), y - 12)
        ctx.line_to(W / 2 + sd * (hw + 24 + lw), y - 12)
    ctx.stroke()
    text_rise(ctx, HANDLE, "semi", 38, GOLD_L, W / 2, y, hp, align="c", tracking=2,
              glow=10, glow_a=0.35)


# --------------------------------------------------------------------------
# Pictures, camera, masks
# --------------------------------------------------------------------------
class Pic:
    """RGB(A) numpy image as a Cairo surface (premultiplied if alpha is given)."""

    def __init__(self, rgb, alpha=None):
        rgb = np.ascontiguousarray(rgb)
        h, w = rgb.shape[:2]
        out = np.empty((h, w, 4), np.uint8)
        if alpha is None:
            out[..., 0], out[..., 1], out[..., 2] = rgb[..., 2], rgb[..., 1], rgb[..., 0]
            out[..., 3] = 255
        else:
            a = alpha.astype(np.float32) / 255.0
            for k, c in ((0, 2), (1, 1), (2, 0)):
                out[..., k] = (rgb[..., c] * a + 0.5).astype(np.uint8)
            out[..., 3] = alpha
        self.arr = out
        self.surf = cairo.ImageSurface.create_for_data(out, cairo.FORMAT_ARGB32, w, h, w * 4)
        self.w, self.h = w, h

    def rgb(self):
        return np.ascontiguousarray(self.arr[..., [2, 1, 0]])


def load_rgb(path):
    if not os.path.isabs(path):
        path = os.path.join(IDIR, path)
    return np.asarray(Image.open(path).convert("RGB"))


def grade(rgb, sat=1.0, gain=(1.0, 1.0, 1.0), contrast=1.0, gamma=1.0, lift=0.0):
    """Precomputed colour grade (cheap at render time: crossfade graded variants)."""
    x = rgb.astype(np.float32) / 255.0
    lum = (x @ np.array([0.299, 0.587, 0.114], np.float32))[..., None]
    x = lum + (x - lum) * sat
    x = (x - 0.5) * contrast + 0.5
    x = x * np.array(gain, np.float32) + lift
    x = np.clip(x, 0, 1) ** gamma
    return (x * 255 + 0.5).astype(np.uint8)


def duotone(rgb, dark, light):
    """Map luminance to a two-colour ramp (posters, memories, flashbacks)."""
    x = rgb.astype(np.float32) / 255.0
    lum = (x @ np.array([0.299, 0.587, 0.114], np.float32))[..., None]
    d, l_ = np.array(dark[:3], np.float32), np.array(light[:3], np.float32)
    return ((d * (1 - lum) + l_ * lum) * 255 + 0.5).astype(np.uint8)


def resize(rgb, f):
    im = Image.fromarray(rgb)
    return np.asarray(im.resize((max(1, round(im.width * f)), max(1, round(im.height * f))),
                                Image.LANCZOS))


def blurred(rgb, radius, f=0.5, dark=1.0):
    """Blurred (and optionally darkened) copy at scale f — draw it scaled by 1/f."""
    im = Image.fromarray(resize(rgb, f)).filter(ImageFilter.GaussianBlur(radius * f))
    a = np.asarray(im).astype(np.float32) * dark
    return np.clip(a, 0, 255).astype(np.uint8)


def cutout_luma(rgb, y1=None, x0=0, x1=None, thresh=0.42, soft=0.10, close=7, feather=1.2,
                dark=True):
    """Subject mask by luminance (dark subject on bright sky, or the reverse) for
    'text behind subject' and parallax. Restrict to a region to avoid stray pixels."""
    y1 = y1 or rgb.shape[0]
    x1 = x1 or rgb.shape[1]
    reg = rgb[:y1].astype(np.float32) / 255.0
    lum = reg @ np.array([0.299, 0.587, 0.114], np.float32)
    m = np.clip(((thresh - lum) if dark else (lum - thresh)) / soft, 0, 1)
    m[:, :x0] = 0
    m[:, x1:] = 0
    mi = Image.fromarray((m * 255).astype(np.uint8))
    if close:
        mi = mi.filter(ImageFilter.MaxFilter(close)).filter(ImageFilter.MinFilter(close))
    if feather:
        mi = mi.filter(ImageFilter.GaussianBlur(feather))
    return Pic(rgb[:y1], np.asarray(mi))


def paint_pic(ctx, pic, s, tx, ty, alpha=1.0, filt=cairo.FILTER_BILINEAR, pad=True):
    """Draw picture scaled by s with its top-left at (tx, ty)."""
    if alpha <= 0.003:
        return
    ctx.save()
    ctx.translate(tx, ty)
    ctx.scale(s, s)
    ctx.set_source_surface(pic.surf, 0, 0)
    pat = ctx.get_source()
    pat.set_filter(filt)
    if pad:
        pat.set_extend(cairo.EXTEND_PAD)
    else:
        ctx.rectangle(0, 0, pic.w, pic.h)
        ctx.clip()
    ctx.paint_with_alpha(alpha)
    ctx.restore()


def cam_cover(pic, fx, fy, z=1.0, px=None, py=None, box=None, base=None):
    """Scale so the picture covers `box` (times z) with picture point (fx,fy) at (px,py),
    clamped so no edge of the picture shows inside the box. Returns (s, tx, ty)."""
    bx0, by0, bx1, by1 = box or (0, 0, W, H)
    px = W / 2 if px is None else px
    py = H / 2 if py is None else py
    s = (base if base else max((bx1 - bx0) / pic.w, (by1 - by0) / pic.h)) * z
    tx, ty = px - fx * s, py - fy * s
    tx = min(bx0, max(bx1 - pic.w * s, tx))
    ty = min(by0, max(by1 - pic.h * s, ty))
    return s, tx, ty


def zoom_between(s0, A0, s1, A1, e):
    """Camera move that feels like one continuous zoom about a fixed point
    (screen = A + s * world). Use for dives into / out of a picture or collage."""
    s = s0 * (s1 / s0) ** e
    f = (s - s0) / (s1 - s0) if s1 != s0 else e
    return s, lerp2(A0, A1, f)


def polaroid(ctx, pic, cx, cy, w, rot=0.0, alpha=1.0, focus=None, border=22, bottom=90):
    """Frame-in-frame photo card with shadow (memories, flashbacks)."""
    if alpha <= 0:
        return
    h = w
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(rot)
    ctx.set_source_rgba(0, 0, 0, 0.35 * alpha)
    round_rect(ctx, -w / 2 - border + 10, -h / 2 - border + 16, w + 2 * border, h + border + bottom, 8)
    ctx.fill()
    ctx.set_source_rgba(0.97, 0.95, 0.9, alpha)
    round_rect(ctx, -w / 2 - border, -h / 2 - border, w + 2 * border, h + border + bottom, 8)
    ctx.fill()
    ctx.rectangle(-w / 2, -h / 2, w, h)
    ctx.clip()
    fx, fy = focus or (pic.w / 2, pic.h / 2)
    s = max(w / pic.w, h / pic.h)
    ctx.translate(-fx * s, -fy * s)
    ctx.scale(s, s)
    ctx.set_source_surface(pic.surf, 0, 0)
    ctx.get_source().set_filter(cairo.FILTER_BILINEAR)
    ctx.paint_with_alpha(alpha)
    ctx.restore()


class Mosaic:
    """Pictures laid out as rectangles in one coordinate space (e.g. a source collage).
    screen = A + s * world. Keeps mip levels so tiny tiles don't shimmer."""

    def __init__(self, pics, rects):
        self.rects = rects
        self.levels = [list(pics), [], []]
        for p in pics:
            rgb = p.rgb()
            self.levels[1].append(Pic(resize(rgb, 0.5)))
            self.levels[2].append(Pic(resize(rgb, 0.25)))

    def draw(self, ctx, s, A, alphas, radius=7, border=None, sweep=None, color=GOLD_L):
        for i, (x0, y0, x1, y1) in enumerate(self.rects):
            a = alphas[i]
            if a <= 0.003:
                continue
            X0, Y0 = A[0] + x0 * s, A[1] + y0 * s
            rw, rh = (x1 - x0) * s, (y1 - y0) * s
            if X0 > W or Y0 > H or X0 + rw < 0 or Y0 + rh < 0:
                continue
            k = rw / self.levels[0][i].w
            lvl = 0 if k >= 0.5 else 1 if k >= 0.25 else 2
            pic = self.levels[lvl][i]
            kk = rw / pic.w
            ctx.save()
            round_rect(ctx, X0, Y0, rw, rh, radius * s)
            ctx.clip()
            ctx.translate(X0, Y0)
            ctx.scale(kk, kk)
            ctx.set_source_surface(pic.surf, 0, 0)
            ctx.get_source().set_filter(cairo.FILTER_BILINEAR)
            ctx.get_source().set_extend(cairo.EXTEND_PAD)
            ctx.paint_with_alpha(a)
            ctx.restore()
            ba = (border[i] if border else 0) + (sweep[i] if sweep else 0)
            if ba > 0.003:
                round_rect(ctx, X0, Y0, rw, rh, radius * s)
                ctx.set_line_width(3)
                ctx.set_source_rgba(*color[:3], min(1, ba))
                ctx.stroke()
                if sweep and sweep[i] > 0:
                    add_glow(ctx, X0 + rw / 2, Y0 + rh / 2, max(rw, rh) * 0.7, GOLD, 0.18 * sweep[i])


def glitch(surf, amt, seed):
    """RGB split + horizontal slice displacement on a finished layer (in place)."""
    if amt <= 0.01:
        return
    surf.flush()
    a = np.ndarray((surf.get_height(), surf.get_width(), 4), np.uint8, surf.get_data())
    rng = np.random.default_rng(seed)
    d = int(round(amt * 16))
    if d:
        a[..., 2] = np.roll(a[..., 2], d, axis=1)
        a[..., 0] = np.roll(a[..., 0], -d, axis=1)
    for _ in range(int(2 + amt * 8)):
        y0 = int(rng.integers(0, a.shape[0] - 100))
        hh = int(rng.integers(10, 80))
        sh = int(rng.integers(-90, 90) * amt)
        if sh:
            a[y0:y0 + hh] = np.roll(a[y0:y0 + hh], sh, axis=1)
    surf.mark_dirty()


def make_grain(seed=42, k=4):
    g = np.random.default_rng(seed)
    out = []
    for _ in range(k):
        n = np.clip(g.normal(128, 38, (H // 2, W // 2)), 0, 255).astype(np.uint8)
        out.append(Pic(np.repeat(n[..., None], 3, 2)))
    return out


# --------------------------------------------------------------------------
# Transitions — TRANS = {boundary_index: (name, total_duration[, {options}])}
# --------------------------------------------------------------------------
def paint_scaled(ctx, surf, s, alpha=1.0, dx=0.0, dy=0.0, rot=0.0):
    ctx.save()
    ctx.translate(W / 2 + dx, H / 2 + dy)
    if rot:
        ctx.rotate(rot)
    ctx.scale(s, s)
    ctx.translate(-W / 2, -H / 2)
    ctx.set_source_surface(surf)
    ctx.paint_with_alpha(alpha)
    ctx.restore()


def _dirvec(d):
    return {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}[d]


def tr_fade(ctx, sa, sb, p, o):
    paint_scaled(ctx, sa, 1.0)
    paint_scaled(ctx, sb, 1.0, e_io(p))


def tr_burn(ctx, sa, sb, p, o):
    """Film burn / light leak flash between shots."""
    e, fl = e_io(p), math.sin(p * math.pi)
    paint_scaled(ctx, sa, 1 + 0.06 * e)
    paint_scaled(ctx, sb, 1.04 - 0.04 * e, e)
    add_glow(ctx, o.get("x", W * 0.83), o.get("y", H * 0.27), 1500, o.get("color", WARM), 0.55 * fl)
    add_glow(ctx, W * 0.7, H * 0.36, 900, WHITE, 0.22 * fl)


def tr_zoom(ctx, sa, sb, p, o):
    """Zoom through + crossfade + gold light line sweeping up."""
    e, fl = e_io(p), math.sin(p * math.pi)
    paint_scaled(ctx, sa, 1 + 0.10 * e)
    paint_scaled(ctx, sb, 0.92 + 0.08 * e, e)
    y = lerp(H * 1.05, -H * 0.05, e)
    g = cairo.LinearGradient(0, y - 160, 0, y + 160)
    g.add_color_stop_rgba(0, *GOLD_L[:3], 0)
    g.add_color_stop_rgba(0.5, *GOLD_L[:3], 0.22 * fl)
    g.add_color_stop_rgba(1, *GOLD_L[:3], 0)
    ctx.set_source(g)
    ctx.paint()
    ctx.set_source_rgba(*GOLD_L[:3], 0.8 * fl)
    ctx.set_line_width(2)
    ctx.move_to(0, y)
    ctx.line_to(W, y)
    ctx.stroke()


def tr_dissolve(ctx, sa, sb, p, o):
    """Slow soft dissolve with a bloom — for calm after chaos."""
    e, fl = e_io(p), math.sin(p * math.pi)
    paint_scaled(ctx, sa, 1 + 0.03 * e)
    paint_scaled(ctx, sb, 1.03 - 0.03 * e, e)
    add_glow(ctx, W / 2, H * 0.47, 1300, o.get("color", GOLD_L), 0.20 * fl)


def tr_whip(ctx, sa, sb, p, o):
    """Whip pan with real box motion blur (running average of taps)."""
    e, fl = e_io(p), math.sin(p * math.pi)
    vx, vy = _dirvec(o.get("dir", "up"))
    blur = o.get("blur", 220) * fl
    n = 18
    for k in range(n):
        off = (k / (n - 1) - 0.5) * blur
        ctx.push_group()
        paint_scaled(ctx, sa, 1.0, 1.0, dx=vx * W * e + vx * off, dy=vy * H * e + vy * off)
        paint_scaled(ctx, sb, 1.0, 1.0, dx=-vx * W * (1 - e) + vx * off,
                     dy=-vy * H * (1 - e) + vy * off)
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(1.0 / (k + 1))
    # glow on the seam between the two shots
    gx = W / 2 if not vx else (W * (1 - e) if vx < 0 else W * e)
    gy = H / 2 if not vy else (H * (1 - e) if vy < 0 else H * e)
    add_glow(ctx, gx, gy, 700, GOLD_L, 0.25 * fl)


def tr_flare(ctx, sa, sb, p, o):
    """Crossfade under a horizontal golden flare sweeping across."""
    e, fl = e_io(p), math.sin(p * math.pi)
    paint_scaled(ctx, sa, 1 + 0.04 * e)
    paint_scaled(ctx, sb, 1.04 - 0.04 * e, e)
    x, y = lerp(-300, W + 300, e), o.get("y", H * 0.4)
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_ADD)
    ctx.translate(x, y)
    ctx.scale(1, 0.05)
    g = cairo.RadialGradient(0, 0, 0, 0, 0, 1400)
    g.add_color_stop_rgba(0, *GOLD_L[:3], 0.8 * fl)
    g.add_color_stop_rgba(1, *GOLD_L[:3], 0)
    ctx.set_source(g)
    ctx.arc(0, 0, 1400, 0, 2 * math.pi)
    ctx.fill()
    ctx.restore()
    add_glow(ctx, x, y, 600, WARM, 0.35 * fl)


def tr_iris(ctx, sa, sb, p, o):
    """Next shot opens inside a growing circle (optionally from a point of interest)."""
    e = e_io(p)
    x, y = o.get("x", W / 2), o.get("y", H / 2)
    paint_scaled(ctx, sa, 1 + 0.05 * e)
    r = math.hypot(max(x, W - x), max(y, H - y)) * e
    if r > 1:
        ctx.save()
        ctx.arc(x, y, r, 0, 2 * math.pi)
        ctx.clip()
        paint_scaled(ctx, sb, 1.06 - 0.06 * e)
        ctx.restore()
        ctx.set_line_width(3)
        ctx.set_source_rgba(*GOLD_L[:3], 0.9 * (1 - e))
        ctx.arc(x, y, r, 0, 2 * math.pi)
        ctx.stroke()


def tr_blinds(ctx, sa, sb, p, o):
    """Venetian blinds: n strips open one after another."""
    n = o.get("n", 8)
    vertical = o.get("vertical", False)
    paint_scaled(ctx, sa, 1.0)
    ctx.save()
    any_ = False
    for k in range(n):
        q = e_io(prog(p, k / n * 0.5, 0.5))
        if q <= 0:
            continue
        any_ = True
        if vertical:
            sw = W / n
            ctx.rectangle(k * sw + sw * (1 - q) / 2, 0, sw * q + 1, H)
        else:
            sh = H / n
            ctx.rectangle(0, k * sh + sh * (1 - q) / 2, W, sh * q + 1)
    if any_:
        ctx.clip()
        paint_scaled(ctx, sb, 1.0)
    ctx.restore()


def tr_push(ctx, sa, sb, p, o):
    """Hard push: the new shot shoves the old one out of frame."""
    e = e_out5(p) if o.get("snap") else e_io(p)
    vx, vy = _dirvec(o.get("dir", "left"))
    paint_scaled(ctx, sa, 1.0, 1.0, dx=vx * W * e, dy=vy * H * e)
    paint_scaled(ctx, sb, 1.0, 1.0, dx=-vx * W * (1 - e), dy=-vy * H * (1 - e))
    ctx.set_source_rgba(*GOLD_L[:3], 0.9 * math.sin(p * math.pi))
    ctx.set_line_width(4)
    if vx:
        xe = W / 2 + vx * W * (e - 0.5)
        ctx.move_to(xe, 0)
        ctx.line_to(xe, H)
    else:
        ye = H / 2 + vy * H * (e - 0.5)
        ctx.move_to(0, ye)
        ctx.line_to(W, ye)
    ctx.stroke()


def tr_luma(ctx, sa, sb, p, o):
    """Soft gradient wipe at an angle."""
    e = e_io(p)
    ang = o.get("angle", 0.6)
    soft = o.get("soft", 260)
    dx, dy = math.cos(ang), math.sin(ang)
    L = abs(W * dx) + abs(H * dy)
    c = lerp(-L / 2 - soft, L / 2 + soft, e)
    g = cairo.LinearGradient(W / 2 + dx * (c - soft), H / 2 + dy * (c - soft),
                             W / 2 + dx * (c + soft), H / 2 + dy * (c + soft))
    g.add_color_stop_rgba(0, 0, 0, 0, 1)
    g.add_color_stop_rgba(1, 0, 0, 0, 0)
    paint_scaled(ctx, sa, 1.0)
    ctx.save()
    ctx.set_source_surface(sb)
    ctx.mask(g)
    ctx.restore()


def tr_glitchcut(ctx, sa, sb, p, o):
    """Cut in the middle of a glitch burst."""
    paint_scaled(ctx, sa if p < 0.5 else sb, 1.0 + 0.04 * math.sin(p * math.pi))
    glitch(ctx.get_target(), 1.2 * math.sin(p * math.pi), int(p * 1000))


def tr_spin(ctx, sa, sb, p, o):
    """Rotational zoom: out-shot spins away, in-shot spins in."""
    e, fl = e_io(p), math.sin(p * math.pi)
    ang = o.get("angle", 0.35)
    paint_scaled(ctx, sa, 1 + 0.5 * e, 1.0, rot=ang * e)
    paint_scaled(ctx, sb, 1.5 - 0.5 * e, e, rot=-ang * (1 - e))
    add_glow(ctx, W / 2, H / 2, 900, WHITE, 0.25 * fl)


def tr_heart(ctx, sa, sb, p, o):
    """Next shot opens inside a growing heart shape (from a heart already on screen)."""
    e = e_in(p) * 0.35 + e_io(p) * 0.65
    x, y, r0 = o.get("x", W / 2), o.get("y", H / 2), o.get("r", 120)
    paint_scaled(ctx, sa, 1 + 0.04 * e)
    r = lerp(r0, max(W, H) * 1.25, e)
    ctx.save()
    heart(ctx, x, y, r)
    ctx.clip()
    paint_scaled(ctx, sb, 1.0)
    ctx.restore()
    ctx.set_line_width(4)
    ctx.set_source_rgba(*o.get("color", GOLD_L)[:3], 0.9 * (1 - e))
    heart(ctx, x, y, r)
    ctx.stroke()
    add_glow(ctx, x, y, 500, o.get("color", GOLD_L), 0.35 * math.sin(p * math.pi))


TRANSITIONS = {"fade": tr_fade, "burn": tr_burn, "zoom": tr_zoom, "dissolve": tr_dissolve,
               "whip": tr_whip, "flare": tr_flare, "iris": tr_iris, "blinds": tr_blinds,
               "push": tr_push, "luma": tr_luma, "glitchcut": tr_glitchcut, "spin": tr_spin,
               "heart": tr_heart}


# --------------------------------------------------------------------------
# Compositor
# --------------------------------------------------------------------------
_GRAIN = []


def _bounds():
    return [s for s, _ in PROJECT.SCENES] + [DUR]


def render_scene(i, t):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    start, fn = PROJECT.SCENES[i]
    fn(ctx, t - start, t)
    surf.flush()
    return surf


def render_frame(t):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    bounds = _bounds()
    n = len(PROJECT.SCENES)
    idx = max(i for i in range(n) if bounds[i] <= t)
    trans = getattr(PROJECT, "TRANS", {})
    done = False
    for b in (idx, idx + 1):
        if b in trans and 0 < b < n:
            spec = trans[b]
            typ, d = spec[0], spec[1]
            opts = spec[2] if len(spec) > 2 else {}
            if d > 0 and abs(t - bounds[b]) < d / 2:
                p = clamp((t - (bounds[b] - d / 2)) / d)
                TRANSITIONS[typ](ctx, render_scene(b - 1, t), render_scene(b, t), p, opts)
                done = True
                break
    if not done:
        PROJECT.SCENES[idx][1](ctx, t - bounds[idx], t)
    overlay = getattr(PROJECT, "OVERLAY", None)
    if overlay:  # elements that live across scene cuts (timers, logos, progress)
        overlay(ctx, t)
    post = getattr(PROJECT, "POST", {})
    ga = post.get("grain", 0.10)
    if ga > 0:
        if not _GRAIN:
            _GRAIN.extend(make_grain())
        g = _GRAIN[int(t * FPS) % len(_GRAIN)]
        ctx.save()
        ctx.set_operator(cairo.OPERATOR_OVERLAY)
        ctx.scale(2, 2)
        ctx.set_source_surface(g.surf, 0, 0)
        ctx.paint_with_alpha(ga)
        ctx.restore()
    fi, fo = post.get("fade_in", 0.5), post.get("fade_out", 0.7)
    fade = max(1 - clamp(t / fi) if fi else 0, clamp((t - (DUR - fo)) / (fo * 0.86)) if fo else 0)
    if fade > 0:
        ctx.set_source_rgba(0, 0, 0, fade)
        ctx.paint()
    surf.flush()
    return surf


def encode_chunk(f0, f1, path):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgra",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
           "-crf", "17", "-pix_fmt", "yuv420p", path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(f0, f1):
        s = render_frame(f / FPS)
        p.stdin.write(bytes(s.get_data()))
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError("ffmpeg encode failed")


def load_project(path):
    """Import projects/<nom>.py so that its `import render` is THIS module."""
    global PROJECT
    sys.modules.setdefault("render", sys.modules[__name__])
    spec = importlib.util.spec_from_file_location("montaj_project", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    PROJECT = mod
    if hasattr(mod, "prepare"):
        mod.prepare()
    return mod


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    proj, src = args[0], args[1]
    load_project(proj)
    if "--preview" in args:
        k = args.index("--preview")
        outdir = os.path.join(HERE, "previews")
        os.makedirs(outdir, exist_ok=True)
        for ts in args[k + 1:]:
            s = render_frame(float(ts))
            s.write_to_png(os.path.join(outdir, f"t_{float(ts):05.2f}.png"))
        return
    if "--check" in args:
        for f in range(nframes()):
            render_frame(f / FPS)
        print("ok", nframes())
        return
    out = args[2] if len(args) > 2 and not args[2].startswith("--") else \
        os.path.join(HERE, getattr(PROJECT, "OUTPUT", "output/video_montaj.mp4"))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    total = nframes()
    workers = os.cpu_count() or 4
    tmp = tempfile.mkdtemp(prefix="montaj_")
    per = math.ceil(total / workers)
    procs, parts = [], []
    for w in range(workers):
        f0, f1 = w * per, min(total, (w + 1) * per)
        if f0 >= f1:
            break
        part = os.path.join(tmp, f"part{w:02d}.mp4")
        parts.append(part)
        pr = Process(target=encode_chunk, args=(f0, f1, part))
        pr.start()
        procs.append(pr)
    for pr in procs:
        pr.join()
    if any(pr.exitcode != 0 for pr in procs):
        sys.exit("render xatosi: kamida bitta bo'lak muvaffaqiyatsiz tugadi")
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as fh:
        fh.writelines(f"file '{p}'\n" for p in parts)
    silent = os.path.join(tmp, "video.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                    "-c", "copy", silent], check=True)
    # original audio, untouched — no sound effects added
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", silent, "-i", src,
                    "-map", "0:v:0", "-map", "1:a:0?", "-c:v", "copy", "-c:a", "copy",
                    "-movflags", "+faststart", out], check=True)
    print("tayyor:", out)


if __name__ == "__main__":
    main()
