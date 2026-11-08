# Video-montaj

Premium vertikal (1080×1920) montaj dvigateli. Yo'riqnoma: [`SKILL.md`](SKILL.md).

## Tuzilma
- `render.py` — dvigatel (asboblar qutisi + parallel render). Sahnalar unda emas.
- `projects/<nom>.py` — har video o'z fayli; `projects/ideas_log.json` — ishlatilgan g'oyalar.
- `tools/`
  - `analyze_audio.py` — pauzalar, bass zarbalari, onsetlar, spektrogramma.
  - `split_and_upscale.py` — kollajni kadrlarga ajratish + waifu2x (ncnn) 4x.
  - `subject_mask.py` — GrabCut subyekt niqobi (matn odam ortida, parallaks).
  - `mix_audio.py` — hikoya ovozi + fon nashid/musiqa (kesish/loop, balandlik).
  - `sheet.py` — kontakt varaq va koordinata to'ri.
- `assets/` — shriftlar, rasmlar (`panels/`, `masks/`), audio.
- `output/` — tayyor videolar.

## O'rnatish
```bash
pip install pycairo pillow numpy scipy ncnn opencv-python-headless
# shriftlar: Inter (v3.19 otf) + Playfair Display (variable ttf) -> assets/fonts/
# waifu2x modellari -> models/ (qarang SKILL.md)
```

## "Hayo naqadar goʻzal" (namuna)
```bash
python3 tools/split_and_upscale.py assets/images/kollaj.png models assets/images/panels
python3 tools/mix_audio.py assets/audio/hayo_ovoz.wav assets/audio/subhan_allah.mp3 \
    assets/audio/hayo_mix.m4a --dur 46.5 --voice-offset 0.4 --voice-gain-db 10.8 \
    --music-start 145.63 --bed-db -19 --open-db -9.5 --speech 0.75 43.84 --fade-out 1.9
python3 render.py projects/hayo_naqadar_gozal.py assets/audio/hayo_mix.m4a --preview 1.9 10.4
python3 render.py projects/hayo_naqadar_gozal.py assets/audio/hayo_mix.m4a
```
