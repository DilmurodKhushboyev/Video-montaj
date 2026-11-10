"""Vizual effektlar: kamera, rang gradatsiyasi, bloom, nur, linza yorqinligi, zarrachalar."""
import math
import os

import cv2
import numpy as np

W, H, FPS = 1080, 1920, 30
QW, QH = W // 4, H // 4
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL_DIR = os.path.join(ROOT, "build", "panels_x4")


def hexbgr(h):
    h = h.lstrip("#")
    r, g, b = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return np.array([b, g, r], np.float32)


WHITE = hexbgr("FFFDF6")
GOLD = hexbgr("FFCC5C")
GOLD_HI = hexbgr("FFE49A")
GOLD_DEEP = hexbgr("D8982E")
WARM = hexbgr("FFC27A")
SUN = hexbgr("FFB25C")
COOL = hexbgr("BFD6FF")


# ----------------------------------------------------------------- easing
def ease(p, kind="io"):
    p = min(max(p, 0.0), 1.0)
    if kind == "lin":
        return p
    if kind == "i":
        return p ** 3
    if kind == "i2":
        return p * p
    if kind == "o":
        return 1 - (1 - p) ** 3
    if kind == "o2":
        return 1 - (1 - p) ** 2
    if kind == "io":
        return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2
    if kind == "sine":
        return -(math.cos(math.pi * p) - 1) / 2
    if kind == "expo_o":
        return 1.0 if p >= 1 else 1 - 2 ** (-10 * p)
    if kind == "back_o":
        c1 = 1.70158
        c3 = c1 + 1
        return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2
    raise ValueError(kind)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ----------------------------------------------------------------- panels / camera
_panels = {}


def panel(name):
    if name not in _panels:
        img = cv2.imread(os.path.join(PANEL_DIR, name + ".png"), cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(name)
        _panels[name] = img
    return _panels[name]


def cam_matrix(pw, ph, cx, cy, z, rot_deg=0.0, off=(0.0, 0.0)):
    """Panel koordinatasidan (px) chiqish kadriga affine matritsa. Kadr chetdan chiqmasligi uchun markaz cheklanadi."""
    s = max(W / pw, H / ph) * z
    hw, hh = W / (2 * s), H / (2 * s)
    px = min(max(cx * pw, hw), pw - hw) if pw > 2 * hw else pw / 2
    py = min(max(cy * ph, hh), ph - hh) if ph > 2 * hh else ph / 2
    a = math.radians(rot_deg)
    ca, sa = math.cos(a) * s, math.sin(a) * s
    M = np.array([[ca, -sa, 0.0], [sa, ca, 0.0]], np.float32)
    M[0, 2] = W / 2 + off[0] - (ca * px - sa * py)
    M[1, 2] = H / 2 + off[1] - (sa * px + ca * py)
    return M


def warp_panel(name, cx, cy, z, rot=0.0, off=(0.0, 0.0)):
    img = panel(name)
    ph, pw = img.shape[:2]
    M = cam_matrix(pw, ph, cx, cy, z, rot, off)
    out = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT101)
    return out.astype(np.float32) * (1.0 / 255.0), M, pw, ph


def map_point(M, x, y):
    return (float(M[0, 0] * x + M[0, 1] * y + M[0, 2]), float(M[1, 0] * x + M[1, 1] * y + M[1, 2]))


# ----------------------------------------------------------------- grading
LUMW = np.array([0.114, 0.587, 0.299], np.float32)
GRADES = {
    "heaven": dict(exp=0.92, contrast=1.15, sat=1.10, warm=0.035, knee=0.87,
                   sh=(0.03, 0.012, -0.01), hi=(-0.025, 0.0, 0.02)),
    "earth": dict(exp=1.0, contrast=1.08, sat=1.10, warm=0.03, knee=0.86,
                  sh=(0.025, 0.008, -0.01), hi=(-0.02, 0.0, 0.018)),
    "interior": dict(exp=0.98, contrast=1.15, sat=1.06, warm=0.06, knee=0.84,
                     sh=(0.02, 0.0, -0.012), hi=(-0.035, 0.0, 0.03)),
    "dusk": dict(exp=1.0, contrast=1.12, sat=1.14, warm=0.05, knee=0.86,
                 sh=(0.045, 0.0, -0.02), hi=(-0.035, 0.0, 0.03)),
}


def grade(img, g, exp_add=0.0):
    e = g["exp"] * (1 + exp_add)
    w = g["warm"]
    img *= np.array([e * (1 - w), e, e * (1 + w)], np.float32)
    c = g["contrast"]
    img -= 0.42
    img *= c
    img += 0.42
    lum = img @ LUMW
    l3 = lum[..., None]
    img = l3 + (img - l3) * g["sat"]
    img += (1 - l3) * np.array(g["sh"], np.float32) + l3 * np.array(g["hi"], np.float32)
    k = g["knee"]
    over = np.maximum(img - k, 0)
    img -= over - over / (1 + over / (1.0 - k))
    np.clip(img, 0, 1, out=img)
    return img


def quarter(img):
    return cv2.resize(img, (QW, QH), interpolation=cv2.INTER_AREA)


def bloom(img, small, strength, thr=0.76):
    if strength <= 0:
        return img
    lum = small.max(axis=2)
    m = np.clip((lum - thr) / (1 - thr), 0, 1)
    b = small * (m * m)[..., None]
    bb = cv2.GaussianBlur(b, (0, 0), 3) * 0.55 + cv2.GaussianBlur(b, (0, 0), 13) * 0.9
    up = cv2.resize(bb, (W, H), interpolation=cv2.INTER_LINEAR)
    img += up * strength * (1 - img)
    return img


def god_rays(img, small, src, strength, thr=0.74, length=0.5, steps=12, tint=WARM):
    """Rasmning yorug' joylaridan manbadan tarqaluvchi hajmli nurlar (crepuscular rays)."""
    if strength <= 0:
        return img
    lum = small.max(axis=2)
    m = np.clip((lum - thr) / (1 - thr), 0, 1) ** 2
    lx, ly = src[0] / 4.0, src[1] / 4.0
    acc = m.copy()
    tot = 1.0
    for i in range(1, steps + 1):
        s = 1.0 / (1 - length * i / steps)
        wgt = 0.93 ** i
        M = np.float32([[s, 0, (1 - s) * lx], [0, s, (1 - s) * ly]])
        acc += cv2.warpAffine(m, M, (QW, QH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT) * wgt
        tot += wgt
    acc /= tot
    acc = cv2.GaussianBlur(acc, (0, 0), 1.5)
    up = cv2.resize(acc, (W, H), interpolation=cv2.INTER_LINEAR)
    img += (up[..., None] * tint) * (strength * 1.0) * (1 - img)
    return img


_YY, _XX = np.mgrid[0:QH, 0:QW].astype(np.float32)


def lens_flare(img, pos, intensity, color=SUN):
    if intensity <= 0:
        return img
    px, py = pos[0] / 4.0, pos[1] / 4.0
    d2 = (_XX - px) ** 2 + (_YY - py) ** 2
    core = np.exp(-d2 / (2 * 5 ** 2)) + np.exp(-d2 / (2 * 22 ** 2)) * 0.35 + np.exp(-d2 / (2 * 70 ** 2)) * 0.14
    streak = np.exp(-((_YY - py) ** 2) / (2 * 1.1 ** 2)) * np.exp(-((_XX - px) ** 2) / (2 * 150 ** 2)) * 0.55
    layer = core[..., None] * color + streak[..., None] * COOL
    cx, cy = QW / 2.0, QH / 2.0
    for k, r, a, col in ((0.45, 7, 0.10, GOLD_HI), (0.9, 16, 0.05, COOL), (1.35, 4, 0.14, SUN),
                         (1.7, 26, 0.04, GOLD), (2.1, 9, 0.07, COOL)):
        gx, gy = px + (cx - px) * k, py + (cy - py) * k
        g = np.exp(-((_XX - gx) ** 2 + (_YY - gy) ** 2) / (2 * r * r))
        layer += g[..., None] * col * a
    up = cv2.resize(layer, (W, H), interpolation=cv2.INTER_LINEAR)
    img += up * intensity * (1 - img)
    return img


def light_leak(t, seed, intensity, palette=(SUN, hexbgr("FF9A6A"), GOLD_HI)):
    if intensity <= 0:
        return None
    sw, shh = W // 8, H // 8
    yy, xx = np.mgrid[0:shh, 0:sw].astype(np.float32)
    layer = np.zeros((shh, sw, 3), np.float32)
    for i, col in enumerate(palette):
        ph = seed * 1.7 + i * 2.1
        cx = sw * (0.5 + 0.55 * math.sin(t * 0.9 + ph))
        cy = shh * (0.5 + 0.5 * math.cos(t * 0.6 + ph * 1.3))
        r = sw * (0.45 + 0.15 * math.sin(t * 1.3 + ph))
        g = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r))
        layer += g[..., None] * col
    return cv2.resize(layer, (W, H), interpolation=cv2.INTER_LINEAR) * intensity


class Particles:
    """Sekin suzuvchi oltin chang zarralari va bokeh doiralar."""

    def __init__(self, n, seed, color=GOLD_HI, bokeh=6):
        rng = np.random.default_rng(seed)
        self.x0 = rng.uniform(0, W, n)
        self.y0 = rng.uniform(0, H, n)
        self.vy = rng.uniform(-70, -12, n)
        self.vx = rng.uniform(-12, 12, n)
        self.amp = rng.uniform(4, 26, n)
        self.fq = rng.uniform(0.15, 0.6, n)
        self.ph = rng.uniform(0, 2 * math.pi, n)
        self.r = rng.uniform(1.0, 3.2, n)
        self.tw = rng.uniform(1.0, 3.5, n)
        self.color = color
        self.bx = rng.uniform(0, W, bokeh)
        self.by = rng.uniform(0, H, bokeh)
        self.br = rng.uniform(26, 70, bokeh)
        self.bv = rng.uniform(-25, -6, bokeh)

    def layer(self, t, intensity):
        hw, hh = W // 2, H // 2
        lay = np.zeros((hh, hw, 3), np.float32)
        x = (self.x0 + self.vx * t + self.amp * np.sin(2 * math.pi * self.fq * t + self.ph)) % W
        y = (self.y0 + self.vy * t) % H
        a = 0.55 + 0.45 * np.sin(2 * math.pi * self.tw * t + self.ph)
        for i in range(len(x)):
            col = tuple(float(c * a[i]) for c in self.color)
            cv2.circle(lay, (int(x[i] / 2 * 16), int(y[i] / 2 * 16)), max(1, int(self.r[i] / 2 * 16)), col, -1,
                       cv2.LINE_AA, shift=4)
        lay = cv2.GaussianBlur(lay, (0, 0), 1.0) * 1.6 + cv2.GaussianBlur(lay, (0, 0), 4.0) * 1.2
        # bokeh
        qb = np.zeros((QH, QW, 3), np.float32)
        for i in range(len(self.bx)):
            by = (self.by[i] + self.bv[i] * t) % H
            cv2.circle(qb, (int(self.bx[i] / 4), int(by / 4)), int(self.br[i] / 4), tuple(float(c) * 0.10 for c in self.color),
                       -1, cv2.LINE_AA)
        qb = cv2.GaussianBlur(qb, (0, 0), 2.0)
        out = cv2.resize(lay, (W, H), interpolation=cv2.INTER_LINEAR) + cv2.resize(qb, (W, H), interpolation=cv2.INTER_LINEAR)
        return out * intensity


def fast_blur(img, sigma):
    if sigma < 0.5:
        return img
    if sigma < 6:
        return cv2.GaussianBlur(img, (0, 0), sigma)
    small = cv2.resize(img, (QW, QH), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), sigma / 4.0)
    return cv2.resize(small, (W, H), interpolation=cv2.INTER_LINEAR)


def chroma(img, k):
    """Radial xromatik aberratsiya (o'tishlarda)."""
    if k < 0.4:
        return img
    s = 1 + k / (W / 2)
    M1 = np.float32([[s, 0, (1 - s) * W / 2], [0, s, (1 - s) * H / 2]])
    s2 = 1 / s
    M2 = np.float32([[s2, 0, (1 - s2) * W / 2], [0, s2, (1 - s2) * H / 2]])
    b = cv2.warpAffine(np.ascontiguousarray(img[..., 0]), M1, (W, H), borderMode=cv2.BORDER_REFLECT101)
    r = cv2.warpAffine(np.ascontiguousarray(img[..., 2]), M2, (W, H), borderMode=cv2.BORDER_REFLECT101)
    img[..., 0] = b
    img[..., 2] = r
    return img


# vinyetka va pastki matn zonasi uchun yumshoq qorong'ilash
_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
_r = np.sqrt(((_xx - W / 2) / (W * 0.62)) ** 2 + ((_yy - H / 2) / (H * 0.60)) ** 2)
VIGNETTE = (1 - 0.42 * smoothstep(0.55, 1.3, _r))[..., None].astype(np.float32)
del _yy, _xx, _r
_y = np.arange(H, dtype=np.float32)
BAND = (0.40 * smoothstep(1010, 1250, _y) * (1 - 0.40 * smoothstep(1480, 1900, _y)))[:, None, None].astype(np.float32)
TOPBAND = (0.42 * smoothstep(180, 330, _y) * (1 - smoothstep(640, 820, _y)))[:, None, None].astype(np.float32)

_grain = None


def grain(i):
    global _grain
    if _grain is None:
        rng = np.random.default_rng(7)
        _grain = [cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 0.7)[..., None] for _ in range(6)]
    return _grain[i % 6]
