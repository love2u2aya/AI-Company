#!/usr/bin/env python3
"""
Video_Producer スキル：縦型ショート（1080×1920）生成エンジン

- 音声: Open JTalk（社長ナレーション = nitech m001 / 奥さん = MMDAgent "Mei"）
- 映像: Pillow で1フレームずつ描画 → FFmpeg に直接パイプ
- BGM・効果音: numpy で合成（外部素材なし＝著作権クリア）

各動画スクリプト（wife_intro_pop.py など）が Scene を並べて render() を呼ぶ。
環境構築は setup_shorts_env.sh を参照。
"""

import math
import os
import subprocess
import tempfile
import wave
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FPS = 30
SR = 48000

DIC = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
VOICE_DIR = Path(os.environ.get("PAPAMAMA_VOICE_DIR", Path.home() / ".cache/papamama/voices"))
VOICES = {
    "papa": "/usr/share/hts-voice/nitech-jp-atr503-m001/nitech_jp_atr503_m001.htsvoice",
    "mama": str(VOICE_DIR / "mei/mei_normal.htsvoice"),
    "mama_happy": str(VOICE_DIR / "mei/mei_happy.htsvoice"),
    "mama_angry": str(VOICE_DIR / "mei/mei_angry.htsvoice"),
    "mama_shy": str(VOICE_DIR / "mei/mei_bashful.htsvoice"),
    "mama_sad": str(VOICE_DIR / "mei/mei_sad.htsvoice"),
}

FONT_POP = "/usr/share/fonts/opentype/mplus/Mplus2-Black.otf"
FONT_POP_BOLD = "/usr/share/fonts/opentype/mplus/Mplus2-ExtraBold.otf"
FONT_GOTHIC_BLACK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
FONT_SERIF_BLACK = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Black.ttc"
FONT_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"


# ─── イージング ─────────────────────────────────────────────────────────────

def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out_back(x, s=1.70158):
    x = clamp(x) - 1
    return x * x * ((s + 1) * x + s) + 1


def ease_out_cubic(x):
    return 1 - (1 - clamp(x)) ** 3


def ease_in_cubic(x):
    return clamp(x) ** 3


def ease_out_elastic(x):
    x = clamp(x)
    if x in (0, 1):
        return x
    return 2 ** (-10 * x) * math.sin((x * 10 - 0.75) * (2 * math.pi) / 3) + 1


# ─── 音声 ──────────────────────────────────────────────────────────────────

def read_wav(path):
    with wave.open(str(path)) as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        if w.getnchannels() == 2:
            data = data.reshape(-1, 2).mean(axis=1)
    if sr != SR:
        n = int(len(data) * SR / sr)
        data = np.interp(np.linspace(0, len(data) - 1, n), np.arange(len(data)), data).astype(np.float32)
    return data


def tts(text, voice="papa", speed=1.0, pitch=0.0, volume=0.0):
    """Open JTalk で読み上げ。前後の無音をトリムして返す。"""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "v.wav"
        cmd = ["open_jtalk", "-x", DIC, "-m", VOICES[voice], "-r", str(speed),
               "-fm", str(pitch), "-g", str(volume), "-ow", str(out)]
        subprocess.run(cmd, input=text.encode("utf-8"), check=True, capture_output=True)
        sig = read_wav(out)
    idx = np.where(np.abs(sig) > 0.01)[0]
    if len(idx):
        sig = sig[max(0, idx[0] - 480): idx[-1] + 2400]
    peak = np.max(np.abs(sig)) or 1
    return (sig / peak * 0.85).astype(np.float32)


class Mixer:
    def __init__(self, seconds):
        self.buf = np.zeros(int(seconds * SR) + SR, dtype=np.float32)
        self.voice_mask = np.zeros_like(self.buf)

    def add(self, sig, t, gain=1.0, voice=False):
        i = int(t * SR)
        if i >= len(self.buf):
            return
        sig = sig[: len(self.buf) - i]
        self.buf[i: i + len(sig)] += sig * gain
        if voice:
            self.voice_mask[i: i + len(sig)] = 1

    def add_bgm(self, bgm, gain=0.3, duck=0.45, t0=0.0, t1=None):
        """ナレーション中はBGMを下げる（サイドチェイン風ダッキング）"""
        i0 = int(t0 * SR)
        i1 = len(self.buf) if t1 is None else int(t1 * SR)
        n = i1 - i0
        reps = int(np.ceil(n / len(bgm)))
        b = np.tile(bgm, reps)[:n]
        k = int(0.15 * SR)
        env = np.convolve(self.voice_mask[i0:i1], np.ones(k) / k, mode="same")
        g = gain * (1 - (1 - duck) * np.clip(env * 1.5, 0, 1))
        fade = int(1.0 * SR)
        g[-fade:] *= np.linspace(1, 0, fade)
        self.buf[i0:i1] += b * g

    def save(self, path, seconds):
        x = self.buf[: int(seconds * SR)]
        peak = np.max(np.abs(x))
        if peak > 0.98:
            x = x / peak * 0.98
        pcm = (x * 32767).astype(np.int16)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())


# ─── 合成音（BGM・効果音） ─────────────────────────────────────────────────

def _t(sec):
    return np.arange(int(sec * SR)) / SR


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def pluck(freq, dur, bright=1.0):
    """ウクレレ風の撥弦音（倍音ごとに減衰速度を変える）"""
    t = _t(dur)
    out = np.zeros_like(t)
    for k in range(1, 9):
        out += (1 / k ** 1.2) * np.sin(2 * np.pi * freq * k * t) * np.exp(-t * (3 + 2.5 * k / bright))
    out *= np.minimum(1, t / 0.003)
    return out.astype(np.float32)


def bell(freq, dur):
    """グロッケン風"""
    t = _t(dur)
    out = (np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(2 * np.pi * freq * 2.76 * t) * np.exp(-t * 6)
           + 0.2 * np.sin(2 * np.pi * freq * 5.4 * t) * np.exp(-t * 10))
    return (out * np.exp(-t * 3.5) * np.minimum(1, t / 0.002)).astype(np.float32)


def kick(dur=0.35, depth=1.0):
    t = _t(dur)
    f = 50 + 120 * np.exp(-t * 30) * depth
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * np.exp(-t * 9)).astype(np.float32)


def noise(dur, seed=0):
    return np.random.default_rng(seed).uniform(-1, 1, int(dur * SR)).astype(np.float32)


def hp(sig, a=0.95):
    """簡易ハイパス"""
    y = np.empty_like(sig)
    y[0] = sig[0]
    y[1:] = sig[1:] - a * sig[:-1]
    return y


def lp(sig, k=8):
    return np.convolve(sig, np.ones(k) / k, mode="same").astype(np.float32)


def snare(dur=0.2):
    t = _t(dur)
    return (0.7 * hp(noise(dur, 3)) * np.exp(-t * 22) + 0.4 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30)).astype(np.float32)


def clap(dur=0.25):
    t = _t(dur)
    env = np.exp(-t * 25)
    for d in (0.0, 0.012, 0.024):
        env += np.where(t >= d, np.exp(-(t - d) * 120), 0) * 0.6
    return (hp(noise(dur, 5), 0.9) * env * 0.5).astype(np.float32)


def hat(dur=0.05, seed=7):
    t = _t(dur)
    return (hp(noise(dur, seed), 0.99) * np.exp(-t * 80) * 0.5).astype(np.float32)


def place(buf, sig, t, gain=1.0):
    i = int(t * SR)
    if i >= len(buf):
        return
    sig = sig[: len(buf) - i]
    buf[i: i + len(sig)] += sig * gain


# 効果音
def sfx_pop():
    t = _t(0.12)
    f = 400 + 1400 * t / 0.12
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 30)).astype(np.float32) * 0.8


def sfx_ding():
    return (bell(midi_hz(88), 1.2) + 0.6 * bell(midi_hz(95), 1.2)) * 0.6


def sfx_buzzer():
    t = _t(0.7)
    sq = np.sign(np.sin(2 * np.pi * 110 * t)) * 0.5 + np.sign(np.sin(2 * np.pi * 116 * t)) * 0.5
    gate = (np.floor(t / 0.35) % 2 == 0).astype(np.float32) * (t % 0.35 < 0.3)
    return (lp(sq.astype(np.float32), 6) * gate * 0.35).astype(np.float32)


def sfx_drumroll(dur=1.4):
    out = np.zeros(int((dur + 0.3) * SR), dtype=np.float32)
    n = int(dur / 0.045)
    for i in range(n):
        place(out, snare(0.12), i * 0.045, 0.25 + 0.5 * i / n)
    place(out, kick(0.5), dur, 0.9)
    place(out, hp(noise(0.8, 11), 0.97) * np.exp(-_t(0.8) * 4), dur, 0.35)
    return out


def sfx_whoosh(dur=0.4, up=True):
    t = _t(dur)
    env = np.sin(np.pi * t / dur) ** 2
    n = noise(dur, 13)
    k = np.linspace(30, 4, len(t)) if up else np.linspace(4, 30, len(t))
    out = np.zeros_like(n)
    # 可変ローパス（区間ごと）
    seg = len(n) // 20
    for s in range(20):
        a, b = s * seg, (s + 1) * seg
        out[a:b] = lp(n[a:b], max(2, int(k[a])))
    return (out * env * 0.6).astype(np.float32)


def sfx_boom(dur=1.6):
    t = _t(dur)
    f = 30 + 90 * np.exp(-t * 8)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.5)
    crack = lp(noise(dur, 17), 3) * np.exp(-t * 6)
    out = np.tanh((sub * 1.4 + crack * 0.8) * 1.5)
    return (out * 0.9).astype(np.float32)


def sfx_kira():
    out = np.zeros(int(1.0 * SR), dtype=np.float32)
    for i, m in enumerate([84, 88, 91, 96, 100]):
        place(out, bell(midi_hz(m), 0.6), i * 0.05, 0.35)
    return out


def sfx_tick():
    t = _t(0.05)
    return (np.sin(2 * np.pi * 2200 * t) * np.exp(-t * 120) * 0.6).astype(np.float32)


def sfx_cheer(dur=2.0):
    """歓声っぽいノイズ（帯域ノイズ＋ゆらぎ）"""
    t = _t(dur)
    n = lp(noise(dur, 21), 5) - lp(noise(dur, 21), 40)
    wob = 0.6 + 0.4 * np.sin(2 * np.pi * 3.1 * t) * np.sin(2 * np.pi * 1.7 * t)
    env = np.minimum(1, t / 0.2) * np.minimum(1, (dur - t) / 0.6)
    return (n * wob * env * 1.6).astype(np.float32)


def sfx_gong(dur=3.0):
    t = _t(dur)
    out = np.zeros_like(t)
    for f, a, d in [(90, 1, 1.0), (152, .6, 1.4), (227, .5, 1.8), (318, .35, 2.4), (447, .25, 3)]:
        out += a * np.sin(2 * np.pi * f * t * (1 + 0.004 * np.sin(2 * np.pi * 0.7 * t))) * np.exp(-t * d)
    out += lp(noise(dur, 5), 4) * np.exp(-t * 12) * 0.5
    return (np.tanh(out * 0.8) * 0.8).astype(np.float32)


# ─── 描画ユーティリティ ────────────────────────────────────────────────────

@lru_cache(maxsize=64)
def font(path, size):
    return ImageFont.truetype(path, size)


@lru_cache(maxsize=256)
def text_img(text, size, fill=(255, 255, 255), stroke=(0, 0, 0), stroke_w=0, path=FONT_POP,
             shadow=None, spacing=0.12, outer=None):
    """複数行テキストをRGBA画像に。outer=(色, 太さ) で二重フチ。shadow=(dx,dy,色)"""
    f = font(path, size)
    lines = text.split("\n")
    pad = stroke_w + (outer[1] if outer else 0) + 20 + (max(abs(shadow[0]), abs(shadow[1])) if shadow else 0)
    boxes = [f.getbbox(l, stroke_width=stroke_w) for l in lines]
    lh = int(size * (1 + spacing))
    tw = max(b[2] - b[0] for b in boxes) + pad * 2
    th = lh * len(lines) + pad * 2
    im = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, (l, b) in enumerate(zip(lines, boxes)):
        x = (tw - (b[2] - b[0])) / 2 - b[0]
        y = pad + i * lh - b[1] * 0.5
        if shadow:
            d.text((x + shadow[0], y + shadow[1]), l, font=f, fill=shadow[2],
                   stroke_width=stroke_w + (outer[1] if outer else 0), stroke_fill=shadow[2])
        if outer:
            d.text((x, y), l, font=f, fill=outer[0], stroke_width=stroke_w + outer[1], stroke_fill=outer[0])
        d.text((x, y), l, font=f, fill=fill, stroke_width=stroke_w, stroke_fill=stroke)
    return im


@lru_cache(maxsize=64)
def emoji_img(ch, size):
    f = font(FONT_EMOJI, 109)
    im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10, 10), ch, font=f, embedded_color=True)
    im = im.crop(im.getbbox() or (0, 0, 160, 160))
    r = size / max(im.size)
    return im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)


def paste(base, im, cx, cy, scale=1.0, rot=0.0, alpha=1.0):
    """中心座標(cx,cy)にスケール・回転・透明度付きで合成"""
    if scale <= 0.01 or alpha <= 0.01:
        return
    if scale != 1.0:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if rot:
        im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 1.0:
        a = im.getchannel("A").point(lambda v: int(v * alpha))
        im = im.copy()
        im.putalpha(a)
    base.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def pop_in(lt, start, dur=0.3):
    """登場スケール（easeOutBack）"""
    return ease_out_back((lt - start) / dur) if lt >= start else 0.0


def rounded_box(size, radius, fill, outline=None, width=0):
    im = Image.new("RGBA", (size[0] * 2, size[1] * 2), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, size[0] * 2 - 1, size[1] * 2 - 1], radius * 2, fill=fill,
                                         outline=outline, width=width * 2)
    return im.resize(size, Image.LANCZOS)


# ─── タイムライン ──────────────────────────────────────────────────────────

@dataclass
class Line:
    voice: str          # VOICES のキー
    text: str           # 読み上げテキスト（ひらがな寄りで調整可）
    sub: str = None     # 字幕（省略時は text）
    speed: float = 1.0
    pitch: float = 0.0
    gap: float = 0.25   # 次の行までの間
    delay: float = 0.0  # この行の前に置く間
    # 計算後に埋まる
    start: float = 0.0
    end: float = 0.0
    sig: np.ndarray = None


@dataclass
class Scene:
    name: str
    lines: list
    draw: object                 # draw(frame, lt, scene)
    pre: float = 0.25
    post: float = 0.35
    sfx: list = field(default_factory=list)   # [(名前 or 波形, ("line", i, offset) | 秒, gain)]
    min_dur: float = 0.0
    start: float = 0.0
    dur: float = 0.0

    def L(self, i):
        return self.lines[i]

    def t_of(self, spec):
        if isinstance(spec, (int, float)):
            return spec
        kind, i, off = spec
        ln = self.lines[i]
        return (ln.start if kind == "line" else ln.end) + off


def build_timeline(scenes, voice_defaults=None):
    voice_defaults = voice_defaults or {}
    t = 0.0
    for sc in scenes:
        sc.start = t
        lt = sc.pre
        for ln in sc.lines:
            d = voice_defaults.get(ln.voice, {})
            ln.sig = tts(ln.text, ln.voice, speed=ln.speed * d.get("speed", 1.0),
                         pitch=ln.pitch + d.get("pitch", 0.0))
            lt += ln.delay
            ln.start = lt
            ln.end = lt + len(ln.sig) / SR
            lt = ln.end + ln.gap
        sc.dur = max(lt - (sc.lines[-1].gap if sc.lines else 0) + sc.post, sc.min_dur)
        t += sc.dur
    return t


SFX = {
    "pop": sfx_pop, "ding": sfx_ding, "buzzer": sfx_buzzer, "drumroll": sfx_drumroll,
    "whoosh": sfx_whoosh, "boom": sfx_boom, "kira": sfx_kira, "tick": sfx_tick,
    "cheer": sfx_cheer, "gong": sfx_gong, "kick": kick, "clap": clap,
}


def mix_audio(scenes, total, bgm=None, bgm_gain=0.3, voice_gain=1.0, out_path=None):
    mx = Mixer(total)
    for sc in scenes:
        for ln in sc.lines:
            mx.add(ln.sig, sc.start + ln.start, voice_gain, voice=True)
    for sc in scenes:
        for name, spec, gain in sc.sfx:
            sig = SFX[name]() if isinstance(name, str) else name
            mx.add(sig, sc.start + sc.t_of(spec), gain)
    if bgm is not None:
        mx.add_bgm(bgm, gain=bgm_gain)
    mx.save(out_path, total)


def render(scenes, total, audio_path, out_path, bg_frame=None, overlay=None, crf=20):
    """各フレームを描画して FFmpeg へパイプ"""
    nframes = int(total * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(audio_path),
           "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
           "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out_path)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    si = 0
    for fi in range(nframes):
        t = fi / FPS
        while si < len(scenes) - 1 and t >= scenes[si].start + scenes[si].dur:
            si += 1
        sc = scenes[si]
        lt = t - sc.start
        frame = bg_frame(t, sc, lt) if bg_frame else Image.new("RGBA", (W, H), (0, 0, 0, 255))
        sc.draw(frame, lt, sc)
        if overlay:
            frame = overlay(frame, t, sc, lt) or frame
        p.stdin.write(frame.convert("RGB").tobytes())
        if fi % 300 == 0:
            print(f"  frame {fi}/{nframes}", flush=True)
    p.stdin.close()
    p.wait()
    if p.returncode:
        raise RuntimeError("ffmpeg failed")


def current_line(sc, lt):
    for ln in sc.lines:
        if ln.start - 0.05 <= lt <= ln.end + ln.gap:
            return ln
    return None
