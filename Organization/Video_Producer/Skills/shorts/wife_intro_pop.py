#!/usr/bin/env python3
"""
ショート動画①「うちの奥さん紹介します」— ポップ＆ユーモア版（約60秒・9:16）

使い方:
    python3 wife_intro_pop.py <出力MP4パス>
"""

import math
import random
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import short_engine as E
from short_engine import Line, Scene, W, H, paste, pop_in, text_img, emoji_img, ease_out_cubic, clamp
from characters import mama, papa

FONT = E.FONT_POP
PINK = (255, 92, 141)
BLUE = (60, 130, 230)
YELLOW = (255, 214, 64)
INK = (60, 35, 45)
WHITE = (255, 255, 255)

# シーンごとの背景（上色, 下色, 水玉色）
PALETTES = [
    ((255, 236, 158), (255, 196, 214), (255, 255, 255, 90)),
    ((255, 245, 200), (255, 214, 120), (255, 255, 255, 90)),
    ((206, 236, 255), (190, 214, 255), (255, 255, 255, 100)),
    ((214, 255, 222), (170, 232, 200), (255, 255, 255, 100)),
    ((255, 226, 246), (226, 200, 255), (255, 255, 255, 90)),
    ((255, 238, 214), (255, 200, 170), (255, 255, 255, 90)),
    ((255, 230, 236), (255, 190, 210), (255, 255, 255, 110)),
    ((255, 236, 158), (255, 196, 214), (255, 255, 255, 90)),
]

AV_Y = 1040        # 奥さんの中心Y
SUB_Y = 1500       # 字幕の中心Y


# ─── 共通パーツ ────────────────────────────────────────────────────────────

def T(text, size, fill=WHITE, stroke=PINK, sw=14, outer=(WHITE, 10), shadow=True):
    return text_img(text, size, fill, stroke, sw, FONT,
                    (8, 10, (0, 0, 0, 60)) if shadow else None, 0.1, outer)


def bounce(lt, freq=2.2, amp=10):
    return math.sin(lt * freq * math.pi) * amp


def draw_mama(fr, lt, expr, start=0.0, crown=False, x=W / 2, y=AV_Y, size=560):
    s = pop_in(lt, start, 0.4)
    if s <= 0:
        return
    im = mama(expr, size)
    yy = y + bounce(lt, 1.6, 8)
    rot = math.sin(lt * 2.4) * 2.5
    paste(fr, im, x, yy, s, rot)
    if crown:
        return yy


def stamp(fr, lt, start, text, size=120, color=(230, 40, 60), y=700, rot=-8, x=W / 2):
    """ハンコ風にドンッと押す"""
    if lt < start:
        return
    k = clamp((lt - start) / 0.18)
    sc = 2.2 - 1.2 * E.ease_out_cubic(k)
    im = text_img(text, size, WHITE, color, 12, FONT, (10, 12, (0, 0, 0, 90)), 0.1, (WHITE, 8))
    paste(fr, im, x, y, sc, rot, alpha=clamp(k * 2))


def chip(fr, lt, start, text, color=PINK, y=250):
    s = pop_in(lt, start, 0.3)
    if s <= 0:
        return
    t = text_img(text, 54, WHITE, color, 0, FONT)
    box = E.rounded_box((t.width + 40, 100), 50, color + (255,))
    box.alpha_composite(t, ((box.width - t.width) // 2, (box.height - t.height) // 2 + 2))
    paste(fr, box, W / 2, y, s)


def subtitle(fr, sc, lt):
    ln = E.current_line(sc, lt)
    if not ln:
        return
    text = ln.sub if ln.sub is not None else ln.text
    if not text:
        return
    is_mama = ln.voice.startswith("mama")
    col = PINK if is_mama else BLUE
    t = text_img(text, 60, INK, (0, 0, 0), 0, FONT, None, 0.18)
    bw, bh = max(t.width + 60, 600), t.height + 40
    box = E.rounded_box((bw, bh), 40, (255, 255, 255, 240), col + (255,), 8)
    box.alpha_composite(t, ((bw - t.width) // 2, (bh - t.height) // 2))
    k = clamp((lt - ln.start + 0.05) / 0.15)
    paste(fr, box, W / 2, SUB_Y + (1 - k) * 30, 1.0, alpha=k)
    # 話者タグ
    tag = text_img("奥さん" if is_mama else "社長", 40, WHITE, col, 0, FONT)
    tb = E.rounded_box((tag.width + 30, 64), 32, col + (255,))
    tb.alpha_composite(tag, ((tb.width - tag.width) // 2, (tb.height - tag.height) // 2))
    paste(fr, tb, W / 2 - bw / 2 + tb.width / 2 + 20, SUB_Y - bh / 2 - 10 + (1 - k) * 30, 1.0, alpha=k)


def papa_icon(fr, lt, start, expr="normal", x=200, y=1250, size=240, label=None, end=None):
    if end is not None and lt > end:
        return
    s = pop_in(lt, start, 0.3)
    if s <= 0:
        return
    shake = math.sin(lt * 40) * 4 if expr == "sweat" else 0
    paste(fr, papa(expr, size), x + shake, y + bounce(lt, 2, 5), s)
    if label:
        paste(fr, T(label, 44, WHITE, BLUE, 8, (WHITE, 6), False), x, y + size / 2 + 20, s)


# ─── 浮遊パーティクル（ハート・星・水玉） ───────────────────────────────────

rng = random.Random(7)
PARTICLES = [dict(x=rng.uniform(0, W), y=rng.uniform(0, H), sp=rng.uniform(40, 120), ph=rng.uniform(0, 6.28),
                  ch=rng.choice(["💖", "⭐", "✨", "💛", "🎀"]), sz=rng.randint(40, 80)) for _ in range(16)]


def particles(fr, t, alpha=0.75):
    for p in PARTICLES:
        y = (p["y"] - t * p["sp"]) % (H + 200) - 100
        x = p["x"] + math.sin(t * 1.3 + p["ph"]) * 30
        paste(fr, emoji_img(p["ch"], p["sz"]), x, y, 1.0, math.sin(t + p["ph"]) * 15, alpha)


# ─── 背景 ──────────────────────────────────────────────────────────────────

def make_bg(top, bottom, dot):
    pad = 160
    g = np.linspace(0, 1, H + pad)[:, None, None]
    arr = (np.array(top)[None, None, :] * (1 - g) + np.array(bottom)[None, None, :] * g)
    arr = np.repeat(arr, W + pad, axis=1).astype(np.uint8)
    im = Image.fromarray(arr).convert("RGBA")
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    step = 80
    for yy in range(0, H + pad, step):
        for xx in range(0, W + pad, step):
            ox = step // 2 if (yy // step) % 2 else 0
            d.ellipse([xx + ox - 9, yy - 9, xx + ox + 9, yy + 9], fill=dot)
    im.alpha_composite(ov)
    return im


BGS = [make_bg(*p) for p in PALETTES]
SCENES = []


def bg_frame(t, sc, lt):
    i = SCENES.index(sc)
    off = int(t * 50) % 160
    cur = BGS[i % len(BGS)].crop((off, off, off + W, off + H))
    if i > 0 and lt < 0.35:
        prev = BGS[(i - 1) % len(BGS)].crop((off, off, off + W, off + H))
        r = ease_out_cubic(lt / 0.35) * 1200
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).ellipse([W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r], fill=255)
        prev.paste(cur, (0, 0), mask)
        cur = prev
    fr = cur.copy()
    particles(fr, t)
    # 上部タグ
    tag = text_img("パパママ社 社員紹介", 40, WHITE, INK, 0, FONT)
    box = E.rounded_box((tag.width + 50, 76), 38, (60, 35, 45, 200))
    box.alpha_composite(tag, ((box.width - tag.width) // 2, (box.height - tag.height) // 2))
    fr.alpha_composite(box, (int(W / 2 - box.width / 2), 120))
    return fr


def overlay(fr, t, sc, lt):
    subtitle(fr, sc, lt)
    # 進行バー
    total = SCENES[-1].start + SCENES[-1].dur
    d = ImageDraw.Draw(fr)
    d.rounded_rectangle([140, 1650, W - 140, 1666], 8, fill=(255, 255, 255, 160))
    d.rounded_rectangle([140, 1650, 140 + (W - 280) * t / total, 1666], 8, fill=PINK + (255,))
    paste(fr, emoji_img("💖", 56), 140 + (W - 280) * t / total, 1658)
    return fr


# ─── シーン ────────────────────────────────────────────────────────────────

def s1(fr, lt, sc):
    a, b = sc.L(0), sc.L(1)
    paste(fr, T("うちの奥さん", 150), W / 2, 420 + bounce(lt, 1.5, 6), pop_in(lt, 0.05, 0.35), -3)
    paste(fr, T("紹介します！", 130, YELLOW, PINK), W / 2, 590, pop_in(lt, b.start, 0.35), 3)
    draw_mama(fr, lt, "happy", b.start + 0.4)
    if lt > b.start + 0.4:
        for i, ch in enumerate(["✨", "💕", "✨"]):
            k = pop_in(lt, b.start + 0.5 + i * 0.12)
            paste(fr, emoji_img(ch, 110), [190, 880, 260][i], [820, 800, 1240][i], k)


def s2(fr, lt, sc):
    a, b, c = sc.L(0), sc.L(1), sc.L(2)
    reveal = c.start - 0.15
    chip(fr, lt, 0.1, "その１ 肩書き")
    if lt < reveal:
        paste(fr, T("表向きの社長は…", 104, WHITE, BLUE), W / 2, 450, pop_in(lt, a.start + 0.2))
        papa_icon(fr, lt, a.start + 0.6, "happy", W / 2, 920, 380, "社長（ぼく）")
        if lt > b.start:
            paste(fr, T("本当の社長は…？", 96, YELLOW, PINK), W / 2, 600, pop_in(lt, b.start))
            # ドラムロール中は「？」が揺れる
            if lt > b.end:
                paste(fr, emoji_img("❓", 140), 860 + math.sin(lt * 30) * 10, 820)
    else:
        paste(fr, T("真の社長", 190, YELLOW, (230, 120, 0), 16), W / 2, 470, pop_in(lt, reveal, 0.35), -4)
        draw_mama(fr, lt, "proud", reveal)
        k = pop_in(lt, reveal + 0.2, 0.4)
        paste(fr, emoji_img("👑", 200), W / 2 + 10, AV_Y - 380 + bounce(lt, 1.6, 8), k, -8)
        papa_icon(fr, lt, reveal + 0.3, "sweat", 170, 1170, 200, "(仮)")
        for i, (x, y) in enumerate([(160, 760), (920, 820), (900, 1180)]):
            paste(fr, emoji_img("✨", 90), x, y, pop_in(lt, reveal + 0.3 + i * 0.1))


def s3(fr, lt, sc):
    a, b, c = sc.L(0), sc.L(1), sc.L(2)
    chip(fr, lt, 0.1, "その２ 特技")
    paste(fr, T("ウソ発見器", 150, WHITE, (120, 80, 220)), W / 2, 450, pop_in(lt, a.start + 0.1), -2)
    paste(fr, T("（精度100%）", 64, (120, 80, 220), WHITE, 6, None, False), W / 2 + 250, 580, pop_in(lt, a.start + 1.2), 6)
    expr = "jito" if lt > b.start - 0.6 else "normal"
    draw_mama(fr, lt, expr, 0.3)
    paste(fr, emoji_img("🔍", 150), 860, 820 + bounce(lt, 2, 10), pop_in(lt, a.start + 0.4), 15)
    # カウントダウン 3・2・1
    cd0 = a.end + 0.15
    for i, n in enumerate(["3", "2", "1"]):
        st = cd0 + i * 0.45
        if st <= lt < st + 0.45:
            k = (lt - st) / 0.45
            paste(fr, T(n, 300, WHITE, (230, 60, 80), 18), 860, 1150, 1.4 - 0.4 * ease_out_cubic(k), 0, 1 - k * 0.5)
    papa_icon(fr, lt, c.start, "sweat", 200, 1240, 230)
    stamp(fr, lt, b.start + 0.2, "バレた!!", 110, (230, 60, 80), 1080, -10, 260)


def s4(fr, lt, sc):
    a, b, c = sc.L(0), sc.L(1), sc.L(2)
    chip(fr, lt, 0.1, "その３ 役職")
    score_t = b.end + 0.2
    if lt < score_t:
        paste(fr, T("CFO", 230, WHITE, (20, 160, 90), 18), W / 2, 450, pop_in(lt, a.start), -3)
        sub = "最高 お財布 責任者"
        paste(fr, T(sub, 84, (20, 140, 80), WHITE, 8, (WHITE, 2), False), W / 2, 630, pop_in(lt, a.start + 1.3))
        draw_mama(fr, lt, "proud", 0.3)
        for i, (x, y) in enumerate([(170, 860), (910, 900), (880, 1220)]):
            paste(fr, emoji_img("💰", 120), x, y + bounce(lt + i, 2, 12), pop_in(lt, a.start + 1.5 + i * 0.12))
        if lt > b.start:
            paste(fr, T("お小遣い交渉の戦績は…", 70, WHITE, BLUE, 10), W / 2, 760, pop_in(lt, b.start))
    else:
        paste(fr, T("お小遣い交渉", 96, WHITE, BLUE), W / 2, 420, 1.0)
        board = E.rounded_box((820, 260), 40, (40, 40, 60, 245), (255, 214, 64, 255), 10)
        paste(fr, board, W / 2, 620, pop_in(lt, score_t, 0.3))
        paste(fr, text_img("0勝 128敗", 150, (255, 80, 80), (0, 0, 0), 0, E.FONT_GOTHIC_BLACK), W / 2, 615,
              pop_in(lt, score_t + 0.1, 0.3))
        draw_mama(fr, lt, "angry", score_t)
        k = pop_in(lt, c.start, 0.25)
        paste(fr, emoji_img("💢", 140), W / 2 + 230, AV_Y - 220, k * (1 + 0.08 * math.sin(lt * 20)))
        stamp(fr, lt, c.start + 0.1, "却下", 150, (230, 40, 60), 1230, 12, 820)
        papa_icon(fr, lt, score_t + 0.3, "sweat", 190, 1250, 210)


def s5(fr, lt, sc):
    a, b, c = sc.L(0), sc.L(1), sc.L(2)
    chip(fr, lt, 0.1, "その４ 口ぐせ")
    paste(fr, T("「あと5分で\n準備できる」", 112, WHITE, (240, 120, 40)), W / 2, 480, pop_in(lt, a.start))
    draw_mama(fr, lt, "shy" if lt > b.start - 0.2 else "happy", 0.3)
    # 時計が早回し：5分 → 45分
    ff0, ff1 = a.end + 0.1, a.end + 1.5
    clock_y = 880
    wob = math.sin(lt * 25) * 10 if ff0 < lt < ff1 else 0
    paste(fr, emoji_img("⏰", 170), 870, clock_y, pop_in(lt, a.start + 0.6), wob)
    if lt > ff0:
        k = clamp((lt - ff0) / (ff1 - ff0))
        mins = int(5 + 40 * E.ease_in_cubic(k))
        col = (230, 50, 60) if k >= 1 else (240, 120, 40)
        sc_ = 1.0 + (0.25 * math.sin((lt - ff1) * 12) * math.exp(-(lt - ff1) * 3) if k >= 1 else 0)
        paste(fr, text_img(f"実際は… {mins}分", 92, WHITE, col, 12, FONT, (8, 10, (0, 0, 0, 70)), 0.1, (WHITE, 8)),
              W / 2, 730, sc_)
    stamp(fr, lt, c.start + 0.3, "3回目", 130, (240, 120, 40), 1240, -10, 220)


def s6(fr, lt, sc):
    a, b, c = sc.L(0), sc.L(1), sc.L(2)
    chip(fr, lt, 0.1, "その５ 宝物")
    paste(fr, emoji_img("🍮", 260), W / 2 + 260, 480 + bounce(lt, 1.8, 10), pop_in(lt, 0.2), math.sin(lt * 3) * 6)
    paste(fr, T("冷蔵庫の\nプリン", 120, WHITE, (220, 140, 30)), W / 2 - 160, 470, pop_in(lt, a.start))
    stamp(fr, lt, a.start + 1.3, "絶対死守", 100, (230, 40, 60), 680, 8, W / 2 + 200)
    expr = "jito" if lt > c.end else ("angry" if lt > b.start - 0.2 else "normal")
    draw_mama(fr, lt, expr, 0.3)
    if b.start - 0.2 < lt < c.end:
        paste(fr, emoji_img("💢", 130), W / 2 + 230, AV_Y - 220, 1 + 0.08 * math.sin(lt * 20))
    papa_icon(fr, lt, c.start - 0.1, "sweat", 200, 1240, 220)
    if lt > c.end + 0.2:
        band = E.rounded_box((960, 190), 30, (60, 35, 45, 235))
        k = pop_in(lt, c.end + 0.2, 0.3)
        paste(fr, band, W / 2, 800, k)
        paste(fr, text_img("→ 3秒でバレました", 88, YELLOW, (0, 0, 0), 0, FONT), W / 2, 800, k)


def s7(fr, lt, sc):
    a, b, c = sc.L(0), sc.L(1), sc.L(2)
    if lt < b.start:
        paste(fr, T("怒るとちょっと怖い", 96, WHITE, (120, 80, 220)), W / 2, 460, pop_in(lt, a.start), -2)
    else:
        paste(fr, T("でも笑うと\n家じゅうが明るい", 108, WHITE, (240, 110, 30)), W / 2, 500, pop_in(lt, b.start))
        # 太陽の光
        k = ease_out_cubic((lt - b.start) / 0.6)
        rays = Image.new("RGBA", (1200, 1200), (0, 0, 0, 0))
        d = ImageDraw.Draw(rays)
        for i in range(16):
            ang = i * math.pi / 8 + lt * 0.4
            d.polygon([(600, 600), (600 + 700 * math.cos(ang - 0.09), 600 + 700 * math.sin(ang - 0.09)),
                       (600 + 700 * math.cos(ang + 0.09), 600 + 700 * math.sin(ang + 0.09))],
                      fill=(255, 240, 150, 110))
        paste(fr, rays, W / 2, AV_Y, k)
    draw_mama(fr, lt, "angry" if lt < b.start else "happy", 0.15)
    if lt > c.start:
        paste(fr, T("いつもありがとう", 100, WHITE, PINK), W / 2, 1300, pop_in(lt, c.start))
        for i in range(6):
            st = c.start + i * 0.15
            if lt > st:
                yy = 1200 - (lt - st) * 300
                paste(fr, emoji_img("💖", 90), [180, 900, 260, 820, 120, 960][i], yy, 1.0, 0,
                      clamp(1 - (lt - st) / 2.5))


def s8(fr, lt, sc):
    a = sc.L(0)
    paste(fr, T("……で", 120, WHITE, PINK), W / 2, 430, pop_in(lt, a.start))
    paste(fr, emoji_img("🍮", 200), W / 2 + 330, 450, pop_in(lt, a.start + 0.4), -10)
    draw_mama(fr, lt, "jito", 0.0)
    end_t = a.end + 0.4
    if lt > end_t:
        k = pop_in(lt, end_t, 0.35)
        card = E.rounded_box((900, 330), 50, (255, 255, 255, 245), PINK + (255,), 10)
        paste(fr, card, W / 2, 760, k, -2)
        paste(fr, text_img("おしまい", 120, PINK, (0, 0, 0), 0, FONT), W / 2, 690, k, -2)
        paste(fr, text_img("パパママ社をよろしく！", 60, INK, (0, 0, 0), 0, FONT), W / 2, 830, k, -2)
        papa_icon(fr, lt, end_t + 0.2, "sweat", 190, 1250, 220)


def build_scenes():
    P, M = "papa", "mama"
    return [
        Scene("hook", [
            Line(P, "どうも！パパママ社の社長です。", "どうも！パパママ社の社長です"),
            Line(P, "今日は、うちの奥さんを、紹介します！", "今日はうちの奥さんを紹介します！"),
        ], s1, pre=0.15, post=0.6,
            sfx=[("pop", 0.05, 0.7), ("kira", ("line", 1, 0.0), 0.8), ("pop", ("line", 1, 0.4), 0.7)]),
        Scene("title", [
            Line(P, "まず肩書き。表向きの社長は、僕です。", "まず肩書き。\n表向きの社長は、僕です"),
            Line(P, "でも、本当の社長は。", "でも、本当の社長は…", gap=1.35),
            Line("mama_happy", "呼んだぁ？", "呼んだ？", pitch=1.0),
        ], s2, post=0.6,
            sfx=[("drumroll", ("end", 1, 0.0), 0.7), ("ding", ("line", 2, -0.15), 0.8), ("kira", ("line", 2, 0.0), 0.7)]),
        Scene("lie", [
            Line(P, "特技は、僕のウソを、3秒で見抜くこと。", "特技は、ぼくのウソを\n3秒で見抜くこと", gap=1.5),
            Line(M, "目が、泳いでるよ。", "目が泳いでるよ"),
            Line(P, "はい、すみません。", "…はい、すみません"),
        ], s3, post=0.4,
            sfx=[("pop", ("line", 0, 0.1), 0.6), ("tick", ("end", 0, 0.15), 0.9), ("tick", ("end", 0, 0.6), 0.9),
                 ("tick", ("end", 0, 1.05), 0.9), ("buzzer", ("line", 1, 0.2), 0.5)]),
        Scene("cfo", [
            Line(P, "役職は、シーエフオー。最高、お財布、責任者です。", "役職はCFO\n＝最高 お財布 責任者"),
            Line(P, "お小遣い交渉の、戦績は。", "お小遣い交渉の戦績は…", gap=0.9),
            Line("mama_angry", "却下です。", "却下です"),
        ], s4, post=0.5,
            sfx=[("kira", ("line", 0, 1.3), 0.6), ("buzzer", ("end", 1, 0.2), 0.7), ("pop", ("line", 2, 0.1), 0.6)]),
        Scene("5min", [
            Line(P, "口ぐせは、あと5分で準備できる。", "口ぐせは\n「あと5分で準備できる」", gap=1.7),
            Line("mama_shy", "あと5分だけぇ！", "あと5分だけ！"),
            Line(P, "ちなみに、これ3回目です。", "ちなみに、これ3回目です"),
        ], s5, post=0.7,
            sfx=[("whoosh", ("end", 0, 0.1), 0.6), ("ding", ("end", 0, 1.5), 0.6), ("pop", ("line", 2, 0.3), 0.7)]),
        Scene("pudding", [
            Line(P, "そして、冷蔵庫のプリンは、絶対に死守。", "そして冷蔵庫のプリンは\n絶対に死守"),
            Line("mama_angry", "わたしのプリン、食べたでしょ？", "私のプリン、食べたでしょ？"),
            Line(P, "食べてません。", "た、食べてません", gap=1.6),
        ], s6, post=0.2,
            sfx=[("pop", ("line", 0, 1.3), 0.7), ("buzzer", ("end", 2, 0.2), 0.6)]),
        Scene("warm", [
            Line(P, "怒ると、ちょっと怖いけど。", "怒るとちょっと怖いけど"),
            Line(P, "奥さんが笑うと、家じゅうが、明るくなります。", "奥さんが笑うと\n家じゅうが明るくなります"),
            Line(P, "いつも、ありがとう！", "いつも、ありがとう！"),
        ], s7, post=0.5,
            sfx=[("kira", ("line", 1, 0.0), 0.7), ("kira", ("line", 2, 0.0), 0.7)]),
        Scene("punch", [
            Line("mama", "で、プリンは？", "……で、プリンは？", delay=0.3),
        ], s8, post=2.0,
            sfx=[("buzzer", ("end", 0, 0.1), 0.5), ("pop", ("end", 0, 0.4), 0.7)]),
    ]


# ─── BGM（ウクレレ風・明るい I-V-vi-IV） ───────────────────────────────────

def make_bgm(bpm=124):
    beat = 60 / bpm
    bars = 8
    n = int(bars * 4 * beat * E.SR)
    out = np.zeros(n, dtype=np.float32)
    chords = [[60, 64, 67, 72], [55, 59, 62, 67], [57, 60, 64, 69], [53, 57, 60, 65]]  # C G Am F
    bass = [36, 31, 33, 29]
    strum = [(0, 1), (1, 1), (1.5, -1), (2.5, -1), (3, 1), (3.5, -1)]   # D-DU-UDU
    melody = [72, 76, 79, 76, 74, 79, 74, 71, 72, 76, 81, 79, 77, 76, 74, 72]
    for bar in range(bars):
        ch = chords[bar % 4]
        t0 = bar * 4 * beat
        for pos, dirn in strum:
            notes = ch if dirn > 0 else ch[::-1]
            for k, m in enumerate(notes):
                E.place(out, E.pluck(E.midi_hz(m), 0.6), t0 + pos * beat + k * 0.012, 0.09)
        E.place(out, E.pluck(E.midi_hz(bass[bar % 4]), 1.2, 0.5), t0, 0.35)
        E.place(out, E.pluck(E.midi_hz(bass[bar % 4] + 7), 0.8, 0.5), t0 + 2 * beat, 0.3)
        for b in range(4):
            if b % 2 == 0:
                E.place(out, E.kick(0.3, 0.6), t0 + b * beat, 0.45)
            else:
                E.place(out, E.clap(), t0 + b * beat, 0.45)
            E.place(out, E.hat(), t0 + (b + 0.5) * beat, 0.25)
        if bar >= 4:  # 後半はグロッケンのメロディ
            for i in range(2):
                m = melody[(bar - 4) * 4 // 1 % 16 + i * 2 % 16]
                E.place(out, E.bell(E.midi_hz(m + 12), 0.8), t0 + i * 2 * beat, 0.12)
                E.place(out, E.bell(E.midi_hz(melody[((bar - 4) * 4 + i * 2 + 1) % 16] + 12), 0.8),
                        t0 + (i * 2 + 1) * beat, 0.1)
    return out / (np.max(np.abs(out)) or 1)


def main(out_path):
    global SCENES
    SCENES[:] = build_scenes()
    total = E.build_timeline(SCENES, {"papa": {"speed": 1.08, "pitch": 1.5}})
    print(f"total {total:.2f}s")
    for sc in SCENES:
        print(f"  {sc.name:8s} start {sc.start:6.2f} dur {sc.dur:5.2f}")
        if sc is not SCENES[0]:
            sc.sfx.append(("whoosh", 0.0, 0.35))
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "mix.wav"
        E.mix_audio(SCENES, total, make_bgm(), bgm_gain=0.28, out_path=wav)
        E.render(SCENES, total, wav, out_path, bg_frame=bg_frame, overlay=overlay)
    print("done", out_path)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "wife_intro_pop.mp4")
