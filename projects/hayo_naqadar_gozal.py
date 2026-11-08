"""
"Hayo naqadar goʻzal" — hadis asosidagi premium vertikal montaj (Instagram Reels).

Material: 12 kadrli kollaj (assets/images/kollaj.png -> panels/), hikoya ovozi
(assets/audio/hayo_ovoz.wav) va fon nashid (assets/audio/subhan_allah.mp3, 145.63 s dan).
Audio: tools/mix_audio.py -> assets/audio/hayo_mix.m4a (hikoya 0.40 s ga surilgan).

    python3 render.py projects/hayo_naqadar_gozal.py assets/audio/hayo_mix.m4a

Rang hikoyasi: kunduzgi yorug' (hook) -> masjidning sovuq ko'ki -> chiroq nuri (hadis) ->
zumrad+oltin (ziynat) -> sovuq neon (nafs) -> quyosh botishi (mashaqqat) -> indigo+nur
(Allohdan hayo) -> sepiya (aql/qorin/ezgulik) -> oq-qora (o'lim) -> rang qaytadi -> oltin osmon.
Reels xavfsiz zonasi: matnlar x 80..900, y 260..1480 (o'ng tugmalar va pastki izoh ostida emas).
"""
import math
import re

import cairo
import numpy as np

import render as R

R.configure(size=(1080, 1920), fps=30, dur=46.5)
from render import *  # noqa: F401,F403,E402

OUTPUT = "output/hayo_naqadar_gozal.mp4"
POST = {"grain": 0.07, "fade_in": 0.08, "fade_out": 0.7}

G = {}  # prepared pictures / surfaces

# --------------------------------------------------------------------------
# Palette (this film)
# --------------------------------------------------------------------------
BLUSH = hx("#f4c3b3")
BLUSH_GG = (hx("#fff1e8"), hx("#eea287"))
CREAM = hx("#f7f0e3")
NAVY = hx("#0a1124")
EMER_T, EMER_B = hx("#021512"), hx("#073a30")
INDIGO_T, INDIGO_B = hx("#050817"), hx("#13214a")
SEPIA_T, SEPIA_B = hx("#0c0906"), hx("#1d140b")
COLD = hx("#9fb6d6")

# --------------------------------------------------------------------------
# Speech timing (video time = narration + 0.40 s).  Phrase boundaries come from
# silence analysis (tools/analyze_audio.py); words inside a phrase are spread by
# syllable count.
# --------------------------------------------------------------------------


def _syl(w):
    return max(1, len(re.findall("[aeiouAEIOU]", w)))


def wt(phrase, t0, t1):
    ws = phrase.split(" ")
    n = [_syl(w) for w in ws]
    d = (t1 - t0) / sum(n)
    out, c = [], t0
    for k in n:
        out.append(c)
        c += k * d
    return out


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def paint_cam(ctx, pic, cam, alpha=1.0):
    s, tx, ty = cam
    paint_pic(ctx, pic, s, tx, ty, alpha)


def fill(ctx, c):
    ctx.set_source_rgba(*c[:3], c[3] if len(c) > 3 else 1)
    ctx.paint()


def to_screen(cam, x, y):
    s, tx, ty = cam
    return tx + x * s, ty + y * s


def W_(word, t0, key="med", size=64, color=CREAM, grad=None, glow=0, glow_color=None):
    return dict(w=word, t0=t0, key=key, size=size, color=color, grad=grad, glow=glow,
                gc=glow_color)


def rich(ctx, t, parts, x, y, align="c", rise=30, dur=0.55, blur=9, alpha=1.0, shadow=0,
         lead=0.06, space_key=None, gap=1.0, dy=0.0):
    """One line of mixed-font words; each word fades/rises in at its own time."""
    if alpha <= 0.003:
        return
    sk = space_key or parts[0]["key"]
    ssz = parts[0]["size"]
    sp = font(sk, ssz).getlength(" ") * gap
    ws = [tw(p["w"], p["key"], p["size"]) for p in parts]
    total = sum(ws) + sp * (len(parts) - 1)
    xx = x - {"l": 0, "c": total / 2, "r": total}[align]
    for p, w_ in zip(parts, ws):
        q = prog(t, p["t0"] - lead, dur)
        if q > 0:
            e = e_out(q)
            yy = y + dy + (1 - e) * rise
            cx = xx + w_ / 2
            if blur and q < 1:
                g = sprite(p["w"], p["key"], p["size"], p["color"], 0.0, p["grad"], blur)
                draw_sprite(ctx, g, cx, yy, alpha * (1 - e) * 0.8, 1.0, "c")
            text(ctx, p["w"], p["key"], p["size"], p["color"], cx, yy, alpha=alpha * e ** 1.5,
                 align="c", grad=p["grad"], glow=p["glow"], glow_a=0.55, glow_color=p["gc"],
                 shadow=shadow)
        xx += w_ + sp
    return total


def star8_path(ctx, cx, cy, R_, rot=-math.pi / 2):
    """Eight-pointed star (two interlaced squares, 'khatam')."""
    for k in range(16):
        ang = rot + k * math.pi / 8
        rr = R_ if k % 2 == 0 else R_ * 0.7654
        x, y = cx + rr * math.cos(ang), cy + rr * math.sin(ang)
        if k == 0:
            ctx.move_to(x, y)
        else:
            ctx.line_to(x, y)
    ctx.close_path()


def gold_stroke(ctx, path_fn, p, width=3.0, a=1.0, glow_w=12, color=GOLD_L):
    """Glowing gold line drawing of path_fn() up to fraction p."""
    if p <= 0:
        return
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_ADD)
    path_fn()
    ctx.set_source_rgba(*GOLD[:3], 0.22 * a)
    ctx.set_line_width(glow_w)
    stroke_partial(ctx, p)
    ctx.restore()
    path_fn()
    ctx.set_source_rgba(*color[:3], a)
    ctx.set_line_width(width)
    stroke_partial(ctx, p)


def brackets(ctx, x0, y0, x1, y1, p, color=GOLD_L, L=44, w=4, a=1.0):
    """Camera-autofocus corner brackets snapping onto a box ('attention')."""
    if p <= 0.001:
        return
    e = e_back(p)
    off = (1 - e) * 46
    ctx.set_line_width(w)
    ctx.set_line_cap(cairo.LINE_CAP_SQUARE)
    ctx.set_source_rgba(*color[:3], a * clamp(p * 3))
    for cx, cy, sx, sy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        X, Y = cx - sx * off, cy - sy * off
        ctx.move_to(X, Y + sy * L)
        ctx.line_to(X, Y)
        ctx.line_to(X + sx * L, Y)
    ctx.stroke()


def arc_text(ctx, t, s, fkey, size, cx, cy, r, a_mid, tchars, colors, grads, glow=0,
             rise=26):
    """Text laid along a circle (top arc, letters upright, reading left -> right)."""
    f = font(fkey, size)
    adv = [f.getlength(c) for c in s]
    total = sum(adv)
    ang0 = a_mid - total / r / 2
    x = 0.0
    for i, c in enumerate(s):
        th = ang0 + (x + adv[i] / 2) / r
        x += adv[i]
        if c == " ":
            continue
        q = prog(t, tchars[i], 0.5)
        if q <= 0:
            continue
        e = e_out(q)
        ctx.save()
        ctx.translate(cx + r * math.cos(th), cy + r * math.sin(th))
        ctx.rotate(th + math.pi / 2)
        if q < 1:
            g = sprite(c, fkey, size, colors[i], 0.0, grads[i], 8)
            draw_sprite(ctx, g, 0, -(1 - e) * rise, (1 - e) * 0.8, 1.0, "c")
        text(ctx, c, fkey, size, colors[i], 0, -(1 - e) * rise, alpha=e ** 1.5, align="c",
             grad=grads[i], glow=glow, glow_a=0.5, shadow=8, shadow_a=0.5)
        ctx.restore()


def seal(ctx, cx, cy, r, a, t):
    """Round gold seal with an emerald field (for '(Muttafaqun alayh).')."""
    if a <= 0:
        return
    ctx.set_source_rgba(0, 0, 0, 0.35 * a)
    ctx.arc(cx + 6, cy + 10, r + 8, 0, 2 * math.pi)
    ctx.fill()
    g = cairo.RadialGradient(cx, cy - r * 0.3, r * 0.1, cx, cy, r)
    g.add_color_stop_rgba(0, *hx("#0d4a3b")[:3], 0.97 * a)
    g.add_color_stop_rgba(1, *hx("#03201a")[:3], 0.97 * a)
    ctx.set_source(g)
    ctx.arc(cx, cy, r, 0, 2 * math.pi)
    ctx.fill()
    ctx.set_source_rgba(*GOLD_L[:3], a)
    ctx.set_line_width(4)
    ctx.arc(cx, cy, r, 0, 2 * math.pi)
    ctx.stroke()
    ctx.set_line_width(1.6)
    ctx.arc(cx, cy, r - 14, 0, 2 * math.pi)
    ctx.stroke()
    for k in range(36):
        an = k * 2 * math.pi / 36 + t * 0.15
        ctx.arc(cx + (r - 7) * math.cos(an), cy + (r - 7) * math.sin(an), 1.7, 0, 2 * math.pi)
        ctx.fill()
    ctx.set_line_width(1.4)
    ctx.set_source_rgba(*GOLD[:3], 0.8 * a)
    star8_path(ctx, cx, cy - r * 0.62, 13)
    ctx.stroke()
    text(ctx, "(Muttafaqun", "semi", 34, GOLD_L, cx, cy + 6, alpha=a, align="c", tracking=1)
    text(ctx, "alayh).", "semi", 34, GOLD_L, cx, cy + 50, alpha=a, align="c", tracking=1)


def extend_sky(rgb, ext, top_color, rows=20, smooth=121):
    """Grow a picture upward with a sky gradient continuing its top edge."""
    edge = rgb[:rows].astype(np.float32).mean(0)
    k = np.ones(smooth) / smooth
    pad = smooth // 2
    edge_s = np.stack([np.convolve(np.pad(edge[:, c], (pad, pad), mode="edge"), k, mode="valid")
                       for c in range(3)], 1)
    f = np.linspace(1, 0, ext)[:, None, None] ** 1.35
    tc = np.array(top_color[:3], np.float32) * 255
    sky = edge_s[None] * (1 - f) + tc[None, None] * f
    sky += np.random.default_rng(3).normal(0, 1.1, sky.shape)
    out = np.concatenate([np.clip(sky, 0, 255).astype(np.uint8), rgb], 0)
    # soften the seam
    seam = out[ext - 12:ext + 12].astype(np.float32)
    w8 = np.linspace(0, 1, 24)[:, None, None]
    blend = seam * w8 + np.repeat(edge_s[None], 24, 0) * (1 - w8)
    out[ext - 12:ext + 12] = np.clip(blend * 0.5 + seam * 0.5, 0, 255).astype(np.uint8)
    return out


def lattice_surface(color=GOLD_L, step=150, R_=44):
    """Faint Islamic star lattice (drawn once, painted with low alpha)."""
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, W + 2 * step, H + 2 * step)
    c = cairo.Context(s)
    c.set_source_rgba(*color[:3], 1)
    c.set_line_width(1.6)
    for j in range(0, (H + 2 * step) // step + 1):
        for i in range(0, (W + 2 * step) // step + 2):
            cx = i * step + (step / 2 if j % 2 else 0)
            cy = j * step * 0.866
            star8_path(c, cx, cy, R_, -math.pi / 2 + math.pi / 8)
            c.stroke()
            c.arc(cx, cy, R_ * 0.32, 0, 2 * math.pi)
            c.stroke()
            for k in range(6):
                an = k * math.pi / 3
                c.move_to(cx + R_ * 1.02 * math.cos(an), cy + R_ * 1.02 * math.sin(an))
                c.line_to(cx + (step * 0.5 - 4) * math.cos(an), cy + (step * 0.5 - 4) * math.sin(an))
            c.stroke()
    s.flush()
    return s


def paint_lattice(ctx, a, t, drift=(6, -10), rot=0.0):
    if a <= 0:
        return
    srf = G["lattice"]
    ctx.save()
    if rot:
        ctx.translate(W / 2, H / 2)
        ctx.rotate(rot)
        ctx.translate(-W / 2, -H / 2)
    ctx.set_source_surface(srf, -150 + (t * drift[0]) % 150, -150 + (t * drift[1]) % 130)
    ctx.paint_with_alpha(a)
    ctx.restore()


def soft_cloud(ctx, x, y, rx, ry, a, color=WHITE):
    if a <= 0:
        return
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(1, ry / rx)
    g = cairo.RadialGradient(0, 0, 0, 0, 0, rx)
    g.add_color_stop_rgba(0, *color[:3], a)
    g.add_color_stop_rgba(0.6, *color[:3], a * 0.4)
    g.add_color_stop_rgba(1, *color[:3], 0)
    ctx.set_source(g)
    ctx.arc(0, 0, rx, 0, 2 * math.pi)
    ctx.fill()
    ctx.restore()


# --------------------------------------------------------------------------
# Custom transition: zoom into a light source, emerge from the light
# --------------------------------------------------------------------------
def tr_lightzoom(ctx, sa, sb, p, o):
    x, y = o.get("x", W / 2), o.get("y", H / 2)
    if p < 0.5:
        q = p / 0.5
        s, src, wa = 1 + 2.8 * e_in(q), sa, e_in(q)
    else:
        q = (p - 0.5) / 0.5
        s, src, wa = 1.22 - 0.22 * e_out(q), sb, 1 - e_out(q)
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s, s)
    ctx.translate(-x, -y)
    ctx.set_source_surface(src)
    ctx.paint()
    ctx.restore()
    add_glow(ctx, x, y, 300 + 1700 * wa, GOLD_L, 0.95 * wa)
    flash(ctx, 0.88 * wa ** 1.4, hx("#fff4de"))


R.TRANSITIONS["lightzoom"] = tr_lightzoom


# --------------------------------------------------------------------------
# Prepare pictures
# --------------------------------------------------------------------------
EXT0 = 760    # sky grown above P0 (hook)
EXT11 = 900   # sky grown above P11 (finale)


def prepare():
    P = [load_rgb(f"panels/panel_{i:02d}.png") for i in range(12)]
    from PIL import Image
    m00 = np.asarray(Image.open(R.IDIR + "/masks/m00.png").convert("L"))
    # hook: portrait with grown sky + subject cutout (text goes behind the head)
    p0 = grade(P[0], sat=1.06, gain=(1.03, 1.0, 0.97), contrast=1.05)
    p0x = extend_sky(p0, EXT0, hx("#5d84bf"))
    G["p0x"] = Pic(p0x)
    G["p0cut"] = Pic(p0x, np.concatenate([np.zeros((EXT0, p0.shape[1]), np.uint8), m00], 0))
    # S1 gathering (cool)
    G["p9"] = Pic(grade(P[9], sat=0.82, gain=(0.92, 0.98, 1.1), contrast=1.08, gamma=1.04))
    # S2 lantern / S3 light
    G["p10"] = Pic(grade(P[10], sat=1.1, contrast=1.06))
    G["p10b"] = Pic(blurred(grade(P[10], sat=1.2, gain=(1.08, 0.98, 0.85)), 26, 0.25, 0.85))
    # S4-S5 respect
    G["p8"] = Pic(grade(P[8], sat=1.05, gain=(1.04, 1.0, 0.95), contrast=1.04))
    # S6 rack focus
    p7 = grade(P[7], sat=0.95, contrast=1.03)
    G["p7"] = Pic(p7)
    G["p7b"] = Pic(resize(blurred(p7, 11, 0.5), 2.0))
    G["p7bg"] = Pic(blurred(p7, 34, 0.25, 0.45))
    # S7 nafs: cold / warm
    G["p4c"] = Pic(grade(P[4], sat=0.3, gain=(0.88, 1.0, 1.15), contrast=1.14, gamma=1.05))
    G["p4w"] = Pic(grade(P[4], sat=1.08, gain=(1.07, 1.0, 0.9), contrast=1.04))
    # S8 summit
    G["p3"] = Pic(grade(P[3], sat=1.08, contrast=1.05))
    # S9 dua
    G["p2"] = Pic(grade(P[2], sat=1.0, gain=(0.98, 1.0, 1.03), contrast=1.05))
    # S10 triptych (sepia -> colour)
    for i in (1, 5, 2):
        G[f"t{i}s"] = Pic(grade(P[i], sat=0.35, gain=(1.1, 0.98, 0.8), contrast=1.06))
        G[f"t{i}c"] = Pic(grade(P[i], sat=1.08, gain=(1.04, 1.0, 0.95), contrast=1.05))
    # S11 death: colour + grey
    G["p6c"] = Pic(grade(P[6], sat=0.9, contrast=1.05))
    G["p6g"] = Pic(grade(P[6], sat=0.0, gain=(0.95, 1.0, 1.08), contrast=1.18, gamma=1.08))
    # S12 colour bloom
    G["p0g"] = Pic(grade(P[0], sat=0.0, gain=(0.95, 1.0, 1.07), contrast=1.12))
    G["p0c"] = Pic(grade(P[0], sat=1.12, gain=(1.06, 1.0, 0.93), contrast=1.05))
    # S13 finale: sky grown above
    p11 = grade(P[11], sat=1.08, gain=(1.05, 1.0, 0.94), contrast=1.04)
    G["p11x"] = Pic(extend_sky(p11, EXT11, hx("#4f6fb3")))
    # lattice
    G["lattice"] = lattice_surface()
    # S4: letter 'window' — find a point deep inside a stroke of "mazmuni:"
    from scipy.ndimage import distance_transform_edt
    sz = fit("mazmuni:", "black", 260, 900)
    G["mz_size"] = sz
    sp = sprite("mazmuni:", "black", sz, WHITE)
    al = np.ndarray((sp.surf.get_height(), sp.surf.get_width(), 4), np.uint8,
                    sp.surf.get_data())[..., 3]
    d = distance_transform_edt(al > 200)
    wd = d.shape[1]
    d[:, : int(wd * 0.30)] = 0
    d[:, int(wd * 0.62):] = 0
    r_, c_ = np.unravel_index(np.argmax(d), d.shape)
    G["mz_pt"] = (c_, r_)  # in sprite surface pixels


# --------------------------------------------------------------------------
# Scene 0 — HOOK (0.00 – 2.33): "Hayo naqadar goʻzal"
#   dolly-out from his direct gaze; giant "Hayo" rises from BEHIND his head.
# --------------------------------------------------------------------------
TW0 = wt("Hayo naqadar goʻzal", 0.75, 2.29)


def cam0(lt):
    eyes = (1110, 480 + EXT0)
    s0 = 1.30
    A0 = (540 - eyes[0] * s0, 1000 - eyes[1] * s0)
    s1 = 0.92 + 0.016 * lt
    A1 = (540 - eyes[0] * s1, 1085 - eyes[1] * s1)
    s, A = zoom_between(s0, A0, s1, A1, e_out(prog(lt, 0.0, 1.15)))
    return s, A[0], A[1]


def scene0(ctx, lt, t):
    cam = cam0(lt)
    paint_cam(ctx, G["p0x"], cam)
    vgrad(ctx, 900, 160, 0, 0.5, NAVY)
    god_rays(ctx, t, 560, -260, 0.07 + 0.05 * bump(t, 0.6, 1.6), hx("#fff1d6"), n=8, seed=11,
             ang0=1.15, ang1=2.0, length=1800)
    # light bloom behind the word
    add_glow(ctx, 540, 640, 620, BLUSH, 0.28 * bump(t, 0.55, 1.8) + 0.08 * prog(t, 0.6, 0.6))
    # giant word rising from behind the head
    p = prog(t, TW0[0] - 0.12, 0.85)
    text_rise(ctx, "Hayo", "serif_it_b", 372, WHITE, 540, 770, p, align="c", dist=330,
              grad=BLUSH_GG, shadow=26, shadow_a=0.45)
    paint_cam(ctx, G["p0cut"], cam)
    # rosy 'blush' breath on his face at "goʻzal"
    s, tx, ty = cam
    fx, fy = tx + 1110 * s, ty + (560 + EXT0) * s
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_SOFT_LIGHT)
    glow(ctx, fx, fy, 330 * s / 0.92, hx("#ff9a8a"), 0.32 * prog(t, TW0[2] - 0.1, 0.6))
    ctx.restore()
    # kicker above
    rich(ctx, t, [W_("naqadar", TW0[1], "serif_it", 84, CREAM),
                  W_("goʻzal", TW0[2], "serif_it_b", 84, CREAM, grad=GG, glow=14,
                     glow_color=GOLD)], 540, 392, dur=0.6, shadow=14)
    dust(ctx, t, hx("#fff6e0"), seed=2, n=40, a=0.5, speed=0.6, add=True)
    vignette(ctx, 0.35)


# --------------------------------------------------------------------------
# Scene 1 — RIVOYAT (2.33 – 5.52): the gathering; an isnad thread with nodes
# --------------------------------------------------------------------------
TW1 = wt("Imron ibn Husoyn roziyallohu anhudan rivoyat qilinadi:", 2.36, 5.38)


def cam1(t):
    e = e_io(prog(t, 2.1, 3.6))
    return cam_cover(G["p9"], lerp(830, 650, e), 0, z=1.12 + 0.03 * e, px=540, py=0)


def scene1(ctx, lt, t):
    cam = cam1(t)
    paint_cam(ctx, G["p9"], cam)
    bokeh(ctx, t, hx("#ffcf8a"), seed=21, n=9, a=0.10, rmin=50, rmax=120,
          region=(0, 200, W, 1100))
    vgrad(ctx, 1000, 1500, 0, 0.82, NAVY)
    vgrad(ctx, 500, 120, 0, 0.35, NAVY)
    tint(ctx, hx("#3b5d9a"), 0.18, cairo.OPERATOR_SOFT_LIGHT)
    # isnad timeline (left) -------------------------------------------------
    xn = 118
    ys = (1196, 1281, 1363)
    pl = prog(t, 2.32, 2.4)
    if pl > 0:
        ctx.set_source_rgba(*GOLD[:3], 0.65)
        ctx.set_line_width(2)
        ctx.move_to(xn, ys[0] - 40)
        ctx.line_to(xn, lerp(ys[0] - 40, ys[2] + 40, e_io(pl)))
        ctx.stroke()
    for k, (yy, tk) in enumerate(zip(ys, (TW1[0], TW1[3], TW1[5]))):
        q = prog(t, tk - 0.1, 0.4)
        if q > 0:
            r = 7 * e_back(q) if q > 1e-3 else 0
            ctx.set_source_rgba(*GOLD_L[:3], 1)
            ctx.arc(xn, yy, max(0.5, r), 0, 2 * math.pi)
            ctx.fill()
            add_glow(ctx, xn, yy, 40, GOLD, 0.6 * (1 - q) + 0.15)
    # the narration travels up the thread into the listener
    hx_, hy_ = to_screen(cam, 470, 330)
    pq = e_io(prog(t, 4.75, 0.75))
    if pq > 0:
        def thread():
            ctx.move_to(xn, ys[0])
            ctx.curve_to(xn, ys[0] - 260, hx_ - 60, hy_ + 360, hx_ + 40, hy_ + 120)
        gold_stroke(ctx, thread, pq, width=2.2, a=0.9, glow_w=9)
        if pq < 1:
            pass
        add_glow(ctx, hx_ + 40, hy_ + 120, 160, GOLD_L, 0.55 * bump(t, 5.2, 0.7))
    # text block --------------------------------------------------------------
    rich(ctx, t, [W_("Imron", TW1[0], "serif_it_b", 84, GOLD_L, grad=GG),
                  W_("ibn", TW1[1], "serif_it_b", 84, GOLD_L, grad=GG),
                  W_("Husoyn", TW1[2], "serif_it_b", 84, GOLD_L, grad=GG)],
         170, 1222, align="l", shadow=14)
    rich(ctx, t, [W_("roziyallohu", TW1[3], "light", 46),
                  W_("anhudan", TW1[4], "light", 46)], 172, 1298, align="l", shadow=10)
    rich(ctx, t, [W_("rivoyat", TW1[5], "reg", 54),
                  W_("qilinadi:", TW1[6], "reg", 54)], 172, 1382, align="l", shadow=10)
    dust(ctx, t, GOLD_L, seed=5, n=34, a=0.35, speed=0.5, size=0.8, add=True)
    vignette(ctx, 0.5)


# --------------------------------------------------------------------------
# Scene 2 — RASULULLOH (5.52 – 8.29): from the mosque to the lantern's flame
# --------------------------------------------------------------------------
TW2 = wt("Rasululloh sollallohu alayhi vasallam aytdilar:", 5.66, 8.08)
FLAME = (1096, 548)


def cam2(t):
    e = e_io(prog(t, 5.3, 2.95))
    fx = lerp(470, FLAME[0], e)
    fy = lerp(420, FLAME[1], e)
    z = lerp(1.0, 1.12, e_in(prog(t, 6.0, 2.4)))
    return cam_cover(G["p10"], fx, fy, z=z, px=540, py=lerp(820, 1100, e))


def scene2(ctx, lt, t):
    cam = cam2(t)
    paint_cam(ctx, G["p10"], cam)
    stars(ctx, t, 31, 26, 520, CREAM, 0.55)
    fx, fy = to_screen(cam, *FLAME)
    fl = 0.45 + 0.08 * math.sin(t * 13) + 0.05 * math.sin(t * 23 + 1)
    grow = prog(t, 6.6, 1.8)
    god_rays(ctx, t, fx, fy, 0.05 + 0.12 * grow, hx("#ffcf7a"), n=14, seed=8, ang0=0,
             ang1=2 * math.pi, length=1400)
    add_glow(ctx, fx, fy, 420 + 200 * grow, hx("#ffb347"), fl * 0.55)
    add_glow(ctx, fx, fy, 120, hx("#fff0c8"), fl)
    flying_glyphs(ctx, lt, fx, fy - 40, seed=4, n=26, charset="·•✦", sizes=(18, 24, 30),
                  fkey="reg", color=hx("#ffd59a"), glow_color=hx("#ff9a3c"), a=0.7)
    vgrad(ctx, 820, 170, 0, 0.74, NAVY)
    rich(ctx, t, [W_("Rasululloh", TW2[0], "serif_it_b", 118, GOLD_L, grad=GG, glow=18,
                     glow_color=GOLD)], 540, 420, shadow=16, dur=0.8)
    rich(ctx, t, [W_("sollallohu", TW2[1], "reg", 48),
                  W_("alayhi", TW2[2], "reg", 48),
                  W_("vasallam", TW2[3], "reg", 48)], 540, 510, shadow=16)
    rich(ctx, t, [W_("aytdilar:", TW2[4], "reg", 56)], 540, 598, shadow=10)
    dust(ctx, t, hx("#ffd59a"), seed=9, n=30, a=0.35, speed=0.7, add=True)
    vignette(ctx, 0.5)


# --------------------------------------------------------------------------
# Scene 3 — HADIS (8.29 – 12.04): written in light; « » open like doors; seal
# --------------------------------------------------------------------------
TW3 = wt("«Hayo faqat yaxshilik keltiradi».", 8.49, 10.34)
SEAL_T = 10.80


def scene3(ctx, lt, t):
    # camera shake on the seal hit
    sh = (1 - prog(t, SEAL_T, 0.45)) * (t >= SEAL_T)
    ox = 9 * sh * math.sin(t * 90)
    oy = 7 * sh * math.cos(t * 77)
    pic = G["p10b"]
    s = max(W / pic.w, H / pic.h) * (1.25 + 0.04 * lt)
    paint_pic(ctx, pic, s, W / 2 - pic.w * s * 0.80, H / 2 - pic.h * s * 0.47)
    tint(ctx, hx("#3a1d06"), 0.35, cairo.OPERATOR_MULTIPLY)
    bokeh(ctx, t, hx("#ffc46b"), seed=33, n=12, a=0.13, rmin=40, rmax=150)
    vignette(ctx, 0.7)
    ctx.save()
    ctx.translate(ox, oy)
    zs = 1 + 0.025 * lt
    ctx.translate(W / 2, 900)
    ctx.scale(zs, zs)
    ctx.translate(-W / 2, -900)
    # light burst behind "yaxshilik"
    hb = bump(t, TW3[2] - 0.05, 1.5)
    god_rays(ctx, t, 540, 860, 0.05 + 0.16 * hb, GOLD_L, n=16, seed=3, ang0=0,
             ang1=2 * math.pi, length=1300)
    add_glow(ctx, 540, 860, 700, hx("#ffcf80"), 0.12 + 0.25 * hb)
    # layout
    k1, s1 = "serif_it", 112
    k2, s2 = "serif_it_b", 172
    y1, y2, y3 = 690, 878, 1028
    wq = tw("«", k1, s1)
    wl1 = tw("Hayo faqat", k1, s1)
    x1 = 540 - (wq + wl1) / 2
    wl3 = tw("keltiradi", k1, s1)
    wq2 = tw("».", k1, s1)
    x3 = 540 - (wl3 + wq2) / 2
    # doors: big « » meet in the centre, then fly to their places
    pd = e_out5(prog(t, 8.34, 0.42))
    pin = e_out(prog(t, 8.16, 0.3))
    big = 300
    qa = pin
    qx1 = lerp(540 - 70, x1, pd)
    qy1 = lerp(930, y1, pd)
    qx2 = lerp(540 + 70, x3 + wl3, pd)
    qy2 = lerp(930, y3, pd)
    sc = lerp(big / s1, 1.0, pd)
    text(ctx, "«", k1, s1, GOLD_L, qx1, qy1, alpha=qa, align="l", scale=sc, grad=GG, glow=16,
         glow_a=0.6, glow_color=GOLD)
    text(ctx, "».", k1, s1, GOLD_L, qx2, qy2, alpha=qa, align="l", scale=sc, grad=GG, glow=16,
         glow_a=0.6, glow_color=GOLD)
    # words, revealed between the opening doors
    rich(ctx, t, [W_("Hayo", TW3[0], k1, s1, CREAM), W_("faqat", TW3[1], k1, s1, CREAM)],
         x1 + wq, y1, align="l", shadow=16, dur=0.6)
    yq = prog(t, TW3[2] - 0.08, 0.7)
    if yq > 0:
        e = e_out5(yq)
        text(ctx, "yaxshilik", k2, s2, GOLD_L, 540, y2 + (1 - e) * 40, alpha=e, align="c",
             grad=GG, glow=24, glow_a=0.75 * e, glow_color=hx("#ffb84a"), shadow=18,
             scale=1.0 + 0.12 * (1 - e))
        sparks(ctx, 540, y2 - 60, prog(t, TW3[2], 0.9), seed=4, n=30, reach=520)
    rich(ctx, t, [W_("keltiradi", TW3[3], k1, s1, CREAM)], x3, y3, align="l", shadow=16,
         dur=0.6)
    # seal stamp
    ps = prog(t, SEAL_T - 0.18, 0.22)
    if ps > 0:
        scl = lerp(2.3, 1.0, e_in(ps))
        ctx.save()
        ctx.translate(540, 1300)
        ctx.scale(scl, scl)
        ctx.translate(-540, -1300)
        seal(ctx, 540, 1300, 158, clamp(ps * 2), t)
        ctx.restore()
        q = prog(t, SEAL_T + 0.02, 0.8)
        shockwave(ctx, 540, 1300, q, GOLD_L, rmax=520, width=4)
        add_glow(ctx, 540, 1300, 380, GOLD_L, 0.6 * bump(t, SEAL_T, 0.35))
    ctx.restore()
    dust(ctx, t, GOLD_L, seed=12, n=50, a=0.45, speed=0.8, size=0.9, add=True)
    flash(ctx, 0.18 * bump(t, SEAL_T, 0.14), hx("#fff3d6"))


# --------------------------------------------------------------------------
# Scene 4 — HADISNING MAZMUNI (12.04 – 13.53): the next scene lives inside
#   the letters; we zoom through a letter into it.
# --------------------------------------------------------------------------
TW4 = wt("Hadisning mazmuni:", 12.19, 13.48)
T45 = 13.53


def cam8(t):
    """P8 camera shared by scene 4 (static start frame) and scene 5."""
    pic = G["p8"]
    ea = e_io(prog(t, T45, 1.65))
    camA = cam_cover(pic, lerp(560, 920, ea), 600, z=1.0 + 0.05 * ea)
    eb = e_io(prog(t, 15.15, 1.05))
    if eb <= 0:
        return camA
    box = (540 - 470, 880 - 470, 540 + 470, 880 + 470)
    sB, txB, tyB = cam_cover(pic, 780, 560, z=1.03 + 0.012 * max(0, t - 16.2), box=box,
                             px=540, py=880)
    s, A = zoom_between(camA[0], (camA[1], camA[2]), sB, (txB, tyB), eb)
    return s, A[0], A[1]


def scene4(ctx, lt, t):
    bg_grad(ctx, hx("#080706"), hx("#15100a"))
    paint_lattice(ctx, 0.035, t)
    dust(ctx, t, GOLD_L, seed=14, n=36, a=0.3, speed=0.5, add=True)
    sz = G["mz_size"]
    sp = sprite("mazmuni:", "black", sz, WHITE)
    yb = 1060
    ox = 540 - sp.w / 2
    sx0, sy0 = ox - sp.pad, yb - sp.asc - sp.pad
    zx, zy = sx0 + G["mz_pt"][0], sy0 + G["mz_pt"][1]
    pz = prog(t, 13.12, T45 - 13.12)
    k = 70 ** e_in(pz) if pz > 0 else 1.0
    a_in = e_out(prog(t, TW4[1] - 0.12, 0.45))
    zin = 1.0 + 0.04 * (1 - a_in)
    if a_in > 0:
        ctx.push_group()
        paint_cam(ctx, G["p8"], cam8(T45))
        add_glow(ctx, 540, 900, 900, hx("#ffcf8a"), 0.12)
        src = ctx.pop_group()
        ctx.save()
        ctx.set_source(src)
        ctx.translate(zx, zy)
        ctx.scale(k * zin, k * zin)
        ctx.translate(-zx, -zy)
        ctx.mask_surface(sp.surf, sx0, sy0 + (1 - a_in) * 40)
        ctx.restore()
        if pz < 0.35:
            oa = (1 - pz / 0.35) * a_in
            ctx.save()
            ctx.translate(zx, zy)
            ctx.scale(k * zin, k * zin)
            ctx.translate(-zx, -zy)
            outline_text(ctx, "mazmuni:", "black", sz, GOLD_L, ox, yb + (1 - a_in) * 40,
                         alpha=0.85 * oa, width=2)
            ctx.restore()
        # shine sweep across the letters
        sw = prog(t, TW4[1] + 0.25, 0.7)
        if 0 < sw < 1 and pz <= 0:
            xs = lerp(ox - 200, ox + sp.w + 200, e_io(sw))
            ctx.save()
            g = cairo.LinearGradient(xs - 120, 0, xs + 120, 0)
            g.add_color_stop_rgba(0, 1, 1, 1, 0)
            g.add_color_stop_rgba(0.5, 1, 0.95, 0.85, 0.55)
            g.add_color_stop_rgba(1, 1, 1, 1, 0)
            ctx.set_source(g)
            ctx.set_operator(cairo.OPERATOR_ADD)
            ctx.mask_surface(sp.surf, sx0, sy0)
            ctx.restore()
    # faint outline of the word waits for it to be spoken
    pre = 0.32 * e_out(prog(t, 12.1, 0.6)) * (1 - a_in)
    if pre > 0:
        outline_text(ctx, "mazmuni:", "black", sz, GOLD, ox, yb + 18 * (1 - prog(t, 12.1, 1.0)),
                     alpha=pre, width=2)
    fa = 1 - e_in(prog(t, 13.1, 0.3))
    rich(ctx, t, [W_("Hadisning", TW4[0], "light", 66, CREAM)], 540, 800, alpha=fa,
         space_key="light")
    if fa > 0:
        lw = 220 * e_io(prog(t, TW4[0] + 0.1, 0.6))
        ctx.set_source_rgba(*GOLD[:3], 0.8 * fa)
        ctx.set_line_width(2)
        ctx.move_to(540 - lw, 842)
        ctx.line_to(540 + lw, 842)
        ctx.stroke()


# --------------------------------------------------------------------------
# Scene 5 — CHIROYLI XULQ / ZIYNAT (13.53 – 18.52): respect -> the picture is
#   set into an eight-pointed star that draws itself; ornament blooms on
#   "ziynatlantiradi".
# --------------------------------------------------------------------------
TW5a = wt("Hayo chiroyli xulq bo‘lib,", 13.58, 15.10)
TW5b = wt("Alloh xohlagan bandasini", 15.20, 16.76)
TW5c = wt("u bilan ziynatlantiradi.", 17.08, 18.33)
SC5 = (540, 880)


def scene5(ctx, lt, t):
    cx, cy = SC5
    eb = e_io(prog(t, 15.15, 1.05))
    Rr = lerp(1500, 452, eb)
    if eb > 0:
        bg_grad(ctx, EMER_T, EMER_B)
        paint_lattice(ctx, 0.06, t, rot=0.0)
        add_glow(ctx, cx, cy, 900, hx("#1f8a6a"), 0.25)
        dust(ctx, t, GOLD_L, seed=15, n=40, a=0.35, speed=0.5, add=True)
    cam = cam8(t)
    ctx.save()
    if eb > 0:
        star8_path(ctx, cx, cy, Rr, -math.pi / 2 + t * 0.03)
        ctx.clip()
    paint_cam(ctx, G["p8"], cam)
    if eb < 1:
        vgrad(ctx, 860, 160, 0, 0.92 * (1 - eb), hx("#0b0805"))
    add_glow(ctx, *to_screen(cam, 1013, 366), 360, hx("#ffd9a0"), 0.10 + 0.08 * eb)
    ctx.restore()
    # star outline + ornament bloom
    rot = -math.pi / 2 + t * 0.03
    po = prog(t, 15.5, 1.15)
    if po > 0:
        gold_stroke(ctx, lambda: star8_path(ctx, cx, cy, Rr + 4, rot), po, width=3.2)
    pz = prog(t, TW5c[2] - 0.1, 1.0)
    if pz > 0:
        e = e_io(pz)
        gold_stroke(ctx, lambda: star8_path(ctx, cx, cy, Rr * 1.11, rot + math.pi / 8), e,
                    width=1.6, a=0.85, glow_w=8)
        ctx.new_path()
        ctx.arc(cx, cy, Rr * 1.18, rot, rot + 2 * math.pi)
        ctx.set_source_rgba(*GOLD[:3], 0.7)
        ctx.set_line_width(1.4)
        stroke_partial(ctx, e)
        for k in range(48):
            if k / 48 > e:
                break
            an = rot + k * 2 * math.pi / 48
            ctx.set_source_rgba(*GOLD_L[:3], 0.9)
            ctx.arc(cx + Rr * 1.15 * math.cos(an), cy + Rr * 1.15 * math.sin(an), 2.2, 0,
                    2 * math.pi)
            ctx.fill()
        for k in range(8):
            q = prog(pz, 0.15 + k * 0.06, 0.4)
            if q <= 0:
                continue
            an = rot + k * math.pi / 4
            px, py = cx + Rr * 1.0 * math.cos(an), cy + Rr * 1.0 * math.sin(an)
            tw_ = 0.5 + 0.5 * math.sin(t * 6 + k)
            add_glow(ctx, px, py, 60 + 30 * tw_, GOLD_L, 0.55 * q)
            ctx.set_source_rgba(1, 0.97, 0.88, 0.9 * q)
            L_ = 26 * q * (0.7 + 0.3 * tw_)
            ctx.set_line_width(1.6)
            ctx.move_to(px - L_, py)
            ctx.line_to(px + L_, py)
            ctx.move_to(px, py - L_)
            ctx.line_to(px, py + L_)
            ctx.stroke()
        sparks(ctx, cx, cy - 40, prog(t, TW5c[2] + 0.05, 0.8), seed=9, n=20, reach=520,
               color=GOLD_L)
    # text -------------------------------------------------------------------
    ea = 1 - e_in(prog(t, 15.0, 0.35))
    rich(ctx, t, [W_("Hayo", TW5a[0], "serif_it_b", 92, GOLD_L, grad=GG),
                  W_("chiroyli", TW5a[1], "med", 64), W_("xulq", TW5a[2], "med", 64),
                  W_("bo‘lib,", TW5a[3], "med", 64)], 540, 352, alpha=ea, shadow=18,
         space_key="med", dy=-30 * (1 - ea))
    rich(ctx, t, [W_("Alloh", TW5b[0], "serif_it_b", 84, GOLD_L, grad=GG),
                  W_("xohlagan", TW5b[1], "light", 60),
                  W_("bandasini", TW5b[2], "light", 60)], 540, 352, shadow=12,
         space_key="light")
    rich(ctx, t, [W_("u", TW5c[0], "light", 60), W_("bilan", TW5c[1], "light", 60),
                  W_("ziynatlantiradi.", TW5c[2], "serif_it_b", 84, GOLD_L, grad=GG, glow=16,
                     glow_color=GOLD)], 530, 1452, shadow=12, space_key="light")


# --------------------------------------------------------------------------
# Scene 6 — TUG‘MA (18.52 – 20.55): widescreen card, rack focus friends -> him
# --------------------------------------------------------------------------
TW6 = wt("U tabiatan tug‘ma bo‘lishi", 18.72, 20.43)
CARD6 = (0, 560, 1080, 560 + 818)


def scene6(ctx, lt, t):
    pic = G["p7"]
    bg = G["p7bg"]
    sb = max(W / bg.w, H / bg.h) * (1.1 + 0.02 * lt)
    paint_pic(ctx, bg, sb, W / 2 - bg.w * sb * 0.4, H / 2 - bg.h * sb / 2)
    fill(ctx, (0.02, 0.02, 0.03, 0.12))
    bokeh(ctx, t, hx("#d8e8c0"), seed=61, n=10, a=0.09, rmin=40, rmax=120)
    x0, y0, x1, y1 = CARD6
    ctx.set_source_rgba(0, 0, 0, 0.45)
    ctx.rectangle(x0, y0 + 14, x1 - x0, y1 - y0)
    ctx.fill()
    z = 1.0 + 0.06 * e_io(prog(t, 18.4, 2.3))
    cam = cam_cover(pic, lerp(800, 640, e_io(prog(t, 18.4, 2.3))), 576, z=z, box=CARD6,
                    px=540, py=(y0 + y1) / 2)
    ctx.save()
    ctx.rectangle(x0, y0, x1 - x0, y1 - y0)
    ctx.clip()
    paint_cam(ctx, pic, cam)
    # rack focus: blurred layer masked by a radial hole around the focus point
    e = e_io(prog(t, 19.15, 0.75))
    fxs, fys = to_screen(cam, lerp(1351, 560, e), lerp(470, 560, e))
    s, tx, ty = cam
    blur = G["p7b"]
    kb = s * pic.w / blur.w
    ctx.push_group()
    paint_pic(ctx, blur, kb, tx, ty)
    blur_src = ctx.pop_group()
    m = cairo.RadialGradient(fxs, fys, 150, fxs, fys, 470)
    m.add_color_stop_rgba(0, 0, 0, 0, 0)
    m.add_color_stop_rgba(1, 0, 0, 0, 1)
    ctx.set_source(blur_src)
    ctx.mask(m)
    # friends cool, him warm
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_SOFT_LIGHT)
    glow(ctx, *to_screen(cam, 560, 520), 420, hx("#ffc48a"), 0.45 * e)
    ctx.restore()
    ctx.restore()
    ctx.set_source_rgba(*GOLD_L[:3], 0.55)
    ctx.set_line_width(1.5)
    ctx.move_to(0, y0)
    ctx.line_to(W, y0)
    ctx.move_to(0, y1)
    ctx.line_to(W, y1)
    ctx.stroke()
    # text
    rich(ctx, t, [W_("U", TW6[0], "light", 66), W_("tabiatan", TW6[1], "light", 66)],
         540, 352, shadow=12, space_key="light")
    hp = prog(t, TW6[2] - 0.05, 0.6)
    pulse = 1 + 0.07 * bump(t, TW6[2] + 0.1, 0.5)
    if hp > 0:
        e2 = e_out(hp)
        text(ctx, "tug‘ma", "serif_it_b", 128, GOLD_L, 470, 488 + (1 - e2) * 30, alpha=e2,
             align="c", grad=GG, glow=18, glow_a=0.6 * e2, glow_color=GOLD, scale=pulse,
             shadow=14)
    rich(ctx, t, [W_("bo‘lishi", TW6[3], "light", 66)], 796, 488, shadow=12)
    dust(ctx, t, CREAM, seed=16, n=26, a=0.3, speed=0.5, add=True)


# --------------------------------------------------------------------------
# Scene 7 — NAFS (20.55 – 22.33): cold neon temptation, glitch; his raised
#   palm stops it (shockwave), the frame warms.
# --------------------------------------------------------------------------
TW7 = wt("yoki unga nafsni jilovlab,", 20.67, 22.16)
HIT7 = TW7[3] - 0.04


def cam7(t):
    punch = 1 + 0.05 * (1 - e_out(prog(t, HIT7, 0.5))) * (t >= HIT7)
    return cam_cover(G["p4c"], lerp(880, 840, prog(t, 20.4, 2.0)), 560,
                     z=(1.05 + 0.02 * prog(t, 20.4, 2.0)) * punch, px=540, py=960)


def scene7(ctx, lt, t):
    cam = cam7(t)
    warm = e_out(prog(t, HIT7, 0.45))
    paint_cam(ctx, G["p4c"], cam)
    if warm > 0:
        paint_cam(ctx, G["p4w"], cam, warm)
    ph_x, ph_y = to_screen(cam, 850, 1030)
    hd_x, hd_y = to_screen(cam, 676, 760)
    cold = 1 - warm
    if cold > 0:
        add_glow(ctx, ph_x, ph_y, 420, NEON_P, 0.30 * cold * (0.8 + 0.2 * math.sin(t * 30)))
        add_glow(ctx, ph_x, ph_y, 200, NEON_C, 0.30 * cold)
        social_icons(ctx, t - 20.35, seed=71, n=18, t_range=(0.0, 1.25),
                     region=(260, 760, 1380, 1700), a=cold)
        scanlines(ctx, 0.10 * cold)
        amt = cold * (0.22 + 0.4 * max(0, math.sin(t * 17)) ** 6)
        glitch(ctx.get_target(), amt, int(t * 30) + 7)
    shockwave(ctx, hd_x, hd_y, prog(t, HIT7, 0.75), GOLD_L, rmax=900, width=5)
    shockwave(ctx, hd_x, hd_y, prog(t, HIT7 + 0.12, 0.75), WARM, rmax=700, width=3)
    add_glow(ctx, hd_x, hd_y, 360, GOLD_L, 0.6 * bump(t, HIT7, 0.4))
    vgrad(ctx, 700, 140, 0, 0.78, NAVY)
    vignette(ctx, 0.45)
    rich(ctx, t, [W_("yoki", TW7[0], "light", 56), W_("unga", TW7[1], "light", 56)], 470, 312,
         shadow=12, space_key="light")
    na = prog(t, TW7[2] - 0.05, 0.25)
    if na > 0:
        if t < HIT7:
            glitch_text(ctx, "nafsni", "black", 134, 470, 450, na, 1.0, t)
        else:
            text(ctx, "nafsni", "black", 134, CREAM, 470, 450, alpha=1, align="c", shadow=16)
    jp = prog(t, HIT7, 0.32)
    if jp > 0:
        e = e_out5(jp)
        text(ctx, "jilovlab,", "serif_it_b", 112, GOLD_L, 470, 586, alpha=clamp(jp * 3),
             align="c", grad=GG, glow=18, glow_a=0.7, glow_color=GOLD, scale=lerp(1.6, 1.0, e),
             shadow=16)
    flash(ctx, 0.35 * bump(t, HIT7, 0.16), hx("#fff1dc"))


# --------------------------------------------------------------------------
# Scene 8 — MASHAQQAT (22.33 – 24.80): words climb a staircase to the summit
# --------------------------------------------------------------------------
TW8a = [22.51]
TW8b = wt("mashaqqat ila erishilishi mumkin.", 23.02, 24.67)
STEPS = [("tirishib,", TW8a[0], "semi", 70, CREAM, None, 92, 1415),
         ("mashaqqat", TW8b[0], "serif_it_b", 80, CREAM, None, 170, 1235),
         ("ila", TW8b[1], "semi", 70, CREAM, None, 262, 1058),
         ("erishilishi", TW8b[2], "semi", 72, GOLD_L, GG, 338, 882),
         ("mumkin.", TW8b[3], "serif_it_b", 92, GOLD_L, GG, 432, 700)]


def cam8s(t):
    e = e_io(prog(t, 22.1, 2.9))
    pic = G["p3"]
    s = max(W / pic.w, H / pic.h) * 1.12
    tx = 540 - 700 * s
    ty = lerp(H - pic.h * s, 0, e)
    return s, tx, ty


def scene8(ctx, lt, t):
    cam = cam8s(t)
    paint_cam(ctx, G["p3"], cam)
    sx, sy = to_screen(cam, 410, 720)
    win = e_out(prog(t, TW8b[3] - 0.05, 0.9))
    flare(ctx, sx, sy, 0.35 + 0.65 * win, t, streak=1100)
    light_leak(ctx, t, 0.5 + 0.5 * win, seed=6)
    vgrad(ctx, 1000, 1700, 0, 0.45, hx("#140804"))
    # the zigzag path linking steps
    pts = []
    for w_, t0, k, sz, col, gr, x, y in STEPS:
        wd = tw(w_, k, sz)
        pts.append((x - 22, y + 26, x + wd + 22, t0))
    pl = 0.0
    for i, (a, b, c, t0) in enumerate(pts):
        if t >= t0 - 0.1:
            pl = i + clamp((t - t0 + 0.1) / 0.35)
    if pl > 0:
        def path():
            for i, (a, b, c, t0) in enumerate(pts):
                if i == 0:
                    ctx.move_to(a, b)
                else:
                    ctx.line_to(a, b)
                ctx.line_to(c, b)
        n = len(pts)
        gold_stroke(ctx, path, clamp(pl / n), width=3, a=0.95, glow_w=10)
    for i, (w_, t0, k, sz, col, gr, x, y) in enumerate(STEPS):
        q = prog(t, t0 - 0.08, 0.5)
        if q <= 0:
            continue
        e = e_back(q) if q > 1e-3 else 0
        wd = tw(w_, k, sz)
        pa = clamp(q * 3)
        ctx.set_source_rgba(0.03, 0.02, 0.02, 0.42 * pa)
        round_rect(ctx, x - 22, y - sz * 0.92, wd + 44, sz * 1.18, 10)
        ctx.fill()
        jit = 0.0
        if w_ == "mashaqqat":
            jit = 5 * (1 - prog(t, t0, 0.5)) * math.sin(t * 70)
        text(ctx, w_, k, sz, col, x + jit, y - (1 - e) * 70, alpha=pa, grad=gr, shadow=12,
             glow=14 if gr else 0, glow_color=GOLD, glow_a=0.6)
        add_glow(ctx, x + wd / 2, y + 26, 120, GOLD_L, 0.5 * bump(t, t0, 0.4))
    dust(ctx, t, hx("#ffd9a8"), seed=18, n=30, a=0.35, speed=0.6, add=True)


# --------------------------------------------------------------------------
# Scene 9 — ALLOHDAN HAYO (24.80 – 28.07): mihrab-arch window, light descends
# --------------------------------------------------------------------------
TW9 = wt("Hayoning afzali – Allohdan hayo qilishdir.", 24.92, 28.00)
ARCH = (130, 950, 790, 420, 1250)  # x0, x1, spring, apex, bottom


def arch(ctx, grow=0.0):
    x0, x1, sp, ap, bt = ARCH
    arch_path(ctx, x0 - grow, x1 + grow, sp, ap - grow, bt + grow)


def scene9(ctx, lt, t):
    bg_grad(ctx, INDIGO_T, INDIGO_B)
    paint_lattice(ctx, 0.05, t, drift=(-4, 6))
    add_glow(ctx, 540, 820, 900, hx("#2b4aa0"), 0.25)
    x0, x1, sp, ap, bt = ARCH
    e = e_io(prog(t, 24.6, 3.2))
    pic = G["p2"]
    box = (x0, ap, x1, bt)
    cam = cam_cover(pic, lerp(700, 760, e), lerp(1080, 600, e), z=1.5 - 0.06 * e, box=box,
                    px=540, py=(ap + bt) / 2)
    ctx.save()
    arch(ctx)
    ctx.clip()
    paint_cam(ctx, pic, cam)
    rays = 0.08 + 0.2 * e_io(prog(t, TW9[2] - 0.2, 1.2))
    god_rays(ctx, t, 540, ap - 120, rays, hx("#ffe6b0"), n=10, seed=19, ang0=1.2, ang1=1.94,
             length=1700)
    dust(ctx, t, hx("#fff0c8"), seed=20, n=40, a=0.55, speed=0.4, add=True)
    vgrad(ctx, bt - 260, bt, 0, 0.55, INDIGO_T)
    ctx.restore()
    po = prog(t, 24.8, 1.1)
    gold_stroke(ctx, lambda: arch(ctx, 10), po, width=3)
    gold_stroke(ctx, lambda: arch(ctx, 24), prog(t, 25.0, 1.2), width=1.3, a=0.7, glow_w=6)
    # small star finial on the apex
    fq = prog(t, 25.6, 0.5)
    if fq > 0:
        ctx.set_source_rgba(*GOLD_L[:3], fq)
        ctx.set_line_width(2)
        star8_path(ctx, 540, ap - 64, 18 * e_back(fq) + 0.1)
        ctx.stroke()
        add_glow(ctx, 540, ap - 64, 70, GOLD_L, 0.4 * fq)
    rich(ctx, t, [W_("Hayoning", TW9[0], "light", 56), W_("afzali", TW9[1], "light", 56),
                  W_("–", TW9[1] + 0.15, "light", 56)], 540, 318, shadow=10, space_key="light")
    rich(ctx, t, [W_("Allohdan", TW9[2], "serif_it_b", 104, GOLD_L, grad=GG, glow=16,
                     glow_color=GOLD),
                  W_("hayo", TW9[3], "serif_it_b", 104, GOLD_L, grad=BLUSH_GG, glow=16,
                     glow_color=BLUSH)], 540, 1368, shadow=14, dur=0.7)
    rich(ctx, t, [W_("qilishdir.", TW9[4], "light", 60)], 540, 1452, shadow=10)


# --------------------------------------------------------------------------
# Scene 10 — AQL / QORIN / EZGULIK (28.07 – 36.75): a triptych that builds
#   with the sentence, unites in one frame, then gets "attention" brackets.
# --------------------------------------------------------------------------
TWa = wt("Ya’ni banda aqli va tushunchalarini,", 28.15, 30.20)
TWb = wt("qorni va ezguliklarini", 30.57, 31.94)
TWc = wt("Allohdan hayo qilgan holda", 32.03, 33.67)
TWd = wt("tasarruf etadi,", 33.99, 34.88)
TWe = wt("ularga e’tiborli bo‘ladi.", 35.30, 36.57)
STRIP_X0, STRIP_X1 = 60, 1020
STRIPS = [  # y0, y1, pic key, (fx0, fx1), fy, z, enter time, from-dir
    (590, 880, "t1", (600, 820), 565, 1.12, 28.05, -1),
    (902, 1192, "t5", (780, 560), 880, 1.06, TWb[0] - 0.3, 1),
    (1214, 1504, "t2", (720, 600), 1135, 1.05, TWc[0] - 0.25, -1),
]
UNITE = TWd[0] - 0.05


def scene10(ctx, lt, t):
    bg_grad(ctx, SEPIA_T, SEPIA_B)
    paint_lattice(ctx, 0.03, t)
    dust(ctx, t, GOLD_L, seed=22, n=40, a=0.3, speed=0.4, add=True)
    zs = 1.0 + 0.012 * lt
    ctx.save()
    ctx.translate(540, 1050)
    ctx.scale(zs, zs)
    ctx.translate(-540, -1050)
    col = e_io(prog(t, UNITE, 0.9))
    for i, (y0, y1, key, (fa, fb), fy, z, te, d) in enumerate(STRIPS):
        q = e_out5(prog(t, te, 0.7))
        if q <= 0:
            continue
        off = d * (1 - q) * (W + 80)
        x0, x1 = STRIP_X0 + off, STRIP_X1 + off
        ps = prog(t, te, 36.75 - te)
        box = (x0, y0, x1, y1)
        pic = G[key + "s"]
        cam = cam_cover(pic, lerp(fa, fb, ps), fy, z=z, box=box, px=(x0 + x1) / 2,
                        py=(y0 + y1) / 2)
        ctx.save()
        ctx.rectangle(x0, y0, x1 - x0, y1 - y0)
        ctx.clip()
        paint_cam(ctx, pic, cam)
        if col > 0:
            paint_cam(ctx, G[key + "c"], cam, col)
        # light sweep down the stack when it unites
        sw = prog(t, UNITE + i * 0.12, 0.7)
        if 0 < sw < 1:
            yy = lerp(y0 - 200, y1 + 200, e_io(sw))
            g = cairo.LinearGradient(0, yy - 150, 0, yy + 150)
            g.add_color_stop_rgba(0, 1, 0.9, 0.7, 0)
            g.add_color_stop_rgba(0.5, 1, 0.92, 0.75, 0.35)
            g.add_color_stop_rgba(1, 1, 0.9, 0.7, 0)
            ctx.set_source(g)
            ctx.set_operator(cairo.OPERATOR_ADD)
            ctx.paint()
            ctx.set_operator(cairo.OPERATOR_OVER)
        ctx.restore()
        ctx.set_source_rgba(*GOLD[:3], 0.55 * q)
        ctx.set_line_width(1.5)
        ctx.rectangle(x0, y0, x1 - x0, y1 - y0)
        ctx.stroke()
        add_glow(ctx, x0 if d > 0 else x1, (y0 + y1) / 2, 200, GOLD_L, 0.4 * bump(t, te, 0.6))
        # attention brackets
        bq = prog(t, TWe[0] + i * 0.16, 0.45)
        brackets(ctx, x0 + 18, y0 + 18, x1 - 18, y1 - 18, bq, GOLD_L, a=0.95)
        add_glow(ctx, (x0 + x1) / 2, (y0 + y1) / 2, 380, GOLD_L, 0.12 * bump(t, TWe[0] + i * 0.16,
                                                                              0.5))
    # uniting gold frame
    pf = prog(t, UNITE, 0.9)
    if pf > 0:
        def frame():
            ctx.rectangle(STRIP_X0 - 22, 568, STRIP_X1 - STRIP_X0 + 44, 1526 - 568)
        gold_stroke(ctx, frame, e_io(pf), width=2.6)
    ctx.restore()
    # text slot (top) --------------------------------------------------------
    def slot(alpha_in_t0, alpha_out_t0):
        a = e_out(prog(t, alpha_in_t0, 0.3)) * (1 - e_in(prog(t, alpha_out_t0, 0.3)))
        dy = -40 * e_in(prog(t, alpha_out_t0, 0.3))
        return a, dy
    a, dy = slot(27.9, TWb[0] - 0.35)
    rich(ctx, t, [W_("Ya’ni", TWa[0], "light", 60), W_("banda", TWa[1], "light", 60),
                  W_("aqli", TWa[2], "serif_it_b", 84, GOLD_L, grad=GG),
                  W_("va", TWa[3], "light", 60)], 540, 360, alpha=a, dy=dy, shadow=10,
         space_key="light")
    rich(ctx, t, [W_("tushunchalarini,", TWa[4], "serif_it_b", 84, GOLD_L, grad=GG)],
         540, 470, alpha=a, dy=dy, shadow=10)
    a, dy = slot(TWb[0] - 0.3, TWc[0] - 0.3)
    rich(ctx, t, [W_("qorni", TWb[0], "serif_it_b", 88, GOLD_L, grad=GG),
                  W_("va", TWb[1], "light", 60)], 540, 360, alpha=a, dy=dy, shadow=10,
         space_key="light")
    rich(ctx, t, [W_("ezguliklarini", TWb[2], "serif_it_b", 88, GOLD_L, grad=GG)], 540, 470,
         alpha=a, dy=dy, shadow=10)
    a, dy = slot(TWc[0] - 0.3, TWe[0] - 0.35)
    rich(ctx, t, [W_("Allohdan", TWc[0], "serif_it_b", 80, GOLD_L, grad=GG),
                  W_("hayo", TWc[1], "serif_it_b", 80, GOLD_L, grad=BLUSH_GG),
                  W_("qilgan", TWc[2], "light", 58), W_("holda", TWc[3], "light", 58)],
         540, 362, alpha=a, dy=dy, shadow=10, space_key="light")
    rich(ctx, t, [W_("tasarruf", TWd[0], "med", 64), W_("etadi,", TWd[1], "med", 64)],
         540, 466, alpha=a, dy=dy, shadow=10)
    a, dy = slot(TWe[0] - 0.3, 40.0)
    rich(ctx, t, [W_("ularga", TWe[0], "light", 62),
                  W_("e’tiborli", TWe[1], "serif_it_b", 92, GOLD_L, grad=GG, glow=14,
                     glow_color=GOLD),
                  W_("bo‘ladi.", TWe[2], "light", 62)], 540, 420, alpha=a, dy=dy, shadow=10,
         space_key="light")
    vignette(ctx, 0.45)


# --------------------------------------------------------------------------
# Scene 11 — O‘LIM (36.75 – 39.04): split — his thought (colour drains) above,
#   the graveyard rising from below; rain, lightning on "balolarni".
# --------------------------------------------------------------------------
TW11 = wt("O‘lim va turli balolarni eslaydi.", 36.92, 38.82)
SEAM = 960


def scene11(ctx, lt, t):
    fill(ctx, (0.02, 0.02, 0.03, 1))
    # top: his face
    box = (0, 0, W, SEAM)
    cam = cam_cover(G["p6c"], lerp(600, 640, prog(t, 36.6, 2.6)), 600,
                    z=1.38 + 0.05 * prog(t, 36.6, 2.6), box=box, px=540, py=SEAM / 2 + 40)
    gr = e_io(prog(t, 36.9, 1.4))
    ctx.save()
    ctx.rectangle(*box[:2], W, SEAM)
    ctx.clip()
    paint_cam(ctx, G["p6c"], cam)
    if gr > 0:
        paint_cam(ctx, G["p6g"], cam, gr)
    tint(ctx, COLD, 0.25 * gr, cairo.OPERATOR_SOFT_LIGHT)
    ctx.restore()
    # bottom: graveyard slides up
    up = e_out5(prog(t, 36.65, 0.7))
    y0 = SEAM + (1 - up) * (H - SEAM)
    box2 = (0, y0, W, y0 + (H - SEAM))
    cam2_ = cam_cover(G["p6g"], lerp(1520, 1600, prog(t, 36.6, 2.6)), 560, z=1.30,
                      box=box2, px=540, py=y0 + (H - SEAM) / 2)
    ctx.save()
    ctx.rectangle(0, y0, W, H - SEAM)
    ctx.clip()
    paint_cam(ctx, G["p6g"], cam2_)
    tint(ctx, COLD, 0.35, cairo.OPERATOR_SOFT_LIGHT)
    lt_hit = TW11[3] - 0.03
    fall(ctx, t, "rain", WHITE, seed=41, n=90, a=0.75, speed=1.0, wind=-60)
    fl = bump(t, lt_hit, 0.10) + 0.6 * bump(t, lt_hit + 0.16, 0.08)
    flash(ctx, 0.55 * fl, hx("#e9f0ff"))
    vgrad(ctx, y0 + 380, y0, 0, 0.55, (0, 0, 0))
    ctx.restore()
    # seam
    ctx.set_source_rgba(1, 1, 1, 0.75 * up)
    ctx.set_line_width(2)
    ctx.move_to(0, y0)
    ctx.line_to(W, y0)
    ctx.stroke()
    add_glow(ctx, 540, y0, 500, COLD, 0.15 * up)
    sh = 6 * bump(t, TW11[3], 0.3)
    # text
    p = prog(t, TW11[0] - 0.1, 0.9)
    if p > 0:
        e = e_out(p)
        trk = 6 + 22 * prog(t, TW11[0], 2.2)
        text(ctx, "O‘lim", "thin", 236, WHITE, 540 + sh * math.sin(t * 80), SEAM + 84,
             alpha=e, align="c", tracking=trk, shadow=22, shadow_a=0.6,
             scale=1.06 - 0.06 * e)
    rich(ctx, t, [W_("va", TW11[1], "light", 54), W_("turli", TW11[2], "light", 54),
                  W_("balolarni", TW11[3], "semi", 54), W_("eslaydi.", TW11[4], "light", 54)],
         540, SEAM + 196, shadow=12, space_key="light")
    vignette(ctx, 0.55)


# --------------------------------------------------------------------------
# Scene 12 — SIFATLANGAN INSON (39.04 – 41.60): medallion; colour blooms back
#   from his face; the sentence wraps around him like a halo.
# --------------------------------------------------------------------------
TW12 = wt("Bunday hayo bilan sifatlangan insonga", 39.25, 41.41)
MED = (540, 980, 372)
RING = "Bunday hayo bilan sifatlangan insonga"


def _ring_tables():
    tchars, colors, grads = [], [], []
    wi = 0
    for c in RING:
        if c == " ":
            wi += 1
        tchars.append(TW12[min(wi, len(TW12) - 1)])
        hay = RING.split(" ")[min(wi, 4)] == "hayo"
        colors.append(GOLD_L if hay else CREAM)
        grads.append(BLUSH_GG if hay else None)
    # letters inside a word follow each other quickly
    out, prev, k = [], None, 0
    for tt in tchars:
        k = k + 1 if tt == prev else 0
        out.append(tt + 0.025 * k)
        prev = tt
    return out, colors, grads


RING_T, RING_C, RING_G = _ring_tables()


def scene12(ctx, lt, t):
    cx, cy, r = MED
    warm = e_io(prog(t, 39.4, 1.6))
    bg_grad(ctx, lerpc(hx("#07080c"), hx("#120b07"), warm), lerpc(hx("#10131b"), hx("#24160b"),
                                                                    warm))
    bokeh(ctx, t, lerpc(COLD, hx("#ffc27a"), warm), seed=44, n=12, a=0.10, rmin=40, rmax=140)
    add_glow(ctx, cx, cy, 760, lerpc(COLD, hx("#ffb36b"), warm), 0.10 + 0.18 * warm)
    box = (cx - r, cy - r, cx + r, cy + r)
    z = 1.55 + 0.12 * prog(t, 38.8, 3.0)
    cam = cam_cover(G["p0g"], 1110, 520, z=z, box=box, px=cx, py=cy - 10)
    ctx.save()
    ctx.arc(cx, cy, r, 0, 2 * math.pi)
    ctx.clip()
    paint_cam(ctx, G["p0g"], cam)
    rb = e_out(prog(t, TW12[1] - 0.2, 1.5)) ** 1.3 * (r * 1.9)
    if rb > 1:
        ctx.save()
        fx, fy = to_screen(cam, 1110, 1000)
        ctx.arc(fx, fy, rb, 0, 2 * math.pi)
        ctx.clip()
        paint_cam(ctx, G["p0c"], cam)
        ctx.restore()
        ctx.set_line_width(3)
        ctx.set_source_rgba(*GOLD_L[:3], 0.8 * (1 - rb / (r * 1.9)))
        ctx.arc(fx, fy, rb, 0, 2 * math.pi)
        ctx.stroke()
        add_glow(ctx, fx, fy, rb * 1.1 + 60, hx("#ffcf8a"), 0.16 * (1 - rb / (r * 1.9)))
    ctx.restore()
    # medallion rings
    ctx.set_source_rgba(*GOLD_L[:3], 0.95)
    ctx.set_line_width(3.2)
    ctx.arc(cx, cy, r + 6, 0, 2 * math.pi)
    ctx.stroke()
    ctx.set_line_width(1.2)
    ctx.set_source_rgba(*GOLD[:3], 0.7)
    ctx.arc(cx, cy, r + 20, 0, 2 * math.pi)
    ctx.stroke()
    for k in range(60):
        an = k * 2 * math.pi / 60 - t * 0.08
        ctx.arc(cx + (r + 13) * math.cos(an), cy + (r + 13) * math.sin(an), 1.6, 0, 2 * math.pi)
        ctx.fill()
    # halo text
    arc_text(ctx, t, RING, "serif_it_b", 60, cx, cy, r + 52, -math.pi / 2 - 0.04 * lt,
             RING_T, RING_C, RING_G, glow=0)
    dust(ctx, t, lerpc(CREAM, GOLD_L, warm), seed=46, n=40, a=0.35, speed=0.5, add=True)
    vignette(ctx, 0.5)


# --------------------------------------------------------------------------
# Scene 13 — FINALE (41.60 – 46.50): tilt up with his gaze into the golden sky;
#   callback title + author.
# --------------------------------------------------------------------------
TW13 = wt("bandalaridan hayo etish osonroqdir.", 41.80, 43.84)
OUT_T = 44.05


def cam13(t):
    pic = G["p11x"]
    face = (1055, 494 + EXT11)
    e = e_io(prog(t, 41.3, 5.2))
    s = max(W / pic.w, H / pic.h) * lerp(1.22, 1.12, e)
    tx = 540 - lerp(1040, 1000, e) * s
    py = lerp(1180, 1520, e)
    ty = py - face[1] * s
    ty = min(0, max(H - pic.h * s, ty))
    tx = min(0, max(W - pic.w * s, tx))
    return s, tx, ty


def scene13(ctx, lt, t):
    cam = cam13(t)
    paint_cam(ctx, G["p11x"], cam)
    s, tx, ty = cam
    # living sky: drifting soft clouds in the grown sky, birds, sun light
    for k in range(6):
        cxk = (k * 260 + t * (14 + 3 * k)) % (W + 600) - 300
        cyk = ty + (120 + k * 120) * s
        soft_cloud(ctx, cxk, cyk, 340 + 40 * k, 70 + 10 * k, 0.07, hx("#ffe9d6"))
    flock(ctx, t - 41.6, n=4, y0=ty + 330 * s, dy=60, speed=90, size=26, a=0.55)
    light_leak(ctx, t, 0.6, seed=7)
    add_glow(ctx, 180, ty + 1450 * s, 700, hx("#ffb36b"), 0.30)
    god_rays(ctx, t, 140, ty + 1500 * s, 0.10, hx("#ffd9a0"), n=9, seed=27, ang0=-1.2,
             ang1=-0.2, length=2200)
    vgrad(ctx, 900, 200, 0, 0.35, hx("#1a1430"))
    # line 1-2
    out = 1 - e_in(prog(t, OUT_T, 0.45))
    dy = -50 * e_in(prog(t, OUT_T, 0.45))
    rich(ctx, t, [W_("bandalaridan", TW13[0], "light", 62),
                  W_("hayo", TW13[1], "serif_it_b", 112, GOLD_L, grad=BLUSH_GG, glow=16,
                     glow_color=BLUSH)], 540, 470, alpha=out, dy=dy, shadow=14,
         space_key="light")
    rich(ctx, t, [W_("etish", TW13[2], "med", 66), W_("osonroqdir.", TW13[3], "med", 66)],
         540, 572, alpha=out, dy=dy, shadow=14)
    # callback title
    cp = prog(t, OUT_T + 0.42, 1.0)
    if cp > 0:
        e = e_out(cp)
        add_glow(ctx, 540, 560, 600, hx("#ffd28a"), 0.22 * e)
        text(ctx, "Hayo", "serif_it_b", 210, WHITE, 540, 610 + (1 - e) * 40, alpha=e,
             align="c", grad=BLUSH_GG, glow=22, glow_a=0.55 * e, glow_color=BLUSH, shadow=22,
             scale=1.06 - 0.06 * e)
    chars_in(ctx, t, "naqadar goʻzal", "serif_it", 78, CREAM, 540, 716, OUT_T + 0.75,
             stagger=0.035, dur=0.6, blur=8, shadow=12)
    handle(ctx, t, OUT_T + 1.15, y=868)
    dust(ctx, t, hx("#fff1d8"), seed=48, n=40, a=0.45, speed=0.5, add=True)
    vignette(ctx, 0.3)


# --------------------------------------------------------------------------
SCENES = [
    (0.0, scene0),
    (2.33, scene1),
    (5.52, scene2),
    (8.29, scene3),
    (12.04, scene4),
    (13.53, scene5),
    (18.52, scene6),
    (20.55, scene7),
    (22.33, scene8),
    (24.80, scene9),
    (28.07, scene10),
    (36.75, scene11),
    (39.04, scene12),
    (41.60, scene13),
]

TRANS = {
    1: ("whip", 0.45, {"dir": "up"}),
    2: ("dissolve", 0.8, {"color": GOLD_L}),
    3: ("lightzoom", 0.55, {"x": 540, "y": 1100}),
    4: ("push", 0.45, {"dir": "up", "snap": True}),
    # 5: hard cut — scene 4 already zooms through a letter into scene 5
    6: ("blinds", 0.6, {"n": 9, "vertical": True}),
    7: ("glitchcut", 0.35),
    8: ("whip", 0.5, {"dir": "down"}),
    9: ("dissolve", 0.7, {"color": WARM}),
    10: ("luma", 0.5, {"angle": 1.25}),
    11: ("fade", 0.6),
    12: ("iris", 0.7, {"x": 540, "y": 960}),
    13: ("flare", 0.8, {"y": 820}),
}
