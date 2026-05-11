#!/usr/bin/env python3
"""
Video_Producer スキル：ナレーション原稿＋スライドマップ → MP4生成

使い方:
    python3 produce_video.py <ナレーション原稿.md> <スライドマップ.md> <出力ディレクトリ>

例:
    python3 produce_video.py \
        "Workspace/Output/AgentOutput/ナレーション原稿_第5弾_20260511.md" \
        "Workspace/Output/AgentOutput/スライドマップ_第5弾_20260511.md" \
        "Workspace/Output/FinalOutput"
"""

import sys
import os
import re
import textwrap
from pathlib import Path

import subprocess
from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

# ─── デザイン定数（デザインシステム準拠） ──────────────────────────────────
W, H = 1920, 1080
FPS = 30
NAVY     = (10, 22, 40)      # #0A1628
GOLD     = (255, 215, 0)     # #FFD700
CRIMSON  = (204, 34, 0)      # #CC2200
SKYBLUE  = (74, 159, 212)    # #4A9FD4
WHITE    = (255, 255, 255)
LGRAY    = (204, 204, 204)

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def load_font(size: int):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()


# ─── スライド画像生成 ───────────────────────────────────────────────────────

def make_slide(title: str, body: str, slide_no: str, color: tuple = GOLD) -> Image.Image:
    """1枚のスライド画像を生成する"""
    img = Image.new("RGB", (W, H), NAVY)
    draw = ImageDraw.Draw(img)

    # スライド番号（左上）
    draw.text((60, 40), slide_no, font=load_font(32), fill=SKYBLUE)

    # タイトル
    title_font = load_font(72)
    wrapped = textwrap.fill(title, width=32)
    draw.text((80, 160), wrapped, font=title_font, fill=color)

    # 区切り線
    draw.rectangle([80, 300, W - 80, 306], fill=color)

    # 本文
    body_font = load_font(44)
    y = 340
    for line in textwrap.wrap(body, width=52):
        draw.text((80, y), line, font=body_font, fill=WHITE)
        y += 64
        if y > H - 100:
            break

    # 右下にチャンネル名
    draw.text((W - 420, H - 60), "iDeCoシリーズ", font=load_font(28), fill=LGRAY)

    return img


def parse_slide_map(path: str) -> list[dict]:
    """スライドマップのMarkdownテーブルを解析してスライド情報のリストを返す"""
    slides = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            # "| S01 | 0:00 | ..." の行を解析
            m = re.match(r"\|\s*(S\d+)\s*\|\s*([\d:]+)\s*\|[^|]+\|\s*(.+?)\s*\|", line)
            if not m:
                continue
            no, tc, content = m.group(1), m.group(2), m.group(3)
            # ★スクショ推奨スライドは表示時間を長めに
            is_screenshot = "スクショ推奨" in line or "★" in line
            # タイトルと本文を分割（**太字**をタイトル、残りを本文）
            title_match = re.search(r"\*\*(.+?)\*\*", content)
            title = title_match.group(1) if title_match else content[:40]
            body = re.sub(r"\*\*[^*]+\*\*", "", content).strip()
            body = re.sub(r"[★【】]", "", body).strip()
            slides.append({
                "no": no,
                "tc": tc,
                "title": title,
                "body": body[:200],
                "screenshot": is_screenshot,
            })
    return slides


def parse_narration(path: str) -> str:
    """ナレーション原稿からプレーンテキスト（読み上げ用）を抽出する"""
    lines = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # スライドラベル・見出し・空行・区切り線を除外
            if not line:
                continue
            if line.startswith("#") or line.startswith("---") or line.startswith("|"):
                continue
            if line.startswith("【スライド"):
                continue
            if line.startswith("**") and line.endswith("**"):
                continue
            lines.append(line)
    return "。".join(lines)


# ─── メイン処理 ────────────────────────────────────────────────────────────

def produce(narration_path: str, slide_map_path: str, output_dir: str):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    slides_dir = out / "slides_tmp"
    slides_dir.mkdir(exist_ok=True)

    # 1. ナレーション音声生成（espeak-ngによるローカルTTS）
    print("[1/4] 音声生成中...")
    narration_text = parse_narration(narration_path)
    narration_text = narration_text[:5000]
    wav_path = str(out / "audio_tmp.wav")
    audio_path = str(out / "audio_tmp.mp3")
    subprocess.run(
        ["espeak-ng", "-v", "ja", "-s", "150", "-w", wav_path, narration_text],
        check=True, capture_output=True,
    )
    # WAV → MP3変換
    subprocess.run(
        ["ffmpeg", "-y", "-i", wav_path, "-q:a", "2", audio_path],
        check=True, capture_output=True,
    )
    os.remove(wav_path)
    print(f"      音声保存: {audio_path}")

    # 2. スライド画像生成
    print("[2/4] スライド画像生成中...")
    slide_data = parse_slide_map(slide_map_path)
    if not slide_data:
        print("      スライドマップの解析に失敗しました。ダミースライドを生成します。")
        slide_data = [{"no": "S01", "tc": "0:00", "title": "スライド", "body": "", "screenshot": False}]

    image_paths = []
    for s in slide_data:
        img = make_slide(s["title"], s["body"], s["no"])
        p = str(slides_dir / f"{s['no']}.png")
        img.save(p)
        image_paths.append((p, s["screenshot"]))
    print(f"      {len(image_paths)}枚のスライドを生成しました")

    # 3. 動画クリップ生成（音声の長さをスライド数で均等分割）
    print("[3/4] 動画合成中...")
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    n = len(image_paths)
    base_dur = total_duration / n

    clips = []
    for path, is_screenshot in image_paths:
        # スクショ推奨スライドは表示時間を1.5倍
        dur = base_dur * 1.5 if is_screenshot else base_dur
        clips.append(ImageClip(path).with_duration(dur))

    # 合計尺を音声に合わせて正規化
    total_clip_dur = sum(c.duration for c in clips)
    scale = total_duration / total_clip_dur
    clips = [c.with_duration(c.duration * scale) for c in clips]

    video = concatenate_videoclips(clips, method="compose")
    video = video.with_audio(audio)

    # 4. MP4書き出し
    print("[4/4] MP4書き出し中...")
    title_slug = Path(narration_path).stem.replace("ナレーション原稿_", "動画_")
    output_path = str(out / f"{title_slug}.mp4")
    video.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )

    # 一時ファイル削除
    import shutil
    shutil.rmtree(slides_dir)
    if os.path.exists(audio_path):
        os.remove(audio_path)

    print(f"\n完成: {output_path}")
    return output_path


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    produce(sys.argv[1], sys.argv[2], sys.argv[3])
