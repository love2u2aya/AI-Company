#!/usr/bin/env bash
# 縦型ショート生成エンジンの環境構築（Ubuntu系）
# 使い方: bash setup_shorts_env.sh
set -euo pipefail

# 音声合成（Open JTalk + 男性ボイス）とフォント
apt-get install -y ffmpeg open-jtalk open-jtalk-mecab-naist-jdic hts-voice-nitech-jp-atr503-m001 \
  fonts-noto-cjk fonts-noto-cjk-extra fonts-mplus fonts-noto-color-emoji

pip install numpy pillow

# 奥さん役の女性ボイス "Mei"（MMDAgent / 名古屋工業大学, CC BY 3.0）
VOICE_DIR="${PAPAMAMA_VOICE_DIR:-$HOME/.cache/papamama/voices}"
if [ ! -f "$VOICE_DIR/mei/mei_normal.htsvoice" ]; then
  tmp="$(mktemp -d)"
  curl -sSL -o "$tmp/mmd.zip" \
    "https://sourceforge.net/projects/mmdagent/files/MMDAgent_Example/MMDAgent_Example-1.8/MMDAgent_Example-1.8.zip/download"
  (cd "$tmp" && unzip -q mmd.zip 'MMDAgent_Example-1.8/Voice/mei/*')
  mkdir -p "$VOICE_DIR"
  cp -r "$tmp/MMDAgent_Example-1.8/Voice/mei" "$VOICE_DIR/"
  rm -rf "$tmp"
fi
echo "OK: voices in $VOICE_DIR"
