#!/usr/bin/env python3
"""
split_and_upscale.py — kollajni kadrlarga ajratish va waifu2x (cunet, ncnn) bilan kattalashtirish.

    python3 tools/split_and_upscale.py kollaj.png models/ assets/images/<nom>/ [--scale 4]
                                       [--noise 1] [--no-split] [--prefix p]

* Kadrlar orasidagi oq yoki qora chiziqlar (gutter) avtomatik topiladi: avval to'liq
  eni bo'ylab gorizontal chiziqlar, so'ng har qator ichida vertikal chiziqlar.
* Har kadr chetidagi 1-3 px qoldiq chiziq kesib tashlanadi.
* waifu2x cunet 2x modeli (noise{0,1}_scale2.0x_model.{param,bin}) plitkalab ishlaydi;
  --scale 4 -> ikki marta 2x.
* panels.json — har kadrning kollajdagi to'rtburchagi (x0, y0, x1, y1) va fayl nomi.
"""
import argparse
import json
import os
import sys
import time

import numpy as np
from PIL import Image


def runs(mask, min_len=2):
    out, s = [], None
    for i, v in enumerate(mask):
        if v and s is None:
            s = i
        elif not v and s is not None:
            if i - s >= min_len:
                out.append((s, i))
            s = None
    if s is not None and len(mask) - s >= min_len:
        out.append((s, len(mask)))
    return out


def gutter_mask(a):
    lo, hi = a.min(2), a.max(2)
    return (lo > 232) | (hi < 14)


def split(a):
    g = gutter_mask(a)
    H, W = g.shape
    hr = runs(g.mean(1) > 0.92)
    ys = [0] + [y for r in hr for y in r] + [H]
    bands = [(ys[i], ys[i + 1]) for i in range(0, len(ys), 2) if ys[i + 1] - ys[i] > 40]
    rects = []
    for y0, y1 in bands:
        vr = runs(g[y0:y1].mean(0) > 0.92)
        xs = [0] + [x for r in vr for x in r] + [W]
        for i in range(0, len(xs), 2):
            x0, x1 = xs[i], xs[i + 1]
            if x1 - x0 > 40:
                rects.append([x0, y0, x1, y1])
    # trim leftover light/dark edge lines
    out = []
    for x0, y0, x1, y1 in rects:
        sub = g[y0:y1, x0:x1]
        while y1 - y0 > 40 and sub[0].mean() > 0.5:
            y0 += 1
            sub = g[y0:y1, x0:x1]
        while y1 - y0 > 40 and sub[-1].mean() > 0.5:
            y1 -= 1
            sub = g[y0:y1, x0:x1]
        while x1 - x0 > 40 and sub[:, 0].mean() > 0.5:
            x0 += 1
            sub = g[y0:y1, x0:x1]
        while x1 - x0 > 40 and sub[:, -1].mean() > 0.5:
            x1 -= 1
            sub = g[y0:y1, x0:x1]
        out.append([x0 + 1, y0 + 1, x1 - 1, y1 - 1])  # 1 px safety
    return out


class Waifu2x:
    PAD = 18

    def __init__(self, mdir, noise=1, threads=None):
        import ncnn
        self.ncnn = ncnn
        self.net = ncnn.Net()
        self.net.opt.use_vulkan_compute = False
        self.net.opt.num_threads = threads or os.cpu_count() or 4
        base = os.path.join(mdir, f"noise{noise}_scale2.0x_model")
        self.net.load_param(base + ".param")
        self.net.load_model(base + ".bin")

    def _run(self, tile):
        """tile: float32 HxWx3 in 0..1 (already padded). Returns 2x output float32."""
        m = self.ncnn.Mat(np.ascontiguousarray(tile.transpose(2, 0, 1)))
        ex = self.net.create_extractor()
        ex.input("Input1", m)
        _, out = ex.extract("Eltwise4")
        return np.array(out).transpose(1, 2, 0)

    def up2(self, rgb, tile=192):
        x = rgb.astype(np.float32) / 255.0
        h, w = x.shape[:2]
        P = self.PAD
        xp = np.pad(x, ((P, P + tile), (P, P + tile), (0, 0)), mode="edge")
        out = np.zeros((h * 2, w * 2, 3), np.float32)
        for ty in range(0, h, tile):
            for tx in range(0, w, tile):
                th, tw = min(tile, h - ty), min(tile, w - tx)
                th4, tw4 = (th + 3) // 4 * 4, (tw + 3) // 4 * 4
                inp = xp[ty:ty + th4 + 2 * P, tx:tx + tw4 + 2 * P]
                o = self._run(inp)
                oh, ow = o.shape[:2]
                # cunet output is 2*(in - 2*PAD) after its own cropping; centre-crop if larger
                cy, cx = (oh - th4 * 2) // 2, (ow - tw4 * 2) // 2
                out[ty * 2:(ty + th) * 2, tx * 2:(tx + tw) * 2] = o[cy:cy + th * 2, cx:cx + tw * 2]
        return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("models")
    ap.add_argument("outdir")
    ap.add_argument("--scale", type=int, default=4, choices=(1, 2, 4))
    ap.add_argument("--noise", type=int, default=1)
    ap.add_argument("--no-split", action="store_true")
    ap.add_argument("--prefix", default="p")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    img = np.asarray(Image.open(a.src).convert("RGB"))
    rects = [[0, 0, img.shape[1], img.shape[0]]] if a.no_split else split(img)
    print(f"{len(rects)} ta kadr topildi")
    wx = Waifu2x(a.models, a.noise) if a.scale > 1 else None
    meta = []
    for i, (x0, y0, x1, y1) in enumerate(rects):
        crop = img[y0:y1, x0:x1]
        t0 = time.time()
        up = crop
        if wx:
            up = wx.up2(up)
            if a.scale == 4:
                up = wx.up2(up)
        name = f"{a.prefix}{i:02d}.png"
        Image.fromarray(up).save(os.path.join(a.outdir, name))
        meta.append({"file": name, "rect": [x0, y0, x1, y1], "size": [up.shape[1], up.shape[0]]})
        print(f"  {name}: {x1 - x0}x{y1 - y0} -> {up.shape[1]}x{up.shape[0]}  "
              f"({time.time() - t0:.1f}s)", flush=True)
    with open(os.path.join(a.outdir, "panels.json"), "w") as fh:
        json.dump({"source": os.path.basename(a.src), "size": [img.shape[1], img.shape[0]],
                   "panels": meta}, fh, indent=1)


if __name__ == "__main__":
    sys.exit(main())
