"""
Qutul qulub — "Qalblar ozuqasi" kitobi qayta nashri uchun reels (1080x1920, 30 fps).

Ovoz: azvuchka (qutul.m4a) + kitob promo-videosidagi musiqa (assets/audio/musiqa2.m4a, 0 s dan,
uning 20 s dagi bo'lim almashuvi hikoyadagi burilish bilan bir joyga tushadi), tools/mix_audio.py
bilan miks qilingan: output/qutul_qulub_audio.m4a (render.py uni o'zgartirmasdan ko'chiradi).

Asosiy motiv — muqovadagi YURAK: hookda u qorong'ida uradi, tushkunlikda EKG so'nadi va
yurak konturi chala qoladi ("nimadir yetishmasdi"), kitob topilganda o'sha bo'shliqni
muqovadagi yurak to'ldiradi. Rang hikoyasi: qizil-qorong'i hook -> oltin o'tmish ->
sovuq ko'k inqiroz -> oltin nur -> bugungi kun -> gulli yakun.

Reels xavfsiz zonasi: matnlar x 90..920, y 230..1480 (o'ngdagi tugmalar va pastki
izoh ostiga hech narsa qo'yilmaydi).
"""
import os

import render as R

R.configure(size=(1080, 1920), fps=30, dur=58.5)
from render import *  # noqa: F401,F403,E402

OUTPUT = "output/qutul_qulub.mp4"
POST = {"grain": 0.07, "fade_in": 0.0, "fade_out": 0.8}

TX0, TX1, TC = 90, 920, 505          # safe text column (right side kept free for Reels UI)

# --------------------------------------------------------------------------
# Spoken text (letter-for-letter from the brief) + approximate word timings.
# Phrase borders come from the voice pauses (tools/analyze_audio.py); words inside a
# phrase are spread by syllable count.
# --------------------------------------------------------------------------
SEG = {
    "A": ("Agar keyingi 15 soniyada bu videoni o‘tkazib yubormasangiz, hayotingizdagi eng "
          "to‘g‘ri qarorlardan birini qabul qilgan bo‘lasiz.", 0.57, 7.28, {"15": 2}),
    "B": ("Chunki hozir siz 1000 yillik qidiruvning yakunini bilib olasiz.", 7.73, 11.10,
          {"1000": 1}),
    "C": ("Imom G'azzoliy Mag'ribdan Mashriqqa dong'i ketgan buyuk olim edi.", 11.70, 16.00),
    "D": ("Insonlar u zotdan ilm o'rganish uchun minglab chaqirimlardan kelishardi.", 16.53, 20.00),
    "E": ("Shunday ilmning cho'qqisidagi bir olim", 20.68, 22.70),
    "F": ("bir kuni o'zini taftish qildi.", 22.91, 24.34),
    "G": ("Qattiq tushkunlikka tushdi. Amallaridan qalbi qoniqmadi,", 24.91, 28.12),
    "H": ("ibodatlarida nimadir yetishmasdi go'yo.", 28.56, 30.85),
    "I": ("Va Imom Gʻazoliyni bu kitob izlab topdi.", 31.48, 34.13),
    "J": ("Uni bu tushkunlik botqog'idan olib", 34.56, 36.55),
    "K": ('"Hujjatul islomga" aylantirdi.', 36.86, 38.34),
    "L": ("Bu kitob siz 1-sotuvida sotib olishga ulgurmagan Qutul qulub kitobi edi.", 38.81, 43.49,
          {"1-sotuvida": 7}),
    "M": ("Bu kitobni o'qishni tanlay olmaysiz. Kitob sizni tanlaydi.", 44.14, 47.40),
    "N": ("Biz bu kitobni qayta nashr qilyapmiz.", 47.95, 49.97),
    "O": ("Balki nasibangiz bordir...", 50.35, 51.79),
    "P": ("Tez kunda qayta sotuvda qalblar ozuqasi kitobi.", 52.42, 55.66),
}
WT = {k: word_times(v[0], v[1], v[2], v[3] if len(v) > 3 else None) for k, v in SEG.items()}


def ws(k, i, j=None):
    """Exact words i..j-1 of phrase k (never retyped by hand)."""
    words = SEG[k][0].split()
    return " ".join(words[i:(j if j is not None else i + 1)])


def wt(k, i):
    return WT[k][i][1]


# palette
INK = hx("#07040a")
CRIMSON = hx("#c0162b")
EMBER = hx("#ff7a4a")
COLD = hx("#dfe9f7")
COLD_A = hx("#8fb4ff")
TEAL = hx("#7fd6c2")
ROSE_L = hx("#ffc2cc")
CREAM = hx("#fff3df")

P = {}


# --------------------------------------------------------------------------
# Assets
# --------------------------------------------------------------------------
def _load(name, sharpen=True):
    im = Image.open(os.path.join(IDIR, name + ".png")).convert("RGB")
    if sharpen:
        im = im.filter(ImageFilter.UnsharpMask(radius=2.4, percent=70, threshold=2))
    return np.asarray(im)


def _heart_cutout(rgb):
    """Lift the anatomical heart off the white cover (fit a smooth model of the cover
    colour, keep everything that differs from it)."""
    x = rgb.astype(np.float32) / 255
    h, w = x.shape[:2]
    mx_, mn_ = x.max(2), x.min(2)
    sat = (mx_ - mn_) / (mx_ + 1e-4)
    lum = x @ np.array([0.299, 0.587, 0.114], np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    region = (xx > 680) & (xx < 1735) & (yy < 1590) & (yy > 25)

    def feats(X, Y):
        X, Y = X / 1000, Y / 1000
        return np.stack([np.ones_like(X), X, Y, X * X, X * Y, Y * Y, X ** 3, Y ** 3, X * X * Y,
                         X * Y * Y], -1)

    cand = region & (sat < 0.3) & (lum > 0.45)
    for _ in range(2):
        coef, *_ = np.linalg.lstsq(feats(xx[cand], yy[cand]), x[cand], rcond=None)
        d = np.linalg.norm(x - feats(xx, yy) @ coef, axis=2)
        cand = region & (d < 0.08) & (lum > 0.4)
    m = np.clip((d - 0.09) / 0.07, 0, 1) * region
    m[(xx < 860) & (yy < 680)] = 0
    m[(xx < 1000) & (yy > 1180)] = 0
    mi = Image.fromarray((m * 255).astype(np.uint8))
    mi = mi.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.MinFilter(3))
    mi = mi.filter(ImageFilter.GaussianBlur(1.3))
    return Pic(rgb, np.asarray(mi))


def _swamp(rgb):
    d = duotone(rgb, hx("#020a08"), hx("#9fd2bf"))
    return grade(d, contrast=1.12, gamma=1.0)


def prepare():
    warm = dict(sat=1.06, gain=(1.05, 1.0, 0.92), contrast=1.04)
    cold = dict(sat=0.32, gain=(0.82, 0.94, 1.14), contrast=1.08, gamma=1.12)
    for n in ("k1_00", "k1_02", "k2_00", "k3_00", "k3_11", "k1_30", "k3_20", "k2_40",
              "k3_30", "k3_31", "k1_32", "k1_22"):
        P[n] = Pic(grade(_load(n), **warm))
    k101 = _load("k1_01")
    P["k1_01"] = Pic(grade(k101, **warm))
    P["k1_01c"] = Pic(duotone(grade(k101, contrast=1.1), hx("#060b18"), hx("#c9dcff")))
    k110 = _load("k1_10")
    P["k1_10c"] = Pic(grade(k110, **cold))
    P["k1_10s"] = Pic(_swamp(k110))
    P["k2_10c"] = Pic(grade(_load("k2_10"), **cold))
    k321 = _load("k3_21")
    P["k3_21"] = Pic(grade(k321, sat=1.12, gain=(1.08, 1.0, 0.88), contrast=1.05))
    P["k3_21n"] = Pic(grade(k321, sat=0.55, gain=(0.30, 0.42, 0.78), contrast=1.1, gamma=1.45))
    P["k3_21d"] = Pic(grade(k321, sat=1.2, gain=(1.0, 0.62, 0.78), contrast=1.06, gamma=1.15))
    # three volumes, cropped from the "three books" panel
    k230 = _load("k2_30")
    for i, (x0, x1) in enumerate(((262, 1010), (1052, 1680), (1700, 2392))):
        P[f"book{i}"] = Pic(grade(k230[0:790, x0:x1], sat=1.04, contrast=1.03))
    rug = _load("k2_20")[:, 0:430]          # the prayer-rug ornament behind the press
    P["k2_30bg"] = Pic(blurred(grade(rug, sat=0.9, contrast=1.05), 5, 0.5, dark=0.42))
    macro = np.asarray(Image.open(os.path.join(IDIR, "heart_macro.png")).convert("RGB"))
    P["macro"] = Pic(grade(macro, sat=1.04, gain=(1.03, 1.0, 0.97)))
    P["heart"] = _heart_cutout(macro)
    P["k1_10blur"] = Pic(blurred(grade(k110, **cold), 18, 0.25, dark=0.5))
    for n, dk in (("k3_11", 0.40), ("k1_30", 0.42), ("k1_32", 0.40), ("k2_40", 0.24)):
        P[n + "b"] = Pic(blurred(P[n].rgb() if n in P else _load(n), 30, 0.25, dark=dk))


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
HEART_BODY = (1170, 990)       # heart centre in heart_macro / cutout pixels
K311_MACRO = (992, 0)          # macro pixel (mx, my) -> k3_11 pixel (mx/2 + 992, my/2)


def cover(ctx, pic, fx, fy, z=1.0, px=None, py=None, alpha=1.0, box=None):
    s, tx, ty = cam_cover(pic, fx, fy, z, px, py, box)
    if box:
        ctx.save()
        ctx.rectangle(box[0], box[1], box[2] - box[0], box[3] - box[1])
        ctx.clip()
    paint_pic(ctx, pic, s, tx, ty, alpha)
    if box:
        ctx.restore()
    return s, tx, ty


def scr(cam, x, y):
    s, tx, ty = cam
    return tx + x * s, ty + y * s


def fill(ctx, pic, z=1.0, alpha=1.0):
    """Blurred, darkened copy of a picture covering the frame (behind a band / card)."""
    s, tx, ty = cam_cover(pic, pic.w / 2, pic.h / 2, z)
    paint_pic(ctx, pic, s, tx, ty, alpha)


def band(ctx, pic, s, tx, ty, y0, y1, feather=70, alpha=1.0):
    """A landscape picture shown whole-width as a horizontal band with soft top/bottom edges
    (frees the rest of the vertical frame for type instead of cropping the picture to 9:16)."""
    ctx.save()
    ctx.push_group()
    paint_pic(ctx, pic, s, tx, ty)
    ctx.pop_group_to_source()
    f = clamp(feather / max(1, y1 - y0), 0, 0.45)
    g = cairo.LinearGradient(0, y0, 0, y1)
    g.add_color_stop_rgba(0, 0, 0, 0, 0)
    g.add_color_stop_rgba(f, 0, 0, 0, alpha)
    g.add_color_stop_rgba(1 - f, 0, 0, 0, alpha)
    g.add_color_stop_rgba(1, 0, 0, 0, 0)
    ctx.mask(g)
    ctx.restore()


def heart_pic(ctx, x, y, s, alpha=1.0):
    """Draw the cut-out heart with its body centre at screen (x, y)."""
    paint_pic(ctx, P["heart"], s, x - HEART_BODY[0] * s, y - HEART_BODY[1] * s, alpha, pad=False)


def fade_out(t, t0, d=0.3):
    return 1 - e_io(prog(t, t0, d))


def appear(t, t0, d=0.35):
    return e_out(prog(t, t0, d))


def slam(ctx, s, fkey, size, color, x, y, t, t0, align="l", s0=1.6, alpha=1.0, **kw):
    p = prog(t, t0, 0.32)
    if p <= 0:
        return
    sc = lerp(s0, 1.0, e_out5(p))
    text(ctx, s, fkey, size, color, x, y, alpha=alpha * clamp(p * 3), align=align, scale=sc, **kw)


def shake(t, hits, amp=18, dur=0.35):
    dx = dy = 0.0
    for h in hits:
        q = prog(t, h, dur)
        if 0 < q < 1:
            k = (1 - q) ** 2 * amp
            dx += k * math.sin(q * 61 + h)
            dy += k * math.cos(q * 47 + h * 3)
    return dx, dy


# ==========================================================================
# 0. SUPER HOOK
#    0.00-1.20  cold open: the whole story flashes past on the music hits, a giant "15"
#               hangs over it; on the 1.20 hit it collapses into the headline "15 soniyada"
#    1.20-7.6   the heart beats in the dark inside a 15-second countdown ring
#               (the ring then flies to the corner and keeps counting through scenes 1-2)
# ==========================================================================
HITS = [0.16, 0.63, 1.20, 2.66, 3.12, 5.16, 5.63, 6.09]            # music downbeats
HOOK_BEATS = [(h, 0.7) for h in HITS] + [(1.24, 1.2), (4.84, 1.5), (6.25, 0.6), (7.05, 0.9)]
FLASH = [(0.00, "macro", 1290, 940, 1.45), (0.16, "k1_10c", 900, 560, 1.30),
         (0.41, "k3_00", 1098, 330, 1.35), (0.63, "k3_21", 1300, 485, 1.25),
         (0.85, "k3_31", 1300, 420, 1.25)]
T_MAIN = 1.20


def _flash_shot(ctx, t):
    k = max(i for i, f in enumerate(FLASH) if f[0] <= t)
    t0, name, fx, fy, z = FLASH[k]
    t1 = FLASH[k + 1][0] if k + 1 < len(FLASH) else T_MAIN
    q = prog(t, t0, t1 - t0)
    punch = 1 + 0.10 * (1 - e_out(prog(t, t0, 0.14)))
    cover(ctx, P[name], fx, fy, z * (1 + 0.06 * q) * punch)
    vignette(ctx, 0.75)
    tint(ctx, CRIMSON, 0.18, cairo.OPERATOR_SOFT_LIGHT)
    flash(ctx, 0.55 * (1 - prog(t, t0, 0.09)) if t0 > 0 else 0, CREAM)


def _hook_heart(ctx, t):
    bg_grad(ctx, hx("#0d0507"), hx("#040203"), hx("#14070b"))
    pb = pulse(t, HOOK_BEATS, 0.15)
    hxp = 540 + 8 * math.sin(t * 0.6)
    hyp = lerp(1110, 1150, e_io(prog(t, 3.9, 1.0))) + 5 * math.sin(t * 0.7)
    s = lerp(0.56, 0.48, e_io(prog(t, 3.9, 1.0))) * (1 + 0.045 * pb)
    s *= 1 + 0.25 * (1 - e_out5(prog(t, T_MAIN, 0.45)))          # lands on the 1.20 hit
    glow(ctx, hxp, hyp - 40, 700, CRIMSON, 0.26 + 0.18 * pb)
    god_rays(ctx, t, hxp, hyp - 60, 0.05 + 0.06 * pb, EMBER, n=11, seed=7, ang0=0, ang1=6.28,
             length=1300)
    heart_pic(ctx, hxp, hyp, s)
    add_glow(ctx, hxp, hyp, 260, hx("#ff5a3c"), 0.07 + 0.24 * pb)
    shockwave(ctx, hxp, hyp, prog(t, 4.84, 1.2), color=hx("#ffb39c"), rmax=760, width=4)
    shockwave(ctx, hxp, hyp, prog(t, T_MAIN, 0.9), color=hx("#ffb39c"), rmax=620, width=3)
    sparks(ctx, hxp, hyp - 40, prog(t, 4.86, 0.8), seed=4, n=30, color=hx("#ffd2a6"), reach=520)
    sparks(ctx, hxp, hyp - 40, prog(t, T_MAIN + 0.02, 0.7), seed=9, n=24, color=hx("#ffd2a6"),
           reach=460)
    dust(ctx, t, hx("#ffcfa0"), seed=3, n=55, a=0.42, size=0.9, add=True)
    add_glow(ctx, hxp, hyp - 80, 900, EMBER, 0.55 * e_in(prog(t, 6.85, 0.9)))
    flash(ctx, 0.6 * (1 - prog(t, T_MAIN, 0.12)), CREAM)


def scene_hook(ctx, lt, t):
    if t < T_MAIN:
        _flash_shot(ctx, t)
    else:
        _hook_heart(ctx, t)
    vgrad(ctx, 140, 860, 0.55, 0)
    w15 = tw("15", "black", 300)
    # giant outlined "15" over the cold open, collapsing into the headline on the hit
    m = e_io(prog(t, T_MAIN - 0.04, 0.26))
    if m < 1:
        pb = pulse(t, [(h, 1.0) for h in HITS[:3]], 0.12)
        sp = sprite("15", "black", 860, GOLD_L, 0.0, None, 0, 7)
        k = 300 / 860
        x = lerp(540, TX0 - 6 + w15 / 2, m)
        y = lerp(1420, 690 + sp.asc * 0.35 * (1 - k), m)
        draw_sprite(ctx, sp, x, y, (0.85 + 0.15 * pb) * (1 - m), lerp(1.0 + 0.03 * pb, k, m),
                    align="c")
    # --- A: "Agar keyingi 15 soniyada" (readable from frame 0)
    xA = fade_out(t, 1.96, 0.14)
    if xA > 0:
        up = 40 * (1 - xA)
        text(ctx, ws("A", 0, 2), "semi", 58, WHITE, TX0, 360 - up, alpha=xA * appear(t, -0.1, 0.2),
             tracking=2, shadow=16)
        if t >= T_MAIN - 0.04:
            slam(ctx, "15", "black", 300, WHITE, TX0 - 6, 690 - up, t, T_MAIN - 0.04, grad=GG,
                 alpha=xA, glow=22, glow_a=0.5, glow_color=EMBER, s0=1.35)
            words_in(ctx, t, ws("A", 3), "serif_it", 96, CREAM, TX0 + w15 + 34, 640 - up,
                     wt("A", 3) - 0.08, align="l", blur_in=10, alpha=xA, dur=0.5)
    # --- B: "bu videoni o‘tkazib yubormasangiz,"
    if 2.06 <= t:
        xB = fade_out(t, 3.84, 0.12)
        if xB > 0:
            up = 40 * (1 - xB)
            words_in(ctx, t, ws("A", 4, 6), "med", 60, WHITE, TX0, 400 - up, 2.06, align="l",
                     stagger=0.1, dur=0.3, alpha=xB, tracking=1, shadow=12)
            sz = fit(ws("A", 6, 8), "xbold", 86, TX1 - TX0)
            if xB < 1:
                text(ctx, ws("A", 6, 8), "xbold", sz, WHITE, TX0, 510 - up, alpha=xB, grad=GG,
                     shadow=12)
            else:
                text_rise(ctx, ws("A", 6, 8), "xbold", sz, WHITE, TX0, 510,
                          prog(t, wt("A", 6) - 0.05, 0.35), grad=GG, shadow=12)
    # --- C: "hayotingizdagi ENG TO‘G‘RI qarorlardan birini qabul qilgan bo‘lasiz."
    if t >= 3.97:
        words_in(ctx, t, ws("A", 8), "light", 56, WHITE, TX0, 320, 3.97, align="l", tracking=3,
                 dur=0.35, shadow=10)
        sz = fit(ws("A", 9, 11), "black", 150, TX1 - TX0)
        slam(ctx, ws("A", 9, 11), "black", sz, WHITE, TX0 - 4, 480, t, wt("A", 9) - 0.04,
             grad=GG, glow=18, glow_a=0.4, glow_color=EMBER, s0=1.5, shadow=14)
        words_in(ctx, t, ws("A", 11, 13), "serif_it", 70, CREAM, TX0, 575, wt("A", 11) - 0.05,
                 align="l", stagger=0.22, blur_in=8)
        words_in(ctx, t, ws("A", 13, 16), "serif_it_b", 64, CREAM, TX0, 660, wt("A", 13) - 0.05,
                 align="l", stagger=0.2, blur_in=8, shadow=10)


# --- the 15-second promise: a countdown ring that outlives the hook --------------------------
T15 = 1.24                     # "15" is spoken here


def OVERLAY(ctx, t):
    el = t - T15
    if el < 0 or el > 15.9:
        return
    rem = max(0.0, 15.0 - el)
    m = e_io(prog(t, 6.85, 0.6))                      # big ring around the heart -> corner badge
    cx, cy, r = lerp(540, 900, m), lerp(1105, 288, m), lerp(330, 40, m)
    a = appear(t, T15, 0.35) * (1 - prog(t, T15 + 15.35, 0.5))
    if a <= 0:
        return
    ctx.save()
    if m > 0:
        ctx.set_source_rgba(0.03, 0.02, 0.02, 0.5 * m * a)
        ctx.arc(cx, cy, r + 10, 0, 2 * math.pi)
        ctx.fill()
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_width(2.0)
    ctx.set_source_rgba(*GOLD[:3], 0.35 * a)
    ctx.arc(cx, cy, r, 0, 2 * math.pi)
    ctx.stroke()
    if m < 1:
        for k in range(15):
            an = -math.pi / 2 + k * 2 * math.pi / 15
            ctx.set_line_width(3)
            ctx.set_source_rgba(*GOLD_L[:3], 0.55 * a * (1 - m))
            ctx.move_to(cx + (r - 14) * math.cos(an), cy + (r - 14) * math.sin(an))
            ctx.line_to(cx + (r - 2) * math.cos(an), cy + (r - 2) * math.sin(an))
            ctx.stroke()
    frac = rem / 15.0
    if frac > 0.002:
        ctx.set_line_width(lerp(6, 5, m))
        ctx.set_source_rgba(*GOLD_L[:3], 0.95 * a)
        ctx.arc(cx, cy, r, -math.pi / 2, -math.pi / 2 + 2 * math.pi * frac)
        ctx.stroke()
        an = -math.pi / 2 + 2 * math.pi * frac
        add_glow(ctx, cx + r * math.cos(an), cy + r * math.sin(an), lerp(60, 26, m), GOLD_L, 0.8 * a)
    if m > 0:
        if rem > 0:
            text(ctx, str(int(math.ceil(rem))), "semi", 34, WHITE, cx, cy + 12, alpha=a * m,
                 align="c")
        else:                                       # made it: the ring closes with a tick
            q = prog(t, T15 + 15.0, 0.4)
            ctx.set_line_width(5)
            ctx.set_source_rgba(*GOLD_L[:3], a)
            ctx.move_to(cx - 15, cy + 1)
            ctx.line_to(cx - 15 + 11 * min(1, q * 2), cy + 1 + 11 * min(1, q * 2))
            if q > 0.5:
                ctx.line_to(cx - 4 + 20 * (q - 0.5) * 2, cy + 12 - 24 * (q - 0.5) * 2)
            ctx.stroke()
            shockwave(ctx, cx, cy, prog(t, T15 + 15.0, 0.7), color=GOLD_L, rmax=160, width=2)
    ctx.restore()


# ==========================================================================
# 1. "1000 yillik qidiruv" — a thousand days and nights flicker past, ends at sunrise
# ==========================================================================
def scene_millennium(ctx, lt, t):
    z = lerp(1.26, 1.0, e_out(prog(lt, 0, 3.9)))
    px = lerp(600, 700, e_out(prog(lt, 0, 3.9)))
    py = lerp(960, 760, e_out(prog(lt, 0, 3.9)))
    tl0, tl1 = 8.22, 9.78
    if t < tl0:
        night, base = 0.0, "k3_21d"
    elif t < tl1:
        q = prog(t, tl0, tl1 - tl0)
        cyc = 9 * e_out(q)
        night = (0.5 - 0.5 * math.cos(cyc * 2 * math.pi)) * (1 - q ** 3)
        base = "k3_21d" if q < 0.15 else "k3_21"
    else:
        night, base = 0.0, "k3_21"
    cam = cover(ctx, P["k3_21d"] if base == "k3_21d" else P["k3_21"], 1500, 485, z, px, py)
    if t > tl1 - 0.4:
        cover(ctx, P["k3_21"], 1500, 485, z, px, py, alpha=e_io(prog(t, tl1 - 0.4, 0.6)))
    if night > 0.01:
        cover(ctx, P["k3_21n"], 1500, 485, z, px, py, alpha=night)
        stars(ctx, t, 21, 90, 760, a=0.9 * night)
    sx, sy = scr(cam, 1500, 485)
    flare(ctx, sx, sy, 0.35 + 0.9 * bump(t, 9.55, 1.6) * (1 - night), t, streak=1000)
    god_rays(ctx, t, sx, sy, 0.10 * (1 - night), GOLD_L, n=12, seed=3, ang0=0.0, ang1=6.28,
             length=1700)
    flock(ctx, lt + 2, n=3, y0=330, dy=70, speed=90, size=22, a=0.55 * (1 - night))
    vgrad(ctx, 120, 900, 0.82, 0)
    vgrad(ctx, 1080, 1560, 0, 0.8)
    # copy
    words_in(ctx, t, ws("B", 0, 3), "med", 48, WHITE, TX0, 300, wt("B", 0) - 0.05, align="l",
             tracking=2, stagger=0.1)
    if t > tl0 - 0.1:
        a = appear(t, tl0 - 0.1, 0.2)
        counter(ctx, t, tl0, tl1 - tl0 - 0.1, 0, 1000, "thin", 250, WHITE, TX0 - 8, 545,
                ease=e_out, alpha=a, tracking=4, glow=12, glow_a=0.25, glow_color=GOLD_L)
        wx = TX0 + tw("1000", "thin", 250, 4) + 22
        words_in(ctx, t, ws("B", 4), "serif_it_b", 88, GOLD_L, wx, 545, wt("B", 4) - 0.05,
                 align="l", blur_in=8, grad=GG)
    words_in(ctx, t, ws("B", 5), "light", 60, WHITE, TX0, 1225, wt("B", 5) - 0.05, align="l",
             tracking=3, blur_in=6)
    # bottom: the end of the search lands on the ground
    pY = prog(t, wt("B", 6) - 0.05, 0.6)
    if pY > 0:
        text_rise(ctx, ws("B", 6), "serif_it_b", 132, WHITE, TX0, 1335, pY, grad=GG, shadow=14)
        ww = tw(ws("B", 6), "serif_it_b", 132)
        ctx.set_source_rgba(*GOLD_L[:3], 0.9)
        ctx.set_line_width(4)
        ctx.move_to(TX0 + 6, 1366)
        ctx.line_to(TX0 + 6 + (ww - 12) * e_io(prog(t, wt("B", 6) + 0.15, 0.6)), 1366)
        ctx.stroke()
    words_in(ctx, t, ws("B", 7, 9), "reg", 56, WHITE, TX0, 1450, wt("B", 7) - 0.05, align="l",
             stagger=0.15, blur_in=6)


# ==========================================================================
# 2. "Imom G'azzoliy — Mag'ribdan Mashriqqa": one camera move west -> east
# ==========================================================================
def scene_west_east(ctx, lt, t):
    pan = e_io(prog(t, 12.55, 2.4))
    fx = lerp(1060, 1840, pan) + 40 * e_out(prog(lt, 0, 6))
    z = lerp(1.06, 1.12, prog(lt, 0, 5))
    cam = cover(ctx, P["k3_00"], fx, 560, z)
    sunx, suny = scr(cam, 2350, 300)
    light_leak(ctx, t, 0.6, seed=4)
    god_rays(ctx, t, sunx, suny - 300, 0.07, GOLD_L, n=8, seed=11, ang0=1.9, ang1=2.9)
    dust(ctx, t, GOLD_L, seed=8, n=40, a=0.4, add=True)
    vgrad(ctx, 120, 620, 0.62, 0)
    vgrad(ctx, 960, 1520, 0, 0.88)
    a = fade_out(t, 15.95, 0.3)
    # the route across the sky: an arc from the West to the East
    yE, yP = 470, 330
    pl = prog(t, wt("C", 2) - 0.05, 1.35)
    if pl > 0:
        e = e_io(pl)
        n = 60
        pts = []
        for k in range(n + 1):
            u = k / n * e
            x = lerp(TX0 + 10, TX1 - 10, u)
            y = yE - (yE - yP) * 4 * u * (1 - u)
            pts.append((x, y))
        ctx.save()
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_dash([3, 13])
        ctx.set_line_width(5)
        ctx.set_source_rgba(*GOLD_L[:3], 0.95 * a)
        ctx.move_to(*pts[0])
        for q in pts[1:]:
            ctx.line_to(*q)
        ctx.stroke()
        ctx.restore()
        ctx.set_source_rgba(*GOLD_L[:3], a)
        ctx.arc(pts[0][0], pts[0][1], 8, 0, 2 * math.pi)
        ctx.fill()
        hx_, hy_ = pts[-1]
        add_glow(ctx, hx_, hy_, 80, GOLD_L, 0.9 * a)
        ctx.set_source_rgba(1, 1, 1, a)
        ctx.arc(hx_, hy_, 7, 0, 2 * math.pi)
        ctx.fill()
        text(ctx, ws("C", 2), "semi", 50, WHITE, TX0, yE + 70,
             alpha=a * appear(t, wt("C", 2) - 0.05), tracking=2, shadow=12)
    if t > wt("C", 3) - 0.05:
        text(ctx, ws("C", 3), "semi", 50, WHITE, TX1, yE + 70,
             alpha=a * appear(t, wt("C", 3) - 0.05), align="r", tracking=2, shadow=12)
        q = prog(t, wt("C", 3) + 0.25, 0.6)
        ctx.set_source_rgba(*GOLD_L[:3], a * e_out(q))
        ctx.arc(TX1 - 10, yE, 10 * e_back(q) if q > 0 else 0, 0, 2 * math.pi)
        ctx.fill()
        shockwave(ctx, TX1 - 10, yE, q, color=GOLD_L, rmax=160, width=2)
    # name card at the bottom
    words_in(ctx, t, ws("C", 0), "med", 44, GOLD_L, TX0, 1140, wt("C", 0) - 0.05, align="l",
             tracking=12, alpha=a)
    sz = fit(ws("C", 1), "serif", 150, TX1 - TX0)
    chars_in(ctx, t, ws("C", 1), "serif", sz, WHITE, TX0, 1285, wt("C", 1) - 0.08, align="l",
             stagger=0.045, dur=0.7, blur=12, grad=GG, alpha=a, shadow=16)
    words_in(ctx, t, ws("C", 4, 6), "light", 46, WHITE, TX0, 1370, wt("C", 4) - 0.05, align="l",
             stagger=0.14, blur_in=6, alpha=a, tracking=2)
    words_in(ctx, t, ws("C", 6, 9), "serif_it_b", 84, GOLD_L, TX0, 1458, wt("C", 6) - 0.05,
             align="l", stagger=0.2, dur=0.8, blur_in=10, grad=GG, alpha=a, shadow=14)


# ==========================================================================
# 3. "Insonlar ... minglab chaqirimlardan kelishardi": three roads converge on one teacher
# ==========================================================================
STRIPS = (("k1_00", (420, 900), (820, 520)), ("k1_02", (830, 520), (830, 520)),
          ("k2_00", (980, 300), (1420, 560)))


def scene_converge(ctx, lt, t):
    bg_grad(ctx, INK, INK)
    ex = e_io(prog(t, 19.35, 0.75))              # middle strip takes the whole frame
    punch = 1 + 0.04 * pulse(t, [(16.94, 1.0), (18.30, 0.6)], 0.18)
    gap = 14
    w3 = (W - 2 * gap) / 3
    boxes = [(0, w3), (w3 + gap, 2 * w3 + gap), (2 * w3 + 2 * gap, W)]
    for i, ((name, f0, f1), (x0, x1)) in enumerate(zip(STRIPS, boxes)):
        drift = e_io(prog(lt, -0.3, 4.4))
        fx, fy = lerp(f0[0], f1[0], drift), lerp(f0[1], f1[1], drift)
        if i == 1:
            bx0, bx1 = lerp(x0, 0, ex), lerp(x1, W, ex)
        else:
            off = (-1 if i == 0 else 1) * W * 0.5 * e_in(prog(t, 19.35, 0.6))
            bx0, bx1 = x0 + off, x1 + off
        if bx1 < 0 or bx0 > W:
            continue
        z = (1.0 + 0.05 * drift) * punch * (1.12 if i != 1 else 1.0)
        cover(ctx, P[name], fx, fy, z, (bx0 + bx1) / 2, H / 2, box=(bx0, 0, bx1, H))
        if i != 1 and ex < 1:
            ctx.set_source_rgba(*GOLD_L[:3], 0.35 * (1 - ex))
            ctx.rectangle(bx1 if i == 0 else bx0 - 1.5, 0, 1.5, H)
            ctx.fill()
    # arrivals: light from the teacher once everyone has converged
    add_glow(ctx, 540, 640, 900, GOLD_L, 0.18 * ex)
    dust(ctx, t, GOLD_L, seed=12, n=45, a=0.4, add=True)
    vgrad(ctx, 100, 680, 0.92, 0)
    vgrad(ctx, 960, 1540, 0, 0.88)
    sa = appear(t, wt("D", 0) - 0.2, 0.4)
    if sa > 0:
        ctx.save()
        ctx.translate(TC, 375)
        ctx.scale(1.0, 0.36)
        g = cairo.RadialGradient(0, 0, 60, 0, 0, 520)
        g.add_color_stop_rgba(0, 0, 0, 0, 0.62 * sa)
        g.add_color_stop_rgba(1, 0, 0, 0, 0)
        ctx.set_source(g)
        ctx.arc(0, 0, 520, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()
    words_in(ctx, t, ws("D", 0, 3), "semi", 56, WHITE, TC, 320, wt("D", 0) - 0.05, stagger=0.12,
             tracking=1, blur_in=6, shadow=12)
    words_in(ctx, t, ws("D", 3, 6), "serif_it_b", 80, CREAM, TC, 420, wt("D", 3) - 0.05,
             stagger=0.15, blur_in=8, shadow=16)
    sz = fit(ws("D", 6), "black", 150, TX1 - TX0)
    slam(ctx, ws("D", 6), "black", sz, WHITE, TC, 1215, t, wt("D", 6) - 0.05, align="c",
         shadow=16, s0=1.5)
    sz = fit(ws("D", 7), "bold", 86, TX1 - TX0)
    scatter_in(ctx, t, ws("D", 7), "bold", sz, GOLD_L, TC, 1325, wt("D", 7) - 0.25, dur=1.0,
               spread=1100, seed=8, shadow=10)
    words_in(ctx, t, ws("D", 8), "serif_it", 84, CREAM, TC, 1440, wt("D", 8) - 0.05, dur=0.8,
             blur_in=10)


# ==========================================================================
# 4. "cho'qqisidagi bir olim" (climbing steps) -> "o'zini taftish qildi" (a scan turns him cold)
# ==========================================================================
STEPS = [(0, "light", 50, TX0, 1420), (1, "reg", 62, TX0 + 95, 1312), (2, "serif", 90, TX0 + 205,
                                                                         1192),
         (3, "black", 84, TX0 + 330, 1062)]


def _k101(ctx, t, pic):
    z = lerp(1.15, 1.24, e_io(prog(t, 20.2, 4.4)))
    return cover(ctx, pic, lerp(800, 860, prog(t, 20.2, 4.4)), 520, z, 540, 150)


def scene_summit(ctx, lt, t):
    cam = _k101(ctx, t, P["k1_01"])
    # inner audit: a scanning line passes and leaves him cold
    ys = lerp(-60, H + 60, e_io(prog(t, 22.88, 1.45)))
    if ys > 0:
        ctx.save()
        ctx.rectangle(0, 0, W, ys)
        ctx.clip()
        _k101(ctx, t, P["k1_01c"])
        ctx.restore()
        if ys < H + 40:
            g = cairo.LinearGradient(0, ys - 120, 0, ys + 4)
            g.add_color_stop_rgba(0, *COLD_A[:3], 0)
            g.add_color_stop_rgba(1, *COLD_A[:3], 0.35)
            ctx.set_source(g)
            ctx.rectangle(0, ys - 120, W, 124)
            ctx.fill()
            ctx.set_source_rgba(*COLD[:3], 0.95)
            ctx.rectangle(0, ys - 1.5, W, 3)
            ctx.fill()
            for k in range(0, W, 36):
                ctx.rectangle(k, ys - (9 if k % 180 == 0 else 5), 2, 18 if k % 180 == 0 else 10)
            ctx.fill()
            add_glow(ctx, W * 0.5, ys, 420, COLD_A, 0.35)
    dust(ctx, t, GOLD_L if ys < 900 else COLD, seed=5, n=35, a=0.35, add=True)
    vgrad(ctx, 820, 1380, 0, 0.9)
    # staircase to the summit
    a = fade_out(t, 22.72, 0.3)
    if a > 0:
        pts = []
        for i, fk, sz, x, y in STEPS:
            t0 = wt("E", i) - 0.05
            p = prog(t, t0, 0.5)
            if p > 0:
                color = GOLD_L if i == 2 else WHITE
                text(ctx, ws("E", i) if i < 3 else ws("E", 3, 5), fk, sz, color, x,
                     y + 40 * (1 - e_out(p)), alpha=a * e_out(p), grad=GG if i == 2 else None,
                     shadow=10)
                pts.append((x - 22, y + 22, t0))
        if len(pts) >= 2:
            ctx.set_line_width(3)
            ctx.set_line_join(cairo.LINE_JOIN_ROUND)
            ctx.set_source_rgba(*GOLD_L[:3], 0.85 * a)
            for (x0_, y0_, _), (x1_, y1_, t1_) in zip(pts, pts[1:]):
                q = e_io(prog(t, t1_ - 0.1, 0.4))
                ctx.move_to(x0_, y0_)
                ctx.line_to(x0_ + (x1_ - x0_) * q, y0_ + (y1_ - y0_) * q)
            ctx.stroke()
        if len(pts) == 4:
            pk = (pts[-1][0] + 430, pts[-1][1] - 150)
            q = e_io(prog(t, wt("E", 3) + 0.15, 0.5))
            ctx.set_source_rgba(*GOLD_L[:3], 0.85 * a)
            ctx.move_to(pts[-1][0], pts[-1][1])
            ctx.line_to(pts[-1][0] + (pk[0] - pts[-1][0]) * q, pts[-1][1] + (pk[1] - pts[-1][1]) * q)
            ctx.stroke()
            if q > 0.95:
                add_glow(ctx, pk[0], pk[1], 90, GOLD_L, a * (0.8 + 0.2 * math.sin(t * 9)))
    # self-audit copy
    words_in(ctx, t, ws("F", 0, 2), "light", 48, COLD, TX0, 1230, wt("F", 0) - 0.05, align="l",
             tracking=3, stagger=0.12)
    words_in(ctx, t, ws("F", 2), "serif_it", 116, WHITE, TX0, 1345, wt("F", 2) - 0.05, align="l",
             blur_in=10, shadow=12)
    words_in(ctx, t, ws("F", 3, 5), "bold", 76, COLD, TX0, 1448, wt("F", 3) - 0.05, align="l",
             stagger=0.15, shadow=10)


# ==========================================================================
# 5. "Qattiq tushkunlikka tushdi." — the letters fall
# ==========================================================================
def scene_fall(ctx, lt, t):
    land = wt("G", 2) + 0.38
    dx, dy = shake(t, [land, wt("G", 1) + 0.45], amp=16)
    drop = -260 * (1 - e_bounce(prog(lt, -0.05, 0.6)))
    ctx.save()
    ctx.translate(dx, dy + drop)
    cover(ctx, P["k1_10c"], 860, 600, lerp(1.04, 1.12, prog(lt, 0, 2)), 560, 900)
    ctx.restore()
    fall(ctx, t, "snow", seed=6, n=45, a=0.35, speed=0.6, wind=-10)
    vignette(ctx, 0.8)
    vgrad(ctx, 130, 520, 0.5, 0)
    vgrad(ctx, 1050, 1560, 0, 0.75)
    slam(ctx, ws("G", 0), "black", 118, COLD, TX0 - 4, 390, t, wt("G", 0) - 0.06, s0=1.7,
         shadow=14)
    sz = fit(ws("G", 1), "xbold", 120, TX1 - TX0)
    drop_chars(ctx, t, ws("G", 1), "xbold", sz, WHITE, TC, 1270, wt("G", 1) - 0.08, stagger=0.03,
               dur=0.65, height=1000, shadow=10)
    drop_chars(ctx, t, ws("G", 2), "serif_it_b", 112, COLD_A, TC, 1428, wt("G", 2) - 0.12,
               stagger=0.015, dur=0.5, height=1300, seed=4, tilt=0.2, shadow=10)
    shockwave(ctx, TC, 1410, prog(t, land - 0.05, 0.8), color=COLD, rmax=520, width=2)


# ==========================================================================
# 6. "Amallaridan qalbi qoniqmadi, ibodatlarida nimadir yetishmasdi go'yo."
#    The monitor fades to a flat line; a heart outline that never closes.
# ==========================================================================
HOLE = (430, 800, 190)         # empty heart outline (x, y, r) — the heart transition starts here


def scene_void(ctx, lt, t):
    z = lerp(1.0, 1.1, prog(lt, 0, 5))
    cam = cover(ctx, P["k2_10c"], 1250, 520, z, 640, 960)
    lx, ly = scr(cam, 1975, 770)
    dim = 1 - 0.75 * e_io(prog(t, 28.5, 2.2))
    fl = 0.75 + 0.25 * math.sin(t * 13) * math.sin(t * 7.3)
    add_glow(ctx, lx, ly, 260, AMBER, 0.45 * dim * fl)
    add_glow(ctx, lx, ly, 70, CREAM, 0.6 * dim * fl)
    dust(ctx, t, COLD, seed=9, n=30, a=0.25)
    vignette(ctx, 0.85)
    vgrad(ctx, 120, 700, 0.8, 0)
    vgrad(ctx, 1000, 1540, 0, 0.85)
    # heart monitor — fainter with every beat, then flat
    ea = appear(t, 26.2, 0.3) * fade_out(t, 28.6, 0.6)
    beats = [(26.45, 0.9), (27.12, 0.65), (27.62, 0.32), (28.05, 0.12)]
    ecg(ctx, t, TX0, TX1, 760, beats, amp=120, color=hx("#ff8a8a"), a=ea, sweep=2.2)
    # copy, phase 1
    a1 = fade_out(t, 28.4, 0.3)
    words_in(ctx, t, ws("G", 3), "light", 56, COLD, TX0, 330, wt("G", 3) - 0.05, align="l",
             tracking=3, alpha=a1)
    words_in(ctx, t, ws("G", 4), "serif_it_b", 132, hx("#ffb7b7"), TX0, 480, wt("G", 4) - 0.05,
             align="l", blur_in=10, alpha=a1, shadow=12)
    words_in(ctx, t, ws("G", 5), "med", 62, COLD, TX0, 575, wt("G", 5) - 0.05, align="l", alpha=a1,
             tracking=1)
    # the empty heart: drawn, but never closed
    hp = e_io(prog(t, 28.7, 1.5))
    if hp > 0:
        hx_, hy_, r = HOLE
        pb = pulse(t, [(30.9, 1.0), (31.15, 0.6)], 0.12)
        ctx.save()
        ctx.set_line_width(4 + 3 * pb)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_source_rgba(*COLD[:3], 0.9)
        heart(ctx, hx_, hy_, r * (1 + 0.04 * pb))
        stroke_partial(ctx, 0.86 * hp)
        ctx.restore()
        add_glow(ctx, hx_, hy_, 300, COLD_A, 0.10 + 0.3 * pb)
        # the missing piece flickers where the line stops
        if hp > 0.98:
            ctx.set_line_width(2)
            ctx.set_dash([4, 10])
            ctx.set_source_rgba(*COLD[:3], 0.35 + 0.25 * math.sin(t * 8))
            heart(ctx, hx_, hy_, r)
            ctx.stroke()
            ctx.set_dash([])
    words_in(ctx, t, ws("H", 0), "light", 54, COLD, TC, 1255, wt("H", 0) - 0.05, tracking=3)
    words_in(ctx, t, ws("H", 1), "serif_it", 118, WHITE, TC, 1370, wt("H", 1) - 0.05, blur_in=12,
             shadow=12)
    words_in(ctx, t, ws("H", 2, 4), "med", 56, COLD, TC, 1455, wt("H", 2) - 0.05, stagger=0.25,
             tracking=1)


# ==========================================================================
# 7. "Va Imom Gʻazoliyni bu kitob izlab topdi." — the missing heart is found in the book
# ==========================================================================
def scene_found(ctx, lt, t):
    bg_grad(ctx, hx("#0c0605"), hx("#050303"))
    hx0, hy0, r = HOLE
    m = e_io(prog(t, 31.85, 1.7))
    sK = lerp(1.36, 0.92, m)
    hsx, hsy = lerp(hx0, 760, m), lerp(hy0 + 20, 1035, m)
    A = (hsx - 1577 * sK, hsy - 495 * sK)
    rev = e_io(prog(t, 31.75, 1.5))
    pb = pulse(t, [(31.48, 1.3), (32.15, 0.8), (wt("I", 6), 1.0)], 0.16)
    if rev > 0:
        # light spills out of the heart and reveals the shelf, the book and the hand
        R_ = lerp(60, 2300, rev)
        g = cairo.RadialGradient(hsx, hsy, R_ * 0.55, hsx, hsy, R_)
        g.add_color_stop_rgba(0, 0, 0, 0, 1)
        g.add_color_stop_rgba(1, 0, 0, 0, 0)
        ctx.save()
        ctx.push_group()
        fill(ctx, P["k3_11b"], 1.1)
        y0 = A[1]
        band(ctx, P["k3_11"], sK, A[0], A[1], y0, y0 + 1220 * sK, feather=90)
        # sharper macro over the same spot, feathered
        ms = sK / 2
        mx_, my_ = A[0] + K311_MACRO[0] * sK, A[1] + K311_MACRO[1] * sK
        ctx.save()
        ctx.translate(mx_, my_)
        ctx.scale(ms, ms)
        ctx.set_source_surface(P["macro"].surf, 0, 0)
        ctx.get_source().set_filter(cairo.FILTER_BILINEAR)
        mg = cairo.RadialGradient(HEART_BODY[0], HEART_BODY[1] - 100, 560, HEART_BODY[0],
                                  HEART_BODY[1] - 100, 900)
        mg.add_color_stop_rgba(0, 0, 0, 0, 1)
        mg.add_color_stop_rgba(1, 0, 0, 0, 0)
        ctx.mask(mg)
        ctx.restore()
        ctx.pop_group_to_source()
        ctx.mask(g)
        ctx.restore()
    # the cut-out heart (same pixels as the hook) sits exactly over its place on the cover
    ha = 1 - e_io(prog(t, 32.2, 0.9))
    if ha > 0:
        heart_pic(ctx, hsx, hsy, sK / 2 * (1 + 0.035 * pb), ha)
    add_glow(ctx, hsx, hsy, 380, hx("#ff6a4a"), 0.12 + 0.3 * pb)
    shockwave(ctx, hsx, hsy, prog(t, 31.48, 1.1), color=GOLD_L, rmax=900, width=4)
    god_rays(ctx, t, hsx, hsy - 60, 0.07 * rev, GOLD_L, n=14, seed=2, ang0=0, ang1=6.28,
             length=1600)
    dust(ctx, t, GOLD_L, seed=14, n=50, a=0.5 * rev, add=True)
    vgrad(ctx, 140, 640, 0.6 * rev, 0)
    words_in(ctx, t, ws("I", 0, 3), "med", 50, WHITE, TX0, 300, wt("I", 0) - 0.05, align="l",
             stagger=0.1, tracking=1, shadow=10)
    words_in(ctx, t, ws("I", 3, 5), "serif_it_b", 124, GOLD_L, TX0, 445, wt("I", 3) - 0.05,
             align="l", stagger=0.18, blur_in=10, grad=GG, shadow=14)
    sz = fit(ws("I", 5, 7), "black", 92, 640)
    slam(ctx, ws("I", 5, 7), "black", sz, WHITE, TX0 - 2, 555, t, wt("I", 5) - 0.05, s0=1.4,
         shadow=14)
    flash(ctx, 0.25 * bump(t, wt("I", 6) - 0.02, 0.25), CREAM)


# ==========================================================================
# 8. "Uni bu tushkunlik botqog'idan olib "Hujjatul islomga" aylantirdi."
#    Down in the murk -> lifted up through the surface into the light.
# ==========================================================================
def _swamp_layer(ctx, t, rise):
    off = rise * H
    ctx.save()
    ctx.translate(0, off)
    cover(ctx, P["k1_10s"], 900, 640, 1.12, 540, 960)
    # bubbles
    r = np.random.default_rng(31)
    xs, sp, ph, sz = r.uniform(80, 1000, 26), r.uniform(60, 180, 26), r.uniform(0, 9, 26), \
        r.uniform(3, 11, 26)
    ctx.set_line_width(1.6)
    for i in range(26):
        y = (H + 60) - ((t * sp[i] + ph[i] * 200) % (H + 120))
        ctx.set_source_rgba(*TEAL[:3], 0.35)
        ctx.arc(xs[i] + 8 * math.sin(t * 2 + ph[i]), y, sz[i], 0, 2 * math.pi)
        ctx.stroke()
    god_rays(ctx, t, 540, -200, 0.06, TEAL, n=9, seed=6, ang0=1.2, ang1=1.95, length=2300)
    vignette(ctx, 0.9)
    vgrad(ctx, 140, 700, 0.55, 0)
    a = 1.0
    bob = 6 * math.sin(t * 2.1)
    words_in(ctx, t, ws("J", 0, 3), "light", 54, TEAL, TC, 330 + bob, wt("J", 0) - 0.05,
             stagger=0.12, tracking=2, alpha=a)
    sz = fit(ws("J", 3), "serif_it_b", 124, TX1 - TX0)
    words_in(ctx, t, ws("J", 3), "serif_it_b", sz, hx("#cfe9df"), TC, 475 - bob, wt("J", 3) - 0.05,
             blur_in=12, alpha=a, shadow=12)
    ctx.restore()


def _light_layer(ctx, t, rise):
    off = rise * H - H
    ctx.save()
    ctx.translate(0, off)
    cam = cover(ctx, P["k1_22"], 770, 600, lerp(1.0, 1.07, prog(t, 36.3, 2.4)), 540, 700)
    god_rays(ctx, t, 1180, 120, 0.13, GOLD_L, n=12, seed=9, ang0=1.75, ang1=2.75, length=2600)
    fx_, fy_ = scr(cam, 785, 330)
    add_glow(ctx, fx_ + 60, fy_ - 120, 600, WARM, 0.18)
    dust(ctx, t, GOLD_L, seed=15, n=55, a=0.55, add=True)
    vgrad(ctx, 900, 1420, 0, 0.9)
    ctx.restore()


def scene_lifted(ctx, lt, t):
    t_up = wt("J", 4) - 0.32
    rise = e_io(prog(t, t_up, 0.8))
    if rise <= 0:
        _swamp_layer(ctx, t, 0)
    elif rise >= 1:
        _light_layer(ctx, t, 1)
    else:
        def stack(c):
            _swamp_layer(c, t, rise)
            _light_layer(c, t, rise)
            ys = rise * H
            g = cairo.LinearGradient(0, ys - 70, 0, ys + 70)
            g.add_color_stop_rgba(0, 1, 0.97, 0.9, 0)
            g.add_color_stop_rgba(0.5, 1, 0.97, 0.9, 0.85)
            g.add_color_stop_rgba(1, 1, 0.97, 0.9, 0)
            c.set_source(g)
            c.rectangle(0, ys - 70, W, 140)
            c.fill()
        surf = layer(stack)
        vel = math.sin(rise * math.pi) * 150
        motion_paint(ctx, surf, 0, 0, vy=vel, taps=14)
    # "olib" travels up with the lift
    po = prog(t, wt("J", 4) - 0.1, 0.25)
    if po > 0 and rise < 1:
        y = lerp(610, -120, e_in(rise))
        text(ctx, ws("J", 4), "black", 112, WHITE, TC, y, alpha=clamp(po * 3) * (1 - rise ** 4),
             align="c", glow=16, glow_a=0.5, glow_color=TEAL)
    # title: the honorific, set like an inscription
    if t > wt("K", 0) - 0.2:
        l1, l2 = ws("K", 0), ws("K", 1)
        pt1 = prog(t, wt("K", 0) - 0.12, 0.6)
        pt2 = prog(t, wt("K", 1) - 0.12, 0.6)
        text_rise(ctx, l1, "serif", 128, WHITE, TX0, 1190, pt1, grad=GG, shadow=16, glow=20,
                  glow_a=0.35, glow_color=GOLD)
        text_rise(ctx, l2, "serif", 128, WHITE, TX0 + 60, 1318, pt2, grad=GG, shadow=16, glow=20,
                  glow_a=0.35, glow_color=GOLD)
        glint_text(ctx, l1, "serif", 128, TX0, 1190, prog(t, wt("K", 1) + 0.15, 0.8), color=CREAM)
        glint_text(ctx, l2, "serif", 128, TX0 + 60, 1318, prog(t, wt("K", 1) + 0.35, 0.8),
                   color=CREAM)
        words_in(ctx, t, ws("K", 2), "med", 60, CREAM, TX0 + 4, 1430, wt("K", 2) - 0.05,
                 align="l", tracking=4, blur_in=8)
        q = prog(t, wt("K", 2) + 0.15, 1.0)
        shockwave(ctx, 600, 430, q, color=GOLD_L, rmax=850, width=3)
        sparks(ctx, 600, 430, prog(t, wt("K", 2) + 0.15, 0.9), seed=7, n=34, reach=560)
        add_glow(ctx, 600, 430, 700, GOLD_L, 0.3 * bump(t, wt("K", 2) + 0.1, 0.8))


# ==========================================================================
# 9. "Bu kitob siz 1-sotuvida sotib olishga ulgurmagan Qutul qulub kitobi edi."
# ==========================================================================
def scene_reveal(ctx, lt, t):
    fill(ctx, P["k1_30b"], 1.1)
    bokeh(ctx, t, AMBER, seed=4, n=9, a=0.07)
    y0, y1 = 610, 1650
    s0 = 0.86
    pan = e_io(prog(t, 38.4, 3.3))
    tx0 = lerp(-20, W - P["k1_30"].w * s0 + 10, pan)
    hx0, hy0 = tx0 + 1068 * s0, y0 + 410 * s0
    tq = wt("L", 7) - 0.08
    pin = e_out5(prog(t, tq, 0.6))
    sc = s0 * (1 + 0.16 * pin + 0.03 * prog(lt, 0, 5))
    tx, ty = hx0 - 1068 * sc, hy0 - 410 * sc
    band(ctx, P["k1_30"], sc, tx, ty, y0, y1, feather=80)
    cam = (sc, tx, ty)
    lx, ly = scr(cam, 292, 610)
    fl = 0.8 + 0.2 * math.sin(t * 11) * math.sin(t * 5.1)
    add_glow(ctx, lx, ly, 420, AMBER, 0.30 * fl)
    add_glow(ctx, lx, ly, 110, CREAM, 0.4 * fl)
    hx_, hy_ = scr(cam, 1068, 420)
    pb = pulse(t, [(tq + 0.05, 1.3), (wt("L", 8), 0.8)], 0.16)
    add_glow(ctx, hx_, hy_, 240, hx("#ff5a4a"), 0.25 * pb)
    shockwave(ctx, hx_, hy_, prog(t, tq + 0.05, 1.0), color=GOLD_L, rmax=700, width=3)
    dust(ctx, t, GOLD_L, seed=24, n=35, a=0.4, add=True)
    a1 = fade_out(t, tq - 0.1, 0.25)
    if a1 > 0:
        words_in(ctx, t, ws("L", 0, 3), "med", 54, WHITE, TX0, 300, wt("L", 0) - 0.05, align="l",
                 stagger=0.1, tracking=1, alpha=a1)
        stamp(ctx, ws("L", 3), 600, 300 - 20, prog(t, wt("L", 3) + 0.15, 0.3), size=64, rot=-0.10,
              alpha=a1)
        if t > wt("L", 4) - 0.05:
            typewriter(ctx, t, ws("L", 4, 7), "light", 56, WHITE, TX0, 440, wt("L", 4) - 0.05,
                       cps=21, alpha=a1, cursor=t < wt("L", 7) - 0.15)
    flash(ctx, 0.22 * bump(t, tq - 0.02, 0.22), CREAM)
    if t > tq - 0.05:
        title = ws("L", 7, 9)
        sz = fit(title, "serif", 160, TX1 - TX0)
        pt = prog(t, tq - 0.05, 0.45)
        text(ctx, title, "serif", sz, WHITE, TC, 410, alpha=e_out(pt), align="c",
             scale=lerp(1.25, 1.0, e_out5(pt)), grad=GG, glow=22, glow_a=0.35, glow_color=GOLD,
             shadow=16)
        glint_text(ctx, title, "serif", sz, TC, 410, prog(t, tq + 0.4, 1.0), align="c",
                   color=CREAM)
        words_in(ctx, t, ws("L", 9, 11), "light", 54, CREAM, TC, 520, wt("L", 9) - 0.05,
                 stagger=0.2, tracking=3)


# ==========================================================================
# 10. "Bu kitobni o'qishni tanlay olmaysiz." — the focus hunts and can't lock
# ==========================================================================
HUNT = [(150, 1150, 470, 1540), (560, 300, 1010, 760), (90, 1040, 560, 1500),
        (300, 820, 760, 1240), (170, 1180, 430, 1500), (640, 360, 980, 700)]


def scene_hunt(ctx, lt, t):
    cover(ctx, P["k3_20"], 1080, 600, lerp(1.0, 1.07, prog(lt, 0, 2.6)))
    dust(ctx, t, GOLD_L, seed=21, n=35, a=0.35, add=True)
    vgrad(ctx, 140, 640, 0.66, 0)
    # hunting focus brackets
    seg = 0.38
    k = int(max(0.0, lt - 0.1) / seg)
    q = (max(0.0, lt - 0.1) % seg) / seg
    b0, b1 = HUNT[k % len(HUNT)], HUNT[(k + 1) % len(HUNT)]
    e = e_expo(clamp(q * 2.2))
    box = [lerp(a, b, e) for a, b in zip(b0, b1)]
    fail = prog(t, wt("M", 3) - 0.05, 0.4)
    jx, jy = 9 * fail * math.sin(t * 57), 7 * fail * math.cos(t * 43)
    col = lerpc(hx("#e8f4ff"), hx("#ff6b6b"), fail)
    blink = 1.0 if fail < 0.5 else (0.35 + 0.65 * (int(t * 12) % 2))
    brackets(ctx, box[0] + jx, box[1] + jy, box[2] + jx, box[3] + jy, 54, col,
             0.9 * appear(t, 43.85, 0.2) * blink, width=4, dash=fail > 0.5)
    words_in(ctx, t, ws("M", 0, 2), "med", 54, WHITE, TX0, 300, wt("M", 0) - 0.05, align="l",
             stagger=0.14, tracking=1, shadow=10)
    p = prog(t, wt("M", 3) - 0.05, 0.3)
    if p > 0:
        sz = fit(ws("M", 3, 5), "black", 96, TX1 - TX0)
        glitch_text(ctx, ws("M", 3, 5), "black", sz, TX0, 420, e_out(p),
                    0.6 * bump(t, wt("M", 4) - 0.05, 0.5), t, align="l")


# ==========================================================================
# 11. "Kitob sizni tanlaydi." — the brackets leave the book and lock onto the viewer
# ==========================================================================
def scene_chosen(ctx, lt, t):
    # callback to the hook: the same heart, now it is the one doing the choosing
    fill(ctx, P["k2_40b"], lerp(1.15, 1.25, prog(lt, 0, 1.6)))
    hx_, hy_ = 540, 650
    lock = wt("M", 7) - 0.02
    pb = pulse(t, [(46.25, 0.8), (lock + 0.05, 1.4)], 0.15)
    glow(ctx, hx_, hy_ - 40, 640, CRIMSON, 0.22 + 0.2 * pb)
    god_rays(ctx, t, hx_, hy_ - 60, 0.05 + 0.06 * pb, EMBER, n=11, seed=7, ang0=0, ang1=6.28,
             length=1200)
    heart_pic(ctx, hx_, hy_, 0.40 * (1 + 0.05 * pb))
    add_glow(ctx, hx_, hy_, 240, hx("#ff5a3c"), 0.1 + 0.25 * pb)
    shockwave(ctx, hx_, hy_, prog(t, lock + 0.05, 1.0), color=GOLD_L, rmax=900, width=3)
    dust(ctx, t, hx("#ffcfa0"), seed=3, n=45, a=0.4, size=0.9, add=True)
    flash(ctx, 0.3 * (1 - prog(lt, 0, 0.16)), CREAM)
    # brackets: from the heart out to the edges of YOUR screen
    ex = e_expo(prog(t, wt("M", 6) - 0.05, 0.55))
    b0 = (hx_ - 200, hy_ - 330, hx_ + 200, hy_ + 260)
    b1 = (46, 236, W - 46, 1660)
    box = [lerp(a, b, ex) for a, b in zip(b0, b1)]
    locked = t >= lock
    col = GOLD_L if locked else hx("#e8f4ff")
    brackets(ctx, *box, 76 if locked else 50, col, 0.95, width=6 if locked else 4)
    if locked:
        q = prog(t, lock, 0.6)
        ctx.set_line_width(2)
        ctx.set_source_rgba(*GOLD_L[:3], 0.6 * (1 - q))
        round_rect(ctx, b1[0] - 14 * q, b1[1] - 14 * q, b1[2] - b1[0] + 28 * q,
                   b1[3] - b1[1] + 28 * q, 24)
        ctx.stroke()
        flash(ctx, 0.2 * (1 - q), GOLD_L)
    words_in(ctx, t, ws("M", 5), "light", 60, WHITE, TX0 + 10, 1180, wt("M", 5) - 0.08, align="l",
             tracking=4)
    slam(ctx, ws("M", 6), "serif_it_b", 200, GOLD_L, TX0 + 4, 1350, t, wt("M", 6) - 0.05,
         grad=GG, glow=20, glow_a=0.4, glow_color=GOLD, s0=1.45, shadow=16)
    words_in(ctx, t, ws("M", 7), "semi", 70, WHITE, TX0 + 10, 1450, wt("M", 7) - 0.05, align="l",
             tracking=2, blur_in=8)


# ==========================================================================
# 12. "Biz bu kitobni qayta nashr qilyapmiz." — three volumes come off the press
# ==========================================================================
CARDS = [("book0", 300, 1095, -0.09, 0), ("book2", 722, 1095, 0.09, 2), ("book1", 511, 1040, 0.0, 1)]


def scene_press(ctx, lt, t):
    s, tx, ty = cam_cover(P["k2_30bg"], P["k2_30bg"].w / 2, P["k2_30bg"].h / 2,
                          lerp(1.1, 1.2, prog(lt, 0, 2.5)))
    paint_pic(ctx, P["k2_30bg"], s, tx, ty)
    tint(ctx, AMBER, 0.22, cairo.OPERATOR_SOFT_LIGHT)
    vignette(ctx, 0.85)
    bokeh(ctx, t, GOLD_L, seed=12, n=10, a=0.07)
    starts = [47.55, wt("N", 2) + 0.05, wt("N", 4) - 0.05]
    for name, cx, cy, rot, order in CARDS:
        pic = P[name]
        cw = 460
        sc = cw / pic.w
        ch = pic.h * sc
        p = prog(t, starts[order], 0.7)
        if p <= 0:
            continue
        settle = e_out(clamp(p * 1.6))
        ctx.save()
        ctx.translate(cx, cy + 40 * (1 - settle))
        ctx.rotate(rot * settle)
        # shadow
        rv = e_io(p)
        ctx.set_source_rgba(0, 0, 0, 0.45 * settle)
        round_rect(ctx, -cw / 2 + 14, -ch / 2 + 22, cw, ch * rv, 10)
        ctx.fill()
        ctx.save()
        ctx.rectangle(-cw / 2 - 2, -ch / 2 - 2, cw + 4, ch * rv + 2)
        ctx.clip()
        ctx.translate(-cw / 2, -ch / 2)
        ctx.scale(sc, sc)
        ctx.set_source_surface(pic.surf, 0, 0)
        ctx.get_source().set_filter(cairo.FILTER_BILINEAR)
        ctx.paint()
        ctx.restore()
        if rv < 1:
            yl = -ch / 2 + ch * rv
            g = cairo.LinearGradient(0, yl - 60, 0, yl)
            g.add_color_stop_rgba(0, *CREAM[:3], 0)
            g.add_color_stop_rgba(1, *CREAM[:3], 0.55)
            ctx.set_source(g)
            ctx.rectangle(-cw / 2, yl - 60, cw, 60)
            ctx.fill()
            ctx.set_source_rgba(1, 1, 1, 0.95)
            ctx.rectangle(-cw / 2 - 10, yl - 2, cw + 20, 4)
            ctx.fill()
            add_glow(ctx, 0, yl, 260, GOLD_L, 0.55)
        ctx.restore()
    words_in(ctx, t, ws("N", 0, 3), "med", 54, WHITE, TC, 300, wt("N", 0) - 0.05, stagger=0.12,
             tracking=1)
    title = ws("N", 3, 5)
    sz = fit(title, "serif", 140, TX1 - TX0)
    chars_in(ctx, t, title, "serif", sz, WHITE, TC, 450, wt("N", 3) - 0.08, stagger=0.04, dur=0.6,
             blur=12, grad=GG)
    words_in(ctx, t, ws("N", 5), "light", 58, CREAM, TC, 548, wt("N", 5) - 0.05, tracking=4,
             blur_in=6)


# ==========================================================================
# 13. "Balki nasibangiz bordir..." — lantern, prayer beads, a breath
# ==========================================================================
def scene_destiny(ctx, lt, t):
    z = lerp(1.04, 1.16, e_io(prog(lt, -0.4, 2.6)))
    cam = cover(ctx, P["k3_30"], 760, 640, z, 560, 940)
    lx, ly = scr(cam, 440, 519)
    fl = 0.8 + 0.2 * math.sin(t * 9.7) * math.sin(t * 4.3)
    add_glow(ctx, lx, ly, 480, AMBER, 0.32 * fl)
    add_glow(ctx, lx, ly, 120, CREAM, 0.45 * fl)
    bokeh(ctx, t, AMBER, seed=8, n=12, a=0.10, rmin=30, rmax=110)
    dust(ctx, t, GOLD_L, seed=19, n=40, a=0.45, add=True)
    vgrad(ctx, 1020, 1560, 0, 0.8)
    words_in(ctx, t, ws("O", 0), "light", 56, CREAM, TX0, 1240, wt("O", 0) - 0.05, align="l",
             tracking=4, blur_in=6)
    sz = fit(ws("O", 1), "serif_it", 140, TX1 - TX0)
    chars_in(ctx, t, ws("O", 1), "serif_it", sz, GOLD_L, TX0, 1370, wt("O", 1) - 0.1, align="l",
             stagger=0.05, dur=0.8, blur=12, grad=GG)
    if t > wt("O", 2) - 0.05:
        typewriter(ctx, t, ws("O", 2), "reg", 60, CREAM, TX0, 1455, wt("O", 2) - 0.05, cps=9,
                   cursor=False)


# ==========================================================================
# 14. "Tez kunda qayta sotuvda" — today, the same book under a young man's arm
# ==========================================================================
def scene_soon(ctx, lt, t):
    z = lerp(1.02, 1.1, prog(lt, -0.3, 2.2))
    cam = cover(ctx, P["k3_31"], 1330, 560, z, 560, 940)
    # ghost of the scholar from scene 2 — the same walk, a thousand years apart
    ga = 0.4 * (1 - e_io(prog(lt, 0.05, 0.75)))
    if ga > 0:
        hx_, hy_ = scr(cam, 1256, 218)
        s2 = cam[0]
        paint_pic(ctx, P["k3_00"], s2, hx_ - 1098 * s2, hy_ - 252 * s2, ga)
    light_leak(ctx, t, 0.5, seed=7)
    vgrad(ctx, 140, 700, 0.66, 0)
    bx, by = scr(cam, 1594, 1008)
    add_glow(ctx, bx, by, 220, GOLD_L, 0.12 + 0.2 * pulse(t, [(wt("P", 3), 1.0)], 0.2))
    # "Tez kunda" chip with a live dot
    pc = appear(t, wt("P", 0) - 0.1, 0.3)
    if pc > 0:
        label = ws("P", 0, 2)
        lw = tw(label, "semi", 44, 2)
        ctx.set_source_rgba(0.04, 0.03, 0.03, 0.62 * pc)
        round_rect(ctx, TX0, 236, lw + 96, 76, 38)
        ctx.fill()
        ctx.set_source_rgba(*GOLD_L[:3], 0.6 * pc)
        ctx.set_line_width(2)
        round_rect(ctx, TX0, 236, lw + 96, 76, 38)
        ctx.stroke()
        dot = 0.55 + 0.45 * math.sin(t * 7)
        ctx.set_source_rgba(1, 0.25, 0.3, pc)
        ctx.arc(TX0 + 38, 274, 9, 0, 2 * math.pi)
        ctx.fill()
        add_glow(ctx, TX0 + 38, 274, 34, hx("#ff4f5e"), 0.7 * dot * pc)
        text(ctx, label, "semi", 44, WHITE, TX0 + 64, 290, alpha=pc, tracking=2)
    sz = fit(ws("P", 2, 4), "black", 116, TX1 - TX0)
    text_rise(ctx, ws("P", 2, 4), "black", sz, WHITE, TX0, 445, prog(t, wt("P", 2) - 0.08, 0.45),
              shadow=18)


# ==========================================================================
# 15. "qalblar ozuqasi kitobi." — the heart blossoms; signature
# ==========================================================================
def _petals(ctx, t, ox, oy, a):
    r = np.random.default_rng(77)
    n = 26
    ts = r.uniform(53.9, 58.2, n)
    ang = r.uniform(-2.7, -0.45, n)
    spd = r.uniform(120, 260, n)
    sz = r.uniform(7, 15, n)
    rot = r.uniform(-3, 3, n)
    for i in range(n):
        age = t - ts[i]
        if age <= 0 or age > 3.2:
            continue
        x = ox + math.cos(ang[i]) * spd[i] * age + 30 * math.sin(age * 2 + i)
        y = oy + math.sin(ang[i]) * spd[i] * age + 40 * age * age
        al = a * min(1, age / 0.3) * (1 - age / 3.2)
        ctx.save()
        ctx.translate(x, y)
        ctx.rotate(rot[i] * age)
        ctx.scale(1, 0.55 + 0.4 * math.sin(age * 4 + i))
        ctx.set_source_rgba(*ROSE_L[:3], al)
        ctx.arc(0, 0, sz[i], 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()


def scene_finale(ctx, lt, t):
    fill(ctx, P["k1_32b"], lerp(1.1, 1.2, prog(lt, 0, 4.6)))
    bokeh(ctx, t, ROSE_L, seed=6, n=10, a=0.08)
    # the whole photo as a framed card; the blossoms escape the frame
    cw = 920
    pic = P["k1_32"]
    s0 = cw / pic.w
    ch = pic.h * s0
    cx0, cy0 = (W - cw) / 2, 690
    ent = e_out(prog(lt, -0.3, 0.9))
    cy = cy0 + 50 * (1 - ent) + 10 * math.sin(lt * 1.3)
    tilt = 0.012 * math.sin(lt * 0.9 + 0.5)
    ctx.save()
    ctx.translate(W / 2, cy + 340)
    ctx.rotate(tilt)
    ctx.translate(-W / 2, -(cy + 340))
    ctx.set_source_rgba(0, 0, 0, 0.5)
    round_rect(ctx, cx0 + 16, cy + 26, cw, ch, 26)
    ctx.fill()
    z = lerp(1.12, 1.0, e_out(prog(lt, -0.3, 4.6)))
    sc = s0 * z
    hxi, hyi = 1080, 330
    tx = cx0 + cw * 0.62 - hxi * sc
    ty = cy + ch * 0.30 - hyi * sc
    tx = min(cx0, max(cx0 + cw - pic.w * sc, tx))
    ty = min(cy, max(cy + ch - pic.h * sc, ty))
    ctx.save()
    round_rect(ctx, cx0, cy, cw, ch, 26)
    ctx.clip()
    paint_pic(ctx, pic, sc, tx, ty)
    light_leak(ctx, t, 0.35, seed=9, colors=(WARM, ROSE, GOLD_L))
    ctx.restore()
    ctx.set_line_width(2.5)
    ctx.set_source_rgba(*GOLD_L[:3], 0.75 * ent)
    round_rect(ctx, cx0, cy, cw, ch, 26)
    ctx.stroke()
    hx_, hy_ = ctx.user_to_device(tx + hxi * sc, ty + hyi * sc)
    ctx.restore()
    pb = pulse(t, [(wt("P", 5), 1.0), (55.16, 0.7), (55.7, 1.4), (57.66, 1.0)], 0.17)
    add_glow(ctx, hx_, hy_, 260, hx("#ff5a4a"), 0.10 + 0.32 * pb)
    shockwave(ctx, hx_, hy_, prog(t, 55.7, 1.2), color=ROSE_L, rmax=800, width=3)
    _petals(ctx, t, hx_, hy_ - 30, 0.95)
    fall(ctx, t, "petal", ROSE_L, seed=5, n=20, a=0.5, speed=0.7, wind=25)
    words_in(ctx, t, ws("P", 4), "serif_it", 100, CREAM, TC, 330, wt("P", 4) - 0.08, blur_in=10)
    sz = fit(ws("P", 5), "serif", 170, TX1 - TX0)
    chars_in(ctx, t, ws("P", 5), "serif", sz, WHITE, TC, 488, wt("P", 5) - 0.1, stagger=0.045,
             dur=0.7, blur=12, grad=GG)
    glint_text(ctx, ws("P", 5), "serif", sz, TC, 488, prog(t, 55.4, 1.1), align="c", color=CREAM)
    words_in(ctx, t, ws("P", 6), "light", 56, CREAM, TC, 590, wt("P", 6) - 0.05, tracking=4,
             blur_in=6)
    handle(ctx, t, 56.0, y=1470)


SCENES = [(0.0, scene_hook), (7.62, scene_millennium), (11.40, scene_west_east),
          (16.27, scene_converge), (20.34, scene_summit), (24.62, scene_fall),
          (26.30, scene_void), (31.30, scene_found), (34.40, scene_lifted),
          (38.60, scene_reveal), (43.80, scene_hunt), (46.15, scene_chosen),
          (47.70, scene_press), (50.15, scene_destiny), (52.10, scene_soon),
          (53.85, scene_finale)]

TRANS = {
    1: ("burn", 0.7, {"x": 560, "y": 1000, "color": EMBER}),
    2: ("luma", 0.6, {"angle": 0.0, "soft": 300}),
    3: ("blinds", 0.55, {"n": 3, "vertical": True}),
    4: ("dissolve", 0.7),
    6: ("fade", 0.5),
    7: ("heart", 0.8, {"x": HOLE[0], "y": HOLE[1], "r": HOLE[2], "color": GOLD_L}),
    8: ("fade", 0.6),
    9: ("iris", 0.7, {"x": 230, "y": 1135}),
    10: ("whip", 0.5, {"dir": "left"}),
    12: ("push", 0.5, {"dir": "up", "snap": True}),
    13: ("dissolve", 0.7),
    14: ("flare", 0.6, {"y": 760}),
    15: ("zoom", 0.6),
}
