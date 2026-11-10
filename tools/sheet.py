#!/usr/bin/env python3
"""sheet.py — kontakt varaq: python3 tools/sheet.py out.jpg COLS img1.png img2.png ...
   [--w 360] [--grid 200] (grid: rasm koordinata to'ri, har N px, asl o'lchamda)"""
import sys

from PIL import Image, ImageDraw, ImageFont


def main():
    args = sys.argv[1:]
    opts = {"--w": 360, "--grid": 0}
    for k in list(opts):
        if k in args:
            i = args.index(k)
            opts[k] = int(args[i + 1])
            del args[i:i + 2]
    out, cols, files = args[0], int(args[1]), args[2:]
    tw = opts["--w"]
    ims = []
    for f in files:
        im = Image.open(f).convert("RGB")
        if opts["--grid"]:
            d = ImageDraw.Draw(im)
            g = opts["--grid"]
            fnt = ImageFont.load_default(size=max(14, im.width // 60))
            for x in range(0, im.width, g):
                d.line([(x, 0), (x, im.height)], fill=(255, 0, 0), width=2)
                d.text((x + 4, 4), str(x), fill=(255, 255, 0), font=fnt)
            for y in range(0, im.height, g):
                d.line([(0, y), (im.width, y)], fill=(255, 0, 0), width=2)
                d.text((4, y + 4), str(y), fill=(255, 255, 0), font=fnt)
        th = round(im.height * tw / im.width)
        ims.append((im.resize((tw, th), Image.LANCZOS), f.rsplit("/", 1)[-1]))
    rows = (len(ims) + cols - 1) // cols
    rh = [max(im.height for im, _ in ims[r * cols:(r + 1) * cols]) + 22 for r in range(rows)]
    sheet = Image.new("RGB", (cols * (tw + 6), sum(rh)), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    y = 0
    for r in range(rows):
        for c, (im, name) in enumerate(ims[r * cols:(r + 1) * cols]):
            sheet.paste(im, (c * (tw + 6), y))
            d.text((c * (tw + 6) + 4, y + im.height + 4), name, fill=(220, 220, 220))
        y += rh[r]
    sheet.save(out, quality=88)
    print(out, sheet.size)


if __name__ == "__main__":
    main()
