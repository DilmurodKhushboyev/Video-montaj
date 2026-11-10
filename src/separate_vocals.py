"""MDX-Net (UVR) ONNX modeli bilan nutqni fon musiqasidan ajratish.
Foydalanish: python separate_vocals.py model.onnx input.wav out_prefix
Natija: out_prefix_vocals.wav va out_prefix_music.wav (music = mix - vocals)."""
import sys
import numpy as np
import soundfile as sf
import onnxruntime as ort
from scipy.signal import resample_poly

model_path, inp, outp = sys.argv[1:4]
N_FFT, HOP, DIM_F, DIM_T = 7680, 1024, 3072, 256
N_BINS = N_FFT // 2 + 1
CHUNK = HOP * (DIM_T - 1)
TRIM = N_FFT // 2
GEN = CHUNK - 2 * TRIM
WIN = np.hanning(N_FFT + 1)[:-1].astype(np.float32)  # periodic hann

def stft(x):  # x: [2, CHUNK] -> [2, N_BINS, DIM_T] complex (center=True, reflect)
    xp = np.pad(x, ((0, 0), (N_FFT // 2, N_FFT // 2)), mode="reflect")
    idx = np.arange(DIM_T)[:, None] * HOP + np.arange(N_FFT)[None, :]
    frames = xp[:, idx] * WIN  # [2, T, N_FFT]
    return np.fft.rfft(frames, axis=-1).transpose(0, 2, 1)

def istft(X):  # X: [2, N_BINS, DIM_T] -> [2, CHUNK]
    frames = np.fft.irfft(X.transpose(0, 2, 1), n=N_FFT, axis=-1) * WIN
    L = N_FFT + HOP * (DIM_T - 1)
    out = np.zeros((2, L), np.float64); wsum = np.zeros(L, np.float64)
    for t in range(DIM_T):
        out[:, t * HOP:t * HOP + N_FFT] += frames[:, t]
        wsum[t * HOP:t * HOP + N_FFT] += WIN ** 2
    out /= np.maximum(wsum, 1e-8)
    return out[:, N_FFT // 2:N_FFT // 2 + CHUNK]

mix, sr = sf.read(inp, dtype="float32", always_2d=True)
mix = mix.T
if mix.shape[0] == 1:
    mix = np.repeat(mix, 2, 0)
orig_sr = sr
if sr != 44100:
    mix = resample_poly(mix, 44100, sr, axis=1).astype(np.float32); sr = 44100
n = mix.shape[1]
pad = GEN - n % GEN
mp = np.concatenate([np.zeros((2, TRIM)), mix, np.zeros((2, pad)), np.zeros((2, TRIM))], 1).astype(np.float32)
sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
voc = []
# yarim siljish bilan ikki marta o'tib, chegaralardagi artefaktlarni kamaytirish
for i in range(0, n + pad, GEN):
    w = mp[:, i:i + CHUNK]
    if w.shape[1] < CHUNK:
        w = np.pad(w, ((0, 0), (0, CHUNK - w.shape[1])))
    X = stft(w)[:, :DIM_F]  # [2, F, T]
    inp_t = np.stack([X[0].real, X[0].imag, X[1].real, X[1].imag])[None].astype(np.float32)
    o = sess.run(None, {"input": inp_t})[0][0]
    Y = np.zeros((2, N_BINS, DIM_T), np.complex64)
    Y[0, :DIM_F] = o[0] + 1j * o[1]
    Y[1, :DIM_F] = o[2] + 1j * o[3]
    voc.append(istft(Y)[:, TRIM:-TRIM])
    print(f"chunk {i / sr:.1f}s", flush=True)
voc = np.concatenate(voc, 1)[:, :n].astype(np.float32)
music = mix - voc
if orig_sr != sr:
    voc = resample_poly(voc, orig_sr, sr, axis=1); music = resample_poly(music, orig_sr, sr, axis=1)
sf.write(outp + "_vocals.wav", voc.T, orig_sr, subtype="FLOAT")
sf.write(outp + "_music.wav", music.T, orig_sr, subtype="FLOAT")
print("done")
