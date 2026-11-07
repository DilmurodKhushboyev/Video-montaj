#!/usr/bin/env python3
"""
sheet.py — kontakt varaq: bir nechta rasmni nomi bilan to'rga joylash.

    python3 tools/sheet.py chiqish.jpg <ustunlar> rasm1.png rasm2.png ... [--w 360]
"""
import os
import sys

from PIL import Image, ImageDraw


def main():
    args = sys.argv[1:]
    tw = 360
    if "--w" in args:
        k = args.index("--w")
        tw = int(args[k + 1])
        del args[k:k + 2]
    out, cols, files = args[0], int(args[1]), args[2:]
    ims = []
    for f in files:
        im = Image.open(f).convert("RGB")
        im = im.resize((tw, max(1, round(im.height * tw / im.width))), Image.LANCZOS)
        ims.append((os.path.basename(f), im))
    th = max(im.height for _, im in ims) + 26
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + 8) + 8, rows * (th + 8) + 8), (18, 18, 22))
    d = ImageDraw.Draw(sheet)
    for i, (name, im) in enumerate(ims):
        x, y = 8 + (i % cols) * (tw + 8), 8 + (i // cols) * (th + 8)
        sheet.paste(im, (x, y))
        d.text((x + 4, y + im.height + 6), name, fill=(240, 220, 160))
    sheet.save(out, quality=88)
    print(out, sheet.size)


if __name__ == "__main__":
    main()
