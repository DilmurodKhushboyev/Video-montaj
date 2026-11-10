#!/usr/bin/env python3
"""
cutout.py — subyektni fondan ajratish (IS-Net anime, onnxruntime). Anime/illyustratsiya
uslubidagi rasmlar uchun; natija — alfa kanalli PNG (RGBA) va alohida niqob.

    python3 tools/cutout.py in.png out.png [--model models/isnet-anime.onnx]
                            [--thresh 0.5] [--soft 0.12] [--feather 1.2] [--mask mask.png]

Model: https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-anime.onnx
`pip install onnxruntime`
"""
import argparse
import os

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def predict(img, model):
    import onnxruntime as ort
    sess = ort.InferenceSession(model, providers=["CPUExecutionProvider"])
    im = np.asarray(img.convert("RGB").resize((1024, 1024), Image.LANCZOS)).astype(np.float32)
    im /= max(im.max(), 1e-6)
    im = (im - np.array([0.485, 0.456, 0.406], np.float32)) / 1.0
    x = im.transpose(2, 0, 1)[None].astype(np.float32)
    out = sess.run(None, {sess.get_inputs()[0].name: x})[0][0, 0]
    out = (out - out.min()) / max(out.max() - out.min(), 1e-6)
    m = Image.fromarray((out * 255).astype(np.uint8)).resize(img.size, Image.LANCZOS)
    return np.asarray(m).astype(np.float32) / 255.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--model", default=os.path.join(HERE, "models", "isnet-anime.onnx"))
    ap.add_argument("--thresh", type=float, default=0.5)
    ap.add_argument("--soft", type=float, default=0.12)
    ap.add_argument("--feather", type=float, default=1.2)
    ap.add_argument("--mask")
    a = ap.parse_args()
    img = Image.open(a.src).convert("RGB")
    p = predict(img, a.model)
    m = np.clip((p - (a.thresh - a.soft / 2)) / a.soft, 0, 1)
    mi = Image.fromarray((m * 255).astype(np.uint8))
    if a.feather:
        mi = mi.filter(ImageFilter.GaussianBlur(a.feather))
    if a.mask:
        mi.save(a.mask)
    rgba = img.copy()
    rgba.putalpha(mi)
    rgba.save(a.out)
    print(a.out, img.size)


if __name__ == "__main__":
    main()
