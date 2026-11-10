# Video-montaj

Premium vertikal (1080×1920) montaj dvigateli va loyihalar. Yo'riqnoma: `SKILL.md`.

- `render.py` — dvigatel (tipografiya, kamera, zarralar, niqoblar, o'tishlar, parallel render)
- `projects/<nom>.py` — har video o'z fayli; `projects/ideas_log.json` — ishlatilgan g'oyalar
- `tools/` — `analyze_audio.py`, `align_words.py` (so'z-ovoz bog'lash), `mix_audio.py`
  (azvuchka + fon musiqa, ducking, nutq diapazoni EQ, balans hisoboti), `split_and_upscale.py` (kollaj -> kadrlar, waifu2x),
  `sheet.py` (kontakt varaq), `ideas.py` (g'oya generatori), `cutout.py` (subyektni fondan ajratish, IS-Net anime)

```bash
pip install pycairo pillow numpy scipy matplotlib ncnn
python3 render.py projects/zal_tana.py assets/audio/zal_tana_mix.m4a --preview 3.5 12
python3 render.py projects/zal_tana.py assets/audio/zal_tana_mix.m4a        # -> output/zal_tana.mp4
```

Muqova (Reels cover, 1080×1920): `python3 projects/zal_tana_cover.py [--variant sticker]`
-> `output/zal_tana_cover.png`. Cutout modeli: `models/isnet-anime.onnx`
(github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-anime.onnx), `pip install onnxruntime`.
