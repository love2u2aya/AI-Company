#!/usr/bin/env bash
# produce_video_pro.py の実行環境セットアップ（初回のみ）
#   - Open JTalk（日本語音声合成エンジン）＋辞書
#   - Noto Sans CJK（デザインシステム指定フォント Noto Sans JP の全ウェイト）
#   - 女性話者モデル tohoku-f01（CC BY 4.0, 東北大学 伊藤・能勢研究室）
set -euo pipefail
cd "$(dirname "$0")"
apt-get install -y -qq open-jtalk open-jtalk-mecab-naist-jdic hts-voice-nitech-jp-atr503-m001 \
  fonts-noto-cjk fonts-noto-cjk-extra ffmpeg >/dev/null
pip install -q pillow numpy
if [ ! -f voices/tohoku-f01-neutral.htsvoice ]; then
  tmp=$(mktemp -d)
  git clone -q --depth 1 https://github.com/icn-lab/htsvoice-tohoku-f01 "$tmp"
  mkdir -p voices
  cp "$tmp"/*.htsvoice "$tmp"/COPYRIGHT.txt voices/
  rm -rf "$tmp"
fi
echo "セットアップ完了"
