#!/usr/bin/env python3
"""The sprites: the players, the ball, shadows, boards, the logo and the cup.

Players are drawn from a skeleton: each frame is a pose, a set of joints, and the
body is built on it with lines and ellipses in the fixed sprite colours. The same
poses make the back view (the near pair, seen from behind) and, scaled down and
mirrored, the front view (the far pair, facing the camera). Shirt, hair and skin
colours are swapped at draw time (src/azzurra.c: tint tables), so one set of
frames dresses every player of the tour.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from art_common import TRANSPARENT, firmware_font, fixed_rgb
import palette as pal

FIX = pal.FIXED_INDEX


def C(name: str):
    return fixed_rgb(name)


# ---- poses -----------------------------------------------------------------------------
# Joints in back-view pixels, x to the right of the screen, y up from the feet (so the
# numbers read like a figure). r = right hand side of the player (screen right when
# seen from behind). "rk" is the racket direction in degrees (0 = screen right, 90 = up).

BASE = {
    "head": (0, 39), "rsh": (6, 32), "lsh": (-6, 32), "rhip": (4, 18), "lhip": (-4, 18),
}


def pose(**kw):
    p = dict(BASE)
    p.update(kw)
    return p


POSES = {
    "ready": pose(rel=(10, 25), rh=(8, 19), lel=(-9, 25), lh=(-4, 19), rk=(8, 20, 55),
                  rkn=(5, 9), lkn=(-5, 9), rf=(7, 0), lf=(-7, 0), crouch=2),
    "run1": pose(rel=(10, 26), rh=(11, 20), lel=(-9, 27), lh=(-8, 21), rk=(11, 20, 70),
                 rkn=(5, 10), lkn=(-3, 8), rf=(6, 3), lf=(-5, -0), crouch=1),
    "run2": pose(rel=(10, 27), rh=(9, 21), lel=(-10, 26), lh=(-11, 20), rk=(9, 21, 60),
                 rkn=(3, 8), lkn=(-5, 10), rf=(5, 0), lf=(-6, 3), crouch=1),
    "back": pose(rel=(13, 28), rh=(17, 26), lel=(-6, 26), lh=(0, 24), rk=(17, 26, 20),
                 rkn=(6, 9), lkn=(-4, 9), rf=(8, 0), lf=(-6, 0), crouch=2, turn=2),
    "hit": pose(rel=(10, 30), rh=(6, 30), lel=(-10, 27), lh=(-13, 24), rk=(6, 30, 160),
                rkn=(4, 9), lkn=(-6, 9), rf=(7, 0), lf=(-8, 0), crouch=1, turn=-1),
    "follow": pose(rel=(-2, 33), rh=(-7, 36), lel=(-11, 28), lh=(-13, 25), rk=(-7, 36, 230),
                   rkn=(5, 9), lkn=(-5, 9), rf=(7, 0), lf=(-7, 0), crouch=0, turn=-2),
    "toss": pose(rel=(12, 34), rh=(9, 40), lel=(-7, 40), lh=(-5, 48), rk=(9, 40, 260),
                 rkn=(4, 9), lkn=(-4, 9), rf=(6, 0), lf=(-6, 0), crouch=2),
    "smash": pose(rel=(6, 42), rh=(4, 50), lel=(-9, 32), lh=(-10, 26), rk=(4, 50, 95),
                  rkn=(4, 9), lkn=(-4, 9), rf=(5, 1), lf=(-6, 0), crouch=0),
    "cheer": pose(rel=(10, 41), rh=(10, 50), lel=(-10, 41), lh=(-10, 50), rk=(10, 50, 80),
                  rkn=(4, 9), lkn=(-4, 9), rf=(6, 2), lf=(-6, 2), crouch=0),
}
FRAMES = ["ready", "run1", "run2", "back", "hit", "follow", "toss", "smash", "cheer"]


def draw_player(view: str) -> list[Image.Image]:
    """`view` is "back" (near pair, 1:1) or "front" (far pair, smaller, facing us)."""
    if view == "back":
        scale, W, H, mirror = 1.0, 34, 58, 1
    else:
        scale, W, H, mirror = 0.62, 22, 36, -1
    out = []
    for name in FRAMES:
        p = POSES[name]
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        cx, base = W // 2, H - 1
        crouch = p.get("crouch", 0)
        turn = p.get("turn", 0)

        def pt(j, dy=0):
            x, y = j
            if y > 12:
                y -= crouch
            return (cx + mirror * x * scale, base - (y + dy) * scale)

        lw = max(1, round(3 * scale))
        aw = max(1, round(2 * scale))
        skin, skind, shirt, shirtd = C("skin"), C("skind"), C("shirt"), C("shirtd")
        white, grey, greyd, hair = C("white"), C("grey"), C("greyd"), C("blonde")
        # Legs: thigh and shin, a white sock, a shoe.
        for side, hip, knee, foot in (("l", "lhip", "lkn", "lf"), ("r", "rhip", "rkn", "rf")):
            h, k, f = pt(p[hip]), pt(p[knee]), pt(p[foot])
            d.line([h, k], fill=skin, width=lw)
            d.line([k, f], fill=skin if side == "r" else skind, width=lw)
            sock = (f[0] + (k[0] - f[0]) * 0.25, f[1] + (k[1] - f[1]) * 0.25)
            d.line([sock, f], fill=white, width=lw)
            d.rectangle([f[0] - 2 * scale, f[1] - 1 * scale, f[0] + 2 * scale, f[1] + 0.5], fill=grey if view == "back" else white)
        # The skirt.
        hl, hr = pt(p["lhip"], 3), pt(p["rhip"], 3)
        d.polygon([(hl[0] - 1 * scale, hl[1]), (hr[0] + 1 * scale, hr[1]),
                   (hr[0] + 3 * scale, hr[1] + 7 * scale), (hl[0] - 3 * scale, hl[1] + 7 * scale)], fill=white)
        # The shirt, shaded on one side; a turn of the body narrows it.
        sl, sr = pt((p["lsh"][0] + max(0, turn), p["lsh"][1])), pt((p["rsh"][0] + min(0, turn), p["rsh"][1]))
        d.polygon([sl, sr, (hr[0] + 0.5, hr[1]), (hl[0] - 0.5, hl[1])], fill=shirt)
        shade_x = (sr[0] + hr[0]) / 2
        d.line([(sr[0], sr[1] + 1), (hr[0], hr[1] - 1)], fill=shirtd, width=max(1, round(2 * scale)))
        d.line([(hl[0] - 0.5, hl[1]), (hr[0] + 0.5, hr[1])], fill=shirtd, width=1)
        # Arms: a short sleeve, then skin, down to the hand.
        racket_in_front = view == "front"
        def arm(sh, el, hand):
            s, e, h = pt(p[sh]), pt(p[el]), pt(p[hand])
            mid = (s[0] + (e[0] - s[0]) * 0.35, s[1] + (e[1] - s[1]) * 0.35)
            d.line([s, mid], fill=shirt, width=aw + 1)
            d.line([mid, e], fill=skin, width=aw)
            d.line([e, h], fill=skin, width=aw)
        def racket():
            hx, hy, ang = p["rk"]
            h = pt((hx, hy))
            a = math.radians(ang)
            ux, uy = mirror * math.cos(a), -math.sin(a)
            handle = 5 * scale
            neck = (h[0] + ux * handle, h[1] + uy * handle)
            d.line([h, neck], fill=greyd, width=max(1, round(1.6 * scale)))
            L, Wd = 11 * scale, 4.2 * scale
            cxr, cyr = neck[0] + ux * L / 2, neck[1] + uy * L / 2
            pts = []
            for k in range(20):
                t = 2 * math.pi * k / 20
                ex, ey = math.cos(t) * L / 2, math.sin(t) * Wd
                pts.append((cxr + ex * ux - ey * uy, cyr + ex * uy + ey * ux))
            d.polygon(pts, fill=C("grey"), outline=C("racket"))
        arm("lsh", "lel", "lh")
        if not racket_in_front:
            racket()
        arm("rsh", "rel", "rh")
        if racket_in_front:
            racket()
        # The head.
        hx, hy = pt(p["head"])
        r = 4.3 * scale
        if view == "back":
            d.ellipse([hx - r, hy - r, hx + r, hy + r], fill=hair)
            d.ellipse([hx - r + 1, hy + r - 2, hx - r + 2, hy + r - 1], fill=skind)      # an ear
            d.ellipse([hx + r - 2, hy + r - 2, hx + r - 1, hy + r - 1], fill=skind)
            d.line([(hx, hy + r - 2), (hx + 1, hy + r + 4)], fill=hair, width=3)        # the ponytail
            d.line([(hx - r + 1, hy - r + 2), (hx + r - 1, hy - r + 2)], fill=white, width=1)  # a visor's band
        else:
            d.ellipse([hx - r, hy - r, hx + r, hy + r], fill=hair)
            d.ellipse([hx - r + 0.8, hy - r + 1.6, hx + r - 0.8, hy + r], fill=skin)
            d.point((round(hx - 1), round(hy)), fill=C("ink"))
            d.point((round(hx + 1), round(hy)), fill=C("ink"))
            d.line([(hx - r, hy - r + 1), (hx + r, hy - r + 1)], fill=white, width=1)
        out.append(img)
    return out


def ellipse_sprite(w: int, h: int, color: str) -> Image.Image:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse([0, 0, w - 1, h - 1], fill=C(color))
    return img


def ball_sprite() -> Image.Image:
    img = Image.new("RGBA", (6, 6), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, 5, 5], fill=C("ball"))
    d.point((1, 1), fill=C("white"))
    d.point((2, 1), fill=C("white"))
    d.point((4, 4), fill=C("balld"))
    d.point((3, 4), fill=C("balld"))
    d.point((4, 3), fill=C("balld"))
    return img


# ---- boards: a 3 x 5 font for the advertising boards ---------------------------------------

MINI = {
    "A": "010101111101101", "C": "011100100100011", "E": "111100110100111", "H": "101101111101101",
    "I": "111010010010111", "N": "110101101101101", "O": "010101101101010", "P": "110101110100100",
    "R": "110101110101101", "S": "011100010001110", "T": "111010010010010", "U": "101101101101111",
    "V": "101101101101010", "W": "101101101111101", "G": "011100101101011", "-": "000000111000000",
    "2": "110001010100111", "3": "110001010001110", " ": "000000000000000",
}
SPONSORS = ["RISC-V", "UNIPARTHENOPE", "PRG32", "OPEN-HW", "OPEN-SW"]


def board_sprite(text: str, w: int, h: int, accent: str) -> Image.Image:
    img = Image.new("RGBA", (w, h), C("navy") + (255,))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], outline=C(accent))
    tw = len(text) * 4 - 1
    x0, y0 = (w - tw) // 2, (h - 5) // 2
    for i, ch in enumerate(text):
        bits = MINI[ch]
        for k, b in enumerate(bits):
            if b == "1":
                d.point((x0 + i * 4 + k % 3, y0 + k // 3), fill=C("white" if accent != "gold" else "gold"))
    return img


# ---- the logo ---------------------------------------------------------------------------------

def big_text(text: str, sx: int, sy: int, top, bottom, font) -> Image.Image:
    """The 8 x 8 firmware font scaled up, with a vertical gradient, an ink outline and a
    drop shadow."""
    w, h = len(text) * 8 * sx + 4, 8 * sy + 4
    mask = Image.new("L", (w, h), 0)
    m = mask.load()
    for i, ch in enumerate(text):
        glyph = font.get(ch, font[" "])
        for gy in range(8):
            for gx in range(8):
                if glyph[gy] & (0x80 >> gx):
                    for yy in range(sy):
                        for xx in range(sx):
                            m[1 + i * 8 * sx + gx * sx + xx, 1 + gy * sy + yy] = 255
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    ink = C("ink") + (255,)
    for y in range(h):
        for x in range(w):
            if m[x, y]:
                continue
            near = any(0 <= x + dx < w and 0 <= y + dy < h and m[x + dx, y + dy]
                       for dx in (-1, 0, 1) for dy in (-1, 0, 1))
            shadow = x >= 2 and y >= 2 and m[x - 2, y - 2]
            if near or shadow:
                px[x, y] = ink
    for y in range(h):
        t = min(1.0, max(0.0, (y - 1) / max(1, 8 * sy - 1)))
        col = tuple(int(top[k] + (bottom[k] - top[k]) * t) for k in range(3)) + (255,)
        for x in range(w):
            if m[x, y]:
                px[x, y] = col
    return img


def logo_sprite() -> Image.Image:
    font = firmware_font()
    a = big_text("AZZURRA'S", 3, 3, C("white"), C("shirt"), font)
    b = big_text("PRO TENNIS", 2, 2, C("goldl"), C("gold"), font)
    c = big_text("CHALLENGE", 2, 2, C("goldl"), C("goldd"), font)
    w = max(a.width, b.width, c.width)
    img = Image.new("RGBA", (w, a.height + b.height + c.height - 2), (0, 0, 0, 0))
    img.alpha_composite(a, ((w - a.width) // 2, 0))
    img.alpha_composite(b, ((w - b.width) // 2, a.height - 1))
    img.alpha_composite(c, ((w - c.width) // 2, a.height + b.height - 2))
    return img


def trophy_sprite() -> Image.Image:
    W, H = 44, 62
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    gold, goldd, goldl, ink = C("gold"), C("goldd"), C("goldl"), C("ink")
    # Handles.
    d.ellipse([1, 6, 15, 24], outline=goldd, width=3)
    d.ellipse([29, 6, 43, 24], outline=goldd, width=3)
    # The bowl.
    d.pieslice([6, -14, 38, 34], 0, 180, fill=gold, outline=ink)
    d.rectangle([6, 2, 38, 10], fill=gold)
    d.line([(6, 2), (38, 2)], fill=ink)
    d.ellipse([7, 0, 37, 5], fill=goldd)
    d.line([(12, 8), (14, 22)], fill=goldl, width=2)
    # Stem, knot and foot.
    d.rectangle([19, 34, 25, 42], fill=goldd)
    d.ellipse([15, 38, 29, 46], fill=gold, outline=ink)
    d.polygon([(12, 52), (32, 52), (28, 46), (16, 46)], fill=gold, outline=ink)
    d.rectangle([8, 52, 36, 61], fill=C("brown"), outline=ink)
    d.rectangle([14, 55, 30, 58], fill=goldl)
    return img


def confetti() -> list[Image.Image]:
    out = []
    for color in ("red", "gold", "cyan", "pink", "white", "green"):
        img = Image.new("RGBA", (3, 2), C(color) + (255,))
        out.append(img)
    return out


# ---- to indices -------------------------------------------------------------------------------

_SPRITE_RGB = {pal.rgb888(c): i for i, c in enumerate(pal.FIXED_RGB565[:pal.SPRITE_COUNT]) if i != TRANSPARENT}


def to_indices(img: Image.Image) -> list[list[int]]:
    """Map an RGBA picture drawn in fixed sprite colours to palette indices (nearest
    colour where antialiasing slipped in, transparency where alpha is low)."""
    w, h = img.size
    px = img.load()
    rows = []
    cache: dict = {}
    for y in range(h):
        row = []
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 128:
                row.append(TRANSPARENT)
                continue
            key = (r, g, b)
            if key not in cache:
                if key in _SPRITE_RGB:
                    cache[key] = _SPRITE_RGB[key]
                else:
                    cache[key] = min(_SPRITE_RGB.items(),
                                     key=lambda kv: sum((kv[0][k] - key[k]) ** 2 for k in range(3)))[1]
            row.append(cache[key])
        rows.append(row)
    return rows
