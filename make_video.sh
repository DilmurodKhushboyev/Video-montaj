#!/usr/bin/env bash
# "Agar Alloh sizni sevib qolsa" Reels videosini noldan yig'ish.
# Talablar: ffmpeg, python3; internet (pip, GitHub releases).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build/models build/audio output

pip install -q numpy pillow opencv-python-headless ncnn onnxruntime soundfile scipy pyloudnorm

# 1) Modellar: Real-ESRGAN (anime, ncnn) va MDX-Net vokal ajratish (UVR, ONNX)
if [ ! -d build/models/realesrgan ]; then
  curl -sSL -o build/models/realesrgan.zip \
    https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip
  unzip -q -o build/models/realesrgan.zip -d build/models/realesrgan
fi
[ -f build/models/Kim_Vocal_2.onnx ] || curl -sSL -o build/models/Kim_Vocal_2.onnx \
  https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/Kim_Vocal_2.onnx

# 2) Kollajlardan panellarni kesish va 4x sifat oshirish
python3 src/extract_panels.py assets/collages build/panels
python3 src/upscale_panels.py build/models/realesrgan/models build/panels build/panels_x4

# 3) Ovoz: nutq va fon musiqasini ajratish (faqat matn tugaguncha kerak, 54 s bilan zaxira)
ffmpeg -v error -y -i assets/source/ovoz_manba.mp4 -vn -t 54 -c:a pcm_s16le build/audio/src54.wav
python3 src/separate_vocals.py build/models/Kim_Vocal_2.onnx build/audio/src54.wav build/audio/sep54
# (so'z vaqtlari data/words.json da; qayta hisoblash uchun: src/align_words.py <ovoz_16k.wav>)

# 4) Miks + mastering (-14 LUFS, -1.5 dBTP)
python3 src/audio_mix.py
ffmpeg -v error -y -i build/audio/premaster.wav \
  -af "volume=3.1dB,aresample=192000,alimiter=limit=0.83:attack=2:release=60:level=disabled:asc=1,aresample=48000" \
  -c:a pcm_s24le build/audio/master.wav

# 5) Video render (1080x1920, 30 fps) va birlashtirish
python3 src/montage.py --render --workers "$(nproc)" --out build
ffmpeg -v error -y -i build/video_noaudio.mp4 -i build/audio/master.wav \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -ar 48000 -shortest -movflags +faststart \
  output/agar_alloh_sevib_qolsa_reels.mp4
echo "Tayyor: output/agar_alloh_sevib_qolsa_reels.mp4"
