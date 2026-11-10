"""
"Hayo naqadar goʻzal" — Reels uchun zamonaviy cover, OQ fon, 1080×1920.

    python3 projects/hayo_cover.py            # -> output/hayo_naqadar_gozal_cover.png/.jpg

Uslub (zamonaviy poster): fon faqat sof oq (#ffffff); odam kesmasi yumshoq soya bilan
ajralib turadi, pastga qarab oqqa singib ketadi; ulkan qora "Hayo"
(Anton) boshi ORTIDA; tepada Instagram tugmasi va hadis kicker; pastda ikki qiya yorliq
("naqadar" qora, "goʻzal" oltin). Muhim qismlar markaziy 3:4 kesim (y 240..1680) ichida.
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
from render import (W, H, hx, text, tw, sprite, draw_sprite, paint_pic, round_rect,  # noqa: E402
                    instagram_icon, HANDLE, BLACK, Pic)

INK = hx("#0f0f11")
EMER_1, EMER_2 = hx("#16996c"), hx("#0a5139")
EMER = hx("#0f7a55")
GOLD_1, GOLD_2 = hx("#f6d57a"), hx("#d7a23a")
GRAY = hx("#3b3d3c")

# geometry
S = 0.82                       # cutout scale
EYES = (540, 1040)             # where his eyes land
ARCH_R, ARCH_CY = 480, 1240    # semicircle top: centre (540, 1240), top at y=760
HAYO_SIZE, HAYO_BASE = 440, 830


def arch_shape(ctx, grow=0.0):
    r = ARCH_R + grow
    ctx.move_to(540 - r, H + 10)
    ctx.line_to(540 - r, ARCH_CY)
    ctx.arc(540, ARCH_CY, r, math.pi, 2 * math.pi)
    ctx.line_to(540 + r, H + 10)
    ctx.close_path()


def blurred_alpha_pic(alpha, blur, a, color=(0, 0, 0)):
    m = np.asarray(Image.fromarray(alpha).filter(ImageFilter.GaussianBlur(blur)), np.float32)
    rgb = np.zeros(alpha.shape + (3,), np.uint8)
    rgb[:] = [int(c * 255) for c in color[:3]]
    return Pic(rgb, (m * a).astype(np.uint8))


def layer_alpha(draw):
    """Render draw(ctx) into an A8 mask and return it as a numpy array."""
    ms = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    mc = cairo.Context(ms)
    draw(mc)
    ms.flush()
    return np.ndarray((H, W, 4), np.uint8, ms.get_data())[..., 3].copy()


def sparkle(ctx, x, y, r, color):
    k = r * 0.13
    ctx.save()
    ctx.translate(x, y)
    ctx.move_to(0, -r)
    ctx.curve_to(k, -k, k, -k, r, 0)
    ctx.curve_to(k, k, k, k, 0, r)
    ctx.curve_to(-k, k, -k, k, -r, 0)
    ctx.curve_to(-k, -k, -k, -k, 0, -r)
    ctx.close_path()
    ctx.set_source_rgba(*color[:3], 1)
    ctx.fill()
    ctx.restore()


def diamond(ctx, x, y, r):
    ctx.move_to(x, y - r)
    ctx.line_to(x + r, y)
    ctx.line_to(x, y + r)
    ctx.line_to(x - r, y)
    ctx.close_path()


def label(ctx, s, fkey, size, cx, cy, rot, fill, txt_color, pad=(34, 16), grad=None):
    """Tilted sticker label: solid box + text (with a soft drop shadow)."""
    f = R.font(fkey, size)
    asc, desc = f.getmetrics()
    bb = f.getbbox(s)
    tw_ = f.getlength(s)
    cap_top, cap_bot = bb[1], bb[3]           # relative to the text top (ascent origin)
    hh = cap_bot - cap_top
    bw, bh = tw_ + 2 * pad[0], hh + 2 * pad[1]
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(rot)
    for k, a in ((14, 0.06), (8, 0.08), (3, 0.10)):
        ctx.set_source_rgba(0, 0, 0, a)
        ctx.rectangle(-bw / 2 - k / 2 + 6, -bh / 2 - k / 2 + 12, bw + k, bh + k)
        ctx.fill()
    if grad:
        g = cairo.LinearGradient(0, -bh / 2, 0, bh / 2)
        g.add_color_stop_rgba(0, *grad[0][:3], 1)
        g.add_color_stop_rgba(1, *grad[1][:3], 1)
        ctx.set_source(g)
    else:
        ctx.set_source_rgba(*fill[:3], 1)
    ctx.rectangle(-bw / 2, -bh / 2, bw, bh)
    ctx.fill()
    # baseline so that the caps sit centred in the box
    base = -hh / 2 - cap_top + asc
    text(ctx, s, fkey, size, txt_color, 0, base, align="c")
    ctx.restore()


def main():
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    ctx.set_source_rgba(1, 1, 1, 1)
    ctx.paint()
    # background: pure white only

    # giant "Hayo" (behind the head) ------------------------------------------
    sh = sprite("Hayo", "anton", HAYO_SIZE, BLACK, 0.0, None, 18)
    draw_sprite(ctx, sh, 540, HAYO_BASE + 12, 0.16, 1.0, "c")
    text(ctx, "Hayo", "anton", HAYO_SIZE, INK, 540, HAYO_BASE, align="c")

    # subject cutout ------------------------------------------------------------
    cut = P.G["p0cut"]
    ex, ey = 1110, 480 + P.EXT0
    tx, ty = EYES[0] - ex * S, EYES[1] - ey * S
    bottom = ty + cut.h * S
    fade0 = bottom - 170

    def draw_cut(c):
        c.save()
        c.push_group()
        paint_pic(c, cut, S, tx, ty)
        g2 = cairo.LinearGradient(0, fade0, 0, bottom)
        g2.add_color_stop_rgba(0, 0, 0, 0, 1)
        g2.add_color_stop_rgba(1, 0, 0, 0, 0)
        c.set_operator(cairo.OPERATOR_DEST_IN)
        c.set_source(g2)
        c.paint()
        c.set_operator(cairo.OPERATOR_OVER)
        c.pop_group_to_source()
        c.paint()
        c.restore()

    al = layer_alpha(draw_cut)
    paint_pic(ctx, blurred_alpha_pic(al, 26, 0.30), 1.0, 0, 20)
    draw_cut(ctx)

    # top: Instagram pill + hadith kicker ----------------------------------
    hs = 32
    ic = hs * 1.3
    gap = hs * 0.45
    total = ic + gap + tw(HANDLE, "semi", hs, 1.5)
    px0 = 540 - total / 2
    py = 296
    round_rect(ctx, px0 - 28, py - 34, total + 56, 68, 34)
    ctx.set_source_rgba(*INK[:3], 1)
    ctx.fill()
    instagram_icon(ctx, px0 + ic / 2, py, ic, 1.0)
    text(ctx, HANDLE, "semi", hs, hx("#ffffff"), px0 + ic + gap, py + hs * 0.36, tracking=1.5)

    kick = "«Hayo faqat yaxshilik keltiradi»."
    src = "(Muttafaqun alayh)."
    ks, ss = 34, 27
    kw = tw(kick, "semi", ks, 0.5)
    sw = tw(src, "reg", ss, 0.5)
    gap2 = 14
    full = kw + gap2 + sw
    kx = 540 - full / 2
    ky = 408
    text(ctx, kick, "semi", ks, GRAY, kx, ky, tracking=0.5)
    text(ctx, src, "reg", ss, hx("#7d817f"), kx + kw + gap2, ky, tracking=0.5)
    ctx.set_source_rgba(*EMER[:3], 1)
    ctx.set_line_width(2.2)
    for sd in (-1, 1):
        x_in = 540 + sd * (full / 2 + 20)
        ctx.move_to(x_in, ky - 12)
        ctx.line_to(x_in + sd * 40, ky - 12)
        ctx.stroke()
        diamond(ctx, x_in + sd * 48, ky - 12, 5)
        ctx.fill()

    # accents
    sparkle(ctx, 968, 470, 26, GOLD_2)
    sparkle(ctx, 1004, 540, 12, EMER)
    sparkle(ctx, 104, 860, 16, GOLD_2)

    # bottom labels ------------------------------------------------------------
    label(ctx, "naqadar", "anton", 118, 516, 1424, math.radians(-3.0), INK, hx("#ffffff"))
    label(ctx, "goʻzal", "anton", 150, 566, 1592, math.radians(2.2), None, INK,
          grad=(GOLD_1, GOLD_2))

    surf.flush()
    out = os.path.join(ROOT, "output", "hayo_naqadar_gozal_cover")
    surf.write_to_png(out + ".png")
    a = np.ndarray((H, W, 4), np.uint8, surf.get_data())
    Image.fromarray(a[..., [2, 1, 0]].copy()).save(out + ".jpg", quality=95)
    print("tayyor:", out + ".png", out + ".jpg")


if __name__ == "__main__":
    main()
