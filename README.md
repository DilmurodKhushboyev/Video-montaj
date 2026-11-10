# Video-montaj

## «Agar Alloh sizni sevib qolsa nima bo‘ladi?» — Instagram Reels

Tayyor video: **`output/agar_alloh_sevib_qolsa_reels.mp4`**. U 1080×1920 (9:16), 30 fps, H.264 + AAC formatida, davomiyligi 49.2 s.

### Nimalar qilingan

**Ovoz**
- Nutq manba videodan olingan va matn tugaydigan joyda kesilgan: «…dunyoga maqbuliyatlik darajasi beriladi» (46.0 s). Videoning qolgan qismi ishlatilmagan.
- Asl videoda nutq fon musiqasidan atigi 1–3 LU baland edi, 33–37 s oralig‘ida esa musiqa ostida qolib ketgan edi. Shu sababli nutq va musiqa MDX-Net modeli bilan ajratildi, keyin qayta balanslandi:
  - nutqqa HPF, yengil EQ va kompressor berildi;
  - musiqa nutqdan 8–14 dB past qilib qo‘yildi, ducking bilan;
  - gaplar orasida qolgan nashid/hum qoldig‘i gate bilan pasaytirildi.
- Oxirgi so‘zga reverb «dumi» qo‘shilgan, musiqa esa sekin so‘nadi.
- Montaj tovushlari (whoosh, impact, shimmer, riser) sintez qilingan.
- Mastering: −14 LUFS, true peak −1.6 dBTP.

**Tasvir**
- Har bir kollaj panellarga ajratilgan. Kollajning o‘zi butunligicha ishlatilmagan. Har bir panel Real-ESRGAN (anime) bilan 4 barobar kattalashtirilgan va to‘liq vertikal kadr qilib ishlatilgan.
- Qo‘llangan usullar: Ken Burns (zoom, pan, tilt), whip-pan (harakat xiraligi bilan), zoom-through, oq chaqnash, yorug‘lik orqali o‘tish (light-wipe), blur-dissolve, kamera silkinishi, god rays, bloom, lens flare, oltin zarrachalar, light leak, xromatik aberratsiya, rang gradatsiyasi, vinyetka va grain.
- Hook birinchi soniyadanoq boshlanadi: savol so‘zma-so‘z «zarba» bilan chiqadi, 2.4-soniyada esa tojli kadr oq chaqnash bilan ochiladi.
- Matnlar ovozga so‘zma-so‘z sinxronlangan. Oddiy gaplar Montserrat shriftida, Alloh va Jabroil alayhissalomning so‘zlari Cormorant kursiv iqtibos uslubida, sarlavhalar Cinzel shriftida, «ﷺ» belgisi Amiri shriftida berilgan.
- Matnlar Reels xavfsiz zonasida joylashgan: o‘ngdagi like, izoh va ulashish tugmalari hamda pastki izoh qatoriga tegmaydi.
- Ikki panel (B2, D2) atayin ishlatilmagan. Ularda nurli «gigant siymo» bor va «Alloh aytadi» degan so‘zlar bilan birga chiqsa, Allohni tasvirlashdek tushunilishi mumkin. Shu sababdan A4 kadri ham darvozasiz qismdan kesilgan.

### Qayta yig‘ish

```bash
./make_video.sh
```

| Fayl | Vazifasi |
|---|---|
| `src/extract_panels.py` | Kollajlarni panellarga ajratadi |
| `src/upscale_panels.py` | Real-ESRGAN (ncnn, CPU) bilan 4x kattalashtiradi |
| `src/separate_vocals.py` | MDX-Net (ONNX) yordamida nutqni musiqadan ajratadi |
| `src/align_words.py` | So‘zlarni vaqtga moslaydi (natija: `data/words.json`) |
| `src/audio_mix.py` | Miks va SFX |
| `src/montage.py`, `src/fx.py`, `src/typo.py` | Kadrlar ro‘yxati (EDL), effektlar va kinetik tipografiya |

Shriftlar SIL Open Font License asosida tarqatiladi (Montserrat, Cinzel, Cormorant Garamond, Amiri).
