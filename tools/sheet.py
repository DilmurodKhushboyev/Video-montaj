#!/usr/bin/env python3
"""
sheet.py — kontakt varaq (preview kadrlarni bitta rasmga yig'ish) va koordinata to'ri.

  python3 tools/sheet.py <chiqish.jpg> <ustunlar> <rasm1> <rasm2> ...  [--w 360]
  python3 tools/sheet.py --grid <rasm> <chiqish.jpg> [--step 200] [--w 1000]
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont


def contact(out, cols, paths, cw=360):
    ims = [Image.open(p).convert("RGB") for p in paths]
    ims = [im.resize((cw, int(im.height * cw / im.width))) for im in ims]
    ch = max(im.height for im in ims)
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (cw + 6) + 6, rows * (ch + 30) + 6), (18, 18, 20))
    dr = ImageDraw.Draw(sheet)
    for i, (im, p) in enumerate(zip(ims, paths)):
        x, y = 6 + (i % cols) * (cw + 6), 6 + (i // cols) * (ch + 30)
        sheet.paste(im, (x, y))
        dr.text((x + 4, y + ch + 6), os.path.basename(p), fill=(230, 230, 230))
    sheet.save(out, quality=90)


def grid(src, out, step=200, w=1000):
    im = Image.open(src).convert("RGB")
    k = w / im.width
    sm = im.resize((w, int(im.height * k)))
    dr = ImageDraw.Draw(sm)
    for x in range(0, im.width, step):
        dr.line([(x * k, 0), (x * k, sm.height)], fill=(255, 60, 60), width=1)
        dr.text((x * k + 2, 2), str(x), fill=(255, 255, 0))
    for y in range(0, im.height, step):
        dr.line([(0, y * k), (sm.width, y * k)], fill=(60, 160, 255), width=1)
        dr.text((2, y * k + 2), str(y), fill=(255, 255, 0))
    sm.save(out, quality=90)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--grid":
        step = int(a[a.index("--step") + 1]) if "--step" in a else 200
        w = int(a[a.index("--w") + 1]) if "--w" in a else 1000
        grid(a[1], a[2], step, w)
    else:
        cw = 360
        if "--w" in a:
            k = a.index("--w")
            cw = int(a[k + 1])
            a = a[:k] + a[k + 2:]
        contact(a[0], int(a[1]), a[2:], cw)
