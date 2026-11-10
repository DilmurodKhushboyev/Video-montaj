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
HANDLE = "Dilmurod_Sabriy"
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
    "anton": ("Anton-Regular.ttf", None),  # kondensat display (muqova, poster)
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


IG_GRAD = ("#feda75", "#fa7e1e", "#d62976", "#962fbf", "#4f5bd5")


def insta_icon(ctx, x, y, s, a=1.0, mono=None):
    """Instagram belgisi: gradientli yumaloq kvadrat + oq kamera konturi. (x, y) — markaz."""
    if a <= 0.003 or s <= 1:
        return
    ctx.save()
    round_rect(ctx, x - s / 2, y - s / 2, s, s, s * 0.28)
    if mono:
        ctx.set_source_rgba(*mono[:3], a)
    else:
        g = cairo.RadialGradient(x - s * 0.35, y + s * 0.6, s * 0.05, x - s * 0.35, y + s * 0.6, s * 1.45)
        for k, c in enumerate(IG_GRAD):
            g.add_color_stop_rgba(k / (len(IG_GRAD) - 1), *hx(c)[:3], a)
        ctx.set_source(g)
    ctx.fill()
    ctx.set_source_rgba(1, 1, 1, a)
    ctx.set_line_width(s * 0.075)
    round_rect(ctx, x - s * 0.31, y - s * 0.31, s * 0.62, s * 0.62, s * 0.18)
    ctx.stroke()
    ctx.arc(x, y, s * 0.15, 0, 2 * math.pi)
    ctx.stroke()
    ctx.arc(x + s * 0.175, y - s * 0.175, s * 0.042, 0, 2 * math.pi)
    ctx.fill()
    ctx.restore()


def handle(ctx, lt, t0, y=None, x=None, size=40, color=None, glow_c=None):
    """Muallif yozuvi: Instagram belgisi + HANDLE. Reels xavfsiz zonasida (y <= 1480,
    markazda — o'ngdagi tugmalar ostiga tushmaydi). Har video oxirida."""
    hp = prog(lt, t0, 1.0)
    if hp <= 0:
        return
    y = y or 1400
    x = W / 2 if x is None else x
    isz = size * 1.3
    gap = size * 0.42
    tw_ = tw(HANDLE, "semi", size, 1.5)
    x0 = x - (isz + gap + tw_) / 2
    cy = y - size * 0.36
    pe = e_back(prog(lt, t0, 0.65))
    if pe > 0:
        ctx.save()
        ctx.translate(x0 + isz / 2, cy)
        ctx.rotate(-0.5 * (1 - min(1, pe)))
        ctx.scale(pe, pe)
        add_glow(ctx, 0, 0, isz * 1.6, hx("#d62976"), 0.25 * clamp(hp * 2))
        insta_icon(ctx, 0, 0, isz, clamp(hp * 2.5))
        ctx.restore()
    text_rise(ctx, HANDLE, "semi", size, color or WHITE, x0 + isz + gap, y,
              prog(lt, t0 + 0.12, 0.9), tracking=1.5, glow=8, glow_a=0.35,
              glow_color=glow_c or GOLD)
    lp = e_io(prog(lt, t0 + 0.35, 0.8))
    if lp > 0:
        ctx.set_line_width(2)
        g = cairo.LinearGradient(x0, 0, x0 + isz + gap + tw_, 0)
        g.add_color_stop_rgba(0, *GOLD_L[:3], 0)
        g.add_color_stop_rgba(0.5, *GOLD_L[:3], 0.8)
        g.add_color_stop_rgba(1, *GOLD_L[:3], 0)
        ctx.set_source(g)
        xm = x0 + (isz + gap + tw_) / 2
        hw = (isz + gap + tw_) / 2 * lp
        ctx.move_to(xm - hw, y + size * 0.45)
        ctx.line_to(xm + hw, y + size * 0.45)
        ctx.stroke()


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
# v2 asboblar: kalit-niqob, pul yomg'iri, qalqon, tarmoq, eriydigan matn, uy,
# narx yorlig'i, chaqmoq, radial blur, yangi o'tishlar (shutter, timewarp)
# --------------------------------------------------------------------------
def sky_cutout(rgb, y1=None, lo=0.04, hi=0.14, cloud=0.80, close=5, feather=1.6, rgb_out=None):
    """Subject (not-sky) mask by colour key: blue sky (B clearly above R,G) and bright
    low-saturation clouds become transparent. Below y1 everything is kept as subject.
    Great for 'text behind the head' on sky shots where luma keys fail (skin ~ sky)."""
    x = rgb.astype(np.float32) / 255.0
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    blue = np.clip(((b - np.maximum(r, g)) - lo) / (hi - lo), 0, 1)
    lum = x @ np.array([0.299, 0.587, 0.114], np.float32)
    sat = x.max(2) - x.min(2)
    cl = np.clip((lum - cloud) / 0.08, 0, 1) * np.clip((0.22 - sat) / 0.1, 0, 1)
    sky = np.maximum(blue, cl)
    if y1 is not None:
        sky[y1:] = 0
    mi = Image.fromarray(((1 - sky) * 255).astype(np.uint8))
    if close:
        mi = mi.filter(ImageFilter.MinFilter(close)).filter(ImageFilter.MaxFilter(close))
        mi = mi.filter(ImageFilter.MaxFilter(close)).filter(ImageFilter.MinFilter(close))
    if feather:
        mi = mi.filter(ImageFilter.GaussianBlur(feather))
    return Pic(rgb if rgb_out is None else rgb_out, np.asarray(mi))


def banknote(ctx, x, y, w, rot, flip, a, color=hx("#8fd19a"), burn=0.0):
    """One banknote (flip: -1..1 -> 3D flutter around its long axis)."""
    if a <= 0.01:
        return
    h = w * 0.46
    fs = max(0.06, abs(flip))
    shade = 0.62 + 0.38 * fs
    c = lerpc(color[:3], (1.0, 0.45, 0.12), burn)
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.scale(1, fs)
    ctx.set_source_rgba(c[0] * shade, c[1] * shade, c[2] * shade, a)
    round_rect(ctx, -w / 2, -h / 2, w, h, w * 0.05)
    ctx.fill()
    ink = (c[0] * 0.35, c[1] * 0.45, c[2] * 0.35)
    ctx.set_source_rgba(*ink, a * 0.85)
    ctx.set_line_width(max(1.2, w * 0.018))
    round_rect(ctx, -w / 2 + w * 0.06, -h / 2 + h * 0.13, w * 0.88, h * 0.74, w * 0.03)
    ctx.stroke()
    ctx.arc(0, 0, h * 0.27, 0, 2 * math.pi)
    ctx.stroke()
    if flip > 0:
        text(ctx, "$", "bold", max(8, int(h * 0.42)), (*ink, 1.0), 0, h * 0.15, alpha=a * 0.9,
             align="c")
    ctx.restore()


def bills(ctx, t, seed=9, n=22, a=1.0, speed=1.0, size=130, blast=None, reach=1500):
    """Falling banknotes (money rain). blast=(x, y, q): q 0..1 since the blast —
    notes are thrown radially away from (x, y), spin and burn out."""
    xs, ys, sp, sz, ph, fr, dx = _rng_parts(seed, n)
    for i in range(n):
        v = 230 * (0.6 + sp[i] / 4) * speed
        y = (ys[i] + v * t) % (H + 320) - 160
        x = xs[i] + 70 * math.sin(t * fr[i] * 0.9 + ph[i])
        rot = 0.7 * math.sin(t * fr[i] * 1.2 + ph[i]) + dx[i] * 0.03
        flip = math.cos(t * fr[i] * 2.6 + ph[i])
        al, burn = a, 0.0
        if blast and blast[2] > 0:
            bx, by, q = blast
            ux, uy = x - bx, y - by
            d = math.hypot(ux, uy) + 1e-6
            push = e_out(q) * reach * (0.55 + sp[i] / 6) * (1.2 - min(1.0, d / 1600))
            x += ux / d * push
            y += uy / d * push
            rot += q * dx[i] * 0.5
            flip = math.cos(t * fr[i] * 9 + ph[i])
            burn = clamp(q * 2.2)
            al *= clamp(1 - q * 1.15) ** 1.3
        banknote(ctx, x, y, size * (0.72 + sz[i] / 9), rot, flip, al, burn=burn)


def hex_path(ctx, x, y, r):
    for k in range(6):
        an = math.pi / 6 + k * math.pi / 3
        px, py = x + r * math.cos(an), y + r * math.sin(an)
        if k == 0:
            ctx.move_to(px, py)
        else:
            ctx.line_to(px, py)
    ctx.close_path()


@functools.lru_cache(maxsize=None)
def _hex_grid(cx, cy, rx, ry, r):
    pts = []
    ddx, ddy = r * math.sqrt(3), r * 1.5
    nj, ni = int(ry / ddy) + 2, int(rx / ddx) + 2
    for j in range(-nj, nj + 1):
        for i in range(-ni, ni + 1):
            x = cx + i * ddx + (ddx / 2 if j % 2 else 0)
            y = cy + j * ddy
            d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
            if d <= 1.0:
                pts.append((x, y, math.sqrt(d)))
    return tuple(pts)


def hex_shield(ctx, cx, cy, rx, ry, p, t, r=36, hits=(), color=hx("#ffd98a"), a=1.0):
    """Energy dome of hexagons around a subject. p 0..1 builds it from the bottom up;
    hits = [(x, y, q)] impact ripples (q 0..1 since the impact)."""
    if p <= 0 or a <= 0:
        return
    c = color[:3]
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_ADD)
    ctx.save()
    ctx.translate(cx, cy)
    ctx.scale(rx, ry)
    g = cairo.RadialGradient(0, 0, 0.5, 0, 0, 1.0)
    g.add_color_stop_rgba(0, *c, 0)
    g.add_color_stop_rgba(0.82, *c, 0.07 * a * p)
    g.add_color_stop_rgba(1, *c, 0.24 * a * p)
    ctx.set_source(g)
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.fill()
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_line_width(3)
    ctx.set_source_rgba(*c, 0.55 * a * clamp(p * 1.5))
    ctx.stroke()
    ctx.set_line_width(2)
    for x, y, d in _hex_grid(cx, cy, rx, ry, r):
        order = (cy + ry - y) / (2 * ry)
        q = clamp((p * 1.3 - order) / 0.3)
        if q <= 0:
            continue
        fres = 0.10 + 0.90 * d ** 3
        sh = 0.5 + 0.5 * math.sin(t * 2.2 + x * 0.021 + y * 0.013)
        al = a * q * (0.06 + 0.42 * fres) * (0.55 + 0.45 * sh)
        al += a * 0.7 * math.exp(-((order - p * 1.3 + 0.15) / 0.08) ** 2) * (1 - clamp(p))
        for hx_, hy_, hq in hits:
            if 0 < hq < 1:
                ring = 1500 * e_out(hq)
                dist = math.hypot(x - hx_, y - hy_)
                al += a * 1.1 * math.exp(-((dist - ring) / 110) ** 2) * (1 - hq) ** 1.2
        if al < 0.01:
            continue
        hex_path(ctx, x, y, r * 0.9 * (0.55 + 0.45 * q))
        ctx.set_source_rgba(*c, min(1.0, al))
        ctx.stroke()
    ctx.restore()


@functools.lru_cache(maxsize=None)
def _net(seed, n, x0, y0, x1, y1, k):
    r = np.random.default_rng(seed)
    pts = np.c_[r.uniform(x0, x1, n), r.uniform(y0, y1, n)]
    edges = set()
    for i in range(n):
        d = np.hypot(*(pts - pts[i]).T)
        for j in np.argsort(d)[1:k + 1]:
            edges.add((min(i, int(j)), max(i, int(j))))
    edges = sorted(edges)
    return (pts, edges, r.uniform(0, 6.28, n), r.uniform(0.6, 1.5, n),
            r.uniform(-2.5, 2.5, len(edges)), r.uniform(0, 0.5, len(edges)))


def person_icon(ctx, x, y, s, color, a):
    ctx.set_source_rgba(*color[:3], a)
    ctx.arc(x, y - s * 0.55, s * 0.42, 0, 2 * math.pi)
    ctx.fill()
    ctx.arc(x, y + s * 0.75, s * 0.85, math.pi, 2 * math.pi)
    ctx.close_path()
    ctx.fill()


def network(ctx, lt, region, p, snap=0.0, seed=12, n=16, k=2, color=GOLD_L,
            snap_color=hx("#ff5a4f"), a=1.0, node=22):
    """'Tanish-bilish' tarmog'i: odam belgilari chiziqlar bilan bog'langan. p 0..1 chizadi;
    snap 0..1 — bog'lar uziladi (qizil chaqnash), odamlar pastga qulab so'nadi."""
    if a <= 0 or p <= 0:
        return
    pts, edges, ph, fall_, spin, delay = _net(seed, n, *region, k)
    P = []
    for i, (x, y) in enumerate(pts):
        x += 10 * math.sin(lt * 0.8 + ph[i])
        y += 8 * math.cos(lt * 0.7 + ph[i] * 1.3)
        if snap > 0:
            y += 1300 * (snap ** 2) * fall_[i]
            x += 60 * snap * math.sin(ph[i])
        P.append((x, y))
    ctx.save()
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for ei, (i, j) in enumerate(edges):
        q = clamp((p * 1.4 - delay[ei]) / 0.6)
        if q <= 0:
            continue
        (xa, ya), (xb, yb) = P[i], P[j]
        if snap <= 0:
            ctx.set_source_rgba(*color[:3], 0.55 * a)
            ctx.set_line_width(2.2)
            ctx.move_to(xa, ya)
            ctx.line_to(lerp(xa, xb, e_io(q)), lerp(ya, yb, e_io(q)))
            ctx.stroke()
            continue
        col = lerpc(snap_color[:3], color[:3], clamp(snap * 3))
        al = a * 0.9 * (1 - snap) ** 1.5
        mx, my = (xa + xb) / 2, (ya + yb) / 2
        for (ex, ey), sg in (((xa, ya), 1), ((xb, yb), -1)):
            ang = math.atan2(my - ey, mx - ex) + sg * spin[ei] * snap
            L = math.hypot(mx - ex, my - ey) * (1 - 0.35 * snap)
            ctx.set_source_rgba(*col, al)
            ctx.set_line_width(2.6)
            ctx.move_to(ex, ey)
            ctx.line_to(ex + L * math.cos(ang), ey + L * math.sin(ang))
            ctx.stroke()
        if snap < 0.25:
            add_glow(ctx, mx, my, 70, snap_color, 0.9 * (1 - snap / 0.25))
    for i, (x, y) in enumerate(P):
        q = clamp((p * 1.6 - i / len(P) * 0.6) / 0.4)
        if q <= 0:
            continue
        al = a * q * (1 - snap) ** 1.2
        glow(ctx, x, y, node * 2.4, color, 0.25 * al)
        person_icon(ctx, x, y, node * 0.6 * e_back(q) if q < 1 else node * 0.6, color, al)
    ctx.restore()


@functools.lru_cache(maxsize=300)
def _melt(s, fkey, size, color, qk, seed, drip):
    sp = sprite(s, fkey, size, color)
    hh, ww = sp.surf.get_height(), sp.surf.get_width()
    src = np.ndarray((hh, ww, 4), np.uint8, buffer=sp.buf)
    q = qk / 60.0
    r = np.random.default_rng(seed)
    noise = np.interp(np.arange(ww), np.linspace(0, ww, 14), r.uniform(0, 1, 14))
    drips = np.zeros(ww)
    for c in r.uniform(sp.pad, ww - sp.pad, max(3, ww // 70)):
        wd = r.uniform(5, 13)
        drips += r.uniform(0.8, 2.4) * np.exp(-((np.arange(ww) - c) / wd) ** 2)
    amt = (q ** 1.35) * drip * (0.12 + 0.45 * noise + drips)
    ym = sp.pad + sp.asc * 0.86  # melt only the lowest part of the glyphs -> stays readable
    extra = int(drip * 3.2) + 4
    Ho = hh + extra
    Y = np.arange(Ho, dtype=np.float32)[:, None]
    span = hh - ym
    sag = amt * 0.12
    sy = np.where(Y < ym, Y, ym + (Y - ym - sag[None, :]) / (1 + amt[None, :] / span))
    sy = np.where((Y >= ym) & (Y - sag[None, :] < ym), ym, sy)
    sy = np.clip(sy, 0, hh - 1.001)
    i0 = np.floor(sy).astype(np.int32)
    fr_ = (sy - i0)[..., None]
    cols = np.arange(ww)[None, :]
    srcf = src.astype(np.float32)
    out = srcf[i0, cols] * (1 - fr_) + srcf[i0 + 1, cols] * fr_
    out = np.ascontiguousarray(out.astype(np.uint8))
    buf = bytearray(out.tobytes())
    surf = cairo.ImageSurface.create_for_data(buf, cairo.FORMAT_ARGB32, ww, Ho, ww * 4)
    return surf, buf, sp


def melt_text(ctx, s, fkey, size, color, x, y, q, seed=3, align="c", drip=110, alpha=1.0):
    """Text that melts like ice cream: glyph bottoms stretch and drip down (q 0..1)."""
    if alpha <= 0.003:
        return
    if q <= 0.004:
        text(ctx, s, fkey, size, color, x, y, alpha=alpha, align=align)
        return
    surf, _buf, sp = _melt(s, fkey, size, color, int(round(clamp(q) * 60)), seed, drip)
    ox = x - {"l": 0, "c": sp.w / 2, "r": sp.w}[align]
    ctx.set_source_surface(surf, ox - sp.pad, y - sp.asc - sp.pad)
    ctx.paint_with_alpha(alpha)


def house_path(ctx, cx, base, w, h, roof, chimney=True):
    """House outline (walls + roof [+ chimney]) — start point bottom-left, for line drawing."""
    x0, x1 = cx - w / 2, cx + w / 2
    ctx.move_to(x0, base)
    ctx.line_to(x0, base - h)
    ctx.line_to(cx, base - h - roof)
    if chimney:
        k = 0.62
        xc = lerp(cx, x1, k)
        yc = lerp(base - h - roof, base - h, k)
        ctx.line_to(xc, yc)
        ctx.line_to(xc, yc - roof * 0.38)
        ctx.line_to(xc + w * 0.09, yc - roof * 0.38)
        ctx.line_to(xc + w * 0.09, yc + roof * 0.18 * (w * 0.09) / (w / 2) * 2)
    ctx.line_to(x1, base - h)
    ctx.line_to(x1, base)
    ctx.close_path()


def price_tag(ctx, x, y, w, rot, level, a, color=GOLD_L, ink=(0.16, 0.11, 0.04), string=120):
    """Hanging price tag swinging from (x, y). level = number of '$' (fractional fades in)."""
    if a <= 0.01:
        return
    h = w * 1.45
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.set_source_rgba(*color[:3], 0.8 * a)
    ctx.set_line_width(2)
    ctx.move_to(0, 0)
    ctx.line_to(0, string)
    ctx.stroke()
    ty = string - w * 0.12
    ctx.move_to(-w * 0.22, ty)
    ctx.line_to(w * 0.22, ty)
    ctx.line_to(w / 2, ty + w * 0.3)
    ctx.line_to(w / 2, ty + h)
    ctx.line_to(-w / 2, ty + h)
    ctx.line_to(-w / 2, ty + w * 0.3)
    ctx.close_path()
    g = cairo.LinearGradient(-w / 2, ty, w / 2, ty + h)
    g.add_color_stop_rgba(0, *lerpc(color[:3], (1, 1, 1), 0.35), a)
    g.add_color_stop_rgba(1, *color[:3], a)
    ctx.set_source(g)
    ctx.fill()
    ctx.set_source_rgba(*ink, a)
    ctx.arc(0, string + w * 0.02, w * 0.07, 0, 2 * math.pi)
    ctx.fill()
    n = int(level)
    fr_ = level - n
    sz = int(w * 0.36)
    for k in range(min(4, n + (1 if fr_ > 0.02 else 0))):
        al = 1.0 if k < n else fr_
        sc = 1.0 if k < n else e_back(fr_) if fr_ > 1e-3 else 0
        if sc > 0:
            text(ctx, "$", "black", sz, (*ink, 1), 0, ty + w * 0.62 + k * sz * 0.86, alpha=a * al,
                 align="c", scale=sc)
    ctx.restore()


def lightning(ctx, x0, y0, x1, y1, a, seed=1, width=4, color=hx("#e6eeff"), branches=3, jag=0.22):
    """Branching lightning bolt (midpoint displacement)."""
    if a <= 0.01:
        return
    r = np.random.default_rng(seed)

    def bolt(xa, ya, xb, yb, depth, out):
        if depth == 0:
            out.append((xb, yb))
            return
        L = math.hypot(xb - xa, yb - ya)
        mx = (xa + xb) / 2 + r.normal(0, L * jag) * (yb - ya) / (L + 1e-6)
        my = (ya + yb) / 2 - r.normal(0, L * jag) * (xb - xa) / (L + 1e-6)
        bolt(xa, ya, mx, my, depth - 1, out)
        bolt(mx, my, xb, yb, depth - 1, out)

    paths = []
    main = [(x0, y0)]
    bolt(x0, y0, x1, y1, 6, main)
    paths.append((main, 1.0))
    for _ in range(branches):
        i = int(r.integers(len(main) // 5, len(main) * 3 // 4))
        bx, by = main[i]
        ang = math.atan2(y1 - y0, x1 - x0) + r.choice([-1, 1]) * r.uniform(0.4, 0.9)
        Lb = math.hypot(x1 - x0, y1 - y0) * r.uniform(0.18, 0.35)
        br = [(bx, by)]
        bolt(bx, by, bx + Lb * math.cos(ang), by + Lb * math.sin(ang), 4, br)
        paths.append((br, 0.55))
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_ADD)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    for pts, k in paths:
        for lw, al in ((width * 7, 0.10), (width * 3, 0.25), (width, 1.0)):
            ctx.set_line_width(lw * k)
            ctx.set_source_rgba(*color[:3], a * al * k)
            ctx.move_to(*pts[0])
            for px, py in pts[1:]:
                ctx.line_to(px, py)
            ctx.stroke()
    ctx.restore()


def zoom_blur(ctx, surf, s0, s1, alpha=1.0, n=12, cx=None, cy=None, rot0=0.0, rot1=0.0):
    """Paint a full-frame surface with radial (zoom) motion blur spanning scales s0..s1."""
    if alpha <= 0.003:
        return
    cx = W / 2 if cx is None else cx
    cy = H / 2 if cy is None else cy
    ctx.push_group()
    for k in range(n):
        f = k / max(1, n - 1)
        s = lerp(s0, s1, f)
        ctx.save()
        ctx.translate(cx, cy)
        ctx.rotate(lerp(rot0, rot1, f))
        ctx.scale(s, s)
        ctx.translate(-cx, -cy)
        ctx.set_source_surface(surf)
        ctx.paint_with_alpha(1.0 / (k + 1))
        ctx.restore()
    ctx.pop_group_to_source()
    ctx.paint_with_alpha(alpha)


def shutter(ctx, yb, a=1.0, slat=44, tint_=(0.42, 0.45, 0.50)):
    """Metal roller shutter whose bottom edge is at yb (covers 0..yb)."""
    if yb <= 0:
        return
    c = tint_
    ctx.save()
    k = 0
    y = yb - 30
    while y > -slat:
        g = cairo.LinearGradient(0, y - slat, 0, y)
        g.add_color_stop_rgba(0, *(v * 1.25 for v in c), a)
        g.add_color_stop_rgba(0.45, *c, a)
        g.add_color_stop_rgba(0.9, *(v * 0.55 for v in c), a)
        g.add_color_stop_rgba(1, *(v * 0.25 for v in c), a)
        ctx.set_source(g)
        ctx.rectangle(0, y - slat, W, slat)
        ctx.fill()
        y -= slat
        k += 1
    g = cairo.LinearGradient(0, yb - 30, 0, yb)
    g.add_color_stop_rgba(0, 0.30, 0.31, 0.33, a)
    g.add_color_stop_rgba(0.3, 0.62, 0.64, 0.68, a)
    g.add_color_stop_rgba(1, 0.16, 0.16, 0.18, a)
    ctx.set_source(g)
    ctx.rectangle(0, yb - 30, W, 30)
    ctx.fill()
    for hx0 in (W * 0.3, W * 0.7):
        ctx.set_source_rgba(0.08, 0.08, 0.09, a)
        round_rect(ctx, hx0 - 50, yb - 22, 100, 12, 6)
        ctx.fill()
    g = cairo.LinearGradient(0, yb, 0, yb + 80)
    g.add_color_stop_rgba(0, 0, 0, 0, 0.55 * a)
    g.add_color_stop_rgba(1, 0, 0, 0, 0)
    ctx.set_source(g)
    ctx.rectangle(0, yb, W, 80)
    ctx.fill()
    ctx.restore()


def tr_shutter(ctx, sa, sb, p, o):
    """Shop shutter slams down over the old shot (the market closes), holds, then rolls
    up revealing the new one. o: hold (fraction of p kept closed)."""
    hold = o.get("hold", 0.12)
    p_dn = 0.5 - hold / 2
    p_up = 0.5 + hold / 2
    shake = 0.0
    if p_dn <= p < p_dn + 0.12:
        q = (p - p_dn) / 0.12
        shake = 16 * math.sin(q * 30) * (1 - q)
    ctx.save()
    ctx.translate(0, shake)
    if p < p_up:
        paint_scaled(ctx, sa, 1.0)
        yb = H * min(1.0, (p / p_dn) ** 2.2) if p < p_dn else H + 2
        shutter(ctx, yb)
        if p >= p_dn:
            q = (p - p_dn) / (p_up - p_dn + 1e-6)
            dust(ctx, q * 3, (0.8, 0.8, 0.8, 1), seed=88, n=30, a=0.4 * (1 - q), speed=8)
    else:
        q = (p - p_up) / (1 - p_up)
        paint_scaled(ctx, sb, 1.0 + 0.04 * (1 - e_out(q)))
        shutter(ctx, H * (1 - e_io(q)) + 2)
    ctx.restore()


def tr_timewarp(ctx, sa, sb, p, o):
    """Time jump: zoom-blur tunnel + twist into the next shot, warm/white bloom in the
    middle. o: x, y (focus, e.g. matching faces), twist (radians), color."""
    e, fl = e_io(p), math.sin(p * math.pi)
    cx, cy = o.get("x", W / 2), o.get("y", H / 2)
    tw_ = o.get("twist", 0.25)
    zoom_blur(ctx, sa, 1 + 0.9 * e, 1 + 0.9 * e + 0.45 * fl, 1.0, 12, cx, cy, tw_ * e, tw_ * e + 0.08 * fl)
    zoom_blur(ctx, sb, 0.55 + 0.45 * e, 0.55 + 0.45 * e + 0.4 * fl, e, 12, cx, cy,
              -tw_ * (1 - e), -tw_ * (1 - e) + 0.08 * fl)
    add_glow(ctx, cx, cy, 900, o.get("color", WARM), 0.35 * fl ** 2)
    add_glow(ctx, cx, cy, 300, WHITE, 0.3 * fl ** 4)


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


TRANSITIONS = {"fade": tr_fade, "burn": tr_burn, "zoom": tr_zoom, "dissolve": tr_dissolve,
               "whip": tr_whip, "flare": tr_flare, "iris": tr_iris, "blinds": tr_blinds,
               "push": tr_push, "luma": tr_luma, "glitchcut": tr_glitchcut, "spin": tr_spin,
               "shutter": tr_shutter, "timewarp": tr_timewarp}


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
