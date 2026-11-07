# Video-montaj

Premium vertikal (1080×1920) montajlar uchun dvigatel va loyihalar.
Yo'riqnoma: `.claude/skills/video-montaj/SKILL.md`.

| Fayl | Vazifasi |
|------|----------|
| `render.py` | dvigatel: tipografiya, kamera, effektlar, o'tishlar, parallel render |
| `projects/<nom>.py` | bitta video = bitta loyiha (sahnalar har safar noldan) |
| `tools/split_and_upscale.py` | kollajni kadrlarga ajratish + waifu2x 4x/8x |
| `tools/analyze_audio.py` | pauzalar, zarbalar, onsetlar, spektrogramma |
| `tools/mix_audio.py` | azvuchka + musiqa: ovozni ko'tarish, musiqani kesish/ulash, ducking, -14 LUFS |
| `tools/sheet.py` | kontakt varaq |
| `tools/ideas.py` | g'oyalar katalogi (`projects/ideas_log.json` ni hisobga oladi) |

## Qutul qulub (reels)

```bash
pip install pycairo pillow numpy scipy ncnn
bash projects/qutul_qulub_assets.sh        # kadrlar, 8x makro, audio miks
python3 render.py projects/qutul_qulub.py output/qutul_qulub_audio.m4a --preview 3.2 31.6
python3 render.py projects/qutul_qulub.py output/qutul_qulub_audio.m4a
```

Natija: `output/qutul_qulub.mp4` (58.5 s, 30 fps).
