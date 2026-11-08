#!/usr/bin/env python3
"""
split_and_upscale.py — kollajni kadrlarga ajratish va har kadrni waifu2x (CUNet, ncnn)
bilan 4x kattalashtirish.

  python3 tools/split_and_upscale.py <kollaj.png> <models_dir> <out_dir> [--scale 4]
  python3 tools/split_and_upscale.py <rasm.jpg> <models_dir> <out_dir> --single

* Kadrlar orasidagi oq/qora chiziqlar (gutter) avtomatik topiladi: avval to'liq kenglikdagi
  gorizontal chiziqlar (qatorlar), so'ng har qator ichida vertikal chiziqlar.
* Natija: out_dir/panel_XX.png (kattalashtirilgan), out_dir/panels.json
  ({"source": [w, h], "panels": [[x0, y0, x1, y1], ...], "scale": 4}).
* Modellar: models-cunet/noise{0,1}_scale2.0x_model.{param,bin}
  (raw.githubusercontent.com/nihui/waifu2x-ncnn-vulkan/master/models/models-cunet/)
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

PAD = 18      # CUNet 2x prepadding: out = (in - 2*PAD) * 2
TILE = 200


def find_runs(mask, min_len):
    runs, i, n = [], 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            if j - i >= min_len:
                runs.append((i, j))
            i = j
        else:
            i += 1
    return runs


def gutter_mask(a, axis, frac):
    """True where a line (row if axis=1) is almost entirely white or black."""
    lum = a.mean(2)
    white = (a.min(2) > 225)
    black = (lum < 18)
    fw = white.mean(axis)
    fb = black.mean(axis)
    return (fw > frac) | (fb > frac)


def split(a, min_panel=60):
    h, w = a.shape[:2]
    rows_g = gutter_mask(a, 1, 0.96)
    bands = find_runs(~rows_g, min_panel)
    rects = []
    for y0, y1 in bands:
        band = a[y0:y1]
        cols_g = gutter_mask(band, 0, 0.93)
        cols = find_runs(~cols_g, min_panel)
        for x0, x1 in cols:
            # refine vertical extent inside this column (panels in a row may differ)
            sub = a[y0:y1, x0:x1]
            rg = gutter_mask(sub, 1, 0.93)
            inner = find_runs(~rg, min_panel)
            if inner:
                yy0, yy1 = inner[0][0] + y0, inner[-1][1] + y0
            else:
                yy0, yy1 = y0, y1
            rects.append([int(x0), int(yy0), int(x1), int(yy1)])
    return rects


class Waifu:
    def __init__(self, models, noise):
        import ncnn
        self.ncnn = ncnn
        self.net = ncnn.Net()
        self.net.opt.use_vulkan_compute = False
        self.net.opt.num_threads = os.cpu_count() or 4
        base = os.path.join(models, f"noise{noise}_scale2.0x_model")
        self.net.load_param(base + ".param")
        self.net.load_model(base + ".bin")

    def up2(self, rgb):
        """rgb uint8 (h, w, 3) -> uint8 (2h, 2w, 3)."""
        h, w = rgb.shape[:2]
        x = rgb.astype(np.float32) / 255.0
        xp = np.pad(x, ((PAD, PAD + TILE), (PAD, PAD + TILE), (0, 0)), mode="reflect")
        out = np.zeros((2 * h, 2 * w, 3), np.float32)
        for ty in range(0, h, TILE):
            for tx in range(0, w, TILE):
                tile = xp[ty:ty + TILE + 2 * PAD, tx:tx + TILE + 2 * PAD]
                inp = np.ascontiguousarray(tile.transpose(2, 0, 1))
                ex = self.net.create_extractor()
                ex.input("Input1", self.ncnn.Mat(inp))
                _, o = ex.extract("Eltwise4")
                o = np.array(o).transpose(1, 2, 0)
                hh = min(TILE, h - ty) * 2
                ww = min(TILE, w - tx) * 2
                out[ty * 2:ty * 2 + hh, tx * 2:tx * 2 + ww] = o[:hh, :ww]
        return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)


def upscale(rgb, models, scale):
    passes = {2: [1], 4: [1, 0], 8: [1, 0, 0]}[scale]
    nets = {}
    for nz in passes:
        if nz not in nets:
            nets[nz] = Waifu(models, nz)
        rgb = nets[nz].up2(rgb)
    return rgb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("models")
    ap.add_argument("out")
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--single", action="store_true")
    ap.add_argument("--inset", type=int, default=2, help="kadr chetidan kesiladigan px")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    img = np.asarray(Image.open(a.src).convert("RGB"))
    h, w = img.shape[:2]
    rects = [[0, 0, w, h]] if a.single else split(img)
    k = a.inset
    rects = [[x0 + k, y0 + k, x1 - k, y1 - k] for x0, y0, x1, y1 in rects]
    print(f"{len(rects)} ta kadr topildi")
    for i, (x0, y0, x1, y1) in enumerate(rects):
        crop = img[y0:y1, x0:x1]
        up = upscale(crop, a.models, a.scale)
        p = os.path.join(a.out, f"panel_{i:02d}.png")
        Image.fromarray(up).save(p)
        print(f"  {i:02d}: [{x0},{y0},{x1},{y1}] {x1 - x0}x{y1 - y0} -> {up.shape[1]}x{up.shape[0]}")
    with open(os.path.join(a.out, "panels.json"), "w") as fh:
        json.dump({"source": [w, h], "panels": rects, "scale": a.scale}, fh, indent=1)


if __name__ == "__main__":
    sys.exit(main())
