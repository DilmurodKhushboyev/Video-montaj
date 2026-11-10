"""
zal_tana_cover — Instagram Reels muqovasi (1080x1920), qizil fon, zamonaviy poster uslubi.

    python3 projects/zal_tana_cover.py [--variant clean|sticker]

Natija: output/zal_tana_cover.png (+ .jpg; --variant sticker -> *_sticker) va
previews/cover_grid_3x4.jpg (profil to'ridagi
3:4 kesim — barcha muhim elementlar y 240..1680 oralig'ida).
Matnlar videodagi birinchi jumladan harfma-harf: "Chiroyli va mushakdor tanani pulga sotib
ololmaysiz." Subyekt — p02 (tools/cutout.py, IS-Net anime niqobi).
"""
import os
import sys

HERE_P = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE_P))
import render as R  # noqa: E402

R.configure(size=(1080, 1920))
from render import *  # noqa: F401,F403,E402

ROOT = os.path.dirname(HERE_P)
RED_TOP, RED_MID, RED_BOT = hx("#7c0911"), hx("#c8151f"), hx("#3e0306")
CREAM = hx("#fff4ea")
INK = hx("#14090a")


def layer_from_alpha(alpha, color, blur=0, grow=0):
    """Solid-colour RGBA layer from an alpha mask (optionally dilated / blurred)."""
    m = Image.fromarray(alpha)
    if grow:
        m = m.filter(ImageFilter.MaxFilter(grow * 2 + 1))
    if blur:
        m = m.filter(ImageFilter.GaussianBlur(blur))
    a = np.asarray(m)
    rgb = np.empty(a.shape + (3,), np.uint8)
    rgb[...] = (np.array(color[:3]) * 255).astype(np.uint8)
    return Pic(rgb, a)


def rim_layer(alpha, color, width=10, blur=6):
    """Thin light rim along the subject edge (mask minus eroded mask)."""
    m = Image.fromarray(alpha)
    inner = m.filter(ImageFilter.MinFilter(width * 2 + 1))
    rim = np.clip(np.asarray(m, np.int16) - np.asarray(inner, np.int16), 0, 255).astype(np.uint8)
    rim = np.asarray(Image.fromarray(rim).filter(ImageFilter.GaussianBlur(blur)))
    rgb = np.empty(rim.shape + (3,), np.uint8)
    rgb[...] = (np.array(color[:3]) * 255).astype(np.uint8)
    return Pic(rgb, rim)


def grain(ctx, a=0.09, seed=7):
    g = np.random.default_rng(seed).normal(128, 40, (H, W)).clip(0, 255).astype(np.uint8)
    p = Pic(np.repeat(g[..., None], 3, 2))
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_OVERLAY)
    ctx.set_source_surface(p.surf, 0, 0)
    ctx.paint_with_alpha(a)
    ctx.restore()


def pill(ctx, x, y, w, h, fill, alpha, stroke=None):
    round_rect(ctx, x, y, w, h, h / 2)
    ctx.set_source_rgba(*fill[:3], alpha)
    ctx.fill_preserve()
    if stroke:
        ctx.set_source_rgba(*stroke[:3], stroke[3])
        ctx.set_line_width(2)
        ctx.stroke()
    ctx.new_path()


def handle_pill(ctx, cx, y, size=40):
    tw_ = tw(HANDLE, "semi", size, 1.5)
    isz = size * 1.25
    pad = size * 0.75
    w = pad + isz + size * 0.45 + tw_ + pad
    h = size * 2.05
    x0 = cx - w / 2
    ctx.save()
    ctx.set_source_rgba(0, 0, 0, 0.25)
    round_rect(ctx, x0 + 4, y + 10, w, h, h / 2)
    ctx.fill()
    ctx.restore()
    pill(ctx, x0, y, w, h, INK, 0.92, (1, 1, 1, 0.22))
    insta_icon(ctx, x0 + pad + isz / 2, y + h / 2, isz)
    text(ctx, HANDLE, "semi", size, CREAM, x0 + pad + isz + size * 0.45, y + h / 2 + size * 0.36,
         tracking=1.5)


def sticker(ctx, s, fkey, size, x, y, rot, bg, fg, padx=34, pady=22, shadow=True):
    """Text on a solid tilted block (x, y — centre of the baseline)."""
    sp = sprite(s, fkey, size, fg)
    w = sp.w + 2 * padx
    hgt = sp.asc * 0.78 + 2 * pady
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    if shadow:
        ctx.set_source_rgba(0, 0, 0, 0.35)
        ctx.rectangle(-w / 2 + 10, -sp.asc * 0.78 - pady + 14, w, hgt)
        ctx.fill()
    ctx.set_source_rgba(*bg[:3], 1)
    ctx.rectangle(-w / 2, -sp.asc * 0.78 - pady, w, hgt)
    ctx.fill()
    draw_sprite(ctx, sp, 0, pady * 0.15, 1.0, 1.0, "c")
    ctx.restore()


def main():
    variant = "clean"
    if "--variant" in sys.argv:
        variant = sys.argv[sys.argv.index("--variant") + 1]
    cut = np.asarray(Image.open(os.path.join(IDIR, "zal", "p02_cut.png")).convert("RGBA"))
    rgb = grade(cut[..., :3], sat=1.04, contrast=1.06, gain=(1.03, 1.0, 0.97))
    alpha = cut[..., 3]
    subj = Pic(rgb, alpha)
    shadow = layer_from_alpha(alpha, (0.12, 0.0, 0.01), blur=26)
    outline = layer_from_alpha(alpha, CREAM, blur=1.2, grow=7)
    rim = rim_layer(alpha, hx("#ff7a5c"), width=9, blur=5)

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)

    # --- background: deep red, light behind the head, rings, grain
    bg_grad(ctx, RED_TOP, RED_BOT, RED_MID)
    hx_, hy_ = 600, 900
    glow(ctx, hx_, hy_, 760, hx("#ff5a3a"), 0.55)
    glow(ctx, hx_, hy_ - 80, 360, hx("#ffb08a"), 0.18)
    for r_, a_ in ((420, 0.16), (520, 0.09), (640, 0.05)):
        ctx.set_line_width(2)
        ctx.set_source_rgba(1, 1, 1, a_)
        ctx.arc(hx_, hy_, r_, 0, 2 * math.pi)
        ctx.stroke()
    # fine diagonal hairlines (texture)
    ctx.save()
    ctx.set_source_rgba(1, 1, 1, 0.035)
    ctx.set_line_width(1.5)
    for k in range(-30, 60):
        x = k * 38
        ctx.move_to(x, 0)
        ctx.line_to(x - 900, H)
    ctx.stroke()
    ctx.restore()

    # --- kicker
    k_txt = "Chiroyli va mushakdor"
    ky = 380
    kw = tw(k_txt, "semi", 48, 3)
    text(ctx, k_txt, "semi", 48, CREAM, W / 2, ky, align="c", tracking=3, shadow=10, shadow_a=0.35)
    ctx.set_source_rgba(*CREAM[:3], 0.7)
    ctx.set_line_width(2)
    for sd in (-1, 1):
        ctx.move_to(W / 2 + sd * (kw / 2 + 22), ky - 17)
        ctx.line_to(W / 2 + sd * (kw / 2 + 92), ky - 17)
    ctx.stroke()

    # --- giant word behind the subject
    gsz = fit("tanani", "anton", 520, 980, -6)
    gy = 782
    g = sprite("tanani", "anton", gsz, CREAM, -6, (hx("#ffffff"), hx("#ffd9cf")))
    sh = sprite("tanani", "anton", gsz, BLACK, -6, None, 18)
    draw_sprite(ctx, sh, W / 2 + 6, gy + 16, 0.35, 1.0, "c")
    draw_sprite(ctx, g, W / 2, gy, 1.0, 1.0, "c")

    # --- subject
    s = 0.80
    x0, y0 = 600 - 1000 * s, 738 - 150 * s
    paint_pic(ctx, shadow, s, x0 + 16, y0 + 30, 0.75, pad=False)
    if variant == "sticker":
        paint_pic(ctx, outline, s, x0, y0, 1.0, pad=False)
    paint_pic(ctx, subj, s, x0, y0, pad=False)
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_ADD)
    paint_pic(ctx, rim, s, x0, y0, 0.55, pad=False)
    ctx.restore()

    # --- bottom: fade the cut edge into deep red
    vgrad(ctx, 1300, 1700, 0, 1.0, RED_BOT)

    # --- hook line
    text(ctx, "pulga sotib", "anton", 124, CREAM, W / 2, 1478, align="c", tracking=2, shadow=16,
         shadow_a=0.55)
    sticker(ctx, "ololmaysiz.", "anton", 128, W / 2, 1652, -0.035, CREAM, hx("#c8151f"))

    # --- author (top: stays inside the 3:4 profile-grid crop)
    handle_pill(ctx, W / 2, 250, 32)

    grain(ctx, 0.10)
    vignette(ctx, 0.35)
    surf.flush()
    out = os.path.join(ROOT, "output", "zal_tana_cover.png")
    if variant != "clean":
        out = out.replace(".png", f"_{variant}.png")
    surf.write_to_png(out)
    im = Image.open(out).convert("RGB")
    im.save(out.replace(".png", ".jpg"), quality=95)
    os.makedirs(os.path.join(ROOT, "previews"), exist_ok=True)
    grid = "cover_grid_3x4.jpg" if variant == "clean" else f"cover_grid_3x4_{variant}.jpg"
    im.crop((0, 240, 1080, 1680)).save(os.path.join(ROOT, "previews", grid), quality=90)
    print("tayyor:", out)


if __name__ == "__main__":
    main()
