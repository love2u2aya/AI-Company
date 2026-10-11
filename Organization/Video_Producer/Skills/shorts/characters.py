"""
ショート動画用キャラクター（奥さん・社長）を Pillow の図形だけで描く。
2倍サイズで描いてから縮小し、アンチエイリアスをかける。

表情 expr:
  奥さん: normal / happy / angry / shy / jito（ジト目） / proud
  社長  : normal / sweat / happy
"""

from functools import lru_cache

from PIL import Image, ImageDraw

SKIN = (255, 224, 200, 255)
HAIR = (92, 56, 40, 255)
HAIR_HI = (130, 84, 60, 255)
BLUSH = (255, 140, 160, 150)
INK = (50, 30, 30, 255)
MOUTH = (200, 60, 70, 255)
TONGUE = (255, 140, 140, 255)
WHITE = (255, 255, 255, 255)


def _eye(d, cx, cy, s, expr):
    if expr in ("happy", "proud"):
        d.arc([cx - 40 * s, cy - 30 * s, cx + 40 * s, cy + 40 * s], 200, 340, fill=INK, width=int(12 * s))
    elif expr == "shy":
        # > < 目
        d.line([cx - 30 * s, cy - 20 * s, cx + 25 * s, cy, cx - 30 * s, cy + 20 * s], fill=INK, width=int(11 * s), joint="curve")
    elif expr == "jito":
        d.ellipse([cx - 28 * s, cy - 34 * s, cx + 28 * s, cy + 34 * s], fill=INK)
        d.rectangle([cx - 40 * s, cy - 50 * s, cx + 40 * s, cy - 2 * s], fill=SKIN)
        d.line([cx - 40 * s, cy - 2 * s, cx + 40 * s, cy - 2 * s], fill=INK, width=int(10 * s))
    else:
        d.ellipse([cx - 28 * s, cy - 36 * s, cx + 28 * s, cy + 36 * s], fill=INK)
        d.ellipse([cx - 14 * s, cy - 26 * s, cx + 4 * s, cy - 8 * s], fill=WHITE)
        d.ellipse([cx + 6 * s, cy + 8 * s, cx + 16 * s, cy + 18 * s], fill=WHITE)


@lru_cache(maxsize=32)
def mama(expr="normal", size=560, crown=False):
    """奥さん（バストアップ）。size = 画像の幅"""
    S = 2
    s = S  # 図形スケール（基準：幅560）
    w, h = 560 * S, 640 * S
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = w // 2
    fy = 330 * s  # 顔中心

    # 服（肩）
    d.rounded_rectangle([cx - 230 * s, 520 * s, cx + 230 * s, 760 * s], 120 * s, fill=(255, 120, 140, 255))
    d.polygon([(cx - 60 * s, 520 * s), (cx, 600 * s), (cx + 60 * s, 520 * s)], fill=SKIN)
    d.ellipse([cx - 14 * s, 590 * s, cx + 14 * s, 618 * s], fill=(255, 220, 90, 255))
    # 後ろ髪
    d.ellipse([cx - 230 * s, fy - 230 * s, cx + 230 * s, fy + 250 * s], fill=HAIR)
    d.rounded_rectangle([cx - 230 * s, fy - 20 * s, cx + 230 * s, fy + 240 * s], 80 * s, fill=HAIR)
    # お団子
    d.ellipse([cx - 95 * s, fy - 330 * s, cx + 95 * s, fy - 150 * s], fill=HAIR)
    d.ellipse([cx - 60 * s, fy - 305 * s, cx - 10 * s, fy - 270 * s], fill=HAIR_HI)
    d.rounded_rectangle([cx - 70 * s, fy - 175 * s, cx + 70 * s, fy - 150 * s], 12 * s, fill=(255, 210, 80, 255))
    # 首・顔
    d.rectangle([cx - 45 * s, fy + 150 * s, cx + 45 * s, 540 * s], fill=SKIN)
    d.ellipse([cx - 185 * s, fy - 190 * s, cx + 185 * s, fy + 200 * s], fill=SKIN)
    # 前髪
    d.chord([cx - 200 * s, fy - 230 * s, cx + 200 * s, fy + 40 * s], 180, 360, fill=HAIR)
    for bx, bw in [(-150, 80), (-60, 90), (40, 90), (130, 70)]:
        d.ellipse([cx + (bx - bw // 2) * s, fy - 120 * s, cx + (bx + bw // 2) * s, fy - 20 * s], fill=HAIR)
    d.arc([cx - 140 * s, fy - 200 * s, cx + 40 * s, fy - 60 * s], 200, 260, fill=HAIR_HI, width=int(12 * s))

    ey = fy + 30 * s
    # 眉
    if expr == "angry":
        d.line([cx - 130 * s, ey - 85 * s, cx - 40 * s, ey - 55 * s], fill=INK, width=int(14 * s))
        d.line([cx + 130 * s, ey - 85 * s, cx + 40 * s, ey - 55 * s], fill=INK, width=int(14 * s))
    elif expr == "jito":
        d.line([cx - 125 * s, ey - 62 * s, cx - 45 * s, ey - 62 * s], fill=INK, width=int(11 * s))
        d.line([cx + 125 * s, ey - 62 * s, cx + 45 * s, ey - 62 * s], fill=INK, width=int(11 * s))
    elif expr == "shy":
        d.line([cx - 125 * s, ey - 60 * s, cx - 45 * s, ey - 75 * s], fill=INK, width=int(9 * s))
        d.line([cx + 125 * s, ey - 60 * s, cx + 45 * s, ey - 75 * s], fill=INK, width=int(9 * s))
    # 目
    _eye(d, cx - 85 * s, ey, s, expr)
    if expr == "shy":
        d.line([cx + 115 * s, ey - 20 * s, cx + 60 * s, ey, cx + 115 * s, ey + 20 * s], fill=INK, width=int(11 * s), joint="curve")
    else:
        _eye(d, cx + 85 * s, ey, s, expr)
    # ほっぺ
    blush = Image.new("RGBA", im.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(blush)
    bw = 60 if expr == "shy" else 45
    for sx in (-1, 1):
        bx = cx + sx * 125 * s
        bd.ellipse([bx - bw * s, ey + 50 * s, bx + bw * s, ey + 90 * s], fill=BLUSH if expr != "shy" else (255, 110, 140, 200))
    if expr == "shy":
        for sx in (-1, 1):
            for k in range(3):
                x0 = cx + sx * (100 + k * 20) * s
                bd.line([x0, ey + 55 * s, x0 - 10 * s, ey + 85 * s], fill=(230, 80, 110, 255), width=int(5 * s))
    im.alpha_composite(blush)
    # 口
    my = fy + 120 * s
    if expr in ("happy", "proud"):
        d.chord([cx - 55 * s, my - 30 * s, cx + 55 * s, my + 50 * s], 0, 180, fill=MOUTH)
        d.chord([cx - 30 * s, my + 10 * s, cx + 30 * s, my + 48 * s], 180, 360, fill=TONGUE)
    elif expr == "angry":
        d.arc([cx - 45 * s, my, cx + 45 * s, my + 50 * s], 200, 340, fill=INK, width=int(10 * s))
    elif expr == "jito":
        d.line([cx - 30 * s, my + 10 * s, cx + 35 * s, my + 2 * s], fill=INK, width=int(9 * s))
    elif expr == "shy":
        # ω
        d.arc([cx - 40 * s, my - 10 * s, cx, my + 25 * s], 0, 180, fill=INK, width=int(8 * s))
        d.arc([cx, my - 10 * s, cx + 40 * s, my + 25 * s], 0, 180, fill=INK, width=int(8 * s))
    else:
        d.arc([cx - 40 * s, my - 20 * s, cx + 40 * s, my + 25 * s], 20, 160, fill=INK, width=int(9 * s))

    im = im.resize((size, int(size * h / w)), Image.LANCZOS)
    return im


@lru_cache(maxsize=16)
def papa(expr="normal", size=300):
    """社長（顔のみ・小さめ）"""
    S = 2
    w = h = 400 * S
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = w // 2, h // 2 + 20 * S
    s = S
    d.rounded_rectangle([cx - 150 * s, cy + 120 * s, cx + 150 * s, cy + 260 * s], 70 * s, fill=(70, 130, 220, 255))
    d.ellipse([cx - 150 * s, cy - 165 * s, cx + 150 * s, cy + 150 * s], fill=SKIN)
    d.chord([cx - 160 * s, cy - 185 * s, cx + 160 * s, cy + 10 * s], 180, 360, fill=(40, 30, 30, 255))
    d.rectangle([cx - 160 * s, cy - 90 * s, cx - 130 * s, cy - 10 * s], fill=(40, 30, 30, 255))
    d.rectangle([cx + 130 * s, cy - 90 * s, cx + 160 * s, cy - 10 * s], fill=(40, 30, 30, 255))
    ey = cy + 10 * s
    # メガネ
    for sx in (-1, 1):
        ex = cx + sx * 62 * s
        d.rounded_rectangle([ex - 48 * s, ey - 34 * s, ex + 48 * s, ey + 34 * s], 18 * s, outline=INK, width=int(8 * s))
        if expr == "happy":
            d.arc([ex - 22 * s, ey - 12 * s, ex + 22 * s, ey + 22 * s], 200, 340, fill=INK, width=int(8 * s))
        else:
            d.ellipse([ex - 12 * s, ey - 14 * s, ex + 12 * s, ey + 14 * s], fill=INK)
    d.line([cx - 14 * s, ey, cx + 14 * s, ey], fill=INK, width=int(7 * s))
    my = cy + 85 * s
    if expr == "sweat":
        d.line([cx - 35 * s, my, cx - 12 * s, my - 10 * s, cx + 12 * s, my, cx + 35 * s, my - 10 * s], fill=INK, width=int(7 * s))
        d.ellipse([cx + 110 * s, cy - 70 * s, cx + 145 * s, cy - 20 * s], fill=(120, 200, 255, 255))
        d.polygon([(cx + 112 * s, cy - 50 * s), (cx + 127 * s, cy - 95 * s), (cx + 143 * s, cy - 50 * s)], fill=(120, 200, 255, 255))
    elif expr == "happy":
        d.chord([cx - 40 * s, my - 25 * s, cx + 40 * s, my + 30 * s], 0, 180, fill=MOUTH)
    else:
        d.arc([cx - 35 * s, my - 25 * s, cx + 35 * s, my + 15 * s], 20, 160, fill=INK, width=int(7 * s))
    return im.resize((size, size), Image.LANCZOS)
