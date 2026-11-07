#!/usr/bin/env bash
# Qutul qulub loyihasi uchun zaxiralarni qayta yaratish (assets/images git'da saqlanmaydi).
#   bash projects/qutul_qulub_assets.sh
set -euo pipefail
cd "$(dirname "$0")/.."
M=https://raw.githubusercontent.com/nihui/waifu2x-ncnn-vulkan/master/models/models-cunet
mkdir -p models assets/images
for n in noise0_scale2.0x_model noise1_scale2.0x_model; do
  for e in param bin; do [ -f models/$n.$e ] || curl -sSfL -o models/$n.$e $M/$n.$e; done
done
for k in 1 2 3; do
  python3 tools/split_and_upscale.py assets/src/kollaj$k.png models assets/images --prefix k$k
done
# muqovadagi yurak — 8x makro (hook va "kitob topildi" sahnalari uchun)
python3 tools/split_and_upscale.py assets/src/kollaj3.png models assets/images \
  --crop 880,318,1150,600 --scale 8 --prefix heart_macro
# ovoz + musiqa miksi
# musiqa: kitob promo-videosidan (2_5310219967600304179.mp4) ajratib olingan
python3 tools/mix_audio.py --voice assets/audio/qutul_ovoz_v2.wav --music assets/audio/musiqa2.m4a \
  --dur 58.5 --edit "0:" --music-open -17 --music-duck -25.5 --music-fade 1.3 \
  --out output/qutul_qulub_audio.m4a
