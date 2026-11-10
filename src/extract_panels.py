"""Collage rasmlardan har bir panelni alohida kesib olish."""
import os, sys
from PIL import Image

SRC = sys.argv[1] if len(sys.argv) > 1 else "assets/collages"
OUT = sys.argv[2] if len(sys.argv) > 2 else "build/panels"
os.makedirs(OUT, exist_ok=True)

# (fayl, panel nomi, x0, y0, x1, y1) -- oq chegaralar avtomatik topilgan
PANELS = {
    "collage_a.png": {  # 1212x1297, 2 ustun x 4 qator
        "A1": (0, 0, 525, 343), "A2": (529, 0, 1212, 343),
        "A3": (0, 346, 598, 652), "A4": (602, 346, 1212, 652),
        "A5": (0, 656, 598, 964), "A6": (602, 656, 1212, 964),
        "A7": (0, 968, 598, 1297), "A8": (602, 968, 1212, 1297),
    },
    "collage_b.png": {  # 1672x941, 3 + 2 + 1
        "B1": (0, 0, 516, 345), "B2": (520, 0, 1114, 345), "B3": (1154, 0, 1672, 345),
        "B4": (0, 349, 834, 646), "B5": (839, 349, 1672, 646),
        "B6": (0, 649, 1672, 941),
    },
    "collage_c.png": {  # 1672x941, 3x3
        "C1": (0, 0, 555, 316), "C2": (560, 0, 1118, 316), "C3": (1123, 0, 1672, 316),
        "C4": (0, 321, 555, 624), "C5": (560, 321, 1118, 624), "C6": (1123, 321, 1672, 624),
        "C7": (0, 629, 555, 941), "C8": (560, 629, 1118, 941), "C9": (1123, 629, 1672, 941),
    },
    "collage_d.png": {  # 1672x941, 3x3
        "D1": (0, 0, 555, 312), "D2": (559, 0, 1114, 312), "D3": (1119, 0, 1672, 312),
        "D4": (0, 316, 555, 626), "D5": (559, 316, 1114, 626), "D6": (1119, 316, 1672, 626),
        "D7": (0, 630, 555, 941), "D8": (559, 630, 1114, 941), "D9": (1119, 630, 1672, 941),
    },
}
INSET = 3  # chegara chiziqlari qolmasligi uchun

for fname, panels in PANELS.items():
    im = Image.open(os.path.join(SRC, fname)).convert("RGB")
    W, H = im.size
    for name, (x0, y0, x1, y1) in panels.items():
        box = (x0 + (INSET if x0 > 0 else 1), y0 + (INSET if y0 > 0 else 1),
               x1 - (INSET if x1 < W else 1), y1 - (INSET if y1 < H else 1))
        im.crop(box).save(os.path.join(OUT, f"{name}.png"))
        print(name, box[2] - box[0], box[3] - box[1])
