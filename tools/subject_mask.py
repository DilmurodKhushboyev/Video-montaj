#!/usr/bin/env python3
"""
subject_mask.py — subyekt niqobi (GrabCut) — "matn odam ortida", parallaks, rangli/oq-qora
qisman ochilish uchun.

  python3 tools/subject_mask.py <rasm> <chiqish_mask.png> --rect x0 y0 x1 y1
        [--fg x0 y0 x1 y1 ...] [--fge cx cy rx ry ...] [--bg x0 y0 x1 y1 ...]
        [--work 900] [--feather 2.0] [--iters 6] [--preview prev.jpg]

  --rect  subyekt to'liq ichida bo'lgan to'rtburchak (tashqarisi aniq fon);
  --fg    aniq subyekt to'rtburchaklari; --fge aniq subyekt ellipslari (yuz);
  --bg    aniq fon to'rtburchaklari.
Koordinatalar asl rasm pikselida. Hisob --work kenglikda bajariladi, so'ng
niqob kattalashtirilib, chetlari yumshatiladi.
"""
import argparse

import cv2
import numpy as np
from PIL import Image, ImageFilter


def quads(v, n):
    return [v[i:i + n] for i in range(0, len(v or []), n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--rect", nargs=4, type=float, required=True)
    ap.add_argument("--fg", nargs="+", type=float)
    ap.add_argument("--fge", nargs="+", type=float)
    ap.add_argument("--bg", nargs="+", type=float)
    ap.add_argument("--work", type=int, default=900)
    ap.add_argument("--feather", type=float, default=2.0)
    ap.add_argument("--iters", type=int, default=6)
    ap.add_argument("--preview")
    a = ap.parse_args()
    img = np.asarray(Image.open(a.src).convert("RGB"))
    H, W = img.shape[:2]
    k = a.work / W
    sm = cv2.resize(img, (a.work, int(round(H * k))), interpolation=cv2.INTER_AREA)
    bgr = cv2.cvtColor(sm, cv2.COLOR_RGB2BGR)
    mask = np.full(sm.shape[:2], cv2.GC_BGD, np.uint8)
    x0, y0, x1, y1 = [int(round(v * k)) for v in a.rect]
    mask[y0:y1, x0:x1] = cv2.GC_PR_FGD
    for q in quads(a.bg, 4):
        bx0, by0, bx1, by1 = [int(round(v * k)) for v in q]
        mask[by0:by1, bx0:bx1] = cv2.GC_BGD
    for q in quads(a.fg, 4):
        fx0, fy0, fx1, fy1 = [int(round(v * k)) for v in q]
        mask[fy0:fy1, fx0:fx1] = cv2.GC_FGD
    for q in quads(a.fge, 4):
        cx, cy, rx, ry = [int(round(v * k)) for v in q]
        cv2.ellipse(mask, (cx, cy), (rx, ry), 0, 0, 360, int(cv2.GC_FGD), -1)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(bgr, mask, None, bgd, fgd, a.iters, cv2.GC_INIT_WITH_MASK)
    m = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    # keep the largest connected component(s) only
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    if n > 2:
        keep = 1 + np.argsort(-stats[1:, cv2.CC_STAT_AREA])
        big = stats[keep[0], cv2.CC_STAT_AREA]
        m2 = np.zeros_like(m)
        for kk in keep:
            if stats[kk, cv2.CC_STAT_AREA] > big * 0.08:
                m2[lab == kk] = 255
        m = m2
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    full = cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)
    mi = Image.fromarray(full).filter(ImageFilter.GaussianBlur(a.feather / k * 0.5))
    mi.save(a.out)
    if a.preview:
        al = np.asarray(mi, np.float32)[..., None] / 255
        vis = img * al + np.array([255, 0, 120]) * (1 - al) * 0.6 + img * (1 - al) * 0.4
        Image.fromarray(vis.astype(np.uint8)).resize((900, int(900 * H / W))).save(a.preview,
                                                                                  quality=88)
    print("niqob:", a.out, f"({(full > 127).mean() * 100:.1f}% subyekt)")


if __name__ == "__main__":
    main()
