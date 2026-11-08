"""
"Hayo naqadar goʻzal" — Reels uchun oq (fil suyagi) fonli cover, 1080×1920.

    python3 projects/hayo_cover.py            # -> output/hayo_naqadar_gozal_cover.png/.jpg

Kompozitsiya: oq fon + och oltin naqsh; mehrob ravog'i ichida portret, boshi ravoqdan
chiqib turadi; ulkan "Hayo" so'zi boshi ORTIDA (video hook'i bilan bir uslub).
Muhim qismlar markaziy 1080×1440 (profil to'ri 3:4 kesimi) ichida: y 240..1680.
"""
import math
import os
import sys

import cairo
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import render as R  # noqa: E402

P = R.load_project(os.path.join(HERE, "hayo_naqadar_gozal.py"))
from render import (W, H, hx, text, tw, add_glow, glow, arch_path, instagram_icon,  # noqa: E402
                    paint_pic, Pic, HANDLE)

IVORY_T, IVORY_B = hx("#fffdf9"), hx("#f3ebdd")
INK = hx("#1c2238")
WARM_GRAY = hx("#7a6650")
GOLD_DK = (hx("#d9b46a"), hx("#94692a"))       # readable gold on white
GOLD_LINE = hx("#b8924f")
HAYO_G = (hx("#e7b27c"), hx("#a8642f"))         # warm gold-blush for the big word

ARCH = (170, 910, 830, 606, 1214)  # x0, x1, spring, apex, bottom


def main():
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    # background -------------------------------------------------------------
    g = cairo.LinearGradient(0, 0, 0, H)
    g.add_color_stop_rgba(0, *IVORY_T)
    g.add_color_stop_rgba(1, *IVORY_B)
    ctx.set_source(g)
    ctx.paint()
    lat = P.lattice_surface(color=hx("#c9a86a"), step=150, R_=44)
    ctx.set_source_surface(lat, -75, -40)
    ctx.paint_with_alpha(0.10)
    glow(ctx, 540, 900, 900, hx("#fff4e2"), 0.9)
    x0, x1, sp, ap, bt = ARCH
    # soft shadow under the arch
    for k, a in ((22, 0.03), (12, 0.04), (5, 0.05)):
        ctx.save()
        ctx.translate(0, 18)
        arch_path(ctx, x0 - k, x1 + k, sp, ap - k, bt + k)
        ctx.set_source_rgba(0.35, 0.25, 0.12, a)
        ctx.fill()
        ctx.restore()
    # portrait inside the arch ----------------------------------------------
    pic, cut = P.G["p0x"], P.G["p0cut"]
    s = 0.66
    eyes = (1110, 480 + P.EXT0)
    tx, ty = 540 - eyes[0] * s, 826 - eyes[1] * s
    ctx.save()
    arch_path(ctx, x0, x1, sp, ap, bt)
    ctx.clip()
    paint_pic(ctx, pic, s, tx, ty)
    R.vgrad(ctx, bt - 240, bt, 0, 0.18, hx("#3a2a14"))
    ctx.restore()
    # gold arch outline (double) + finial star
    for grow, wdt, a in ((10, 3.2, 1.0), (24, 1.3, 0.75)):
        arch_path(ctx, x0 - grow, x1 + grow, sp, ap - grow, bt + grow)
        ctx.set_source_rgba(*GOLD_LINE[:3], a)
        ctx.set_line_width(wdt)
        ctx.stroke()
    # giant "Hayo" behind the head -------------------------------------------
    text(ctx, "Hayo", "serif_it_b", 330, hx("#c98a52"), 540, 606, align="c", grad=HAYO_G,
         shadow=30, shadow_a=0.22)
    # the head breaks out of the arch (cutout, only above the spring line)
    ctx.save()
    ctx.rectangle(0, 0, W, sp - 60)
    ctx.clip()
    ctx.push_group()
    paint_pic(ctx, cut, s, tx + 6, ty + 10)
    sh = ctx.pop_group()
    ctx.set_source_rgba(0.25, 0.16, 0.06, 0.18)
    ctx.mask(sh)
    paint_pic(ctx, cut, s, tx, ty)
    ctx.restore()
    # title + subtitle --------------------------------------------------------
    text(ctx, "naqadar goʻzal", "serif_it", 118, INK, 540, 1352, align="c", shadow=10,
         shadow_a=0.12)
    # ornament divider
    yd = 1406
    ctx.set_line_width(1.6)
    ctx.set_source_rgba(*GOLD_LINE[:3], 0.9)
    for sd in (-1, 1):
        ctx.move_to(540 + sd * 34, yd)
        ctx.line_to(540 + sd * 230, yd)
    ctx.stroke()
    P.star8_path(ctx, 540, yd, 15)
    ctx.stroke()
    ctx.arc(540, yd, 3.2, 0, 2 * math.pi)
    ctx.fill()
    hadis = "«Hayo faqat yaxshilik keltiradi»."
    text(ctx, hadis, "serif_it", 50, WARM_GRAY, 540, 1490, align="c")
    # Instagram + name
    size = 34
    ic = size * 1.3
    gap = size * 0.42
    total = ic + gap + tw(HANDLE, "semi", size, 2)
    hx0 = 540 - total / 2
    yb = 1574
    instagram_icon(ctx, hx0 + ic / 2, yb - size * 0.36, ic, 1.0)
    text(ctx, HANDLE, "semi", size, GOLD_LINE, hx0 + ic + gap, yb, tracking=2)
    surf.flush()
    out = os.path.join(ROOT, "output", "hayo_naqadar_gozal_cover")
    surf.write_to_png(out + ".png")
    from PIL import Image
    a = np.ndarray((H, W, 4), np.uint8, surf.get_data())
    Image.fromarray(a[..., [2, 1, 0]].copy()).save(out + ".jpg", quality=95)
    print("tayyor:", out + ".png", out + ".jpg")


if __name__ == "__main__":
    main()
