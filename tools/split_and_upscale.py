#!/usr/bin/env python3
"""
split_and_upscale.py — kollajni kadrlarga ajratish (oq/qora chiziqlar avtomatik topiladi)
va har kadrni waifu2x (ncnn, CPU) bilan 4x kattalashtirish.

    python3 tools/split_and_upscale.py kollaj.png models/ assets/images/ [--prefix k1] [--scale 4]
    python3 tools/split_and_upscale.py rasm.jpg   models/ assets/images/ --single
    python3 tools/split_and_upscale.py kollaj.png models/ assets/images/ --crop 880,318,1150,600 \
        --scale 8 --prefix makro          # bitta bo'lakni (masalan, muqova yuragi) 8x makro

Chiqish: <out>/<prefix>_<qator><ustun>.png va <out>/<prefix>_panels.json
(kollajdagi to'rtburchaklar, original piksellarda).
Modellar: models/noise{0,1}_scale2.0x_model.{param,bin} (waifu2x models-cunet).
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

PRE = 18          # cunet prepadding
TILE = 200        # inner tile -> net input TILE + 2*PRE, output 2*TILE


def gutters(lum, axis, std_max=18, lo=25, hi=225, min_frac=0.06):
    """Uniform near-white/near-black lines across the whole image -> cut positions."""
    s, m = lum.std(axis), lum.mean(axis)
    idx = [i for i in range(len(s)) if s[i] < std_max and (m[i] > hi or m[i] < lo)]
    groups = []
    for i in idx:
        if groups and i - groups[-1][1] <= 1:
            groups[-1][1] = i
        else:
            groups.append([i, i])
    n = len(s)
    # keep only interior gutters (not borders) and not tiny panels
    return [(a, b) for a, b in groups if a > n * min_frac and b < n * (1 - min_frac)]


def panels(rgb, inset=2):
    lum = rgb.astype(np.float32).mean(2)
    h, w = lum.shape
    rg = gutters(lum, 1)
    cg = gutters(lum, 0)
    ys = [0] + [v for a, b in rg for v in (a, b + 1)] + [h]
    xs = [0] + [v for a, b in cg for v in (a, b + 1)] + [w]
    rects = []
    for r in range(0, len(ys), 2):
        for c in range(0, len(xs), 2):
            y0, y1, x0, x1 = ys[r], ys[r + 1], xs[c], xs[c + 1]
            rects.append((r // 2, c // 2, x0 + inset, y0 + inset, x1 - inset, y1 - inset))
    return rects


class Waifu2x:
    def __init__(self, models, noise):
        import ncnn
        self.net = ncnn.Net()
        self.net.opt.use_vulkan_compute = False
        self.net.opt.num_threads = os.cpu_count() or 4
        base = os.path.join(models, f"noise{noise}_scale2.0x_model")
        self.net.load_param(base + ".param")
        self.net.load_model(base + ".bin")
        self.ncnn = ncnn

    def x2(self, rgb):
        h, w = rgb.shape[:2]
        x = rgb.astype(np.float32).transpose(2, 0, 1) / 255.0
        ph, pw = (-h) % TILE, (-w) % TILE
        xp = np.pad(x, ((0, 0), (PRE, PRE + ph), (PRE, PRE + pw)), mode="edge")
        out = np.zeros((3, (h + ph) * 2, (w + pw) * 2), np.float32)
        for ty in range(0, h + ph, TILE):
            for tx in range(0, w + pw, TILE):
                tile = np.ascontiguousarray(xp[:, ty:ty + TILE + 2 * PRE, tx:tx + TILE + 2 * PRE])
                ex = self.net.create_extractor()
                ex.input("Input1", self.ncnn.Mat(tile))
                _, o = ex.extract("Eltwise4")
                out[:, ty * 2:(ty + TILE) * 2, tx * 2:(tx + TILE) * 2] = np.array(o)
        out = out[:, :h * 2, :w * 2]
        return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8).transpose(1, 2, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("models")
    ap.add_argument("out")
    ap.add_argument("--prefix", default=None)
    ap.add_argument("--scale", type=int, default=4, choices=(1, 2, 4, 8))
    ap.add_argument("--crop", help="x0,y0,x1,y1 — faqat shu bo'lak (--single bilan)")
    ap.add_argument("--single", action="store_true", help="kollaj emas, bitta rasm")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rgb = np.asarray(Image.open(a.src).convert("RGB"))
    if a.crop:
        x0, y0, x1, y1 = map(int, a.crop.split(","))
        rgb = rgb[y0:y1, x0:x1]
        a.single = True
    prefix = a.prefix or os.path.splitext(os.path.basename(a.src))[0]
    rects = [(0, 0, 0, 0, rgb.shape[1], rgb.shape[0])] if a.single else panels(rgb)
    w1 = Waifu2x(a.models, 1) if a.scale >= 2 else None
    w0 = Waifu2x(a.models, 0) if a.scale >= 4 else None
    passes = [w for w in (w1, w0) if w] + ([w0] if a.scale == 8 else [])
    meta = []
    for r, c, x0, y0, x1, y1 in rects:
        crop = rgb[y0:y1, x0:x1]
        for net in passes:
            crop = net.x2(crop)
        name = f"{prefix}.png" if a.single else f"{prefix}_{r}{c}.png"
        Image.fromarray(crop).save(os.path.join(a.out, name))
        meta.append({"name": name, "rect": [x0, y0, x1, y1], "row": r, "col": c,
                     "size": [crop.shape[1], crop.shape[0]]})
        print(name, crop.shape[1], "x", crop.shape[0], flush=True)
    json.dump({"src": os.path.basename(a.src), "panels": meta},
              open(os.path.join(a.out, f"{prefix}_panels.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
