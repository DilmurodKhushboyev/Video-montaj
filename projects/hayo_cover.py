"""
"Hayo naqadar goʻzal" — Reels uchun OQ fonli, zamonaviy-luxury cover, 1080×1920.

    python3 projects/hayo_cover.py            # -> output/hayo_naqadar_gozal_cover.png/.jpg

Uslub: oq marmar (juda nozik kulrang tomirlar, fon baribir oq) + oltin varaq (foil).
Qatlamlar: ramka (burchak naqshlari) -> oltin geometrik rozetka (halo) -> mehrob ravog'i
ichida portret -> ulkan foil "Hayo" boshi ORTIDA (+ ingichka kontur aks-sadosi) -> boshi
ravoqdan chiqadi -> muhr "(Muttafaqun alayh)." -> sarlavha, hadis ramkada, Instagram.
Muhim qismlar markaziy 1080×1440 (profil to'ri 3:4 kesimi) ichida: y 240..1680.
"""
import math
import os
import sys

import cairo
import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import render as R  # noqa: E402

P = R.load_project(os.path.join(HERE, "hayo_naqadar_gozal.py"))
from render import (W, H, hx, text, tw, sprite, arch_path, paint_pic, round_rect,  # noqa: E402
                    draw_sprite, HANDLE, BLACK, Pic)

INK = hx("#101014")
GRAY = hx("#4a4640")
GOLD = hx("#b8913f")
GOLD_SOFT = hx("#cfae6a")
FOIL = ((0.00, "#7a4f16"), (0.18, "#c99a45"), (0.38, "#f7e3a3"), (0.50, "#e2bb65"),
        (0.66, "#a8742a"), (0.84, "#d9b05c"), (1.00, "#8c5e1f"))

FRAME = (52, 238, 1028, 1682)
ARCH = (206, 874, 812, 600, 1196)   # x0, x1, spring, apex, bottom
ROS = (540, 760, 470)               # rosette centre / radius


def foil(x0, y0, x1, y1):
    g = cairo.LinearGradient(x0, y0, x1, y1)
    for off, c in FOIL:
        g.add_color_stop_rgba(off, *hx(c)[:3], 1)
    return g


def foil_text(ctx, s, fkey, size, x, baseline, align="c", shadow=0.16, sheen=True):
    """Text filled with a metallic gold-foil gradient (sprite used as a mask)."""
    sp = sprite(s, fkey, size, (1, 1, 1, 1))
    ox = x - {"l": 0, "c": sp.w / 2, "r": sp.w}[align]
    x0, y0 = ox - sp.pad, baseline - sp.asc - sp.pad
    if shadow:
        sh = sprite(s, fkey, size, BLACK, 0.0, None, max(6, size // 16))
        draw_sprite(ctx, sh, ox, baseline + size * 0.04, shadow, 1.0, "l")
    top = baseline - sp.asc * 0.80
    ctx.set_source(foil(ox + sp.w / 2 - 40, top, ox + sp.w / 2 + 40, baseline + sp.desc * 0.5))
    ctx.mask_surface(sp.surf, x0, y0)
    if sheen:
        g2 = cairo.LinearGradient(ox + sp.w * 0.15, top, ox + sp.w * 0.55, baseline)
        g2.add_color_stop_rgba(0.0, 1, 1, 1, 0)
        g2.add_color_stop_rgba(0.5, 1, 0.98, 0.9, 0.35)
        g2.add_color_stop_rgba(1.0, 1, 1, 1, 0)
        ctx.save()
        ctx.set_operator(cairo.OPERATOR_ADD)
        ctx.set_source(g2)
        ctx.mask_surface(sp.surf, x0, y0)
        ctx.restore()
    return sp.w


def marble():
    """White marble: pure white with very faint grey veins."""
    rng = np.random.default_rng(7)
    h, w = H // 4, W // 4

    def noise(sc):
        n = rng.normal(0, 1, (max(2, h // sc), max(2, w // sc))).astype(np.float32)
        im = Image.fromarray(((n - n.min()) / np.ptp(n) * 255).astype(np.uint8))
        return np.asarray(im.resize((w, h), Image.BICUBIC), np.float32) / 255
    nz = noise(60) * 0.55 + noise(24) * 0.3 + noise(8) * 0.15
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = np.abs(np.sin((xx * 0.55 + yy * 0.95) / 26 + nz * 9.0))
    vein = (1 - v) ** 18 + 0.5 * (1 - np.abs(np.sin((xx * 0.9 - yy * 0.4) / 40 + nz * 6))) ** 24
    vein = np.clip(vein, 0, 1)
    a = np.asarray(Image.fromarray((vein * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
                   .filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255
    rgb = np.zeros((H, W, 3), np.uint8)
    rgb[:] = (150, 148, 145)
    return Pic(rgb, (a * 0.08 * 255).astype(np.uint8))


def star_poly(ctx, cx, cy, r, n, k, rot=-math.pi / 2):
    """Star polygon {n/k} — interlaced geometric lines."""
    pts = [(cx + r * math.cos(rot + 2 * math.pi * i / n), cy + r * math.sin(rot + 2 * math.pi * i / n))
           for i in range(n)]
    i = 0
    ctx.move_to(*pts[0])
    for _ in range(n):
        i = (i + k) % n
        ctx.line_to(*pts[i])
    ctx.close_path()


def rosette(ctx):
    cx, cy, r = ROS
    ctx.save()
    ctx.set_line_join(cairo.LINE_JOIN_MITER)
    for rr, wdt, a in ((r, 1.6, 0.85), (r - 14, 0.9, 0.6), (r * 0.64, 1.0, 0.5)):
        ctx.set_source_rgba(*GOLD[:3], a)
        ctx.set_line_width(wdt)
        ctx.arc(cx, cy, rr, 0, 2 * math.pi)
        ctx.stroke()
    ctx.set_source_rgba(*GOLD[:3], 0.55)
    ctx.set_line_width(1.0)
    star_poly(ctx, cx, cy, r - 22, 16, 5)
    ctx.stroke()
    ctx.set_source_rgba(*GOLD[:3], 0.38)
    star_poly(ctx, cx, cy, r - 22, 16, 3, -math.pi / 2 + math.pi / 16)
    ctx.stroke()
    ctx.set_source_rgba(*GOLD[:3], 0.7)
    ctx.set_line_width(1.3)
    P.star8_path(ctx, cx, cy, r * 0.64, -math.pi / 2 + math.pi / 8)
    ctx.stroke()
    for i in range(64):
        an = 2 * math.pi * i / 64
        rr = r - 7
        ctx.set_source_rgba(*GOLD[:3], 0.9 if i % 4 == 0 else 0.5)
        ctx.arc(cx + rr * math.cos(an), cy + rr * math.sin(an), 2.6 if i % 4 == 0 else 1.4, 0,
                2 * math.pi)
        ctx.fill()
    ctx.restore()


def sparkle(ctx, x, y, r):
    """Four-point gold glint."""
    ctx.save()
    ctx.translate(x, y)
    k = r * 0.12
    ctx.move_to(0, -r)
    ctx.curve_to(k, -k, k, -k, r, 0)
    ctx.curve_to(k, k, k, k, 0, r)
    ctx.curve_to(-k, k, -k, k, -r, 0)
    ctx.curve_to(-k, -k, -k, -k, 0, -r)
    ctx.close_path()
    ctx.set_source(foil(-r, -r, r, r))
    ctx.fill()
    ctx.restore()


def diamond(ctx, x, y, r):
    ctx.move_to(x, y - r)
    ctx.line_to(x + r, y)
    ctx.line_to(x, y + r)
    ctx.line_to(x - r, y)
    ctx.close_path()


def frame(ctx):
    x0, y0, x1, y1 = FRAME
    ctx.set_source_rgba(*GOLD[:3], 1)
    ctx.set_line_width(1.6)
    ctx.rectangle(x0, y0, x1 - x0, y1 - y0)
    ctx.stroke()
    ctx.set_line_width(0.9)
    ctx.set_source_rgba(*GOLD[:3], 0.7)
    ctx.rectangle(x0 + 10, y0 + 10, x1 - x0 - 20, y1 - y0 - 20)
    ctx.stroke()
    # corner ornaments
    for cx, cy, sx, sy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        ctx.set_source_rgba(1, 1, 1, 1)
        ctx.rectangle(cx + sx * 2 - (40 if sx < 0 else 0), cy + sy * 2 - (40 if sy < 0 else 0), 38, 38)
        ctx.fill()
        ctx.set_source(foil(cx, cy - 30, cx, cy + 30))
        ctx.set_line_width(1.6)
        ctx.arc(cx, cy, 30, 0, 2 * math.pi)
        ctx.stroke()
        ctx.set_line_width(1.0)
        ctx.arc(cx, cy, 20, 0, 2 * math.pi)
        ctx.stroke()
        P.star8_path(ctx, cx, cy, 13)
        ctx.fill()
        ctx.set_line_width(1.2)
        ctx.move_to(cx + sx * 30, cy + sy * 46)
        ctx.line_to(cx + sx * 30, cy + sy * 90)
        ctx.move_to(cx + sx * 46, cy + sy * 30)
        ctx.line_to(cx + sx * 90, cy + sy * 30)
        ctx.stroke()
        diamond(ctx, cx + sx * 30, cy + sy * 96, 4)
        diamond(ctx, cx + sx * 96, cy + sy * 30, 4)
        ctx.fill()
    # centre medallions on the top / bottom edges
    for yy in (y0, y1):
        ctx.set_source_rgba(1, 1, 1, 1)
        ctx.rectangle(540 - 46, yy - 14, 92, 28)
        ctx.fill()
        ctx.set_source(foil(540, yy - 16, 540, yy + 16))
        P.star8_path(ctx, 540, yy, 15)
        ctx.fill()
        for sd in (-1, 1):
            diamond(ctx, 540 + sd * 32, yy, 5)
            ctx.fill()


def seal(ctx, cx, cy, r, rot=-0.14):
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(rot)
    # soft shadow
    for k, a in ((10, 0.05), (5, 0.07)):
        ctx.set_source_rgba(0, 0, 0, a)
        ctx.arc(4, 8, r + k, 0, 2 * math.pi)
        ctx.fill()
    ctx.set_source_rgba(1, 1, 1, 1)
    ctx.arc(0, 0, r, 0, 2 * math.pi)
    ctx.fill()
    ctx.set_source(foil(-r, -r, r * 0.6, r))
    ctx.set_line_width(7)
    ctx.arc(0, 0, r - 4, 0, 2 * math.pi)
    ctx.stroke()
    ctx.set_line_width(1.2)
    ctx.arc(0, 0, r - 15, 0, 2 * math.pi)
    ctx.stroke()
    for i in range(40):
        an = 2 * math.pi * i / 40
        ctx.arc((r - 23) * math.cos(an), (r - 23) * math.sin(an), 1.4, 0, 2 * math.pi)
        ctx.fill()
    P.star8_path(ctx, 0, -r * 0.47, 10)
    ctx.fill()
    text(ctx, "(Muttafaqun", "semi", 18, hx("#8a6424"), 0, 6, align="c", tracking=1)
    text(ctx, "alayh).", "semi", 18, hx("#8a6424"), 0, 31, align="c", tracking=1)
    diamond(ctx, 0, r * 0.62, 4)
    ctx.set_source_rgba(*GOLD[:3], 1)
    ctx.fill()
    ctx.restore()


def notched_box(ctx, x0, y0, x1, y1, c):
    ctx.move_to(x0 + c, y0)
    ctx.line_to(x1 - c, y0)
    ctx.line_to(x1, y0 + c)
    ctx.line_to(x1, y1 - c)
    ctx.line_to(x1 - c, y1)
    ctx.line_to(x0 + c, y1)
    ctx.line_to(x0, y1 - c)
    ctx.line_to(x0, y0 + c)
    ctx.close_path()


def ig_mono(ctx, cx, cy, s, color=INK):
    x0, y0 = cx - s / 2, cy - s / 2
    ctx.set_source_rgba(*color[:3], 1)
    ctx.set_line_width(s * 0.085)
    round_rect(ctx, x0, y0, s, s, s * 0.28)
    ctx.stroke()
    ctx.arc(cx, cy, s * 0.22, 0, 2 * math.pi)
    ctx.stroke()
    ctx.arc(x0 + s * 0.76, y0 + s * 0.24, s * 0.055, 0, 2 * math.pi)
    ctx.fill()


def blurred_shadow(ctx, path_fn, blur=34, a=0.2, dy=30):
    ms = cairo.ImageSurface(cairo.FORMAT_A8, W, H)
    mc = cairo.Context(ms)
    path_fn(mc)
    mc.fill()
    ms.flush()
    m = np.ndarray((H, ms.get_stride()), np.uint8, ms.get_data())[:, :W].copy()
    m = np.asarray(Image.fromarray(m).filter(ImageFilter.GaussianBlur(blur)))
    shade = Pic(np.zeros((H, W, 3), np.uint8), (m * a).astype(np.uint8))
    paint_pic(ctx, shade, 1.0, 0, dy)


def main():
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    ctx.set_source_rgba(1, 1, 1, 1)
    ctx.paint()
    paint_pic(ctx, marble(), 1.0, 0, 0)
    frame(ctx)
    rosette(ctx)
    x0, x1, sp, ap, bt = ARCH
    blurred_shadow(ctx, lambda c: arch_path(c, x0 + 10, x1 - 10, sp + 20, ap + 20, bt))
    # portrait inside the arch (white backing hides the rosette)
    pic, cut = P.G["p0x"], P.G["p0cut"]
    s = 0.62
    eyes = (1110, 480 + P.EXT0)
    tx, ty = 540 - eyes[0] * s, 826 - eyes[1] * s
    ctx.save()
    arch_path(ctx, x0, x1, sp, ap, bt)
    ctx.clip()
    paint_pic(ctx, pic, s, tx, ty)
    R.vgrad(ctx, bt - 220, bt, 0, 0.16, hx("#2a1c0c"))
    ctx.restore()
    # foil arch band + hairlines
    arch_path(ctx, x0 - 7, x1 + 7, sp, ap - 7, bt + 7)
    ctx.set_source(foil(x0, ap, x1, bt))
    ctx.set_line_width(9)
    ctx.stroke()
    arch_path(ctx, x0, x1, sp, ap, bt)
    ctx.set_source_rgba(*INK[:3], 0.55)
    ctx.set_line_width(1.0)
    ctx.stroke()
    arch_path(ctx, x0 - 24, x1 + 24, sp, ap - 24, bt + 24)
    ctx.set_source_rgba(*GOLD[:3], 0.9)
    ctx.set_line_width(1.1)
    ctx.stroke()
    for sd in (-1, 1):
        xx = 540 + sd * (x1 - x0) / 2 + sd * 7
        ctx.set_source(foil(xx - 12, bt - 12, xx + 12, bt + 12))
        diamond(ctx, xx, bt + 7, 11)
        ctx.fill()
    # giant "Hayo": white knockout (like foil stamped on paper), then foil
    ko = sprite("Hayo", "serif_it_b", 336, (1, 1, 1, 1), 0.0, None, 16)
    ctx.save()
    ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    ctx.rectangle(0, 0, W, H)
    arch_path(ctx, x0 - 4, x1 + 4, sp, ap - 4, bt)
    ctx.clip()
    for _ in range(4):
        draw_sprite(ctx, ko, 540, 600, 1.0, 1.0, "c")
    ctx.restore()
    foil_text(ctx, "Hayo", "serif_it_b", 336, 540, 600)
    # head breaks out of the arch (redrawn above the spring line; identical pixels inside)
    ctx.save()
    ctx.rectangle(0, 0, W, sp - 60)
    ctx.clip()
    ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    ctx.rectangle(0, 0, W, H)
    arch_path(ctx, x0 + 14, x1 - 14, sp, ap + 14, bt)
    ctx.clip()
    ctx.set_fill_rule(cairo.FILL_RULE_WINDING)
    ctx.push_group()
    paint_pic(ctx, cut, s, tx + 5, ty + 9)
    shd = ctx.pop_group()
    ctx.set_source_rgba(0, 0, 0, 0.14)
    ctx.mask(shd)
    ctx.restore()
    ctx.save()
    ctx.rectangle(0, 0, W, sp - 60)
    ctx.clip()
    paint_pic(ctx, cut, s, tx, ty)
    ctx.restore()
    # seal on the arch corner
    seal(ctx, 850, 1146, 94)
    # gold glints and dust
    for (gx, gy, gr) in ((176, 372, 26), (948, 700, 20), (148, 980, 14), (930, 452, 12),
                         (300, 1300, 12), (812, 1260, 9)):
        sparkle(ctx, gx, gy, gr)
    rng = np.random.default_rng(5)
    for _ in range(70):
        gx, gy = rng.uniform(80, 1000), rng.uniform(270, 1250)
        if 190 < gx < 890 and 560 < gy < 1220:
            continue
        ctx.set_source_rgba(*GOLD_SOFT[:3], rng.uniform(0.35, 0.9))
        ctx.arc(gx, gy, rng.uniform(1.0, 2.8), 0, 2 * math.pi)
        ctx.fill()
    # title: "naqadar" ink + "goʻzal" foil
    size = 112
    w1 = tw("naqadar", "serif_it", size)
    w2 = tw("goʻzal", "serif_it_b", size)
    gap = size * 0.26
    xl = 540 - (w1 + gap + w2) / 2
    yb = 1338
    text(ctx, "naqadar", "serif_it", size, INK, xl, yb, shadow=8, shadow_a=0.12)
    foil_text(ctx, "goʻzal", "serif_it_b", size, xl + w1 + gap, yb, align="l", shadow=0.12)
    # flourish divider
    yd = 1388
    ctx.set_source(foil(300, yd, 780, yd))
    ctx.set_line_width(1.3)
    for sd in (-1, 1):
        ctx.move_to(540 + sd * 26, yd)
        ctx.line_to(540 + sd * 240, yd)
        ctx.stroke()
        diamond(ctx, 540 + sd * 248, yd, 4)
        ctx.fill()
    P.star8_path(ctx, 540, yd, 11)
    ctx.fill()
    # hadith in a notched box
    bx0, by0, bx1, by1 = 150, 1418, 930, 1516
    notched_box(ctx, bx0, by0, bx1, by1, 14)
    ctx.set_source_rgba(*GOLD[:3], 1)
    ctx.set_line_width(1.3)
    ctx.stroke()
    notched_box(ctx, bx0 + 7, by0 + 7, bx1 - 7, by1 - 7, 10)
    ctx.set_source_rgba(*GOLD[:3], 0.45)
    ctx.set_line_width(0.8)
    ctx.stroke()
    text(ctx, "«Hayo faqat yaxshilik keltiradi».", "serif_it", 42, GRAY, 540, 1480, align="c")
    # Instagram pill
    hs = 28
    ic = hs * 1.25
    gp = hs * 0.55
    total = ic + gp + tw(HANDLE, "med", hs, 3)
    hx0 = 540 - total / 2
    yb = 1598
    round_rect(ctx, hx0 - 26, yb - hs * 0.36 - 30, total + 52, 60, 30)
    ctx.set_source_rgba(*INK[:3], 1)
    ctx.fill()
    ig_mono(ctx, hx0 + ic / 2, yb - hs * 0.36, ic, hx("#f3e2b5"))
    text(ctx, HANDLE, "med", hs, hx("#f3e2b5"), hx0 + ic + gp, yb, tracking=3)
    surf.flush()
    out = os.path.join(ROOT, "output", "hayo_naqadar_gozal_cover")
    surf.write_to_png(out + ".png")
    a = np.ndarray((H, W, 4), np.uint8, surf.get_data())
    Image.fromarray(a[..., [2, 1, 0]].copy()).save(out + ".jpg", quality=95)
    print("tayyor:", out + ".png", out + ".jpg")


if __name__ == "__main__":
    main()
