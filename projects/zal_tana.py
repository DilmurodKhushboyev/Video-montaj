"""
zal_tana — "Chiroyli va mushakdor tanani pulga sotib ololmaysiz..."

12 ta rasm (kollajdan ajratilgan, 4x waifu2x) + ovoz yozuvi (+11.7 dB) + fon musiqasi
(Manasha Over (Slowed), 37.01 s dan; "Eng muhimi" so'zi musiqa zarbasiga tushadi).
Matn — so'zma-so'z ovozga bog'langan (tools/align_words.py -> zal_tana_words.json).

Rang hikoyasi: sovuq bozor (po'lat-ko'k) -> zal (qahrabo) -> o'zgarish (oltin) ->
oila (bo'ron ichida iliq qalqon) -> quyosh botishi -> ko'zgu (yakun).
"""
import json
import math
import os

import render as R

R.configure(size=(1080, 1920), fps=30, dur=47.0)
from render import *  # noqa: F401,F403,E402

OUTPUT = "output/zal_tana.mp4"
POST = {"grain": 0.07, "fade_in": 0.12, "fade_out": 0.7}
HERE_P = os.path.dirname(os.path.abspath(__file__))
WORDS = json.load(open(os.path.join(HERE_P, "zal_tana_words.json"), encoding="utf-8"))

P = {}
TOP = {}

COLD = hx("#3d6788")
STEEL = hx("#9fb6cc")
ICE = (hx("#ffc6d6"), hx("#fff0cf"), hx("#bff3df"))
RED = hx("#ff5a3c")
GOLD2 = (hx("#fff1c9"), hx("#f2c25c"))


def seg(i, a=0, b=None):
    return [w for w in WORDS if w["seg"] == i][a:b]


# ---------------------------------------------------------------------------
# preparation
# ---------------------------------------------------------------------------
def _top_color(rgb, rows=6):
    return tuple(float(v) / 255 for v in rgb[:rows].reshape(-1, 3).mean(0)) + (1.0,)


def prepare():
    L = {k: load_rgb(f"zal/p{k:02d}.png") for k in range(12)}
    P["p00c"] = Pic(grade(L[0], sat=0.55, gain=(0.90, 0.97, 1.08), contrast=1.06))
    P["p01"] = Pic(grade(L[1], sat=1.0, contrast=1.06))
    P["p01g"] = Pic(grade(L[1], sat=0.18, gain=(0.86, 0.92, 1.0), contrast=0.95, gamma=1.1))
    P["p02"] = Pic(grade(L[2], sat=1.0, contrast=1.05))
    P["p02w"] = Pic(grade(L[2], sat=1.05, gain=(1.08, 1.0, 0.88), contrast=1.08))
    P["p02d"] = Pic(grade(L[2], sat=0.25, gain=(0.55, 0.58, 0.62)))
    P["p03"] = Pic(grade(L[3], sat=0.85, gain=(0.95, 1.0, 1.06), contrast=1.08))
    P["p03b"] = Pic(blurred(L[3], 34, 0.25, 0.42))
    P["p04"] = Pic(grade(L[4], sat=1.08, contrast=1.04))
    cut = sky_cutout(grade(L[4], sat=1.08, contrast=1.04), y1=760)
    a = cut.arr[..., 3].copy()
    a[:600, :430] = 0
    a[:600, 1120:] = 0
    P["p04cut"] = Pic(grade(L[4], sat=1.08, contrast=1.04), a)
    TOP["p04"] = _top_color(grade(L[4], sat=1.08, contrast=1.04))
    P["p05"] = Pic(grade(L[5], sat=1.05, gain=(1.04, 1.0, 0.94), contrast=1.04))
    P["p05b"] = Pic(blurred(L[5], 40, 0.25, 0.45))
    P["p06s"] = Pic(grade(L[6], sat=0.35, gain=(0.70, 0.78, 0.95), contrast=1.12))
    P["p06w"] = Pic(grade(L[6], sat=1.1, gain=(1.10, 1.0, 0.86), contrast=1.05))
    P["p06b"] = Pic(blurred(grade(L[6], sat=0.3, gain=(0.6, 0.68, 0.85)), 40, 0.25, 0.6))
    P["p07"] = Pic(grade(L[7], sat=1.08, gain=(1.05, 1.0, 0.92), contrast=1.04))
    P["p08"] = Pic(grade(L[8], sat=1.0, gain=(1.04, 1.02, 0.96), contrast=1.04))
    P["p08b"] = Pic(blurred(L[8], 30, 0.25, 0.8))
    P["p09"] = Pic(grade(L[9], sat=0.9, gain=(1.06, 0.98, 0.9), contrast=1.1))
    P["p09b"] = Pic(blurred(grade(L[9], sat=0.9, gain=(1.06, 0.98, 0.9), contrast=1.1), 18, 0.5))
    P["p10"] = Pic(grade(L[10], sat=1.08, contrast=1.05))
    TOP["p10"] = _top_color(grade(L[10], sat=1.08, contrast=1.05))
    P["p11"] = Pic(grade(L[11], sat=0.92, gain=(0.98, 1.0, 1.04), contrast=1.06))
    P["p11b"] = Pic(blurred(grade(L[11], sat=0.92, gain=(0.98, 1.0, 1.04), contrast=1.06), 9, 0.5))


def paint_blur(ctx, pic, s, tx, ty, alpha=1.0, f=0.5):
    """Draw a blurred() copy that was made at scale f."""
    paint_pic(ctx, pic, s / f, tx, ty, alpha)


# ---------------------------------------------------------------------------
# kinetic captions (word timings from the voice)
# ---------------------------------------------------------------------------
def _anim(kind, p, size):
    """-> (dy, scale, alpha, blur_alpha)"""
    if kind == "rise":
        e = e_out5(p)
        return (1 - e) * size * 0.9, 1.0, clamp(p * 2.5), 0.0
    if kind == "blur":
        e = e_out(p)
        return (1 - e) * 22, 1.0, e ** 1.6, (1 - e) * 0.9
    if kind == "pop":
        return 0.0, (e_back(p, 0.9) if p < 1 else 1.0), clamp(p * 3), 0.0
    if kind == "slam":
        return 0.0, 1 + 0.5 * (1 - e_expo(p)), clamp(p * 5), 0.0
    if kind == "drop":
        return -(1 - e_out(p)) * 70, 1.0, clamp(p * 2), 0.0
    if kind == "lift":
        return (1 - e_back(p)) * 90 if p > 0 else 90, 1.0, clamp(p * 3), 0.0
    return 0.0, 1.0, 1.0, 0.0


def row(ctx, t, parts, x, y, align="c", maxw=870, lead=0.06, alpha=1.0):
    """parts: list of (words, fkey, size, opts). opts: color, anim, dur, hl, grad, glow,
    glow_a, glow_color, shadow, tracking. Lays the words out in one line; each word
    appears when it is spoken. Returns list of (word, x0, x1)."""
    sizes = [p[2] for p in parts]
    total = 0

    def measure(k):
        tot, items = 0, []
        for (words, fkey, _sz, opts), sz in zip(parts, sizes):
            sz = int(sz * k)
            tr = opts.get("tracking", 0.0)
            spc = font(fkey, sz).getlength(" ") * 1.3
            for w in words:
                wd = tw(w["w"], fkey, sz, tr)
                items.append((w, fkey, sz, opts, wd, spc))
                tot += wd + spc
        return tot - (items[-1][5] if items else 0), items

    k = 1.0
    total, items = measure(k)
    while total > maxw and k > 0.3:
        k *= 0.97
        total, items = measure(k)
    xx = x - {"l": 0, "c": total / 2, "r": total}[align]
    out = []
    for w, fkey, sz, opts, wd, spc in items:
        cx = xx + wd / 2
        p = prog(t, w["s"] - lead, opts.get("dur", 0.5))
        out.append((w, xx, xx + wd, sz))
        if p > 0:
            kind = opts.get("anim", "rise")
            dy, sc, a, ba = _anim(kind, p, sz)
            a *= alpha * opts.get("alpha", 1.0)
            col = opts.get("color", WHITE)
            kw = {k_: opts[k_] for k_ in ("grad", "glow", "glow_a", "glow_color", "shadow", "tracking")
                  if k_ in opts}
            if kind == "rise":
                ctx.save()
                ctx.rectangle(cx - wd / 2 - sz, y - sz * 1.15, wd + 2 * sz, sz * 1.55)
                ctx.clip()
            if ba > 0:
                g = sprite(w["w"], fkey, sz, col, kw.get("tracking", 0.0), kw.get("grad"), 10)
                draw_sprite(ctx, g, cx, y + dy, alpha * ba, sc, "c")
            text(ctx, w["w"], fkey, sz, col, cx, y + dy, alpha=a, align="c", scale=sc, **kw)
            hl = opts.get("hl")
            if hl:
                act = clamp((t - w["s"] + lead) / 0.08) * clamp(1 - (t - w["e"]) / 0.45)
                if act > 0:
                    text(ctx, w["w"], fkey, sz, hl, cx, y + dy, alpha=a * act, align="c", scale=sc,
                         tracking=kw.get("tracking", 0.0))
            if kind == "rise":
                ctx.restore()
        xx += wd + spc
    return out


def line(ctx, t, words, x, y, fkey, size, align="c", maxw=870, alpha=1.0, **opts):
    return row(ctx, t, [(words, fkey, size, opts)], x, y, align, maxw, alpha=alpha)


def hits_env(t, hits, tau=0.16):
    v = 0.0
    for h in hits:
        if t >= h:
            v += math.exp(-(t - h) / tau)
    return v


def shake(t, hits, amp=14, tau=0.18):
    v = 0.0
    for h in hits:
        if t >= h:
            v += amp * math.exp(-(t - h) / tau) * math.sin((t - h) * 70)
    return v


# ---------------------------------------------------------------------------
# A. HOOK — pul yomg'iri tanaga tegib portlab ketadi (0.00 – 3.05)
# ---------------------------------------------------------------------------
def sA(ctx, lt, t):
    pic = P["p01"]
    punch = 0.07 * hits_env(t, (0.72,), 0.2) + 0.045 * hits_env(t, (1.13,), 0.2) \
        + 0.06 * hits_env(t, (2.10,), 0.25)
    z = 1.17 - 0.13 * e_out(prog(t, 0, 3.0)) + punch
    s, tx, ty = cam_cover(pic, 1320, 640, z, 600, 900)
    ctx.save()
    ctx.translate(0, shake(t, (2.10,), 12))
    paint_pic(ctx, pic, s, tx, ty)
    tint(ctx, COLD, 0.30, cairo.OPERATOR_SOFT_LIGHT)
    bx, by = tx + 1310 * s, ty + 760 * s
    add_glow(ctx, bx + 60, by - 380, 520, WARM, 0.10 + 0.05 * math.sin(t * 3))
    q = prog(t, 2.10, 0.95)
    bills(ctx, t, seed=31, n=24, a=1.0, speed=1.1, size=150, blast=(bx, by, q))
    if q > 0:
        shockwave(ctx, bx, by, q, GOLD_L, 1150, 6)
        shockwave(ctx, bx, by, clamp(q * 1.4), WARM, 700, 3)
        sparks(ctx, bx, by, q, seed=4, n=40, color=GOLD_L, reach=700)
        add_glow(ctx, bx, by, 700, WARM, 0.55 * (1 - q) ** 2)
    for hb in (0.72, 1.13):
        add_glow(ctx, bx, by - 300, 900, WHITE, 0.16 * bump(t, hb - 0.03, 0.25))
    ctx.restore()
    vgrad(ctx, 960, 1560, 0, 0.86)
    vgrad(ctx, 380, 0, 0, 0.45)
    flash(ctx, 0.55 * (1 - prog(t, 2.10, 0.22)) if t >= 2.10 else 0, hx("#fff3dc"))
    line(ctx, t, seg(0, 0, 3), 540, 1130, "xbold", 68, anim="blur", shadow=14, hl=GOLD_L)
    line(ctx, t, seg(0, 3, 4), 540, 1290, "serif_it_b", 158, anim="pop", color=GOLD_L, grad=GG,
         glow=20, glow_a=0.45, glow_color=AMBER, shadow=16)
    row(ctx, t, [(seg(0, 4, 6), "xbold", 70, {"anim": "rise", "shadow": 14}),
                 (seg(0, 6, 7), "black", 76, {"anim": "slam", "color": RED, "glow": 16,
                                              "glow_a": 0.7, "glow_color": hx("#ff3b1f"),
                                              "shadow": 14})], 540, 1418)


# ---------------------------------------------------------------------------
# B. "Bu borada bozor tugaydi." — sovuq do'kon, matn futbolkaga bosilgan (3.05 – 4.62)
# ---------------------------------------------------------------------------
def sB(ctx, lt, t):
    pic = P["p00c"]
    z = 1.0 + 0.06 * e_io(prog(lt, 0, 1.9))
    s, tx, ty = cam_cover(pic, 900, 430, z, 540, 560)
    paint_pic(ctx, pic, s, tx, ty)
    for (x, y, w, ph, lvl) in ((70, 225, 60, 0.0, 3), (1010, 330, 56, 1.9, 2), (60, 700, 50, 3.1, 4)):
        rot = 0.22 * math.sin(t * 2.3 + ph)
        price_tag(ctx, x, y, w, rot, lvl, 0.92, color=hx("#d8e8f6"), ink=(0.10, 0.14, 0.2), string=110)
    vgrad(ctx, 360, 0, 0, 0.5)
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_MULTIPLY)
    line(ctx, t, seg(1, 0, 2), 540, 1222, "bold", 58, color=hx("#33343d"), anim="rise")
    line(ctx, t, seg(1, 2, 3), 540, 1388, "black", 200, color=hx("#1d1e26"), anim="slam", tracking=-4)
    line(ctx, t, seg(1, 3, 4), 540, 1468, "xbold", 64, color=hx("#7a1b10"), anim="rise", tracking=6)
    ctx.restore()


# ---------------------------------------------------------------------------
# C. Arzon / qimmat — split-screen, narx yorliqlari (4.62 – 10.55)
# ---------------------------------------------------------------------------
def sC(ctx, lt, t):
    ph2 = e_io(prog(t, 7.42, 0.6))
    seam = lerp(1010, 905, ph2)
    gap = 120
    top = (0, 0, W, seam - gap)
    bot = (0, seam + gap, W, H)
    ctx.set_source_rgba(0.03, 0.03, 0.035, 1)
    ctx.paint()
    # top: trained body in a plain black tee
    ctx.save()
    ctx.rectangle(*top[:2], W, top[3])
    ctx.clip()
    s, tx, ty = cam_cover(P["p02w"], 800, 700, 1.06 + 0.05 * lt / 6, 560, top[3] * 0.52, box=top)
    paint_pic(ctx, P["p02w"], s, tx, ty)
    paint_pic(ctx, P["p02d"], s, tx, ty, 0.8 * ph2)
    add_glow(ctx, 760, top[3] * 0.4, 600, WARM, 0.18 * (1 - ph2) * (0.8 + 0.2 * math.sin(t * 4)))
    lvl = 1 + 3 * e_out(prog(t, 6.88, 0.7))
    sw = 0.32 * math.sin((t - 6.88) * 6) * math.exp(-max(0, t - 6.88) * 1.5) if t > 6.88 else \
        0.08 * math.sin(t * 2)
    price_tag(ctx, 150, 225, 88, sw, lvl, 1.0 - 0.5 * ph2, color=GOLD_L, string=110)
    ctx.restore()
    # bottom: untrained body
    ctx.save()
    ctx.rectangle(0, bot[1], W, H - bot[1])
    ctx.clip()
    s, tx, ty = cam_cover(P["p01"], 470, 560, 2.3 + 0.06 * lt / 6, 540, (bot[1] + H) / 2 - 140, box=bot)
    paint_pic(ctx, P["p01"], s, tx, ty)
    paint_pic(ctx, P["p01g"], s, tx, ty, 0.35 + 0.65 * ph2)
    ctx.set_source_rgba(0, 0, 0, 0.55 * (1 - ph2))
    ctx.paint()
    if ph2 > 0:
        lvl2 = 4 - 3 * e_out(prog(t, 9.42, 0.7))
        sw2 = 0.4 * math.sin((t - 9.42) * 5) * math.exp(-max(0, t - 9.42) * 1.2) if t > 9.42 else \
            0.06 * math.sin(t * 2.4)
        price_tag(ctx, 150, bot[1] + 20, 80, sw2, lvl2, ph2, color=hx("#b8bec6"),
                  ink=(0.12, 0.13, 0.15), string=90)
    ctx.restore()
    # seam band edges
    for yy in (top[3], bot[1]):
        ctx.set_source_rgba(*GOLD[:3], 0.55)
        ctx.rectangle(0, yy - 1, W, 2)
        ctx.fill()
    a1 = 1 - prog(t, 7.40, 0.25)
    if a1 > 0:
        line(ctx, t, seg(2, 0, 4), 540, seam - 26, "semi", 60, anim="blur", alpha=a1)
        row(ctx, t, [(seg(2, 4, 5), "semi", 60, {"anim": "blur"}),
                     (seg(2, 5, 6), "serif_it_b", 104, {"anim": "pop", "color": GOLD_L, "grad": GG,
                                                        "glow": 14, "glow_a": 0.5})],
            540, seam + 78, alpha=a1)
    line(ctx, t, seg(3, 0, 4), 540, seam - 26, "semi", 60, anim="blur")
    row(ctx, t, [(seg(3, 4, 5), "semi", 60, {"anim": "blur"}),
                 (seg(3, 5, 6), "serif_it_b", 100, {"anim": "drop", "color": hx("#aeb4bd")}),
                 (seg(3, 6, 7), "semi", 60, {"anim": "blur"})], 540, seam + 78)
    if t > 9.6:
        lay = row(ctx, -1, [(seg(3, 4, 5), "semi", 60, {}),
                            (seg(3, 5, 6), "serif_it_b", 100, {}),
                            (seg(3, 6, 7), "semi", 60, {})], 540, seam + 78)
        _, x0, x1, _sz = lay[1]
        strike(ctx, x0 - 6, x1 + 6, seam + 50, prog(t, 9.6, 0.4), color=hx("#d9dde3"), width=5)


# ---------------------------------------------------------------------------
# D. "Zal bu tanish-bilish ishlamaydigan joy." — tanishlar tarmog'i uziladi (10.55 – 13.20)
# ---------------------------------------------------------------------------
SNAP = 11.98


def sD(ctx, lt, t):
    pic = P["p09"]
    fx = lerp(560, 860, e_io(prog(lt, 0, 2.7)))
    s, tx, ty = cam_cover(pic, fx, 520, 1.0 + 0.07 * lt / 2.7, 540, 1010)
    rack = 1 - e_io(prog(t, 12.55, 0.45))
    paint_pic(ctx, pic, s, tx, ty)
    paint_blur(ctx, P["p09b"], s, tx, ty, 0.9 * rack)
    tint(ctx, hx("#ff9a3c"), 0.16, cairo.OPERATOR_SOFT_LIGHT)
    vgrad(ctx, 980, 120, 0, 0.62)
    vgrad(ctx, 1000, 1560, 0, 0.7)
    sn = prog(t, SNAP, 1.0)
    network(ctx, lt, (120, 280, 960, 860), e_out(prog(t, 11.10, 0.7)), snap=sn, seed=14, n=14, k=2,
            color=GOLD_L, a=1.0, node=34)
    jp = prog(t, 12.70, 0.6)
    if jp > 0:
        add_glow(ctx, tx + 820 * s, ty + 520 * s, 520, WARM, 0.35 * bump(t, 12.65, 1.2))
    line(ctx, t, seg(4, 0, 1), 96, 1075, "black", 230, align="l", anim="slam", shadow=18)
    lay = row(ctx, t, [(seg(4, 1, 2), "semi", 66, {"anim": "rise"}),
                       (seg(4, 2, 3), "xbold", 84, {"anim": "rise", "color": GOLD_L})],
              96, 1190, align="l")
    if t > SNAP:
        _, x0, x1, _sz = lay[1]
        strike(ctx, x0 - 4, x1 + 6, 1163, prog(t, SNAP, 0.3), color=RED, width=7)
    w5 = seg(4, 3, 4)[0]
    if t > w5["s"] - 0.06:
        amt = 0.9 * bump(t, SNAP - 0.05, 0.6)
        p = prog(t, w5["s"] - 0.06, 0.4)
        x_ = 96 + tw(w5["w"], "xbold", 84) / 2
        if amt > 0.02:
            glitch_text(ctx, w5["w"], "xbold", 84, x_, 1295, clamp(p * 3), amt, t)
        else:
            text(ctx, w5["w"], "xbold", 84, WHITE, x_, 1295 + (1 - e_out(p)) * 30, alpha=clamp(p * 3),
                 align="c", shadow=12)
    line(ctx, t, seg(4, 4, 5), 96, 1432, "serif_it_b", 120, align="l", anim="pop", color=GOLD_L,
         grad=GG, glow=16, glow_a=0.5)
    if 0 < sn < 0.35:
        glitch(ctx.get_target(), 0.8 * (1 - sn / 0.35), int(t * 100))


# ---------------------------------------------------------------------------
# E. "Shtanga kimligingizni emas, mehnat va intizomingizni so'raydi." (13.20 – 17.08)
# ---------------------------------------------------------------------------
def sE(ctx, lt, t):
    pic = P["p03"]
    reps = [w["s"] for w in seg(6)]
    lift = 0.0
    for r_ in reps:
        if t >= r_ - 0.05:
            d = t - r_ + 0.05
            lift += 30 * (e_out(clamp(d / 0.18)) if d < 0.18 else math.exp(-(d - 0.18) / 0.35))
    s = 0.86 + 0.025 * lt / 3.9
    by = 548 - lift * 0.5
    s_bg, tbx, tby = cam_cover(P["p03b"], P["p03b"].w / 2, P["p03b"].h * 0.4, 1.05)
    paint_pic(ctx, P["p03b"], s_bg, tbx, tby)
    tx, ty = 540 - 800 * s, by - 120 * s
    paint_pic(ctx, pic, s, tx, ty)
    for y0, y1, a0 in ((ty, ty + 140, 0.95), (ty + pic.h * s, ty + pic.h * s - 170, 0.95)):
        g = cairo.LinearGradient(0, y0, 0, y1)
        g.add_color_stop_rgba(0, 0.02, 0.025, 0.03, a0)
        g.add_color_stop_rgba(1, 0.02, 0.025, 0.03, 0)
        ctx.set_source(g)
        ctx.rectangle(0, min(y0, y1), W, abs(y1 - y0))
        ctx.fill()
    ctx.set_source_rgba(0.02, 0.025, 0.03, 0.96)
    ctx.rectangle(0, 0, W, ty + 2)
    ctx.fill()
    yb = ty + pic.h * s
    ctx.rectangle(0, yb - 2, W, H)
    ctx.fill()
    god_rays(ctx, t, 540, -160, 0.10, STEEL, n=7, seed=9, ang0=1.25, ang1=1.9, length=2200)
    dust(ctx, t, (1, 1, 1, 1), seed=21, n=40, a=0.35, speed=0.6, size=0.9)
    gx = lerp(-200, W + 200, e_io(prog(t, 13.40, 0.9)))
    gy = ty + lerp(140, 75, clamp((gx - tx) / (pic.w * s))) * s
    add_glow(ctx, gx, gy, 160, GOLD_L, 0.8 * bump(t, 13.40, 0.9))
    line(ctx, t, seg(5, 0, 1), 540, 330, "black", 150, anim="slam", shadow=16, tracking=2)
    lay = line(ctx, t, seg(5, 1, 3), 540, 432, "semi", 62, anim="blur", color=STEEL)
    if t > 14.40:
        _, x0, x1, _sz = lay[0]
        strike(ctx, x0 - 6, x1 + 6, 412, prog(t, 14.40, 0.35), color=RED, width=6)
    line(ctx, t, seg(6, 0, 1), 540, 1215, "serif_it_b", 128, anim="lift", color=GOLD_L, grad=GG,
         glow=16, glow_a=0.45, dur=0.6)
    line(ctx, t, seg(6, 1, 3), 540, 1330, "black", 96, anim="lift", dur=0.6, shadow=14)
    line(ctx, t, seg(6, 3, 4), 540, 1430, "semi", 66, anim="lift", dur=0.6, color=WHITE, shadow=10)


# ---------------------------------------------------------------------------
# F. "Tana o'zgarsa," — oltin chiziq tanani (va matnni) o'zgartiradi (17.08 – 17.95)
# ---------------------------------------------------------------------------
LINE_T = (17.36, 0.55)
SLANT = -0.085


def _left_of(ctx, xc):
    """Path: everything left of the slanted light line through (xc, H/2)."""
    k = math.tan(SLANT)
    ctx.move_to(-50, -50)
    ctx.line_to(xc + k * (-50 - H / 2), -50)
    ctx.line_to(xc + k * (H + 50 - H / 2), H + 50)
    ctx.line_to(-50, H + 50)
    ctx.close_path()


def sF(ctx, lt, t):
    pic = P["p01"]
    s = 1.441 * (1.03 + 0.03 * lt)
    ty = -30
    txa = 540 - 560 * s
    txb = max(W - pic.w * s, min(0, 540 - 1310 * s))
    e = e_io(prog(t, *LINE_T))
    xc = lerp(W + 180, -180, e)
    paint_pic(ctx, pic, s, txb, ty)
    add_glow(ctx, xc + 260, 700, 700, WARM, 0.18 * e)
    ctx.save()
    _left_of(ctx, xc)
    ctx.clip()
    paint_pic(ctx, pic, s, txa, ty)
    ctx.restore()
    vgrad(ctx, 1080, 1600, 0, 0.75)
    words = seg(7, 0, 2)
    # text: thin outline (before) on the right, solid gold (after) on the left of the line
    lay = row(ctx, -1, [(words, "black", 124, {})], 540, 1400)
    sz = lay[0][3]
    for w, x0, x1, _ in lay:
        p = prog(t, w["s"] - 0.06, 0.4)
        if p <= 0:
            continue
        cx = (x0 + x1) / 2
        dy = (1 - e_out5(p)) * 40
        al = clamp(p * 3)
        ctx.save()
        _left_of(ctx, xc)
        ctx.clip()
        outline_text(ctx, w["w"], "black", sz, WHITE, cx, 1400 + dy, alpha=al * 0.9, align="c", width=2)
        ctx.restore()
        ctx.save()
        ctx.rectangle(-50, -50, W + 100, H + 100)
        _left_of(ctx, xc)
        ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        ctx.clip()
        text(ctx, w["w"], "black", sz, GOLD_L, cx, 1400 + dy, alpha=al, align="c", grad=GG, glow=18,
             glow_a=0.5, shadow=12)
        ctx.restore()
    if 0 < e < 1:
        x_top = xc + math.tan(SLANT) * (-H / 2)
        x_bot = xc + math.tan(SLANT) * (H / 2)
        ctx.save()
        ctx.set_operator(cairo.OPERATOR_ADD)
        for lw, a in ((60, 0.10), (22, 0.25), (6, 0.9)):
            ctx.set_line_width(lw)
            ctx.set_source_rgba(*GOLD_L[:3], a)
            ctx.move_to(x_top, 0)
            ctx.line_to(x_bot, H)
            ctx.stroke()
        ctx.restore()
        for k in range(6):
            yy = 200 + k * 300
            add_glow(ctx, lerp(x_top, x_bot, yy / H), yy, 260, WARM, 0.22)
        sparks(ctx, lerp(x_top, x_bot, 0.5), 960, (e * 3) % 1, seed=int(e * 3) + 7, n=24, color=GOLD_L,
               reach=420)
    flash(ctx, 0.35 * bump(t, LINE_T[0] + LINE_T[1] - 0.08, 0.25), hx("#fff1d0"))


# ---------------------------------------------------------------------------
# G. "o'zingizga ishonchingiz, tashqi ko'rinishingiz" — matn bosh ortida, osmonda (17.95 – 20.45)
# ---------------------------------------------------------------------------
def sG(ctx, lt, t):
    pic, cut = P["p04"], P["p04cut"]
    z = 1.0 + 0.055 * e_io(prog(lt, 0, 2.6))
    s0 = 0.95
    ax, ay = 540, 1046
    s = s0 * z
    tx, ty = ax - 780 * s, ay - 400 * s
    tc = TOP["p04"]
    g = cairo.LinearGradient(0, 0, 0, ty + 40)
    g.add_color_stop_rgba(0, *lerpc(tc[:3], (0.05, 0.22, 0.62), 0.55), 1)
    g.add_color_stop_rgba(1, *tc[:3], 1)
    ctx.set_source(g)
    ctx.paint()
    for k in range(4):
        cx_ = (180 + k * 290 + lt * 18) % (W + 300) - 150
        add_glow(ctx, cx_, 150 + 120 * (k % 2) + ty * 0.25, 220, WHITE, 0.10)
    paint_pic(ctx, pic, s, tx, ty, pad=False)
    g = cairo.LinearGradient(0, ty, 0, ty + 70)
    g.add_color_stop_rgba(0, *tc[:3], 1)
    g.add_color_stop_rgba(1, *tc[:3], 0)
    ctx.set_source(g)
    ctx.rectangle(0, ty - 1, W, 72)
    ctx.fill()
    flare(ctx, 930, 170 + 10 * math.sin(t), 0.55, t, streak=700)
    line(ctx, t, seg(7, 2, 3), 540, 520, "xbold", 88, anim="blur", shadow=10)
    line(ctx, t, seg(7, 3, 4), 540, 728, "black", 160, anim="drop", maxw=960, shadow=8,
         color=hx("#fffaf0"))
    paint_pic(ctx, cut, s, tx, ty, pad=False)
    vgrad(ctx, 1150, 1560, 0, 0.55)
    row(ctx, t, [(seg(8, 0, 1), "semi", 66, {"anim": "rise", "color": hx("#dfe8f2")}),
                 (seg(8, 1, 2), "xbold", 84, {"anim": "rise", "hl": GOLD_L})], 540, 1420)


# ---------------------------------------------------------------------------
# H. "va odamlarning sizga bo'lgan munosabati ham o'zgaradi." (20.45 – 23.41)
# ---------------------------------------------------------------------------
def _cam_keys(t, keys):
    if t <= keys[0][0]:
        return keys[0][1:]
    for (t0, *a), (t1, *b) in zip(keys, keys[1:]):
        if t <= t1:
            e = e_io((t - t0) / (t1 - t0))
            return tuple(lerp(x, y, e) for x, y in zip(a, b))
    return keys[-1][1:]


def sH(ctx, lt, t):
    pic = P["p05"]
    fx, fy, z = _cam_keys(t, [(20.30, 1290, 600, 1.18), (20.95, 1230, 600, 1.20),
                              (21.20, 1010, 470, 1.26), (21.55, 1010, 470, 1.30)])
    z += 0.08 * hits_env(t, (21.23,), 0.2)
    s_c, tx_c, ty_c = cam_cover(pic, fx, fy, z, 540, 900)
    s_k = 0.665
    tx_k, ty_k = 540 - pic.w * s_k / 2, 985 - pic.h * s_k / 2
    e = e_io(prog(t, 21.55, 0.75))
    if e <= 0:
        paint_pic(ctx, pic, s_c, tx_c, ty_c)
    else:
        sb, tbx, tby = cam_cover(P["p05b"], P["p05b"].w / 2, P["p05b"].h / 2, 1.1)
        paint_pic(ctx, P["p05b"], sb, tbx, tby)
        tint(ctx, hx("#ffb36b"), 0.18, cairo.OPERATOR_SOFT_LIGHT)
        sc = s_c * (s_k / s_c) ** e
        f = (sc - s_c) / (s_k - s_c) if s_k != s_c else e
        tx, ty = lerp(tx_c, tx_k, f), lerp(ty_c, ty_k, f)
        rad = 34 * e
        ctx.save()
        ctx.set_source_rgba(0, 0, 0, 0.45 * e)
        round_rect(ctx, tx + 14, ty + 26, pic.w * sc, pic.h * sc, rad)
        ctx.fill()
        round_rect(ctx, tx, ty, pic.w * sc, pic.h * sc, rad)
        ctx.clip()
        paint_pic(ctx, pic, sc, tx, ty)
        ctx.restore()
        round_rect(ctx, tx, ty, pic.w * sc, pic.h * sc, rad)
        ctx.set_line_width(3)
        ctx.set_source_rgba(*GOLD_L[:3], 0.7 * e)
        ctx.stroke()
        # admiration: warm hearts rising from the friends
        for i, (px_, py_) in enumerate(((300, 520), (1300, 640), (250, 760), (1350, 800))):
            for k in range(3):
                ag = t - 21.9 - k * 0.45 - i * 0.12
                if 0 < ag < 1.6:
                    hx_ = tx + px_ * sc + 20 * math.sin(ag * 3 + i + k)
                    hy_ = ty + py_ * sc - 220 * e_out(ag / 1.6)
                    al = min(1, ag / 0.2) * (1 - ag / 1.6)
                    ctx.set_source_rgba(*hx("#ff9eb0")[:3], 0.85 * al)
                    heart(ctx, hx_, hy_, 16 + 6 * (k % 2))
                    ctx.fill()
                    add_glow(ctx, hx_, hy_, 50, ROSE, 0.25 * al)
    vgrad(ctx, 640, 120, 0, 0.62)
    light_leak(ctx, t, 0.6, seed=5)
    line(ctx, t, seg(8, 2, 6), 540, 330, "semi", 58, anim="blur", shadow=10)
    line(ctx, t, seg(8, 6, 7), 540, 470, "serif_it_b", 132, anim="pop", color=GOLD_L, grad=GG,
         glow=16, glow_a=0.45, shadow=12)
    row(ctx, t, [(seg(8, 7, 8), "semi", 64, {"anim": "rise"}),
                 (seg(8, 8, 9), "black", 88, {"anim": "slam", "color": WHITE, "hl": GOLD_L})],
        540, 1468)


# ---------------------------------------------------------------------------
# I. "Eng muhimi, oilangizni ... qalqondek himoya qila olasiz." (23.41 – 27.25)
# ---------------------------------------------------------------------------
SH_C = (540, 1080, 515, 560)


def sI(ctx, lt, t):
    e = e_io(prog(t, 23.85, 1.2))
    s0, A0 = 2.35, (540 - 760 * 2.35, 800 - 430 * 2.35)
    s1, A1 = 1.0, (540 - 860, 1080 - 800)
    s, A = zoom_between(s0, A0, s1, A1, e)
    tx, ty = A
    sk = shake(t, (23.41, 26.64, 27.05), 12)
    ctx.save()
    ctx.translate(sk * 0.6, sk)
    sb, tbx, tby = cam_cover(P["p06b"], P["p06b"].w * 0.4, P["p06b"].h * 0.3, 1.15)
    paint_pic(ctx, P["p06b"], sb, tbx, tby)
    paint_pic(ctx, P["p06s"], s, tx, ty, pad=False)
    yb = ty + P["p06s"].h * s
    if yb < H:
        g = cairo.LinearGradient(0, yb - 260, 0, yb)
        g.add_color_stop_rgba(0, 0.02, 0.03, 0.05, 0)
        g.add_color_stop_rgba(1, 0.02, 0.03, 0.05, 1)
        ctx.set_source(g)
        ctx.rectangle(0, yb - 260, W, 262)
        ctx.fill()
        ctx.set_source_rgba(0.02, 0.03, 0.05, 1)
        ctx.rectangle(0, yb, W, H - yb + 40)
        ctx.fill()
    if ty > 0:
        g = cairo.LinearGradient(0, ty, 0, ty + 200)
        g.add_color_stop_rgba(0, 0.02, 0.03, 0.05, 0.9)
        g.add_color_stop_rgba(1, 0.02, 0.03, 0.05, 0)
        ctx.set_source(g)
        ctx.rectangle(0, ty - 2, W, 204)
        ctx.fill()
    sp = e_out(prog(t, 25.30, 0.75))
    cx, cy, rx, ry = SH_C
    if sp > 0:
        ctx.save()
        ctx.translate(cx, cy)
        ctx.scale(rx, ry)
        ctx.arc(0, 0, 1, 0, 2 * math.pi)
        ctx.restore()
        ctx.clip()
        paint_pic(ctx, P["p06w"], s, tx, ty, sp, pad=False)
        add_glow(ctx, cx, cy - 200, 700, WARM, 0.22 * sp)
        ctx.restore()
        ctx.save()
        ctx.translate(sk * 0.6, sk)
    # rain only outside the shield
    ctx.save()
    ctx.rectangle(0, 0, W, H)
    if sp > 0:
        ctx.save()
        ctx.translate(cx, cy)
        ctx.scale(rx * (0.6 + 0.4 * sp), ry * (0.6 + 0.4 * sp))
        ctx.arc_negative(0, 0, 1, 2 * math.pi, 0)
        ctx.restore()
    ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    ctx.clip()
    fall(ctx, t, "rain", hx("#cfe0ff"), seed=6, n=110, a=0.9 * prog(t, 24.3, 0.6), speed=1.3, wind=-120)
    ctx.restore()
    strikes = ((25.20, 980, 0, 860, 610, 3), (26.62, 1000, 60, 860, 640, 5), (27.03, 40, 160, 120, 860, 8))
    hits = []
    for t0, x0, y0, x1, y1, sd in strikes:
        a = clamp(1 - (t - t0) / 0.28) if t >= t0 else 0
        if a > 0:
            flick = 0.6 + 0.4 * math.sin((t - t0) * 90)
            lightning(ctx, x0, y0, x1, y1, a * flick, seed=sd, width=6)
            flash(ctx, 0.28 * a * flick, hx("#dde6ff"))
        if t >= t0 and t0 > 26:
            hits.append((x1, y1, prog(t, t0, 1.0)))
    hex_shield(ctx, cx, cy, rx, ry, sp, t, r=46, hits=hits, color=hx("#ffd98a"), a=0.8)
    ctx.restore()
    flash(ctx, 0.55 * (1 - prog(t, 23.41, 0.3)), hx("#fff6e6"))
    vgrad(ctx, 620, 160, 0, 0.6)
    a1 = 1 - prog(t, 24.58, 0.22)
    if a1 > 0:
        line(ctx, t, seg(9, 0, 2), 540, 345, "black", 120, anim="slam", shadow=16, alpha=a1)
        line(ctx, t, seg(9, 2, 3), 540, 500, "serif_it_b", 128, anim="pop", color=GOLD_L, grad=GG,
             glow=16, glow_a=0.45, alpha=a1)
    line(ctx, t, seg(9, 3, 6), 540, 320, "xbold", 66, anim="blur", shadow=12, hl=hx("#cfe0ff"))
    line(ctx, t, seg(9, 6, 8), 540, 440, "black", 104, anim="pop", color=GOLD_L, grad=GG, glow=18,
         glow_a=0.5, shadow=12)
    line(ctx, t, seg(9, 8, 10), 540, 535, "semi", 62, anim="rise", shadow=10)


# ---------------------------------------------------------------------------
# J. "Farzandlaringiz ko'p bo'lsa, ayolingiz qo'shib ko'tarib ololasiz." (27.25 – 31.30)
# ---------------------------------------------------------------------------
STACK = [((10, 0, 1), "xbold", 82, {"color": WHITE}),
         ((10, 1, 3), "semi", 62, {"color": hx("#ffe6cf")}),
         ((10, 3, 4), "serif_it_b", 104, {"color": hx("#ffc7a6")}),
         ((10, 4, 5), "xbold", 82, {"color": WHITE}),
         ((10, 5, 6), "black", 118, {"color": GOLD_L, "grad": GG, "glow": 18, "glow_a": 0.5}),
         ((10, 6, 7), "semi", 62, {"color": hx("#ffe6cf")})]


def sJ(ctx, lt, t):
    pic = P["p07"]
    lift_t = seg(10, 5, 6)[0]["s"]
    keys = [(27.10, 1250, 330, 1.32), (28.70, 1170, 400, 1.30), (29.15, 520, 1150, 1.30),
            (29.40, 520, 1150, 1.30), (29.85, 1020, 430, 1.22), (31.4, 990, 470, 1.16)]
    fx, fy, z = _cam_keys(t, keys)
    s, tx, ty = cam_cover(pic, fx, fy, z, 560, 860)
    paint_pic(ctx, pic, s, tx, ty)
    add_glow(ctx, tx + 520 * s, ty + 520 * s, 800, WARM, 0.16 + 0.06 * math.sin(t * 2))
    dust(ctx, t, GOLD_L, seed=12, n=45, a=0.55, speed=0.5, size=1.0, add=True)
    g = cairo.LinearGradient(0, 0, 820, 0)
    g.add_color_stop_rgba(0, 0.05, 0.02, 0.0, 0.72)
    g.add_color_stop_rgba(1, 0.05, 0.02, 0.0, 0)
    ctx.set_source(g)
    ctx.rectangle(0, 650, W, H - 650)
    ctx.fill()
    vgrad(ctx, 1150, 1600, 0, 0.5)
    vgrad(ctx, 300, 0, 0, 0.3)
    # word tower: each new line pushes the stack up; on "ko'tarib" the whole tower is lifted
    y = 1452
    lifted = 120 * (e_back(prog(t, lift_t - 0.05, 0.55)) if t > lift_t - 0.05 else 0)
    for (sg, a, b), fkey, size, opts in reversed(STACK):
        words = seg(sg, a, b)
        st = words[0]["s"]
        if t < st - 0.06:
            continue
        line(ctx, t, words, 96, y - lifted, fkey, size, align="l", anim="lift", dur=0.55,
             shadow=14, **opts)
        grow = e_out(prog(t, st - 0.06, 0.35))
        y -= size * 1.12 * grow


# ---------------------------------------------------------------------------
# K1. "Bugungi mashqlaringiz" -> vaqt sakrashi (31.30 – 33.10)
# K2. "70 yoshdagi hayotingizga ham ta'sirini o'tkazmay qolmaydi." (33.10 – 36.45)
# ---------------------------------------------------------------------------
FACE_Y = 330
CNT = (32.50, 0.62)


def age_counter(ctx, t, x=96, y=1175):
    if t < CNT[0] - 0.1:
        return 0
    v = lerp(20, 70, e_out(prog(t, *CNT)))
    a = clamp((t - CNT[0] + 0.1) / 0.2)
    sc = 1 + 0.25 * bump(t, CNT[0] + CNT[1] - 0.05, 0.3)
    s_ = f"{int(round(v))}"
    if t >= CNT[0] + CNT[1]:
        s_ = seg(11, 2, 3)[0]["w"]
    text(ctx, s_, "black", 250, GOLD_L, x, y, alpha=a, grad=GG, glow=22, glow_a=0.5, scale=sc,
         shadow=18)
    return tw(s_, "black", 250)


def sK1(ctx, lt, t):
    pic = P["p02"]
    z = 1.12 + 0.42 * e_in(prog(lt, 0, 1.95))
    s, tx, ty = cam_cover(pic, 1000, 520, z, 540, lerp(560, FACE_Y, e_in(prog(lt, 0, 1.95))))
    paint_pic(ctx, pic, s, tx, ty)
    tint(ctx, COLD, 0.22, cairo.OPERATOR_SOFT_LIGHT)
    vgrad(ctx, 1000, 1560, 0, 0.75)
    a = 1 - prog(t, 32.55, 0.25)
    line(ctx, t, seg(11, 0, 1), 540, 1300, "serif_it_b", 150, anim="pop", color=GOLD_L, grad=GG,
         glow=16, glow_a=0.45, alpha=a, shadow=14)
    line(ctx, t, seg(11, 1, 2), 540, 1420, "black", 92, anim="rise", alpha=a, shadow=12)
    clock_icon(ctx, 900, 330, 70, lt, prog(t, 31.9, 0.4) * (1 - prog(t, 32.7, 0.3)))
    age_counter(ctx, t)


def sK2(ctx, lt, t):
    pic = P["p08"]
    s, tx, ty = cam_cover(pic, 750, 175, 1.0 + 0.04 * lt / 3.3, 540, FACE_Y)
    paint_pic(ctx, pic, s, tx, ty)
    sh = shake(t, (35.26, 35.67), 10)
    god_rays(ctx, t, 1150, -100, 0.14, hx("#fff2cc"), n=8, seed=3, ang0=1.9, ang1=2.7, length=2400)
    light_leak(ctx, t, 0.55, seed=8)
    dust(ctx, t, GOLD_L, seed=5, n=40, a=0.45, speed=0.4, add=True)
    ctx.save()
    ctx.translate(0, sh)
    vgrad(ctx, 950, 1560, 0, 0.55)
    wx = age_counter(ctx, t)
    line(ctx, t, seg(11, 3, 4), 96 + wx + 26, 1175, "serif_it_b", 92, align="l", anim="rise",
         color=WHITE, shadow=12, maxw=900 - wx)
    line(ctx, t, seg(11, 4, 5), 96, 1282, "xbold", 80, align="l", anim="blur", shadow=12)
    line(ctx, t, seg(12, 0, 2), 96, 1372, "semi", 64, align="l", anim="rise", shadow=12,
         color=hx("#fff1d6"))
    row(ctx, t, [(seg(12, 2, 3), "black", 84, {"anim": "slam", "shadow": 12, "color": GOLD_L,
                                               "grad": GG, "glow": 14, "glow_a": 0.5}),
                 (seg(12, 3, 4), "black", 84, {"anim": "slam", "shadow": 12})], 96, 1466, align="l")
    ctx.restore()
    for hb, (hx_, hy_) in ((35.26, (320, 1440)), (35.67, (760, 1440))):
        q = prog(t, hb, 0.6)
        shockwave(ctx, hx_, hy_, q, GOLD_L, 520, 4)


# ---------------------------------------------------------------------------
# L. "Tanangiz — umr bo'yi yashaydigan yagona uyingiz." — uy chizig'i (36.45 – 39.25)
# ---------------------------------------------------------------------------
def sL(ctx, lt, t):
    pic = P["p10"]
    s = 1.15
    ty = H - pic.h * s + 2
    txs, txe = 540 - 1500 * s, 450 - 900 * s
    tx = lerp(txs, txe, e_io(prog(t, 36.25, 1.55)))
    tc = TOP["p10"]
    g = cairo.LinearGradient(0, 0, 0, ty + 30)
    g.add_color_stop_rgba(0, 0.07, 0.05, 0.16, 1)
    g.add_color_stop_rgba(0.55, *lerpc((0.36, 0.16, 0.30), tc[:3], 0.3), 1)
    g.add_color_stop_rgba(1, *tc[:3], 1)
    ctx.set_source(g)
    ctx.paint()
    stars(ctx, t, 41, 50, ty * 0.55, WHITE, 0.55)
    paint_pic(ctx, pic, s, tx, ty, pad=False)
    g = cairo.LinearGradient(0, ty, 0, ty + 90)
    g.add_color_stop_rgba(0, *tc[:3], 1)
    g.add_color_stop_rgba(1, *tc[:3], 0)
    ctx.set_source(g)
    ctx.rectangle(0, ty - 1, W, 92)
    ctx.fill()
    sx_, sy_ = tx + 1580 * s, ty + 410 * s
    flare(ctx, sx_, sy_, 0.75, t, streak=420)
    # the house drawn around the sitting man
    mx = tx + 905 * s
    base = ty + 885 * s
    hp = e_io(prog(t, 37.55, 1.0))
    if hp > 0:
        hw, hh, rf = 640, base - 1075, 300
        ctx.save()
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_operator(cairo.OPERATOR_ADD)
        for lw, a in ((26, 0.10), (10, 0.25), (4, 1.0)):
            house_path(ctx, mx, base, hw, hh, rf)
            ctx.set_line_width(lw)
            ctx.set_source_rgba(*GOLD_L[:3], a)
            stroke_partial(ctx, hp)
        ctx.restore()
        wl = bump(t, 38.45, 1.6) * 0.6 + 0.4 * prog(t, 38.45, 0.4)
        if wl > 0:
            ctx.save()
            house_path(ctx, mx, base, hw, hh, rf)
            ctx.clip()
            add_glow(ctx, mx, base - hh * 0.55, 520, WARM, 0.30 * wl)
            add_glow(ctx, mx, base - hh - rf * 0.3, 260, GOLD_L, 0.25 * wl)
            ctx.restore()
        if hp >= 1:
            steam(ctx, t, mx + 0.62 * hw / 2 + hw * 0.045, base - hh - rf * 0.38 - 10 + 60, 0.7, 150)
    line(ctx, t, seg(13, 0, 2), 540, 300, "serif_it_b", 124, anim="pop", color=GOLD_L, grad=GG,
         glow=16, glow_a=0.45, shadow=12)
    line(ctx, t, seg(13, 2, 5), 540, 405, "semi", 60, anim="blur", shadow=10)
    row(ctx, t, [(seg(13, 5, 6), "black", 100, {"anim": "rise", "shadow": 12}),
                 (seg(13, 6, 7), "black", 100, {"anim": "rise", "shadow": 12, "hl": GOLD_L,
                                                "glow": 16, "glow_a": 0.35})], 540, 560)


# ---------------------------------------------------------------------------
# M. "Muzqaymoqdek oqib yuravermasdan o'zingizga qarab yuring." — eriydigan matn, ko'zgu
# ---------------------------------------------------------------------------
PAN = (40.88, 0.42)


def sM(ctx, lt, t):
    pic = P["p11"]
    e = e_io(prog(t, *PAN))
    fx = lerp(1060, 1230, e)
    z = lerp(1.12, 1.05, e) + 0.03 * lt / 3.5
    s, tx, ty = cam_cover(pic, fx, 470, z, 540, lerp(860, 800, e))
    paint_pic(ctx, pic, s, tx, ty)
    rack = 1 - e_io(prog(t, PAN[0], 0.55))
    paint_blur(ctx, P["p11b"], s, tx, ty, 0.92 * rack)
    tint(ctx, hx("#7fa6d6"), 0.12, cairo.OPERATOR_SOFT_LIGHT)
    add_glow(ctx, tx + 1250 * s, ty + 420 * s, 700, hx("#a9c8ff"), 0.10 * rack)
    bokeh(ctx, t, hx("#cfe0ff"), seed=19, n=9, a=0.07, rmin=50, rmax=140)
    sh = prog(t, 41.35, 0.9)
    if 0 < sh < 1:
        xx = lerp(-400, W + 400, e_io(sh))
        ctx.save()
        ctx.set_operator(cairo.OPERATOR_ADD)
        g = cairo.LinearGradient(xx - 160, 0, xx + 160, 300)
        g.add_color_stop_rgba(0, 1, 1, 1, 0)
        g.add_color_stop_rgba(0.5, 1, 1, 1, 0.16)
        g.add_color_stop_rgba(1, 1, 1, 1, 0)
        ctx.set_source(g)
        ctx.paint()
        ctx.restore()
    vgrad(ctx, 700, 120, 0, 0.55)
    vgrad(ctx, 1080, 1560, 0, 0.7)
    # melting ice-cream words
    lay1 = row(ctx, -1, [(seg(14, 0, 2), "black", 104, {})], 540, 360)
    lay2 = row(ctx, -1, [(seg(14, 2, 3), "black", 104, {})], 540, 500)
    for i, (w, x0, x1, sz) in enumerate(lay1 + lay2):
        y = 360 if i < len(lay1) else 500
        p = prog(t, w["s"] - 0.06, 0.4)
        if p <= 0:
            continue
        q = prog(t, w["s"] + 0.35, 1.5)
        fade = 1 - prog(t, 41.05, 0.45)
        col = ICE[i % 3]
        melt_text(ctx, w["w"], "black", sz, col, (x0 + x1) / 2, y + (1 - e_out(p)) * 30, q,
                  seed=5 + i, align="c", drip=95, alpha=clamp(p * 3) * fade)
    line(ctx, t, seg(14, 3, 4), 540, 1350, "serif_it_b", 116, anim="pop", color=GOLD_L, grad=GG,
         glow=16, glow_a=0.45, shadow=12)
    line(ctx, t, seg(14, 4, 6), 540, 1455, "xbold", 80, anim="rise", shadow=12)


# ---------------------------------------------------------------------------
# N. "Uyat bo'ldi axir." + muallif (42.80 – 47.00)
# ---------------------------------------------------------------------------
def sN(ctx, lt, t):
    pic = P["p11"]
    pull = e_io(prog(t, 43.85, 1.5))
    z = lerp(2.15, 1.08, pull) + 0.10 * hits_env(t, (42.84,), 0.18)
    s, tx, ty = cam_cover(pic, 1245, 440, z, 540, lerp(900, 880, pull))
    sk = shake(t, (42.84, 43.25), 12)
    ctx.save()
    ctx.translate(sk * 0.5, sk)
    paint_pic(ctx, pic, s, tx, ty)
    ctx.restore()
    dim = lerp(0.62, 0.30, pull)
    ctx.set_source_rgba(0, 0, 0, dim)
    ctx.paint()
    vignette(ctx, 0.7)
    flash(ctx, 0.28 * (1 - prog(t, 42.84, 0.22)) if t >= 42.84 else 0, hx("#fff2e0"))
    vgrad(ctx, 760, 150, 0, 0.55 * pull)
    # punchline block: big at the centre, then settles to the top
    ctx.save()
    k = lerp(1.0, 0.72, pull)
    ax, ay = 540, lerp(1010, 470, pull)
    ctx.translate(ax, ay)
    ctx.scale(k, k)
    ctx.translate(-540, -1010)
    line(ctx, t, seg(15, 0, 1), 540, 1010, "black", 250, anim="slam", shadow=20, tracking=4)
    line(ctx, t, seg(15, 1, 3), 540, 1160, "serif_it_b", 124, anim="pop", color=GOLD_L, grad=GG,
         glow=18, glow_a=0.5, shadow=14)
    ctx.restore()
    dust(ctx, t, GOLD_L, seed=77, n=30, a=0.4 * pull, speed=0.4, add=True)
    handle(ctx, lt, 44.55 - 42.80, y=1405, size=50)


# ---------------------------------------------------------------------------
SCENES = [(0.0, sA), (3.05, sB), (4.62, sC), (10.55, sD), (13.20, sE), (17.08, sF), (17.95, sG),
          (20.45, sH), (23.41, sI), (27.25, sJ), (31.30, sK1), (33.10, sK2), (36.45, sL),
          (39.25, sM), (42.80, sN)]

TRANS = {
    1: ("whip", 0.5, {"dir": "up"}),
    2: ("shutter", 0.8, {"hold": 0.15}),
    3: ("push", 0.5, {"dir": "up"}),
    4: ("glitchcut", 0.3),
    5: ("zoom", 0.45),
    6: ("flare", 0.45, {"y": 900}),
    7: ("whip", 0.42, {"dir": "left"}),
    9: ("burn", 0.6, {"x": 300, "y": 700}),
    10: ("blinds", 0.5, {"n": 9}),
    11: ("timewarp", 0.9, {"x": 540, "y": FACE_Y, "twist": 0.3}),
    12: ("dissolve", 0.7, {"color": WARM}),
    13: ("luma", 0.6, {"angle": 2.2}),
}
