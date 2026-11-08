"""
"Hayo naqadar goʻzal" — Reels uchun toza OQ fonli, zamonaviy-luxury cover, 1080×1920.

    python3 projects/hayo_cover.py            # -> output/hayo_naqadar_gozal_cover.png/.jpg

Uslub: sof oq (#ffffff) fon, ko'p bo'sh joy; oltin varaq (foil) effektli ulkan "Hayo"
portretning boshi ORTIDA; ingichka qora/oltin chiziqlar; keng harf oralig'idagi yupqa
sans-serif + yuqori kontrastli serif. Muhim qismlar markaziy 1080×1440 (profil to'ri 3:4
kesimi) ichida: y 240..1680.
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
from render import (W, H, hx, text, tw, sprite, arch_path, paint_pic, round_rect,  # noqa: E402
                    draw_sprite, HANDLE, BLACK)

INK = hx("#0e0e10")
GRAY = hx("#55524d")
GOLD_HAIR = hx("#b8913f")
FOIL = ((0.00, "#7a4f16"), (0.18, "#c99a45"), (0.38, "#f7e3a3"), (0.50, "#e2bb65"),
        (0.66, "#a8742a"), (0.84, "#d9b05c"), (1.00, "#8c5e1f"))

ARCH = (196, 884, 846, 628, 1236)  # x0, x1, spring, apex, bottom


def foil_text(ctx, s, fkey, size, cx, baseline, shadow=True):
    """Text filled with a metallic gold-foil gradient (sprite used as a mask)."""
    sp = sprite(s, fkey, size, (1, 1, 1, 1))
    ox = cx - sp.w / 2
    x0, y0 = ox - sp.pad, baseline - sp.asc - sp.pad
    if shadow:
        sh = sprite(s, fkey, size, BLACK, 0.0, None, 22)
        draw_sprite(ctx, sh, cx, baseline + 14, 0.16, 1.0, "c")
    top = baseline - sp.asc * 0.80
    g = cairo.LinearGradient(cx - 40, top, cx + 40, baseline + sp.desc * 0.5)
    for off, c in FOIL:
        g.add_color_stop_rgba(off, *hx(c)[:3], 1)
    ctx.set_source(g)
    ctx.mask_surface(sp.surf, x0, y0)
    # fine specular sweep across the letters
    g2 = cairo.LinearGradient(ox + sp.w * 0.15, top, ox + sp.w * 0.55, baseline)
    g2.add_color_stop_rgba(0.0, 1, 1, 1, 0)
    g2.add_color_stop_rgba(0.5, 1, 0.98, 0.9, 0.35)
    g2.add_color_stop_rgba(1.0, 1, 1, 1, 0)
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_ADD)
    ctx.set_source(g2)
    ctx.mask_surface(sp.surf, x0, y0)
    ctx.restore()


def ig_mono(ctx, cx, cy, s, color=INK):
    """Monochrome Instagram glyph (luxury, single colour)."""
    x0, y0 = cx - s / 2, cy - s / 2
    ctx.set_source_rgba(*color[:3], 1)
    ctx.set_line_width(s * 0.085)
    round_rect(ctx, x0, y0, s, s, s * 0.28)
    ctx.stroke()
    ctx.arc(cx, cy, s * 0.22, 0, 2 * math.pi)
    ctx.stroke()
    ctx.arc(x0 + s * 0.76, y0 + s * 0.24, s * 0.055, 0, 2 * math.pi)
    ctx.fill()


def diamond(ctx, x, y, r):
    ctx.move_to(x, y - r)
    ctx.line_to(x + r, y)
    ctx.line_to(x, y + r)
    ctx.line_to(x - r, y)
    ctx.close_path()


def main():
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    ctx.set_source_rgba(1, 1, 1, 1)
    ctx.paint()
    x0, x1, sp, ap, bt = ARCH
    # floating-card shadow: blurred arch silhouette (neutral grey)
    from PIL import Image, ImageFilter
    ms = cairo.ImageSurface(cairo.FORMAT_A8, W, H)
    mc = cairo.Context(ms)
    arch_path(mc, x0 + 10, x1 - 10, sp + 20, ap + 20, bt)
    mc.fill()
    ms.flush()
    st = ms.get_stride()
    m = np.ndarray((H, st), np.uint8, ms.get_data())[:, :W].copy()
    m = np.asarray(Image.fromarray(m).filter(ImageFilter.GaussianBlur(34)))
    shade = R.Pic(np.zeros((H, W, 3), np.uint8), (m * 0.20).astype(np.uint8))
    paint_pic(ctx, shade, 1.0, 0, 30)
    # portrait inside the arch
    pic, cut = P.G["p0x"], P.G["p0cut"]
    s = 0.62
    eyes = (1110, 480 + P.EXT0)
    tx, ty = 540 - eyes[0] * s, 846 - eyes[1] * s
    ctx.save()
    arch_path(ctx, x0, x1, sp, ap, bt)
    ctx.clip()
    paint_pic(ctx, pic, s, tx, ty)
    R.vgrad(ctx, bt - 200, bt, 0, 0.12, (0, 0, 0))
    ctx.restore()
    # hairline frames: thin black on the photo edge, gold offset outside
    arch_path(ctx, x0, x1, sp, ap, bt)
    ctx.set_source_rgba(*INK[:3], 0.9)
    ctx.set_line_width(1.4)
    ctx.stroke()
    arch_path(ctx, x0 - 18, x1 + 18, sp, ap - 18, bt + 18)
    ctx.set_source_rgba(*GOLD_HAIR[:3], 1)
    ctx.set_line_width(1.2)
    ctx.stroke()
    # giant gold-foil "Hayo" behind the head
    foil_text(ctx, "Hayo", "serif_it_b", 336, 540, 640)
    # head breaks out of the arch
    ctx.save()
    ctx.rectangle(0, 0, W, sp - 60)
    ctx.clip()
    ctx.push_group()
    paint_pic(ctx, cut, s, tx + 5, ty + 9)
    shd = ctx.pop_group()
    ctx.set_source_rgba(0, 0, 0, 0.12)
    ctx.mask(shd)
    paint_pic(ctx, cut, s, tx, ty)
    ctx.restore()
    # typography below ---------------------------------------------------------
    text(ctx, "naqadar goʻzal", "xlight", 74, INK, 540, 1368, align="c", tracking=11)
    yd = 1426
    ctx.set_source_rgba(*GOLD_HAIR[:3], 1)
    ctx.set_line_width(1.2)
    for sd in (-1, 1):
        ctx.move_to(540 + sd * 22, yd)
        ctx.line_to(540 + sd * 250, yd)
    ctx.stroke()
    diamond(ctx, 540, yd, 7)
    ctx.fill()
    hadis = "«Hayo faqat yaxshilik keltiradi»."
    text(ctx, hadis, "serif_it", 44, GRAY, 540, 1500, align="c")
    # Instagram + name
    size = 30
    ic = size * 1.25
    gap = size * 0.55
    total = ic + gap + tw(HANDLE, "med", size, 3)
    hx0 = 540 - total / 2
    yb = 1586
    ig_mono(ctx, hx0 + ic / 2, yb - size * 0.36, ic)
    text(ctx, HANDLE, "med", size, INK, hx0 + ic + gap, yb, tracking=3)
    surf.flush()
    out = os.path.join(ROOT, "output", "hayo_naqadar_gozal_cover")
    surf.write_to_png(out + ".png")
    from PIL import Image
    a = np.ndarray((H, W, 4), np.uint8, surf.get_data())
    Image.fromarray(a[..., [2, 1, 0]].copy()).save(out + ".jpg", quality=95)
    print("tayyor:", out + ".png", out + ".jpg")


if __name__ == "__main__":
    main()
