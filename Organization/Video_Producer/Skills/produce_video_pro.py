#!/usr/bin/env python3
"""
Video_Producer スキル（PRO版）：シーン台本(JSON) → モーショングラフィックス動画(MP4)

旧版 produce_video.py との違い:
  - 文単位の音声合成（Open JTalk）→ 字幕・アニメーションがナレーションと完全同期
  - 10種類のシーンテンプレート（デザインシステム Type1〜7 準拠＋α）を 30fps でアニメーション描画
  - Noto Sans JP（Black/Bold/Regular）で日本語を正しく描画
  - BGM（自動作曲）＋効果音（自動合成）＋ナレーション中の自動ダッキング＋ラウドネス正規化
  - 字幕(.srt)・YouTubeチャプター・サムネイル(1280x720)を同時出力
  - シーン単位の並列レンダリング

使い方:
    bash Organization/Video_Producer/Skills/setup_pro.sh   # 初回のみ（音声エンジン・フォント導入）
    python3 Organization/Video_Producer/Skills/produce_video_pro.py <シーン台本.json> <出力ディレクトリ>

台本の書き方は Organization/Video_Producer/Skills/produce_video_pro.md を参照。
ナレーション内の {表示|読み} は、字幕に「表示」を出し、音声は「読み」で読み上げる。
"""

import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import wave
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ─── デザインシステム ────────────────────────────────────────────────────────
W, H = 1920, 1080
FPS = 30
SR = 48000
NAVY = (10, 22, 40)
NAVY2 = (18, 36, 64)
GOLD = (255, 215, 0)
CRIMSON = (204, 34, 0)
SKYBLUE = (74, 159, 212)
WHITE = (255, 255, 255)
LGRAY = (204, 204, 204)
DGRAY = (42, 58, 74)
COLORS = {"gold": GOLD, "crimson": CRIMSON, "sky": SKYBLUE, "white": WHITE, "gray": LGRAY}

FONT_DIR = "/usr/share/fonts/opentype/noto"
FONT_FILES = {
    "black": "NotoSansCJK-Black.ttc",
    "bold": "NotoSansCJK-Bold.ttc",
    "medium": "NotoSansCJK-Medium.ttc",
    "regular": "NotoSansCJK-Regular.ttc",
    "light": "NotoSansCJK-Light.ttc",
}
FALLBACK_FONT = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"

DIC = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
VOICE_DIRS = [Path(__file__).parent / "voices", Path("/usr/share/hts-voice")]

LEAD_IN = 0.5      # シーン開始から最初の発話まで
SENT_GAP = 0.28    # 文と文の間
TAIL = 0.9         # 最後の発話からシーン終了まで
EXIT = 0.35        # シーン末尾の退場アニメーション

_font_cache = {}


def font(weight: str, size: int):
    key = (weight, size)
    if key not in _font_cache:
        try:
            _font_cache[key] = ImageFont.truetype(os.path.join(FONT_DIR, FONT_FILES[weight]), size, index=0)
        except OSError:
            _font_cache[key] = ImageFont.truetype(FALLBACK_FONT, size)
    return _font_cache[key]


# ─── イージング ─────────────────────────────────────────────────────────────

def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(p):
    return 1 - (1 - p) ** 3


def ease_in_out(p):
    return 3 * p * p - 2 * p * p * p


def ease_back(p):
    c = 1.70158
    return 1 + (c + 1) * (p - 1) ** 3 + c * (p - 1) ** 2


# ─── ナレーション（{表示|読み} 記法） ─────────────────────────────────────────
RUBY = re.compile(r"\{([^|{}]+)\|([^{}]+)\}")


def display_text(s):
    return RUBY.sub(r"\1", s)


def reading_text(s):
    return RUBY.sub(r"\2", s)


def find_voice(name):
    for d in VOICE_DIRS:
        p = d / f"{name}.htsvoice"
        if p.exists():
            return str(p)
    raise FileNotFoundError(f"音声モデル {name}.htsvoice が見つかりません。setup_pro.sh を実行してください。")


def synth(text, voice_path, speed, pitch, out_wav):
    txt = out_wav + ".txt"
    with open(txt, "w", encoding="utf-8") as f:
        f.write(text)
    subprocess.run(
        ["open_jtalk", "-x", DIC, "-m", voice_path, "-r", str(speed), "-fm", str(pitch),
         "-jf", "1.2", "-ow", out_wav, txt],
        check=True, capture_output=True,
    )
    os.remove(txt)
    with wave.open(out_wav) as w:
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        sr = w.getframerate()
    if sr != SR:
        idx = np.arange(0, len(data), sr / SR)
        data = np.interp(idx, np.arange(len(data)), data).astype(np.float32)
    # 前後の無音をトリム
    nz = np.where(np.abs(data) > 0.01)[0]
    if len(nz):
        data = data[max(0, nz[0] - 480): nz[-1] + 2400]
    return data


# ─── スプライト（描画済みパーツ） ─────────────────────────────────────────────

def text_sprite(text, weight, size, fill, stroke=0, stroke_fill=NAVY, glow=None):
    f = font(weight, size)
    l, t, r, b = f.getbbox(text, stroke_width=stroke)
    pad = 24 if glow else 4
    img = Image.new("RGBA", (r - l + pad * 2, b - t + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if glow:
        g = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).text((pad - l, pad - t), text, font=f, fill=glow + (150,), stroke_width=stroke + 4,
                               stroke_fill=glow + (150,))
        img = Image.alpha_composite(img, g.filter(ImageFilter.GaussianBlur(14)))
        d = ImageDraw.Draw(img)
    d.text((pad - l, pad - t), text, font=f, fill=fill + (255,), stroke_width=stroke, stroke_fill=stroke_fill + (255,))
    return img


def wrap_jp(text, f, max_w):
    """日本語は1文字単位、英数字の単語は分割せずに折り返す（行頭禁則つき）"""
    lines, cur = [], ""
    for ch in re.findall(r"[A-Za-z0-9.\-+%]+|.", text):
        if f.getlength(cur + ch) > max_w and cur:
            # 行頭禁則（句読点を前の行に残す）
            if ch in "、。，．！？）」』ー":
                cur += ch
                lines.append(cur)
                cur = ""
                continue
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def multiline_sprite(text, weight, size, fill, max_w, spacing=1.35, align="left"):
    f = font(weight, size)
    lines = []
    for para in text.split("\n"):
        lines += wrap_jp(para, f, max_w)
    lh = int(size * spacing)
    w = int(max(f.getlength(s) for s in lines)) + 8
    img = Image.new("RGBA", (w, lh * len(lines) + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, s in enumerate(lines):
        x = 4 if align == "left" else (w - f.getlength(s)) / 2
        d.text((x, 4 + i * lh), s, font=f, fill=fill + (255,))
    return img


def panel_sprite(w, h, border=DGRAY, fill=(16, 32, 56), radius=24, accent=None):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=fill + (235,), outline=border + (255,), width=3)
    if accent:
        d.rounded_rectangle([0, 0, w - 1, 10], radius=5, fill=accent + (255,))
    return img


def with_alpha(img, a):
    if a >= 0.999:
        return img
    out = img.copy()
    out.putalpha(img.getchannel("A").point(lambda v: int(v * a)))
    return out


# ─── 要素（アニメーション付きパーツ） ────────────────────────────────────────

class El:
    """スプライトを (cx, cy) を中心に配置し、t_in から anim で登場させる"""

    def __init__(self, sprite, cx, cy, t_in=0.0, anim="up", dur=0.55, anchor="mm"):
        self.sprite, self.cx, self.cy = sprite, cx, cy
        self.t_in, self.anim, self.dur, self.anchor = t_in, anim, dur, anchor

    def pos(self, sw, sh):
        x = self.cx - (sw / 2 if self.anchor[0] == "m" else (sw if self.anchor[0] == "r" else 0))
        y = self.cy - (sh / 2 if self.anchor[1] == "m" else (sh if self.anchor[1] == "b" else 0))
        return x, y

    def draw(self, frame, t, fade):
        p = clamp((t - self.t_in) / self.dur)
        if p <= 0:
            return
        e = ease_out(p)
        spr, dx, dy = self.sprite, 0, 0
        if self.anim == "up":
            dy = (1 - e) * 50
        elif self.anim == "left":
            dx = -(1 - e) * 120
        elif self.anim == "right":
            dx = (1 - e) * 120
        elif self.anim == "pop":
            s = 0.55 + 0.45 * ease_back(p)
            spr = spr.resize((max(1, int(spr.width * s)), max(1, int(spr.height * s))), Image.BILINEAR)
        elif self.anim == "wipe":
            cw = max(1, int(spr.width * ease_in_out(p)))
            spr = spr.crop((0, 0, cw, spr.height))
            x, y = self.pos(self.sprite.width, self.sprite.height)
            frame.alpha_composite(with_alpha(spr, fade), (int(x), int(y)))
            return
        x, y = self.pos(spr.width, spr.height)
        a = min(e * 1.4, 1.0) * fade
        frame.alpha_composite(with_alpha(spr, a), (int(x + dx), int(y + dy)))


class Counter:
    """数字のカウントアップ"""

    def __init__(self, cx, cy, value, t_in, dur=1.6, decimals=0, prefix="", suffix="", size=170, color=GOLD):
        self.cx, self.cy, self.value, self.t_in, self.dur = cx, cy, value, t_in, dur
        self.decimals, self.prefix, self.suffix, self.size, self.color = decimals, prefix, suffix, size, color
        self.cache = {}

    def text_at(self, t):
        p = ease_out(clamp((t - self.t_in) / self.dur))
        v = self.value * p
        s = f"{v:,.{self.decimals}f}"
        return f"{self.prefix}{s}{self.suffix}"

    def draw(self, frame, t, fade):
        if t < self.t_in:
            return
        s = self.text_at(t)
        if s not in self.cache:
            self.cache[s] = text_sprite(s, "black", self.size, self.color, glow=self.color)
        spr = self.cache[s]
        a = clamp((t - self.t_in) / 0.25) * fade
        frame.alpha_composite(with_alpha(spr, a), (int(self.cx - spr.width / 2), int(self.cy - spr.height / 2)))


class Drawer:
    """任意の描画関数 fn(draw, frame, t, fade) をラップ"""

    def __init__(self, fn):
        self.fn = fn

    def draw(self, frame, t, fade):
        self.fn(frame, t, fade)


def blend(c, a, bg=NAVY):
    return tuple(int(bg[i] + (c[i] - bg[i]) * a) for i in range(3))


# ─── 背景・HUD ─────────────────────────────────────────────────────────────

def make_background():
    y = np.linspace(0, 1, H)[:, None]
    x = np.linspace(0, 1, W)[None, :]
    r = np.sqrt((x - 0.5) ** 2 * 1.6 + (y - 0.45) ** 2)
    mix = clamp_arr(1 - r * 1.25)
    img = np.zeros((H, W, 3), np.float32)
    for i in range(3):
        img[..., i] = NAVY[i] + (NAVY2[i] - NAVY[i]) * mix
    bg = Image.fromarray(img.astype(np.uint8)).convert("RGBA")
    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(grid)
    for gx in range(0, W, 80):
        d.line([(gx, 0), (gx, H)], fill=(255, 255, 255, 9))
    for gy in range(0, H, 80):
        d.line([(0, gy), (W, gy)], fill=(255, 255, 255, 9))
    return Image.alpha_composite(bg, grid)


def clamp_arr(a):
    return np.clip(a, 0, 1)


class Network:
    """背景で漂うニューラルネット風のノード群（全シーン共通の連続アニメーション）"""

    def __init__(self, n=46, seed=7):
        rnd = random.Random(seed)
        self.nodes = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(-14, 14), rnd.uniform(-10, 10),
                       rnd.uniform(0, 6.28)) for _ in range(n)]

    def draw(self, frame, gt):
        d = ImageDraw.Draw(frame)
        pts = []
        for x, y, vx, vy, ph in self.nodes:
            px = (x + vx * gt) % (W + 200) - 100
            py = (y + vy * gt + 18 * math.sin(gt * 0.4 + ph)) % (H + 200) - 100
            pts.append((px, py, ph))
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                dx, dy = pts[i][0] - pts[j][0], pts[i][1] - pts[j][1]
                dist = math.hypot(dx, dy)
                if dist < 230:
                    a = (1 - dist / 230) * 0.22
                    d.line([pts[i][:2], pts[j][:2]], fill=blend(SKYBLUE, a, NAVY2), width=1)
        for px, py, ph in pts:
            a = 0.35 + 0.25 * math.sin(gt * 1.3 + ph)
            rr = 3
            d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=blend(SKYBLUE, a, NAVY2))


# ─── シーンテンプレート ─────────────────────────────────────────────────────
# 各ビルダーは (scene, cues) を受け取り、要素リストと効果音キューを返す。
# cues[i] = i番目の文の開始時刻（シーン内秒）。item の "cue": i で登場タイミングを文に同期できる。

def cue_time(item, idx, cues, default):
    if isinstance(item, dict) and "cue" in item and item["cue"] < len(cues):
        return cues[item["cue"]]
    return default


def source_el(src):
    return El(text_sprite("出典: " + src, "light", 26, LGRAY), W - 60, 104, 0.4, "up", anchor="rm")


def build_title(sc, cues, dur):
    els, se = [], [(0.0, "whoosh")]
    els.append(El(text_sprite(sc.get("kicker", ""), "bold", 46, SKYBLUE), W / 2, 330, 0.2))
    t = text_sprite(sc["title"], "black", 132, GOLD, glow=GOLD)
    els.append(El(t, W / 2, 500, 0.5, "wipe", 0.9))
    els.append(El(text_sprite(sc.get("subtitle", ""), "medium", 50, WHITE), W / 2, 660, 1.2))

    def ring(frame, t, fade):
        d = ImageDraw.Draw(frame)
        for k in range(3):
            p = ((t * 0.35 + k / 3) % 1.0)
            r = 300 + p * 700
            a = (1 - p) * 0.25 * fade
            d.ellipse([W / 2 - r, 500 - r * 0.42, W / 2 + r, 500 + r * 0.42], outline=blend(GOLD, a, NAVY2), width=2)
        w = int(ease_in_out(clamp((t - 0.9) / 0.8)) * 700)
        if w > 0:
            d.rectangle([W / 2 - w / 2, 585, W / 2 + w / 2, 590], fill=blend(GOLD, fade, NAVY2))

    return [Drawer(ring)] + els, se + [(0.5, "rise")]


def build_chapter(sc, cues, dur):
    els, se = [], [(0.0, "whoosh")]
    cur = sc["current"]
    chapters = sc["chapters"]
    big = text_sprite(f"{cur:02d}", "black", 300, GOLD, glow=GOLD)
    els.append(El(big, 470, 520, 0.1, "pop", 0.7))
    els.append(El(text_sprite("CHAPTER", "bold", 44, SKYBLUE), 470, 330, 0.1))
    n = len(chapters)
    top = 540 - (n - 1) * 62
    for i, name in enumerate(chapters, 1):
        active = i == cur
        col = GOLD if active else (blend(LGRAY, 0.35) if i > cur else blend(LGRAY, 0.6))
        spr = text_sprite(f"{i:02d}  {name}", "black" if active else "medium", 60 if active else 44, col)
        els.append(El(spr, 860, top + (i - 1) * 124, 0.25 + i * 0.09, "left", anchor="lm"))

    def marker(frame, t, fade):
        p = ease_out(clamp((t - 0.6) / 0.5))
        y = top + (cur - 1) * 124
        d = ImageDraw.Draw(frame)
        d.rectangle([820, y - 34, 820 + int(10 * p), y + 34], fill=blend(GOLD, fade, NAVY2))

    return els + [Drawer(marker)], se


def build_impact(sc, cues, dur):
    els, se = [], [(0.0, "whoosh")]
    els.append(El(multiline_sprite(sc.get("context", ""), "bold", 54, WHITE, 1500, align="center"), W / 2, 300, 0.15))
    t_num = cue_time(sc, 0, cues, 0.6)
    col = COLORS.get(sc.get("color", "gold"), GOLD)
    cnt = Counter(W / 2, 540, sc["value"], t_num, sc.get("count_dur", 1.6), sc.get("decimals", 0),
                  sc.get("prefix", ""), sc.get("suffix", ""), sc.get("size", 190), col)
    se.append((t_num + sc.get("count_dur", 1.6), "pop"))

    def glow(frame, t, fade):
        p = ease_out(clamp((t - t_num) / 1.0))
        if p <= 0:
            return
        d = ImageDraw.Draw(frame)
        r = 260 + 40 * math.sin(t * 2)
        for k in range(6):
            rr = r + k * 26
            d.ellipse([W / 2 - rr * 1.9, 540 - rr * 0.42, W / 2 + rr * 1.9, 540 + rr * 0.42],
                      outline=blend(col, 0.05 * (6 - k) * p * fade, NAVY2), width=3)

    els.append(Drawer(glow))
    els.append(cnt)
    if sc.get("caption"):
        els.append(El(multiline_sprite(sc["caption"], "regular", 40, LGRAY, 1500, align="center"), W / 2, 790,
                      t_num + sc.get("count_dur", 1.6) * 0.7))
    if sc.get("source"):
        els.append(source_el(sc["source"]))
    return els, se


def build_bars(sc, cues, dur):
    els, se = [], [(0.0, "whoosh")]
    els.append(El(text_sprite(sc["title"], "bold", 66, WHITE), W / 2, 190, 0.1))
    if sc.get("unit"):
        els.append(El(text_sprite(sc["unit"], "light", 30, LGRAY), W - 160, 270, 0.3, anchor="rm"))
    items = sc["items"]
    n = len(items)
    vmax = max(i["value"] for i in items) * 1.08
    left, right = 520, W - 260
    top, bottom = 320, 830
    row = (bottom - top) / n
    bh = min(76, row * 0.62)
    label_cache, val_cache = {}, {}
    starts = [cue_time(it, i, cues, 0.5 + i * 0.35) for i, it in enumerate(items)]
    for s in starts:
        se.append((s, "tick"))

    def bars(frame, t, fade):
        d = ImageDraw.Draw(frame)
        for i, it in enumerate(items):
            p = ease_out(clamp((t - starts[i]) / 1.1))
            if t < starts[i]:
                continue
            cy = top + row * (i + 0.5)
            col = GOLD if it.get("highlight") else SKYBLUE
            if i not in label_cache:
                label_cache[i] = text_sprite(it["label"], "bold", 40, WHITE)
            lab = label_cache[i]
            frame.alpha_composite(with_alpha(lab, clamp(p * 2) * fade), (int(left - 30 - lab.width), int(cy - lab.height / 2)))
            w = (right - left) * it["value"] / vmax * p
            d.rounded_rectangle([left, cy - bh / 2, left + max(w, 2), cy + bh / 2], radius=10,
                                fill=blend(col, fade, NAVY2))
            v = it["value"] * p
            vs = it.get("display") if (p >= 1 and it.get("display")) else f"{v:,.{sc.get('decimals', 0)}f}{sc.get('suffix', '')}"
            if vs not in val_cache:
                val_cache[vs] = text_sprite(vs, "black", 44, col)
            vsp = val_cache[vs]
            frame.alpha_composite(with_alpha(vsp, clamp(p * 2) * fade), (int(left + w + 18), int(cy - vsp.height / 2)))

    els.append(Drawer(bars))
    if sc.get("source"):
        els.append(source_el(sc["source"]))
    return els, se


def build_cards(sc, cues, dur):
    els, se = [], [(0.0, "whoosh")]
    els.append(El(text_sprite(sc["title"], "bold", 66, WHITE), W / 2, 190, 0.1))
    items = sc["items"]
    n = len(items)
    gap = 36
    cw = int((W - 160 - gap * (n - 1)) / n)
    ch = sc.get("height", 500)
    cy = 570
    for i, it in enumerate(items):
        t0 = cue_time(it, i, cues, 0.45 + i * 0.4)
        se.append((t0, "tick"))
        accent = COLORS.get(it.get("color", "gold"), GOLD)
        card = panel_sprite(cw, ch, accent=accent)
        d = ImageDraw.Draw(card)
        if it.get("tag"):
            tag = text_sprite(it["tag"], "bold", 28, NAVY)
            d.rounded_rectangle([30, 44, 30 + tag.width + 20, 44 + tag.height + 8], radius=8, fill=accent + (255,))
            card.alpha_composite(tag, (40, 48))
        head = multiline_sprite(it["head"], "black", sc.get("head_size", 52), accent, cw - 60, 1.15)
        card.alpha_composite(head, (30, 110))
        body = multiline_sprite(it.get("body", ""), "regular", sc.get("body_size", 34), WHITE, cw - 60, 1.45)
        card.alpha_composite(body, (30, 130 + head.height))
        x = 80 + i * (cw + gap) + cw / 2
        els.append(El(card, x, cy, t0, "up", 0.6))
    return els, se


def build_timeline(sc, cues, dur):
    els, se = [], [(0.0, "whoosh")]
    els.append(El(text_sprite(sc["title"], "bold", 66, WHITE), W / 2, 170, 0.1))
    items = sc["items"]
    n = len(items)
    x0, x1, ly = 160, W - 160, 590
    xs = [x0 + (x1 - x0) * (i + 0.5) / n for i in range(n)]
    starts = [cue_time(it, i, cues, 0.7 + i * 0.5) for i, it in enumerate(items)]

    def line(frame, t, fade):
        d = ImageDraw.Draw(frame)
        p = ease_in_out(clamp((t - 0.3) / 1.2))
        d.rectangle([x0, ly - 3, x0 + (x1 - x0) * p, ly + 3], fill=blend(SKYBLUE, 0.8 * fade, NAVY2))
        for i, x in enumerate(xs):
            q = ease_back(clamp((t - starts[i]) / 0.45))
            if t < starts[i]:
                continue
            r = 16 * q
            col = COLORS.get(items[i].get("color", "gold"), GOLD)
            d.ellipse([x - r, ly - r, x + r, ly + r], fill=blend(col, fade, NAVY2))
            d.ellipse([x - r - 8, ly - r - 8, x + r + 8, ly + r + 8], outline=blend(col, 0.4 * fade, NAVY2), width=2)

    els.append(Drawer(line))
    tw = int((x1 - x0) / n) - 30
    for i, it in enumerate(items):
        se.append((starts[i], "tick"))
        up = i % 2 == 0
        col = COLORS.get(it.get("color", "gold"), GOLD)
        date = text_sprite(it["date"], "black", 40, col)
        txt = multiline_sprite(it["text"], "medium", 32, WHITE, tw, 1.35, align="center")
        if up:
            els.append(El(date, xs[i], ly - 60, starts[i] + 0.1, "up", anchor="mb"))
            els.append(El(txt, xs[i], ly - 120, starts[i] + 0.2, "up", anchor="mb"))
        else:
            els.append(El(date, xs[i], ly + 60, starts[i] + 0.1, "up", anchor="mt"))
            els.append(El(txt, xs[i], ly + 120, starts[i] + 0.2, "up", anchor="mt"))
    return els, se


def build_curve(sc, cues, dur):
    """指数関数的な伸びを描く折れ線（対数軸オプション付き）"""
    els, se = [], [(0.0, "whoosh")]
    els.append(El(text_sprite(sc["title"], "bold", 62, WHITE), W / 2, 160, 0.1))
    pts = sc["points"]
    log = sc.get("log", True)
    gx0, gx1, gy0, gy1 = 260, W - 300, 860, 300
    xs = [p["x"] for p in pts]
    ys = [math.log10(p["y"]) if log else p["y"] for p in pts]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys) - 0.2, max(ys) + 0.3

    def mapx(v):
        return gx0 + (v - xmin) / (xmax - xmin) * (gx1 - gx0)

    def mapy(v):
        return gy0 - (v - ymin) / (ymax - ymin) * (gy0 - gy1)

    P = [(mapx(x), mapy(y)) for x, y in zip(xs, ys)]
    t0 = cue_time(sc, 0, cues, 0.8)
    draw_dur = sc.get("draw_dur", 3.5)
    lab_cache = {}

    def curve(frame, t, fade):
        d = ImageDraw.Draw(frame)
        d.line([(gx0, gy0), (gx1 + 40, gy0)], fill=blend(LGRAY, 0.5 * fade, NAVY2), width=3)
        d.line([(gx0, gy0), (gx0, gy1 - 40)], fill=blend(LGRAY, 0.5 * fade, NAVY2), width=3)
        p = clamp((t - t0) / draw_dur)
        if p <= 0:
            return
        total = len(P) - 1
        reach = p * total
        line = [P[0]]
        for i in range(1, len(P)):
            if i <= reach:
                line.append(P[i])
            else:
                f = reach - (i - 1)
                if f > 0:
                    line.append((P[i - 1][0] + (P[i][0] - P[i - 1][0]) * f, P[i - 1][1] + (P[i][1] - P[i - 1][1]) * f))
                break
        # 面グラデーション
        if len(line) > 1:
            poly = line + [(line[-1][0], gy0), (line[0][0], gy0)]
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(layer).polygon(poly, fill=GOLD + (int(40 * fade),))
            frame.alpha_composite(layer)
            d = ImageDraw.Draw(frame)
            d.line(line, fill=blend(GOLD, fade, NAVY2), width=7, joint="curve")
        for i, (x, y) in enumerate(P):
            if i > reach + 1e-6:
                break
            d.ellipse([x - 11, y - 11, x + 11, y + 11], fill=blend(GOLD, fade, NAVY2), outline=blend(WHITE, fade, NAVY2), width=3)
            if pts[i].get("label"):
                if i not in lab_cache:
                    lab_cache[i] = (multiline_sprite(pts[i]["label"], "bold", 30, WHITE, 340, 1.25, align="center"),
                                    text_sprite(pts[i].get("xlabel", str(pts[i]["x"])), "medium", 28, LGRAY))
                lab, xl = lab_cache[i]
                frame.alpha_composite(with_alpha(lab, fade), (int(x - lab.width / 2), int(y - 30 - lab.height)))
                frame.alpha_composite(with_alpha(xl, fade), (int(x - xl.width / 2), int(gy0 + 16)))

    els.append(Drawer(curve))
    for i in range(len(P)):
        se.append((t0 + draw_dur * i / max(1, len(P) - 1), "tick"))
    if sc.get("callout"):
        co = sc["callout"]
        spr = text_sprite(co["text"], "black", co.get("size", 72), COLORS.get(co.get("color", "gold"), GOLD), glow=GOLD)
        tc = cue_time(co, 0, cues, t0 + draw_dur)
        els.append(El(spr, co.get("x", 760), co.get("y", 380), tc, "pop", 0.6))
        se.append((tc, "pop"))
    if sc.get("source"):
        els.append(source_el(sc["source"]))
    return els, se


def build_compare(sc, cues, dur):
    els, se = [], [(0.0, "whoosh")]
    els.append(El(text_sprite(sc["title"], "bold", 66, WHITE), W / 2, 180, 0.1))
    pw, ph = 780, 500
    for k, side in enumerate(["left", "right"]):
        s = sc[side]
        col = COLORS.get(s.get("color", "sky" if k == 0 else "gold"), GOLD)
        t0 = cue_time(s, k, cues, 0.5 + k * 0.9)
        se.append((t0, "tick"))
        p = panel_sprite(pw, ph, border=col)
        head = text_sprite(s["head"], "black", 60, col)
        p.alpha_composite(head, (int(pw / 2 - head.width / 2), 50))
        y = 170
        for line in s["lines"]:
            b = multiline_sprite("● " + line, "medium", 38, WHITE, pw - 100, 1.35)
            p.alpha_composite(b, (50, y))
            y += b.height + 26
        els.append(El(p, 540 if k == 0 else W - 540, 560, t0, "left" if k == 0 else "right", 0.6))
    vs = text_sprite(sc.get("vs", "→"), "black", 90, WHITE)
    els.append(El(vs, W / 2, 560, cue_time(sc["right"], 1, cues, 1.4), "pop"))
    return els, se


def build_list(sc, cues, dur):
    els, se = [], [(0.0, "whoosh")]
    els.append(El(text_sprite(sc["title"], "bold", 70, GOLD, glow=GOLD), W / 2, 190, 0.1))
    items = sc["items"]
    n = len(items)
    top = 330
    row = min(130, 600 / n)
    for i, it in enumerate(items):
        text = it["text"] if isinstance(it, dict) else it
        t0 = cue_time(it, i, cues, 0.5 + i * 0.45)
        se.append((t0, "tick"))
        row_img = Image.new("RGBA", (1500, int(row)), (0, 0, 0, 0))
        d = ImageDraw.Draw(row_img)
        d.rounded_rectangle([0, 12, 70, 82], radius=14, fill=SKYBLUE + (255,))
        num = text_sprite(str(i + 1), "black", 44, NAVY)
        row_img.alpha_composite(num, (int(35 - num.width / 2), int(47 - num.height / 2)))
        tx = text_sprite(text, "bold", 48, WHITE)
        row_img.alpha_composite(tx, (100, int(47 - tx.height / 2)))
        els.append(El(row_img, 210, top + i * row, t0, "left", anchor="lt"))
    return els, se


def build_outro(sc, cues, dur):
    els, se = [], [(0.0, "whoosh")]
    els.append(El(multiline_sprite(sc["message"], "black", 76, GOLD, 1600, 1.3, align="center"), W / 2, 340, 0.2, "pop", 0.7))
    btn = Image.new("RGBA", (620, 120), (0, 0, 0, 0))
    ImageDraw.Draw(btn).rounded_rectangle([0, 0, 619, 119], radius=60, fill=CRIMSON + (255,))
    lab = text_sprite(sc.get("cta", "チャンネル登録"), "black", 54, WHITE)
    btn.alpha_composite(lab, (int(310 - lab.width / 2), int(60 - lab.height / 2)))
    tc = cue_time(sc, 0, cues, 1.2)
    els.append(El(btn, W / 2, 580, tc, "pop", 0.6))
    se.append((tc, "pop"))
    if sc.get("credits"):
        els.append(El(multiline_sprite(sc["credits"], "light", 24, LGRAY, 1700, 1.4, align="center"), W / 2, 760, 1.0))
    return els, se


BUILDERS = {
    "title": build_title, "chapter": build_chapter, "impact": build_impact, "bars": build_bars,
    "cards": build_cards, "timeline": build_timeline, "curve": build_curve, "compare": build_compare,
    "list": build_list, "outro": build_outro,
}


# ─── HUD・字幕 ──────────────────────────────────────────────────────────────

def subtitle_sprite(text):
    f = font("bold", 46)
    lines = wrap_jp(text, f, 1500)
    if len(lines) > 1:  # 行の長さを揃える（2行目が「した。」だけ、を防ぐ）
        target = f.getlength(text) / len(lines) + 46 * 1.5
        lines = wrap_jp(text, f, min(1500, target))
    lh = 64
    w = int(max(f.getlength(s) for s in lines)) + 80
    h = lh * len(lines) + 34
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=16, fill=(0, 0, 0, 150))
    for i, s in enumerate(lines):
        d.text(((w - f.getlength(s)) / 2, 14 + i * lh), s, font=f, fill=WHITE + (255,), stroke_width=2,
               stroke_fill=(0, 0, 0, 255))
    return img


def render_scene(job):
    """1シーンを rawvideo で ffmpeg に流し込み MP4 セグメントを作る（並列実行される）"""
    sc, idx, start, dur, cues, sents, total, meta, out_path = job
    bg = make_background()
    net = Network()
    elements, _ = BUILDERS[sc["type"]](sc, cues, dur)
    subs = [(cues[i], cues[i] + sents[i][1], subtitle_sprite(sents[i][0])) for i in range(len(sents))]
    hud_l = text_sprite(meta["channel"], "bold", 30, LGRAY)
    hud_r = text_sprite(sc.get("hud", meta.get("hud", "")), "medium", 28, SKYBLUE) if sc.get("hud", meta.get("hud")) else None
    nframes = int(round(dur * FPS))
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
         "-pix_fmt", "yuv420p", out_path],
        stdin=subprocess.PIPE,
    )
    for fi in range(nframes):
        t = fi / FPS
        gt = start + t
        frame = bg.copy()
        net.draw(frame, gt)
        fade = 1.0 - ease_in_out(clamp((t - (dur - EXIT)) / EXIT))
        for el in elements:
            el.draw(frame, t, fade)
        # HUD
        frame.alpha_composite(hud_l, (60, 36))
        if hud_r:
            frame.alpha_composite(hud_r, (W - 60 - hud_r.width, 38))
        d = ImageDraw.Draw(frame)
        d.rectangle([0, H - 8, int(W * gt / total), H], fill=GOLD + (255,))
        # 字幕
        for s0, s1, spr in subs:
            if s0 - 0.05 <= t <= s1 + 0.25:
                a = clamp((t - s0 + 0.05) / 0.15) * clamp((s1 + 0.25 - t) / 0.15)
                frame.alpha_composite(with_alpha(spr, a), (int(W / 2 - spr.width / 2), int(H - 50 - spr.height)))
        proc.stdin.write(frame.convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    return out_path


# ─── オーディオ（BGM作曲・効果音・ミックス） ─────────────────────────────────

def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def compose_bgm(seconds, bpm=92, seed=3):
    """Am7–Fmaj7–C–G のアンビエント・ローファイ風BGMを合成する"""
    rnd = np.random.default_rng(seed)
    n = int(seconds * SR) + SR
    out = np.zeros(n, np.float32)
    beat = 60 / bpm
    bar = beat * 4
    prog = [[57, 60, 64, 67], [53, 57, 60, 64], [48, 55, 60, 64], [55, 59, 62, 67]]
    t_bar = np.arange(int(bar * SR)) / SR
    env_pad = np.minimum(t_bar / 0.8, 1) * np.minimum((bar - t_bar) / 0.8, 1)
    bars = int(seconds / bar) + 2
    for b in range(bars):
        chord = prog[b % 4]
        s = int(b * bar * SR)
        seg = np.zeros_like(t_bar, dtype=np.float32)
        for note in chord:
            f = midi(note)
            for det in (-0.12, 0.12):
                ff = f * 2 ** (det / 12)
                seg += (np.sin(2 * np.pi * ff * t_bar) + 0.25 * np.sin(4 * np.pi * ff * t_bar)) * 0.035
        bass = np.sin(2 * np.pi * midi(chord[0] - 12) * t_bar) * 0.10 * env_pad
        seg = seg * env_pad + bass
        add(out, seg, s / SR)
        # アルペジオ（8分音符）
        for k in range(8):
            note = chord[[0, 2, 1, 3, 2, 1, 3, 2][k]] + 12
            ts = s + int(k * beat / 2 * SR)
            L = int(beat * SR)
            tt = np.arange(L) / SR
            add(out, np.sin(2 * np.pi * midi(note) * tt) * np.exp(-tt * 6) * 0.05, ts / SR)
        # ソフトなキック＋ハット
        for k in range(4):
            ts = s + int(k * beat * SR)
            L = int(0.25 * SR)
            tt = np.arange(L) / SR
            add(out, np.sin(2 * np.pi * (50 + 60 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 14) * 0.16, ts / SR)
            th = s + int((k + 0.5) * beat * SR)
            Lh = int(0.06 * SR)
            hat = rnd.standard_normal(Lh).astype(np.float32)
            add(out, np.diff(hat, prepend=0) * np.exp(-np.arange(Lh) / SR * 70) * 0.025, th / SR)
    # 簡易ローパス（こもらせてナレーションの邪魔をしない）
    k = np.ones(6) / 6
    out = np.convolve(out, k, mode="same").astype(np.float32)
    fade = int(2.5 * SR)
    out[:fade] *= np.linspace(0, 1, fade)
    out[int(seconds * SR) - fade:int(seconds * SR)] *= np.linspace(1, 0, fade)
    out[int(seconds * SR):] = 0
    return out[: int(seconds * SR)]


def sfx(kind):
    rnd = np.random.default_rng(len(kind))
    if kind == "whoosh":
        L = int(0.55 * SR)
        tt = np.arange(L) / SR
        noise = rnd.standard_normal(L).astype(np.float32)
        # 移動平均の窓幅を変えて擬似的なフィルタースイープ
        out = np.zeros(L, np.float32)
        acc = np.cumsum(noise)
        for i in range(0, L, 256):
            w = int(40 - 34 * math.sin(math.pi * i / L))
            j = slice(i, min(L, i + 256))
            idx = np.arange(j.start, j.stop)
            out[j] = (acc[idx] - acc[np.maximum(idx - w, 0)]) / w
        env = np.sin(np.pi * tt / tt[-1]) ** 2
        return out * env * 0.35
    if kind == "pop":
        L = int(0.35 * SR)
        tt = np.arange(L) / SR
        return (np.sin(2 * np.pi * 880 * tt) + 0.5 * np.sin(2 * np.pi * 1320 * tt)) * np.exp(-tt * 9) * 0.14
    if kind == "tick":
        L = int(0.12 * SR)
        tt = np.arange(L) / SR
        return np.sin(2 * np.pi * 1600 * tt) * np.exp(-tt * 45) * 0.10
    if kind == "rise":
        L = int(1.4 * SR)
        tt = np.arange(L) / SR
        f = 200 + 600 * (tt / tt[-1]) ** 2
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * (tt / tt[-1]) ** 2 * np.exp(-np.maximum(tt - 1.2, 0) * 30) * 0.06
    return np.zeros(1, np.float32)


def add(buf, sig, t):
    s = int(t * SR)
    if s >= len(buf):
        return
    e = min(len(buf), s + len(sig))
    buf[s:e] += sig[: e - s]


def write_wav(path, data):
    data = np.clip(data, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((data * 32767).astype(np.int16).tobytes())


# ─── サムネイル ─────────────────────────────────────────────────────────────

def make_thumbnail(meta, path):
    th = meta.get("thumbnail", {})
    img = make_background()
    Network().draw(img, 3.0)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 40, H], fill=GOLD + (255,))
    # 右側：右肩上がりのグロー付きグラフ（成長・最前線のイメージ）
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    xs = [1080, 1240, 1400, 1560, 1720]
    hs = [180, 270, 400, 580, 800]
    for x, h in zip(xs, hs):
        ld.rounded_rectangle([x, H - 80 - h, x + 120, H - 80], radius=14, fill=SKYBLUE + (110,))
    pts = [(x + 60, H - 80 - h - 40) for x, h in zip(xs, hs)]
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).line(pts, fill=GOLD + (255,), width=30, joint="curve")
    layer = Image.alpha_composite(layer, glow.filter(ImageFilter.GaussianBlur(18)))
    ld = ImageDraw.Draw(layer)
    ld.line(pts, fill=GOLD + (255,), width=14, joint="curve")
    tip = pts[-1]
    ld.polygon([(tip[0] - 40, tip[1] + 5), (tip[0] + 50, tip[1] - 70), (tip[0] + 25, tip[1] + 45)], fill=GOLD + (255,))
    for x, y in pts[:-1]:
        ld.ellipse([x - 20, y - 20, x + 20, y + 20], fill=WHITE + (255,), outline=GOLD + (255,), width=6)
    img.alpha_composite(layer)
    big = text_sprite(th.get("big", meta["title"]), "black", th.get("big_size", 230), GOLD, stroke=6, glow=GOLD)
    img.alpha_composite(big, (110, 300 - big.height // 2))
    sub = text_sprite(th.get("sub", ""), "black", 120, WHITE, stroke=5)
    img.alpha_composite(sub, (120, 620 - sub.height // 2))
    if th.get("badge"):
        b = text_sprite(th["badge"], "black", 70, WHITE)
        bw, bh = b.width + 70, b.height + 30
        d.rounded_rectangle([110, 830, 110 + bw, 830 + bh], radius=20, fill=CRIMSON + (255,))
        img.alpha_composite(b, (145, 845))
    img.convert("RGB").resize((1280, 720), Image.LANCZOS).save(path)


# ─── メイン ────────────────────────────────────────────────────────────────

def fmt_ts(t, srt=False):
    h, m = int(t // 3600), int(t % 3600 // 60)
    s = t % 60
    if srt:
        return f"{h:02d}:{m:02d}:{int(s):02d},{int((s % 1) * 1000):03d}"
    return f"{m}:{int(s):02d}"


def produce(script_path, output_dir):
    meta = json.loads(Path(script_path).read_text(encoding="utf-8"))
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    slug = meta.get("slug", Path(script_path).stem)
    work = out / f"_work_{slug}"
    work.mkdir(exist_ok=True)
    vo = meta.get("voice", {})
    voice_path = find_voice(vo.get("model", "tohoku-f01-neutral"))
    speed, pitch = vo.get("speed", 1.1), vo.get("pitch", 0.0)
    scenes = meta["scenes"]

    # 1. 文単位の音声合成 → タイミング決定
    print(f"[1/5] ナレーション音声を文単位で合成中（{sum(len(s['narration']) for s in scenes)}文）...")
    timeline, t_cursor = [], 0.0
    for si, sc in enumerate(scenes):
        cues, sents, clips = [], [], []
        t = LEAD_IN
        for k, line in enumerate(sc["narration"]):
            data = synth(reading_text(line), voice_path, speed, pitch, str(work / f"s{si:02d}_{k:02d}.wav"))
            d = len(data) / SR
            cues.append(t)
            sents.append((display_text(line), d))
            clips.append((t, data))
            t += d + SENT_GAP
        dur = max(t - SENT_GAP + TAIL, sc.get("min_dur", 0))
        timeline.append({"start": t_cursor, "dur": dur, "cues": cues, "sents": sents, "clips": clips})
        t_cursor += dur
    total = t_cursor
    print(f"      総尺 {fmt_ts(total)}（{total:.1f}秒）")

    # 2. シーン並列レンダリング
    print(f"[2/5] {len(scenes)}シーンを並列レンダリング中（{int(total * FPS)}フレーム）...")
    jobs = []
    for si, (sc, tl) in enumerate(zip(scenes, timeline)):
        jobs.append((sc, si, tl["start"], tl["dur"], tl["cues"], tl["sents"], total, meta, str(work / f"seg{si:02d}.mp4")))
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
        for p in ex.map(render_scene, jobs):
            print(f"      ✓ {Path(p).name}")

    # 3. オーディオ：ナレーション＋BGM（ダッキング）＋効果音
    print("[3/5] BGM作曲・効果音・ミックス中...")
    n = int(total * SR) + SR
    voice = np.zeros(n, np.float32)
    fx = np.zeros(n, np.float32)
    for sc, tl in zip(scenes, timeline):
        for t0, data in tl["clips"]:
            add(voice, data, tl["start"] + t0)
        _, se = BUILDERS[sc["type"]](sc, tl["cues"], tl["dur"])
        for t0, kind in se:
            add(fx, sfx(kind), tl["start"] + t0)
    bgm = np.zeros(n, np.float32)
    bgm[: int(total * SR)] = compose_bgm(total)
    env = np.abs(voice)
    win = int(0.3 * SR)
    env = np.convolve(env, np.ones(win) / win, mode="same")
    duck = 1.0 - 0.55 * np.clip(env / 0.03, 0, 1)
    mix = voice * 1.0 + bgm * 0.9 * duck + fx
    mix_path = str(work / "mix.wav")
    write_wav(mix_path, mix[: int(total * SR)])

    # 4. 結合・書き出し
    print("[4/5] セグメント結合・ラウドネス正規化・MP4書き出し中...")
    lst = work / "concat.txt"
    lst.write_text("".join(f"file '{j[-1]}'\n" for j in jobs), encoding="utf-8")
    mp4 = out / f"{slug}.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", mix_path,
         "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-shortest", "-movflags", "+faststart", str(mp4)],
        check=True,
    )

    # 5. 付属物：字幕SRT・チャプター・サムネイル
    print("[5/5] 字幕・チャプター・サムネイル生成中...")
    srt, chapters, k = [], [], 1
    for sc, tl in zip(scenes, timeline):
        for c, (txt, d) in zip(tl["cues"], tl["sents"]):
            s = tl["start"] + c
            srt.append(f"{k}\n{fmt_ts(s, True)} --> {fmt_ts(s + d, True)}\n{txt}\n")
            k += 1
        if sc.get("chapter_title"):
            chapters.append(f"{fmt_ts(tl['start'])} {sc['chapter_title']}")
    (out / f"{slug}.srt").write_text("\n".join(srt), encoding="utf-8")
    (out / f"{slug}_chapters.txt").write_text("\n".join(chapters) + "\n", encoding="utf-8")
    make_thumbnail(meta, str(out / f"{slug}_thumbnail.png"))
    shutil.rmtree(work)
    print(f"\n完成: {mp4}（{total:.1f}秒）")
    return str(mp4)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    produce(sys.argv[1], sys.argv[2])
