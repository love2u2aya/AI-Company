#!/usr/bin/env python3
"""
Video_Producer スキル：ナレーション原稿 → ElevenLabsで音声 → テロップ映像 → MP4

ナレーション原稿（Creator形式の .md）を読み、段落ごとに
  1. ElevenLabs で音声を作る（声は名前かIDで指定。例：パパ）
  2. スライドの見出し＋読んでいる文のテロップを描いた画像を作る
  3. FFmpeg で音声と画像をつないで MP4 と SRT（字幕）を書き出す

必要なもの:
  - Python 3.9+ と Pillow（pip install pillow）
  - ffmpeg / ffprobe（PATH に入っていること）
  - 環境変数 ELEVENLABS_API_KEY（ElevenLabs の API キー）
  - 日本語フォント（自動で探す。見つからなければ --font で指定）

使い方:
  # 声の一覧を見る（「パパ」の声の名前とIDを確認）
  python3 produce_video_elevenlabs.py --list-voices

  # 動画を作る（声は名前の一部で指定できる）
  python3 produce_video_elevenlabs.py <原稿.md> <出力ディレクトリ> --voice-name パパ

  # 音声なしでテロップと尺だけ確認する（APIを使わない）
  python3 produce_video_elevenlabs.py <原稿.md> <出力ディレクトリ> --silent

音声は <出力ディレクトリ>/<原稿名>_work/audio/ に保存され、
再実行すると作成済みの音声は使い回す（途中で止まっても続きから作れる）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ─── デザイン定数 ─────────────────────────────────────────────
W, H = 1920, 1080
NAVY = (10, 22, 40)
PANEL = (20, 40, 68)
GOLD = (255, 205, 60)
SKYBLUE = (110, 180, 230)
WHITE = (255, 255, 255)
LGRAY = (190, 198, 210)
TELOP_BG = (255, 255, 255)
TELOP_FG = (20, 20, 20)
CHANNEL = "パパママ社｜iDeCoシリーズ"

GAP_SEC = 0.35          # 段落と段落のあいだの間
SILENT_CPS = 5.5        # --silent のときの読み上げ速度（文字/秒）
API = "https://api.elevenlabs.io/v1"

FONT_CANDIDATES = [
    # macOS
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    # Windows
    "C:/Windows/Fonts/YuGothB.ttc",
    "C:/Windows/Fonts/meiryob.ttc",
    "C:/Windows/Fonts/meiryo.ttc",
    "C:/Windows/Fonts/msgothic.ttc",
    # Linux
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]


# ─── 原稿の読み込み ───────────────────────────────────────────

SLIDE_RE = re.compile(r"^【スライド\s*(S\d+)[：:](.+?)】")
SECTION_RE = re.compile(r"^##\s+(?:[\d:〜~\-]+\s*[｜|]\s*)?(.+)$")


def parse_script(path: Path) -> list[dict]:
    """原稿から「読む段落」のリストを作る。制作メモなどの見出し・箇条書きは読まない。"""
    units, para = [], []
    section, slide_id, slide_title = "", "", ""
    in_body = False

    def flush():
        if para and slide_id:
            text = "".join(s.strip() for s in para)
            units.append({"section": section, "slide": slide_id,
                          "slide_title": slide_title, "text": text})
        para.clear()

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        m = SECTION_RE.match(line)
        if m:
            flush()
            section = m.group(1).strip()
            in_body = "制作メモ" not in section
            continue
        if not in_body:
            continue
        m = SLIDE_RE.match(line)
        if m:
            flush()
            slide_id, slide_title = m.group(1), m.group(2).strip()
            continue
        if not line or line == "---":
            flush()
            continue
        if line.startswith(("#", "**", "- ", "|", ">")):
            continue
        para.append(line)
    flush()
    # 「タイトル」スライドには動画のタイトルを出す
    m = re.search(r"^\*\*タイトル[^*]*\*\*[：:]\s*(.+)$", path.read_text(encoding="utf-8"), re.M)
    for u in units:
        if m and u["slide_title"] == "タイトル":
            u["slide_title"] = m.group(1).strip()
    return units


# ─── ElevenLabs ──────────────────────────────────────────────

def api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        sys.exit("環境変数 ELEVENLABS_API_KEY が設定されていません。")
    return key


def api_get(path: str) -> dict:
    req = urllib.request.Request(API + path, headers={"xi-api-key": api_key()})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def list_voices() -> list[dict]:
    return api_get("/voices").get("voices", [])


def resolve_voice(name: str | None, voice_id: str | None) -> str:
    if voice_id:
        return voice_id
    voices = list_voices()
    hits = [v for v in voices if name and name in v.get("name", "")]
    if len(hits) == 1:
        print(f"声：{hits[0]['name']}（{hits[0]['voice_id']}）")
        return hits[0]["voice_id"]
    names = "\n".join(f"  {v['name']}  {v['voice_id']}" for v in (hits or voices))
    sys.exit(f"「{name}」に一致する声が{'複数' if hits else '見つかりません'}。--voice-id で指定してください。\n{names}")


def tts(text: str, voice_id: str, model: str, out: Path, prev_text: str, next_text: str,
        stability: float, similarity: float, speed: float):
    body = {
        "text": text,
        "model_id": model,
        "previous_text": prev_text[-300:] or None,
        "next_text": next_text[:300] or None,
        "voice_settings": {"stability": stability, "similarity_boost": similarity, "speed": speed},
    }
    body = {k: v for k, v in body.items() if v is not None}
    req = urllib.request.Request(
        f"{API}/text-to-speech/{voice_id}?output_format=mp3_44100_128",
        data=json.dumps(body).encode("utf-8"),
        headers={"xi-api-key": api_key(), "Content-Type": "application/json", "Accept": "audio/mpeg"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        out.write_bytes(r.read())


# ─── 画像（テロップ） ─────────────────────────────────────────

def find_font(user_font: str | None) -> str:
    for p in ([user_font] if user_font else []) + FONT_CANDIDATES:
        if p and Path(p).exists():
            return p
    sys.exit("日本語フォントが見つかりません。--font でフォントファイルを指定してください。")


def wrap(text: str, font, max_w: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if font.getlength(cur + ch) > max_w and cur:
            # 句読点や閉じかっこを行頭に置かない
            if ch in "、。，．）」』！？・ー":
                cur += ch
                continue
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def split_pages(text: str, font, max_w: int, max_lines: int) -> list[str]:
    """テロップが長いときは、句点・読点で区切って複数ページに分ける。"""
    if len(wrap(text, font, max_w)) <= max_lines:
        return [text]
    parts = [p for p in re.split(r"(?<=[。！？])", text) if p]
    pages, cur = [], ""
    for p in parts:
        if cur and len(wrap(cur + p, font, max_w)) > max_lines:
            pages.append(cur)
            cur = p
        else:
            cur += p
    if cur:
        pages.append(cur)
    out = []
    for pg in pages:  # 1文だけで長すぎるときは読点で切る
        if len(wrap(pg, font, max_w)) <= max_lines:
            out.append(pg)
            continue
        cur = ""
        for p in [x for x in re.split(r"(?<=[、])", pg) if x]:
            if cur and len(wrap(cur + p, font, max_w)) > max_lines:
                out.append(cur)
                cur = p
            else:
                cur += p
        if cur:
            out.append(cur)
    return out


def render(unit: dict, telop: str, fonts: dict, out: Path, page_no: int, total: int):
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    # 上部：セクション名
    d.rectangle([0, 0, W, 96], fill=PANEL)
    d.text((60, 22), unit["section"], font=fonts["section"], fill=SKYBLUE)
    d.text((W - 60, 30), CHANNEL, font=fonts["small"], fill=LGRAY, anchor="ra")
    # 中央：スライドの見出し
    title_lines = wrap(unit["slide_title"], fonts["title"], W - 240)[:3]
    y = {1: 250, 2: 200, 3: 150}[len(title_lines)]
    for ln in title_lines:
        d.text((W // 2, y), ln, font=fonts["title"], fill=GOLD, anchor="ma")
        y += 120
    d.rectangle([W // 2 - 160, y + 10, W // 2 + 160, y + 16], fill=GOLD)
    # 下部：テロップ（白帯に黒文字）
    lines = wrap(telop, fonts["telop"], W - 260)
    lh = 76
    box_h = lh * len(lines) + 60
    top = H - 70 - box_h
    d.rounded_rectangle([90, top, W - 90, H - 70], radius=24, fill=TELOP_BG)
    ty = top + 30
    for ln in lines:
        d.text((W // 2, ty), ln, font=fonts["telop"], fill=TELOP_FG, anchor="ma")
        ty += lh
    # 右下：進行状況
    d.text((W - 60, H - 52), f"{page_no}/{total}", font=fonts["small"], fill=LGRAY, anchor="ra")
    img.save(out)


# ─── FFmpeg ──────────────────────────────────────────────────

def run(cmd: list[str]):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


# ─── メイン ──────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script", nargs="?", help="ナレーション原稿 .md")
    ap.add_argument("out_dir", nargs="?", help="出力ディレクトリ")
    ap.add_argument("--list-voices", action="store_true", help="ElevenLabs の声の一覧を表示して終わる")
    ap.add_argument("--voice-name", default="パパ", help="声の名前（部分一致）。既定：パパ")
    ap.add_argument("--voice-id", help="声のID（名前より優先）")
    ap.add_argument("--model", default="eleven_multilingual_v2", help="ElevenLabs のモデル")
    ap.add_argument("--stability", type=float, default=0.5)
    ap.add_argument("--similarity", type=float, default=0.8)
    ap.add_argument("--speed", type=float, default=1.0, help="話す速さ（0.7〜1.2）")
    ap.add_argument("--silent", action="store_true", help="音声なしでテロップと尺だけ確認する")
    ap.add_argument("--font", help="日本語フォントファイルのパス")
    ap.add_argument("--limit", type=int, help="先頭から何段落だけ作るか（お試し用）")
    a = ap.parse_args()

    if a.list_voices:
        for v in list_voices():
            print(f"{v['name']}\t{v['voice_id']}\t{v.get('category', '')}")
        return
    if not (a.script and a.out_dir):
        ap.error("原稿と出力ディレクトリを指定してください")
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit(f"{tool} が見つかりません。インストールしてください。")

    script = Path(a.script)
    units = parse_script(script)
    if a.limit:
        units = units[: a.limit]
    if not units:
        sys.exit("読む段落が見つかりませんでした。原稿の形式を確認してください。")
    print(f"段落：{len(units)}　文字数：{sum(len(u['text']) for u in units)}")

    out_dir = Path(a.out_dir)
    stem = script.stem.replace("ナレーション原稿_", "動画_")
    work = out_dir / f"{stem}_work"
    for sub in ("audio", "frames", "parts"):
        (work / sub).mkdir(parents=True, exist_ok=True)

    font_path = find_font(a.font)
    fonts = {
        "title": ImageFont.truetype(font_path, 92),
        "section": ImageFont.truetype(font_path, 44),
        "telop": ImageFont.truetype(font_path, 58),
        "small": ImageFont.truetype(font_path, 30),
    }
    voice_id = None if a.silent else resolve_voice(a.voice_name, a.voice_id)

    parts, srt, t = [], [], 0.0
    for i, u in enumerate(units):
        n = f"{i + 1:03}"
        # 音声
        audio = work / "audio" / f"{n}.mp3"
        if a.silent:
            dur = max(1.5, len(u["text"]) / SILENT_CPS)
        else:
            if not audio.exists():
                prev_t = units[i - 1]["text"] if i else ""
                next_t = units[i + 1]["text"] if i + 1 < len(units) else ""
                speak = u["text"].lstrip("※")
                print(f"  音声 {n}/{len(units)}：{speak[:24]}…")
                tts(speak, voice_id, a.model, audio, prev_t, next_t, a.stability, a.similarity, a.speed)
            dur = duration(audio)
        total = dur + GAP_SEC

        # テロップ画像（長い段落は文字数に応じて時間を割り振る）
        pages = split_pages(u["text"], fonts["telop"], W - 260, 3)
        weights = [len(p) for p in pages]
        list_file = work / "frames" / f"{n}.txt"
        entries = []
        for j, pg in enumerate(pages):
            frame = work / "frames" / f"{n}_{j + 1}.png"
            render(u, pg, fonts, frame, i + 1, len(units))
            seg = total * weights[j] / sum(weights)
            entries.append(f"file '{frame.resolve().as_posix()}'\nduration {seg:.3f}")
            srt.append((t, t + seg, pg))
            t += seg
        entries.append(f"file '{(work / 'frames' / f'{n}_{len(pages)}.png').resolve().as_posix()}'")
        list_file.write_text("\n".join(entries) + "\n", encoding="utf-8")

        # 段落ごとの mp4
        part = work / "parts" / f"{n}.mp4"
        audio_in = (["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=44100:cl=stereo"]
                    if a.silent else ["-i", str(audio)])
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), *audio_in,
             "-filter_complex", f"[1:a]apad=pad_dur={GAP_SEC}[a]", "-map", "0:v", "-map", "[a]",
             "-t", f"{total:.3f}", "-r", "30", "-c:v", "libx264", "-preset", "medium", "-tune", "stillimage",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", str(part)])
        parts.append(part)

    # つなげる
    concat = work / "parts.txt"
    concat.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in parts), encoding="utf-8")
    final = out_dir / f"{stem}{'_無音確認用' if a.silent else ''}.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy",
         "-movflags", "+faststart", str(final)])
    srt_path = final.with_suffix(".srt")
    srt_path.write_text("".join(f"{k + 1}\n{srt_time(s)} --> {srt_time(e)}\n{txt}\n\n"
                                for k, (s, e, txt) in enumerate(srt)), encoding="utf-8")
    print(f"完成：{final}（{t / 60:.1f}分）\n字幕：{srt_path}")


if __name__ == "__main__":
    main()
