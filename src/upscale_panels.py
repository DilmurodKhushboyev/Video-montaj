"""Panellarni Real-ESRGAN (x4plus-anime, ncnn CPU) bilan 4x kattalashtirish."""
import os, sys, glob, time
import numpy as np
import ncnn
from PIL import Image

MODEL_DIR = sys.argv[1]
SRC = sys.argv[2] if len(sys.argv) > 2 else "build/panels"
OUT = sys.argv[3] if len(sys.argv) > 3 else "build/panels_x4"
MODEL = os.environ.get("ESRGAN_MODEL", "realesrgan-x4plus-anime")
os.makedirs(OUT, exist_ok=True)

net = ncnn.Net()
net.opt.use_vulkan_compute = False
net.opt.num_threads = int(os.environ.get("THREADS", "4"))
net.load_param(os.path.join(MODEL_DIR, MODEL + ".param"))
net.load_model(os.path.join(MODEL_DIR, MODEL + ".bin"))

TILE, PAD, SCALE = 200, 12, 4

def run(arr):  # arr: HxWx3 float32 0..1
    h, w, _ = arr.shape
    # numpy buferi Mat ishlatilayotganda yashab turishi kerak (aks holda xotira buziladi)
    buf = np.ascontiguousarray(arr.transpose(2, 0, 1), dtype=np.float32)
    mat = ncnn.Mat(buf).clone()
    ex = net.create_extractor()
    ex.input("data", mat)
    _, out = ex.extract("output")
    res = np.array(out, copy=True).transpose(1, 2, 0)
    del buf
    return res

for f in sorted(glob.glob(os.path.join(SRC, "*.png"))):
    dst = os.path.join(OUT, os.path.basename(f))
    if os.path.exists(dst):
        continue
    t = time.time()
    img = np.asarray(Image.open(f).convert("RGB")).astype(np.float32) / 255.0
    H, W, _ = img.shape
    res = np.zeros((H * SCALE, W * SCALE, 3), np.float32)
    padded = np.pad(img, ((PAD, PAD), (PAD, PAD), (0, 0)), mode="reflect")
    for y in range(0, H, TILE):
        for x in range(0, W, TILE):
            th, tw = min(TILE, H - y), min(TILE, W - x)
            tile = padded[y:y + th + 2 * PAD, x:x + tw + 2 * PAD]
            o = run(tile)
            res[y * SCALE:(y + th) * SCALE, x * SCALE:(x + tw) * SCALE] = \
                o[PAD * SCALE:(PAD + th) * SCALE, PAD * SCALE:(PAD + tw) * SCALE]
    Image.fromarray((np.clip(res, 0, 1) * 255 + 0.5).astype(np.uint8)).save(dst)
    print(os.path.basename(f), f"{time.time() - t:.1f}s", flush=True)
