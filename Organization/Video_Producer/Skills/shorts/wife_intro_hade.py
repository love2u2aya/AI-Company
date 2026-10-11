#!/usr/bin/env python3
"""
ショート動画②「奥さん大紹介」— ド派手・どんどんどーん版（約60秒・9:16）
格闘技の入場コール風。衝撃（ドーン）のたびに画面揺れ・フラッシュ・集中線・爆発。

使い方:
    python3 wife_intro_hade.py <出力MP4パス>
"""

import math
import random
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import short_engine as E
from short_engine import Line, Scene, W, H, paste, emoji_img, clamp, ease_out_cubic
from characters import mama, papa

GOTHIC = E.FONT_GOTHIC_BLACK
SERIF = E.FONT_SERIF_BLACK
GOLD = ((255, 250, 190), (255, 196, 30), (200, 110, 0))
RED = ((255, 170, 150), (255, 40, 40), (150, 0, 0))
WHITEG = ((255, 255, 255), (255, 255, 255), (200, 220, 255))
CYAN = ((220, 255, 255), (60, 220, 255), (0, 110, 220))
PINKG = ((255, 220, 240), (255, 90, 170), (190, 0, 110))

VOICE_DEFAULTS = {"papa": {"speed": 0.98, "pitch": -1.0}}
SCENES = []
IMPACTS = []   # (時刻, 強さ)


# ─── 派手テキスト（グラデ塗り＋二重フチ＋影） ───────────────────────────────

@lru_cache(maxsize=256)
def hade_text(text, size, grad=GOLD, path=GOTHIC, stroke=(20, 0, 0), sw=None, outer=(255, 255, 255), ow=None,
              spacing=0.05):
    sw = int(size * 0.07) if sw is None else sw
    ow = int(size * 0.05) if ow is None else ow
    f = E.font(path, size)
    lines = text.split("\n")
    pad = sw + ow + 30
    boxes = [f.getbbox(l) for l in lines]
    lh = int(size * (1 + spacing))
    tw = max(b[2] - b[0] for b in boxes) + pad * 2
    th = lh * len(lines) + pad * 2
    mask = Image.new("L", (tw, th), 0)
    out_mask = Image.new("L", (tw, th), 0)
    st_mask = Image.new("L", (tw, th), 0)
    dm, do, ds = ImageDraw.Draw(mask), ImageDraw.Draw(out_mask), ImageDraw.Draw(st_mask)
    for i, (l, b) in enumerate(zip(lines, boxes)):
        x = (tw - (b[2] - b[0])) / 2 - b[0]
        y = pad + i * lh - b[1] * 0.6
        dm.text((x, y), l, font=f, fill=255)
        ds.text((x, y), l, font=f, fill=255, stroke_width=sw, stroke_fill=255)
        do.text((x, y), l, font=f, fill=255, stroke_width=sw + ow, stroke_fill=255)
    im = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    # 影
    sh = Image.new("RGBA", (tw, th), (0, 0, 0, 160))
    im.paste(sh, (int(size * 0.04), int(size * 0.06)), out_mask)
    im = im.filter(ImageFilter.GaussianBlur(4))
    im.paste(Image.new("RGBA", (tw, th), outer + (255,)), (0, 0), out_mask)
    im.paste(Image.new("RGBA", (tw, th), stroke + (255,)), (0, 0), st_mask)
    # グラデ（上→中→下、中央に光沢ライン）
    g = np.linspace(0, 1, th)[:, None]
    c0, c1, c2 = (np.array(c, dtype=float) for c in grad)
    top = np.where(g < 0.5, 1 - g * 2, 0)
    bot = np.where(g >= 0.5, (g - 0.5) * 2, 0)
    mid = 1 - top - bot
    col = c0 * top[..., None] + c1 * mid[..., None] + c2 * bot[..., None]
    col = np.repeat(col, tw, axis=1)
    shine = (np.abs(g - 0.47) < 0.02)[..., None].repeat(tw, axis=1)
    col = np.where(shine, np.minimum(255, col + 90), col)
    gi = Image.fromarray(col.astype(np.uint8)).convert("RGBA")
    im.paste(gi, (0, 0), mask)
    return im


def slam(fr, lt, start, im, x, y, rot=0.0, from_scale=3.2, dur=0.14, hold=None, wobble=True):
    """巨大化して叩きつける"""
    if lt < start or (hold is not None and lt > start + hold):
        return
    k = (lt - start) / dur
    if k < 1:
        s = from_scale - (from_scale - 1) * E.ease_in_cubic(k) ** 0.6
        a = clamp(k * 1.5)
    else:
        s = 1 + 0.08 * math.exp(-(lt - start - dur) * 7) * math.cos((lt - start - dur) * 30)
        a = 1.0
    if wobble:
        rot += math.sin(lt * 6) * 1.2
    paste(fr, im, x, y, s, rot, a)


# ─── 背景（回転するサンバースト） ─────────────────────────────────────────

N_RAYS = 18
RAY_FRAMES = 24
SCHEMES = {
    "red": ((120, 0, 10), (25, 0, 5), (255, 60, 40)),
    "gold": ((255, 150, 0), (120, 40, 0), (255, 240, 120)),
    "night": ((40, 0, 80), (5, 0, 20), (160, 60, 255)),
    "blue": ((0, 60, 160), (0, 5, 30), (60, 200, 255)),
}


def _rays(scheme, phase):
    c_a, c_b, glow = (np.array(c, dtype=float) for c in SCHEMES[scheme])
    ys, xs = np.mgrid[0:H // 2, 0:W // 2]
    cx, cy = W / 4, H / 4 * 0.9
    ang = np.arctan2(ys - cy, xs - cx) + phase
    r = np.hypot(xs - cx, ys - cy) / (H / 2)
    ray = (np.sin(ang * N_RAYS) > 0).astype(float)
    base = c_a * ray[..., None] + c_b * (1 - ray[..., None])
    glow_k = np.exp(-r * 3.5)[..., None]
    col = base * (1 - glow_k * 0.6) + glow * glow_k * 0.6
    vig = np.clip(1 - (r - 0.35) * 0.9, 0.25, 1)[..., None]
    col = np.clip(col * vig, 0, 255).astype(np.uint8)
    return Image.fromarray(col).resize((W, H), Image.BILINEAR).convert("RGBA")


@lru_cache(maxsize=4)
def ray_frames(scheme):
    period = 2 * math.pi / N_RAYS
    return [_rays(scheme, period * i / RAY_FRAMES) for i in range(RAY_FRAMES)]


@lru_cache(maxsize=1)
def speed_lines():
    out = []
    rng = random.Random(3)
    for v in range(4):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        cx, cy = W / 2, H * 0.42
        for _ in range(90):
            a = rng.uniform(0, 2 * math.pi)
            w = rng.uniform(0.004, 0.018)
            r0 = rng.uniform(330, 560)
            pts = [(cx + r0 * math.cos(a), cy + r0 * math.sin(a)),
                   (cx + 2200 * math.cos(a - w), cy + 2200 * math.sin(a - w)),
                   (cx + 2200 * math.cos(a + w), cy + 2200 * math.sin(a + w))]
            d.polygon(pts, fill=(255, 255, 255, rng.randint(110, 200)))
        out.append(im)
    return out


# ─── パーティクル ───────────────────────────────────────────────────────────

rng = random.Random(11)
CONFETTI = [dict(x=rng.uniform(0, W), y=rng.uniform(-H, 0), vy=rng.uniform(250, 520), ph=rng.uniform(0, 6.3),
                 c=rng.choice([(255, 215, 0), (255, 240, 150), (255, 60, 60), (255, 255, 255), (255, 150, 0)]),
                 w=rng.randint(14, 26)) for _ in range(70)]


def confetti(fr, t, since, alpha=1.0):
    if t < since:
        return
    d = ImageDraw.Draw(fr)
    lt = t - since
    for p in CONFETTI:
        y = p["y"] + lt * p["vy"]
        if y > H + 40:
            y = (y + H) % (H + 80) - 40
        x = p["x"] + math.sin(lt * 2 + p["ph"]) * 40
        flip = abs(math.cos(lt * 6 + p["ph"]))
        w, h = p["w"], p["w"] * 0.5 * (0.2 + flip)
        a = p["ph"] + lt * 3
        pts = [(x + math.cos(a) * w - math.sin(a) * h, y + math.sin(a) * w + math.cos(a) * h),
               (x - math.cos(a) * w - math.sin(a) * h, y - math.sin(a) * w + math.cos(a) * h),
               (x - math.cos(a) * w + math.sin(a) * h, y - math.sin(a) * w - math.cos(a) * h),
               (x + math.cos(a) * w + math.sin(a) * h, y + math.sin(a) * w - math.cos(a) * h)]
        d.polygon(pts, fill=p["c"] + (int(255 * alpha),))


def burst(fr, lt, start, x, y, color=(255, 220, 80), n=36, power=900, seed=0, size=14):
    """爆発・花火の火花"""
    if lt < start or lt > start + 1.2:
        return
    k = lt - start
    r = random.Random(seed)
    d = ImageDraw.Draw(fr)
    for i in range(n):
        a = 2 * math.pi * i / n + r.uniform(-0.1, 0.1)
        v = power * r.uniform(0.5, 1.0)
        dist = v * (1 - math.exp(-k * 4)) / 4
        px, py = x + math.cos(a) * dist, y + math.sin(a) * dist + 120 * k * k
        s = size * (1 - k / 1.2)
        if s <= 0:
            continue
        c = color if i % 3 else (255, 255, 255)
        d.ellipse([px - s, py - s, px + s, py + s], fill=c + (int(255 * (1 - k / 1.2)),))


def shockwave(fr, lt, start, x, y, color=(255, 255, 255)):
    if lt < start or lt > start + 0.45:
        return
    k = (lt - start) / 0.45
    r = 80 + 900 * ease_out_cubic(k)
    d = ImageDraw.Draw(fr)
    d.ellipse([x - r, y - r, x + r, y + r], outline=color + (int(255 * (1 - k)),), width=int(40 * (1 - k)) + 2)


def glow_disc(size, color):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([size * 0.2, size * 0.2, size * 0.8, size * 0.8], fill=color)
    return im.filter(ImageFilter.GaussianBlur(size * 0.12))


GLOW = glow_disc(900, (255, 220, 100, 200))


def spotlight(fr, alpha):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    a = int(110 * alpha)
    d.polygon([(W / 2 - 60, 0), (W / 2 + 60, 0), (W / 2 + 420, 1420), (W / 2 - 420, 1420)], fill=(255, 255, 220, a))
    d.ellipse([W / 2 - 420, 1340, W / 2 + 420, 1500], fill=(255, 255, 220, a))
    fr.alpha_composite(im.filter(ImageFilter.GaussianBlur(20)))


# ─── 共通 ──────────────────────────────────────────────────────────────────

def impact(sc, spec, strength=1.0, sound="boom", gain=0.9):
    """シーン内の衝撃を登録（画面揺れ・フラッシュ・効果音）"""
    sc.sfx.append((sound, spec, gain))
    sc._impacts.append((spec, strength))


def scene(name, lines, draw, scheme, **kw):
    sc = Scene(name, lines, draw, **kw)
    sc.scheme = scheme
    sc._impacts = []
    return sc


def bg_frame(t, sc, lt):
    frames = ray_frames(sc.scheme)
    fr = frames[int(t * 12) % RAY_FRAMES].copy()
    return fr


def telop(fr, sc, lt):
    ln = E.current_line(sc, lt)
    if not ln:
        return
    text = ln.sub if ln.sub is not None else ln.text
    if not text:
        return
    grad = PINKG if ln.voice.startswith("mama") else WHITEG
    im = hade_text(text, 70, grad, GOTHIC, (0, 0, 0), 9, (255, 220, 0) if ln.voice.startswith("papa") else (255, 255, 255), 5)
    k = clamp((lt - ln.start + 0.05) / 0.1)
    paste(fr, im, W / 2, 1540, 1.25 - 0.25 * k, 0, k)


def overlay(fr, t, sc, lt):
    telop(fr, sc, lt)
    # 衝撃：揺れ・ズームパンチ・フラッシュ
    shake_x = shake_y = 0.0
    zoom = 1.0
    flash = 0.0
    for ti, s in IMPACTS:
        dt = t - ti
        if 0 <= dt < 0.5:
            amp = 38 * s * math.exp(-dt * 9)
            shake_x += amp * math.sin(dt * 95 + ti)
            shake_y += amp * math.cos(dt * 83 + ti * 2)
            zoom = max(zoom, 1 + 0.07 * s * math.exp(-dt * 10))
            flash = max(flash, 0.75 * s * math.exp(-dt * 14))
        if 0 <= dt < 0.35:
            sl = speed_lines()[int(t * FPS_HALF) % 4]
            fr.alpha_composite(sl if dt < 0.2 else _fade(sl, 1 - (dt - 0.2) / 0.15))
    if zoom > 1.001 or abs(shake_x) > 0.5:
        zw, zh = int(W / zoom), int(H / zoom)
        x0 = int((W - zw) / 2 - shake_x)
        y0 = int((H - zh) / 2 - shake_y)
        x0 = max(-40, min(W - zw + 40, x0))
        y0 = max(-40, min(H - zh + 40, y0))
        base = Image.new("RGBA", (W + 80, H + 80), (0, 0, 0, 255))
        base.paste(fr, (40, 40))
        fr = base.crop((x0 + 40, y0 + 40, x0 + 40 + zw, y0 + 40 + zh)).resize((W, H), Image.BILINEAR)
    if flash > 0.02:
        fr.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(255 * flash))))
    # 上部ロゴ帯
    tag = hade_text("パパママ社 presents", 44, GOLD, GOTHIC, (0, 0, 0), 5, (0, 0, 0), 3)
    paste(fr, tag, W / 2, 150)
    return fr


FPS_HALF = 15


def _fade(im, a):
    im = im.copy()
    im.putalpha(im.getchannel("A").point(lambda v: int(v * clamp(a))))
    return im


def hero(fr, lt, start, expr="happy", y=1020, size=600, crown=True, rise=0.45):
    """奥さん登場（下からせり上がり＋後光）"""
    if lt < start:
        return
    k = ease_out_cubic((lt - start) / rise)
    yy = y + (1 - k) * 900 + math.sin(lt * 3) * 8
    paste(fr, GLOW, W / 2, yy - 60, 1.0 + 0.05 * math.sin(lt * 5), 0, k)
    paste(fr, mama(expr, size), W / 2, yy, 1.0, math.sin(lt * 2) * 2)
    if crown:
        paste(fr, emoji_img("👑", 210), W / 2 + 10, yy - 400 + math.sin(lt * 4) * 10, 1.0, -8 + math.sin(lt * 3) * 4)


# ─── シーン描画 ────────────────────────────────────────────────────────────

def d_open(fr, lt, sc):
    a, b, c, d1, e = sc.lines
    words = [("どん！", a, RED, -8, 560), ("どん！", b, RED, 8, 860), ("どーーん!!", c, GOLD, -4, 1180)]
    for w, ln, g, rot, y in words:
        if lt < d1.start - 0.1:
            slam(fr, lt, ln.start - 0.05, hade_text(w, 230 if "ー" not in w else 200, g, GOTHIC), W / 2, y, rot)
            shockwave(fr, lt, ln.start + 0.05, W / 2, y)
            burst(fr, lt, ln.start + 0.05, W / 2, y, (255, 200, 60), 40, 1200, hash(w) % 99 + y)
    if lt >= d1.start - 0.1:
        slam(fr, lt, d1.start - 0.1, hade_text("LADIES &\nGENTLEMEN", 120, WHITEG, SERIF, (0, 0, 0)), W / 2, 480, -3)
    if lt >= e.start - 0.05:
        slam(fr, lt, e.start - 0.05, hade_text("奥さん", 270, GOLD, SERIF), W / 2, 820, -4)
        slam(fr, lt, e.start + 0.5, hade_text("大紹介!!", 230, RED, SERIF), W / 2, 1110, 4)
        burst(fr, lt, e.start + 0.55, 250, 700, (255, 80, 80), 30, 900, 5)
        burst(fr, lt, e.start + 0.7, 830, 1250, (255, 220, 80), 30, 900, 6)
    confetti(fr, sc.start + lt, sc.start + e.start + 0.5)


def d_entry(fr, lt, sc):
    a, b, c, d1 = sc.lines
    if lt < c.start + 0.2:
        slam(fr, lt, a.start, hade_text("赤コーナー", 200, RED, SERIF), W / 2, 520, -5)
        if lt > b.start:
            slam(fr, lt, b.start, hade_text("パパママ社\n真の社長", 150, GOLD, SERIF), W / 2, 900, 3)
    else:
        spotlight(fr, clamp((lt - c.start) / 0.3))
        slam(fr, lt, c.start + 0.2, hade_text("うちの\n奥さん!!", 180, GOLD, SERIF), W / 2, 400, -4, 4.0, 0.16)
        hero(fr, lt, c.start + 0.35, "proud" if lt < d1.start else "happy", 1110)
        for i in range(3):
            burst(fr, lt, c.start + 0.4 + i * 0.35, [200, 880, 540][i], [760, 700, 380][i],
                  [(255, 80, 80), (80, 220, 255), (255, 220, 80)][i], 40, 1000, 30 + i)
        confetti(fr, sc.start + lt, sc.start + c.start + 0.3)


SKILLS = [("ウソ見抜き", "3秒", RED), ("お小遣い交渉", "128連勝", GOLD), ("プリン防衛率", "100%", CYAN)]
PROFILE = [("身長", "ヒミツ", PINKG), ("体重", "聞いたら終わり", RED), ("好物", "プリン", GOLD)]


def rows(fr, lt, sc, header, hgrad, items, expr_before, expr_after):
    head = sc.lines[0]
    slam(fr, lt, head.start - 0.05, hade_text(header, 210, hgrad, SERIF), W / 2, 380, -4)
    expr = expr_before if lt < sc.lines[3].start else expr_after
    paste(fr, mama(expr, 340), 190, 1350 + math.sin(lt * 3) * 6, 1.0, 4)
    for i, (name, val, g) in enumerate(items):
        ln = sc.lines[1 + i]
        y = 610 + i * 215
        if lt < ln.start - 0.05:
            continue
        bar = Image.new("RGBA", (980, 200), (0, 0, 0, 0))
        ImageDraw.Draw(bar).polygon([(40, 0), (980, 0), (940, 200), (0, 200)], fill=(0, 0, 0, 190))
        k = ease_out_cubic((lt - ln.start + 0.05) / 0.15)
        paste(fr, bar, W / 2 + (1 - k) * 1100, y)
        nm = hade_text(name, 56, WHITEG, GOTHIC, (0, 0, 0), 5, (0, 0, 0), 2)
        paste(fr, nm, 90 + nm.width / 2 + (1 - k) * 1100, y - 58)
        vsz = 110 if len(val) <= 5 else 92
        slam(fr, lt, ln.start + 0.5, hade_text(val, vsz, g, GOTHIC), 600, y + 38, -3, 2.6)


def d_skills(fr, lt, sc):
    rows(fr, lt, sc, "必殺技", RED, SKILLS, "jito", "proud")


def d_profile(fr, lt, sc):
    rows(fr, lt, sc, "PROFILE", PINKG, PROFILE, "happy", "shy")


def d_vs(fr, lt, sc):
    a, b, c = sc.lines
    slam(fr, lt, a.start - 0.05, hade_text("本日の\n対戦相手", 150, WHITEG, SERIF, (0, 0, 120)), W / 2, 420, -3)
    if lt > b.start - 0.05:
        paste(fr, mama("proud", 420), 800, 1060 + math.sin(lt * 3) * 6, 1.0, -4)
        shake = math.sin(lt * 50) * 6 if lt > c.start else 0
        paste(fr, papa("sweat" if lt > c.start - 0.3 else "normal", 330), 270 + shake, 1060, pop_in_(lt, b.start))
        slam(fr, lt, b.start, hade_text("VS", 260, RED, SERIF), W / 2, 820, -8, 3.0)
        slam(fr, lt, b.start + 0.25, hade_text("社長(ぼく)", 70, CYAN, GOTHIC), 270, 1290, 0, 2.0, hold=c.start + 0.4 - b.start - 0.25)
    if lt > c.start + 0.4:
        slam(fr, lt, c.start + 0.4, hade_text("勝率 0%", 130, RED, GOTHIC), 330, 1380, -8, 2.6)


def pop_in_(lt, start):
    return E.pop_in(lt, start, 0.3)


def d_power(fr, lt, sc):
    a, b, c, d1 = sc.lines
    slam(fr, lt, a.start - 0.05, hade_text("戦闘力", 210, CYAN, SERIF), W / 2, 400, -3)
    # スカウター風のカウンター
    c0, c1 = a.end + 0.1, b.start - 0.05
    if lt > c0 and lt < c1:
        k = (lt - c0) / (c1 - c0)
        val = int(10 ** (2 + 7 * E.ease_in_cubic(k)))
        num = hade_text(f"{val:,}", 120, CYAN, GOTHIC, (0, 0, 0), 8, (255, 255, 255), 3)
        paste(fr, num, W / 2 + math.sin(lt * 70) * 8, 640)
    if lt >= b.start - 0.05:
        slam(fr, lt, b.start - 0.05, hade_text("測定不能!!", 190, RED, SERIF), W / 2, 650, -6, 3.5)
        burst(fr, lt, b.start, W / 2, 650, (255, 120, 40), 50, 1400, 77, 18)
    expr = "angry" if c.start - 0.2 < lt < d1.start + 0.4 else ("jito" if lt > d1.start else "proud")
    paste(fr, mama(expr, 560), W / 2, 1120 + math.sin(lt * 3) * 6, 1.0, math.sin(lt * 2) * 2)
    if c.start - 0.2 < lt:
        paste(fr, emoji_img("💢", 150), W / 2 + 240, 870, 1 + 0.1 * math.sin(lt * 25))
    if lt > d1.start - 0.1:
        paste(fr, papa("sweat", 240), 190 + math.sin(lt * 50) * 6, 1280)
        slam(fr, lt, d1.start, hade_text("土下座", 110, WHITEG, SERIF, (0, 0, 120)), 230, 1080, 10, 2.0)


def d_climax(fr, lt, sc):
    a, b, c = sc.lines
    if lt < b.start - 0.05:
        slam(fr, lt, a.start, hade_text("でも…\n家族の笑顔は", 140, WHITEG, SERIF, (120, 60, 0)), W / 2, 560, -2, 2.0)
        hero(fr, lt, a.start + 0.3, "happy", 1140, 520, False, 0.6)
    else:
        slam(fr, lt, b.start - 0.05, hade_text("No.1", 380, GOLD, SERIF), W / 2, 560, -6, 4.5, 0.16)
        hero(fr, lt, b.start + 0.1, "happy", 1120, 560, True, 0.01)
        for i in range(6):
            burst(fr, lt, b.start + 0.1 + i * 0.28, [180, 900, 300, 780, 540, 150][i], [300, 360, 900, 980, 250, 620][i],
                  [(255, 80, 80), (80, 220, 255), (255, 220, 80), (180, 120, 255), (255, 255, 255), (120, 255, 160)][i],
                  44, 1000, 100 + i, 12)
        confetti(fr, sc.start + lt, sc.start + b.start)


def d_end(fr, lt, sc):
    a, b, c = sc.lines
    for w, ln, g, y, rot in [("どん！", a, RED, 420, -8), ("どん！", b, GOLD, 630, 8), ("どーーん!!", c, RED, 860, -4)]:
        slam(fr, lt, ln.start - 0.05, hade_text(w, 200, g, GOTHIC), W / 2, y, rot)
        shockwave(fr, lt, ln.start + 0.05, W / 2, y)
    end = c.end + 0.25
    if lt > end:
        slam(fr, lt, end, hade_text("チャンネル登録\nよろしく!!", 120, GOLD, SERIF), W / 2, 1180, -3, 2.5)
        paste(fr, mama("happy", 300), 880, 1450 + math.sin(lt * 4) * 10, 1.0, -6)
        paste(fr, papa("happy", 220), 190, 1460 + math.sin(lt * 4 + 1) * 10, 1.0, 6)
    confetti(fr, sc.start + lt, sc.start + c.start)


def build_scenes():
    P, M = "papa", "mama"
    s1 = scene("open", [
        Line(P, "どん！", "どん！", gap=0.28, pitch=1),
        Line(P, "どん！", "どん！", gap=0.28, pitch=2),
        Line(P, "どーーん！", "どーーん!!", gap=0.45, pitch=3),
        Line(P, "レディース、アンド、ジェントルメン！", "レディース＆ジェントルメン!!"),
        Line(P, "うちの奥さんの、大紹介だぁ！", "うちの奥さんの大紹介だ!!"),
    ], d_open, "red", pre=0.3, post=0.7)
    s2 = scene("entry", [
        Line(P, "赤コーナー！", "赤コーナー!!", gap=0.3),
        Line(P, "パパママ社、真の社長！", "パパママ社、真の社長!!", gap=0.3),
        Line(P, "うちの、おくさーーん！", "うちのおくさーーん!!", gap=0.6),
        Line("mama_happy", "どうもー！", "どうもー！", pitch=1),
    ], d_entry, "gold", post=0.9)
    sp = scene("profile", [
        Line(P, "プロフィール！", "プロフィール!!", gap=0.35),
        Line(P, "身長、ひみつ！", "身長 ヒミツ!!", gap=0.45),
        Line(P, "体重、聞いたら、終わり！", "体重 聞いたら終わり!!", gap=0.45),
        Line(P, "好物、プリン！", "好物 プリン!!", gap=0.3),
    ], d_profile, "night", post=0.6)
    sv = scene("vs", [
        Line(P, "本日の、対戦相手は！", "本日の対戦相手は!!", gap=0.4),
        Line(P, "社長、僕！", "社長、ぼく!!", gap=0.4),
        Line(P, "勝率、ゼロパーセント！", "勝率 0%!!"),
    ], d_vs, "blue", post=1.0)
    s3 = scene("skills", [
        Line(P, "必殺技！", "必殺技!!", gap=0.35),
        Line(P, "ウソ見抜き、3秒！", "ウソ見抜き 3秒!!", gap=0.45),
        Line(P, "お小遣い交渉、128連勝！", "お小遣い交渉 128連勝!!", gap=0.45),
        Line(P, "プリン防衛率、100パーセント！", "プリン防衛率 100%!!", gap=0.3),
    ], d_skills, "red", post=0.8)
    s4 = scene("power", [
        Line(P, "そして、戦闘力は。", "そして戦闘力は…", gap=1.6),
        Line(P, "測定不能！", "測定不能!!", gap=0.5),
        Line("mama_angry", "なんか言った？", "なんか言った？", gap=0.3),
        Line(P, "何でもありません！", "何でもありません!!"),
    ], d_power, "blue", post=0.7)
    s5 = scene("climax", [
        Line(P, "でも、家族の笑顔は。", "でも、家族の笑顔は…", gap=0.5),
        Line(P, "ナンバーワン！", "ナンバーワン!!", gap=0.6),
        Line("mama_happy", "みんな、ありがとー！", "みんな、ありがとー！", pitch=1),
    ], d_climax, "gold", post=0.9)
    s6 = scene("end", [
        Line(P, "どん！", "", gap=0.28, pitch=1),
        Line(P, "どん！", "", gap=0.28, pitch=2),
        Line(P, "どーーん！", "", gap=0.3, pitch=3),
    ], d_end, "red", post=3.0)

    # 衝撃ポイント（揺れ＋ドーン）
    impact(s1, ("line", 0, 0.0), 0.8, "kick", 1.0)
    impact(s1, ("line", 1, 0.0), 0.9, "kick", 1.0)
    impact(s1, ("line", 2, 0.0), 1.3, "boom")
    impact(s1, ("line", 3, -0.1), 0.6, "boom", 0.6)
    impact(s1, ("line", 4, -0.05), 1.0, "boom")
    impact(s1, ("line", 4, 0.5), 0.8, "kick", 1.0)
    s1.sfx.append(("gong", ("line", 4, -0.05), 0.5))
    impact(s2, ("line", 0, 0.0), 1.0, "boom")
    impact(s2, ("line", 1, 0.0), 0.8, "boom", 0.7)
    impact(s2, ("line", 2, 0.2), 1.3, "boom")
    s2.sfx += [("gong", ("line", 2, 0.2), 0.6), ("cheer", ("line", 2, 0.3), 0.9)]
    impact(sp, ("line", 0, -0.05), 1.0, "boom")
    for i in (1, 2, 3):
        sp.sfx.append(("whoosh", ("line", i, -0.1), 0.6))
        impact(sp, ("line", i, 0.5), 0.8, "boom", 0.75)
    impact(sv, ("line", 0, -0.05), 0.8, "boom", 0.8)
    impact(sv, ("line", 1, 0.0), 1.3, "boom")
    sv.sfx.append(("gong", ("line", 1, 0.0), 0.5))
    impact(sv, ("line", 2, 0.4), 0.9, "buzzer", 0.8)
    impact(s3, ("line", 0, -0.05), 1.0, "boom")
    for i in (1, 2, 3):
        s3.sfx.append(("whoosh", ("line", i, -0.1), 0.6))
        impact(s3, ("line", i, 0.5), 0.8, "boom", 0.75)
    impact(s4, ("line", 0, -0.05), 0.8, "boom", 0.7)
    s4.sfx.append((E.sfx_whoosh(1.4, True), ("end", 0, 0.1), 0.7))
    impact(s4, ("line", 1, -0.05), 1.5, "boom", 1.0)
    impact(s4, ("line", 3, 0.0), 0.7, "kick", 1.0)
    impact(s5, ("line", 0, 0.0), 0.4, "kick", 0.6)
    impact(s5, ("line", 1, -0.05), 1.5, "boom", 1.0)
    s5.sfx += [("gong", ("line", 1, -0.05), 0.6), ("cheer", ("line", 1, 0.1), 1.0), ("kira", ("line", 2, 0.0), 0.5)]
    impact(s6, ("line", 0, 0.0), 0.8, "kick", 1.0)
    impact(s6, ("line", 1, 0.0), 0.9, "kick", 1.0)
    impact(s6, ("line", 2, 0.0), 1.4, "boom")
    s6.sfx += [("cheer", ("line", 2, 0.1), 0.9), ("gong", ("end", 2, 0.25), 0.5)]
    return [s1, s2, sp, s3, sv, s4, s5, s6]


# ─── 音響 ──────────────────────────────────────────────────────────────────

def arena_echo(sig, delays=(0.11, 0.23, 0.37), gains=(0.35, 0.22, 0.12)):
    """会場アナウンス風エコー"""
    n = len(sig) + int(max(delays) * E.SR)
    out = np.zeros(n, dtype=np.float32)
    out[: len(sig)] += sig
    for d, g in zip(delays, gains):
        i = int(d * E.SR)
        out[i: i + len(sig)] += E.lp(sig, 4) * g
    return out


def saw(freq, dur):
    t = E._t(dur)
    s = np.zeros_like(t)
    for k in range(1, 12):
        s += np.sin(2 * np.pi * freq * k * t) / k * (1 if k % 2 else 0.8)
    return s.astype(np.float32)


def make_bgm(bpm=140):
    """EDM風：4つ打ちキック＋サイドチェインのうねるベース＋スーパーソウ"""
    beat = 60 / bpm
    bars = 8
    n = int(bars * 4 * beat * E.SR)
    out = np.zeros(n, dtype=np.float32)
    prog = [(45, [57, 60, 64]), (41, [53, 57, 60]), (43, [55, 59, 62]), (40, [52, 55, 59])]  # Am F G Em
    t = np.arange(n) / E.SR
    pump = 0.25 + 0.75 * np.clip(((t % beat) / beat) * 2.2, 0, 1) ** 0.7
    for bar in range(bars):
        root, ch = prog[bar % 4]
        t0 = bar * 4 * beat
        seg = np.zeros(int(4 * beat * E.SR) + 1, dtype=np.float32)
        for m in ch:
            for det in (-0.08, 0.0, 0.08):
                seg[: int(4 * beat * E.SR)] += saw(E.midi_hz(m + 12 + det), 4 * beat) * 0.05
        for q in range(8):
            b = saw(E.midi_hz(root - 12 + (12 if q % 2 else 0)), beat / 2) * np.exp(-E._t(beat / 2) * 4)
            E.place(seg, b * 0.25, q * beat / 2)
        E.place(out, E.lp(seg, 6), t0)
    out *= pump
    for b in range(bars * 4):
        E.place(out, E.kick(0.4, 1.2), b * beat, 0.9)
        E.place(out, E.hat(0.05, b), (b + 0.5) * beat, 0.35)
        if b % 2 == 1:
            E.place(out, E.clap(), b * beat, 0.55)
    return out / (np.max(np.abs(out)) or 1)


def main(out_path):
    SCENES[:] = build_scenes()
    total = E.build_timeline(SCENES, VOICE_DEFAULTS)
    for sc in SCENES:
        for ln in sc.lines:
            if ln.voice == "papa":
                ln.sig = arena_echo(ln.sig)
        if sc is not SCENES[0]:
            sc.sfx.append(("whoosh", 0.0, 0.5))
    IMPACTS[:] = [(sc.start + sc.t_of(spec), s) for sc in SCENES for spec, s in sc._impacts]
    print(f"total {total:.2f}s")
    for sc in SCENES:
        print(f"  {sc.name:8s} start {sc.start:6.2f} dur {sc.dur:5.2f}")
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "mix.wav"
        E.mix_audio(SCENES, total, make_bgm(), bgm_gain=0.32, voice_gain=1.0, out_path=wav)
        E.render(SCENES, total, wav, out_path, bg_frame=bg_frame, overlay=overlay)
    print("done", out_path)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "wife_intro_hade.mp4")
