#!/usr/bin/env python3
"""The fourteen cities of the tour: their names, rivals, courts and skylines.

Each skyline is painted here from simple shapes (no photograph is traced or
sampled) at twice the size, reduced to 320 x 40 and then to at most
palette.VIEW_COLORS colours of its own (tools/build_art.py). The landmarks are
the well-known silhouettes of each city, drawn small, as seen from a stadium.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from art_common import hexrgb, mix
from art_court import CLAY, GRASS, HARD

W2, H2 = 640, 80          # painted at twice the size
HORIZON = 64              # ground or sea level, in the painting


# name, rivals, surface, night, sky top, sky horizon, rival shirt, rival shirt dark,
# court colours: inside, outside (the other roles are derived).
CITIES = [
    ("NAPOLI BAY", "VESUVIO VOLLEYS", CLAY, False, "#2f78d0", "#bfe2f6", "#e04a3a", "#902a24", "#c8643a", "#bd5c36"),
    ("ROME CLASSIC", "ROMAN ACES", CLAY, False, "#3d74c4", "#f4dcb4", "#7a2a8a", "#4a1856", "#c66a40", "#ba6038"),
    ("PARIS CLAY", "PARIS TOPSPIN", CLAY, False, "#5a8ed6", "#dcecf8", "#3a3a8a", "#22224e", "#d06a36", "#c26030"),
    ("CHICAGO WIND", "WINDY SMASH", HARD, False, "#3e7cc8", "#d6ecf4", "#d02a2a", "#7a1414", "#3a6cc0", "#3c8a5a"),
    ("LONDON GRASS", "ROYAL VOLLEYS", GRASS, False, "#8a9aae", "#dfe4ea", "#f6f6f6", "#9aa0aa", "#4e9c40", "#479338"),
    ("NEW YORK NIGHT", "METRO POWER", HARD, True, "#0a1030", "#2c3a6e", "#f08a28", "#984e10", "#2e5cb0", "#2e6e4a"),
    ("TOKYO LIGHTS", "NEON SERVERS", HARD, True, "#120a2e", "#4a2a5e", "#ea4aa0", "#8a1c5a", "#6a3aa8", "#2a6a6e"),
    ("CAIRO OPEN", "NILE ACES", CLAY, False, "#6aa0d0", "#f6e2b0", "#20a0a0", "#106060", "#d27a40", "#c87038"),
    ("MADRID MASTERS", "CASTILLA PAIR", CLAY, False, "#1e5cc0", "#acd2f2", "#e8c020", "#9a7a0a", "#c4603a", "#b85834"),
    ("BARCELONA CUP", "CATALAN SPIN", CLAY, False, "#2a86d8", "#c8eaf8", "#b02040", "#681024", "#cc6c3c", "#c06234"),
    ("BERLIN CLASSIC", "BERLIN WALL", HARD, False, "#6c8cb4", "#d8e2ec", "#303030", "#141414", "#a83a30", "#3a5aa0"),
    ("VENICE CANAL", "LAGOON LOBS", CLAY, False, "#4a5aa8", "#f8b070", "#30a050", "#185e2c", "#c8663c", "#bc5e36"),
    ("SYDNEY OPEN", "HARBOUR ACES", HARD, False, "#2a8ae0", "#cceefc", "#f0d030", "#2a8a3a", "#2a74c6", "#2a5aa0"),
    ("ATHENS FINAL", "OLYMPUS PAIR", CLAY, False, "#4a70c0", "#f6d6a0", "#2a5ab8", "#f4f4f4", "#ca6a3e", "#be6036"),
]
SURFACE_NAMES = {CLAY: "CLAY", GRASS: "GRASS", HARD: "HARD COURT"}


def surface_colors(city: int) -> list[tuple[int, int, int]]:
    """The eight court roles of art_court: in, in2, out, out2, line, lined, wear, edge."""
    _, _, kind, night, *_rest, inside, outside = CITIES[city]
    a, b = hexrgb(inside), hexrgb(outside)
    line = (244, 244, 236)
    if kind == CLAY:
        roles = [a, mix(a, (90, 40, 20), 0.12), b, mix(b, (90, 40, 20), 0.12), line,
                 mix(line, a, 0.45), mix(a, (240, 200, 160), 0.18), mix(b, (40, 20, 10), 0.35)]
    elif kind == GRASS:
        roles = [a, mix(a, (150, 200, 90), 0.22), b, mix(b, (150, 200, 90), 0.22), line,
                 mix(line, a, 0.45), (176, 150, 92), mix(b, (10, 40, 10), 0.4)]
    else:
        roles = [a, mix(a, (255, 255, 255), 0.10), b, mix(b, (255, 255, 255), 0.10), line,
                 mix(line, a, 0.45), mix(a, (255, 255, 255), 0.22), mix(b, (0, 0, 0), 0.35)]
    if night:
        # Under floodlights the court stays bright and the surround falls into shadow.
        roles = [mix(c, (10, 10, 30), 0.10 if k in (0, 1, 4, 5, 6) else 0.32) for k, c in enumerate(roles)]
    return roles


# ---- painting helpers (all coordinates at twice the size) -------------------------------

def sky(img: Image.Image, top, bottom, stars: bool = False) -> None:
    d = ImageDraw.Draw(img)
    for y in range(H2):
        t = min(1.0, y / HORIZON)
        d.line([(0, y), (W2, y)], fill=mix(top, bottom, t ** 1.3))
    if stars:
        for k in range(70):
            x = (k * 9301 + 49297) % 640
            y = (k * 233 + 17) % 40
            d.point((x, y), fill=(220, 220, 255))


def clouds(img, y, color, seeds) -> None:
    d = ImageDraw.Draw(img)
    for x, w in seeds:
        for k in range(4):
            cx = x + k * w // 4
            r = w // 5 + (k % 2) * 3
            d.ellipse([cx - r, y - r // 2, cx + r, y + r // 2], fill=color)


def sea(img, y0, color, light) -> None:
    d = ImageDraw.Draw(img)
    d.rectangle([0, y0, W2, H2], fill=color)
    for k in range(40):
        x = (k * 137) % 640
        yy = y0 + 2 + (k * 7) % max(1, (H2 - y0 - 4))
        d.line([(x, yy), (x + 10, yy)], fill=light)


def ground(img, y0, color) -> None:
    ImageDraw.Draw(img).rectangle([0, y0, W2, H2], fill=color)


def buildings(img, x0, x1, base, hmin, hmax, color, window, seed, lit=False) -> None:
    d = ImageDraw.Draw(img)
    x = x0
    k = seed
    while x < x1:
        k = (k * 1103515245 + 12345) & 0x7FFFFFFF
        w = 14 + k % 22
        h = hmin + (k >> 8) % max(1, hmax - hmin)
        d.rectangle([x, base - h, x + w, base], fill=color)
        if window:
            for wy in range(base - h + 4, base - 2, 5):
                for wx in range(x + 3, x + w - 2, 5):
                    if lit and ((wx * 7 + wy * 13 + k) % 5 == 0):
                        continue
                    d.rectangle([wx, wy, wx + 1, wy + 1], fill=window)
        x += w + 2


def tree(img, x, base, h, color, trunk=None) -> None:
    d = ImageDraw.Draw(img)
    if trunk:
        d.rectangle([x - 1, base - h // 2, x + 1, base], fill=trunk)
    d.ellipse([x - h // 3, base - h, x + h // 3, base - h // 3], fill=color)


def pine(img, x, base, h, color, trunk) -> None:
    """The umbrella pine of the Mediterranean."""
    d = ImageDraw.Draw(img)
    d.line([(x, base), (x + 3, base - h + 6)], fill=trunk, width=3)
    d.ellipse([x - h // 2, base - h - 4, x + h // 2 + 6, base - h + 10], fill=color)


def cypress(img, x, base, h, color) -> None:
    ImageDraw.Draw(img).ellipse([x - 4, base - h, x + 4, base], fill=color)


def palm(img, x, base, h, color, trunk) -> None:
    d = ImageDraw.Draw(img)
    d.line([(x, base), (x + 4, base - h)], fill=trunk, width=3)
    tx, ty = x + 4, base - h
    for a in (-150, -110, -70, -30, 10):
        r = math.radians(a)
        d.line([(tx, ty), (tx + 14 * math.cos(r), ty + 10 * math.sin(r) + 6)], fill=color, width=3)


def stadium_rim(img, color, lamp, night) -> None:
    """The top of the stadium: a roof edge and two floodlight towers."""
    d = ImageDraw.Draw(img)
    d.rectangle([0, 72, W2, H2], fill=color)
    d.line([(0, 72), (W2, 72)], fill=mix(color, (255, 255, 255), 0.25), width=1)
    for x in (24, 616):
        d.rectangle([x - 2, 14, x + 2, 72], fill=mix(color, (0, 0, 0), 0.2))
        d.rectangle([x - 12, 6, x + 12, 16], fill=mix(color, (0, 0, 0), 0.35))
        for k in range(4):
            for j in range(2):
                d.rectangle([x - 10 + k * 6, 8 + j * 4, x - 7 + k * 6, 10 + j * 4], fill=lamp)
        if night:
            d.polygon([(x - 12, 16), (x + 12, 16), (x + 70 * (1 if x < 320 else -1), 72)], fill=mix(color, lamp, 0.12))


# ---- the cities ----------------------------------------------------------------------------

def paint(city: int, back: bool = False) -> Image.Image:
    """The view over the far stands: from the broadcast camera (back=False), or from
    the other end of the court, looking the other way (back=True)."""
    name, _, kind, night, top, bottom, *_rest = CITIES[city]
    img = Image.new("RGB", (W2, H2))
    sky(img, hexrgb(top), hexrgb(bottom), stars=night)
    d = ImageDraw.Draw(img)
    lamp = (255, 246, 200) if night else (220, 224, 230)
    rim = (60, 64, 76) if not night else (24, 26, 40)
    P = (BACK_PAINTERS if back else PAINTERS)[city]
    P(img, d)
    stadium_rim(img, rim, lamp, night)
    return img.resize((320, 40), Image.BOX)


def napoli(img, d):
    clouds(img, 14, (240, 248, 255), [(90, 60), (420, 80)])
    # Vesuvio: the cone and the older rim of Monte Somma beside it.
    d.polygon([(330, 64), (430, 22), (452, 26), (470, 18), (560, 64)], fill=(108, 112, 140))
    d.polygon([(430, 22), (452, 26), (470, 18), (500, 34), (440, 40)], fill=(126, 130, 158))
    sea(img, 56, (40, 110, 178), (120, 180, 220))
    # Castel dell'Ovo on its rock in the bay.
    d.rectangle([150, 48, 230, 60], fill=(214, 196, 160))
    d.rectangle([168, 40, 196, 48], fill=(214, 196, 160))
    for x in range(150, 232, 8):
        d.rectangle([x, 46, x + 3, 48], fill=(214, 196, 160))
    d.rectangle([140, 60, 240, 64], fill=(120, 110, 100))
    buildings(img, 0, 120, 70, 8, 22, (232, 196, 140), (190, 120, 80), 3)
    buildings(img, 560, 640, 70, 6, 18, (236, 180, 130), (180, 110, 70), 5)
    pine(img, 70, 70, 30, (46, 96, 50), (90, 60, 40))
    pine(img, 600, 70, 26, (46, 96, 50), (90, 60, 40))


def rome(img, d):
    clouds(img, 12, (255, 240, 220), [(300, 70)])
    # St Peter's dome, far off.
    d.ellipse([470, 24, 530, 60], fill=(190, 170, 150))
    d.rectangle([496, 14, 504, 26], fill=(190, 170, 150))
    d.rectangle([460, 44, 540, 66], fill=(200, 180, 156))
    # The Colosseum: tiers of arches on an oval wall.
    d.rectangle([120, 22, 330, 66], fill=(206, 168, 120))
    d.polygon([(330, 22), (360, 34), (360, 66), (330, 66)], fill=(176, 140, 100))
    for row, y in enumerate((28, 40, 52)):
        for x in range(126, 326, 12):
            d.rectangle([x, y, x + 6, y + 8], fill=(120, 86, 60))
    d.line([(120, 22), (330, 22)], fill=(230, 196, 150), width=2)
    for x in (40, 70, 400, 430, 580, 610):
        cypress(img, x, 70, 40, (40, 76, 46))
    buildings(img, 0, 30, 70, 6, 14, (226, 170, 120), None, 9)


def paris(img, d):
    clouds(img, 18, (250, 252, 255), [(80, 70), (480, 90)])
    buildings(img, 0, 640, 70, 10, 22, (196, 186, 170), (110, 120, 140), 11)
    # Mansard roofs.
    for x in range(0, 640, 30):
        d.polygon([(x, 52), (x + 26, 52), (x + 22, 46), (x + 4, 46)], fill=(100, 110, 130))
    # The Eiffel Tower.
    cx = 250
    d.polygon([(cx - 36, 70), (cx - 10, 30), (cx + 10, 30), (cx + 36, 70), (cx + 24, 70), (cx, 42), (cx - 24, 70)], fill=(110, 86, 70))
    d.polygon([(cx - 10, 30), (cx - 4, 4), (cx + 4, 4), (cx + 10, 30)], fill=(110, 86, 70))
    d.rectangle([cx - 20, 44, cx + 20, 47], fill=(130, 100, 80))
    d.rectangle([cx - 12, 28, cx + 12, 31], fill=(130, 100, 80))
    d.line([(cx, 4), (cx, 0)], fill=(110, 86, 70), width=2)
    # Sacre-Coeur on its hill.
    d.ellipse([440, 40, 560, 80], fill=(150, 170, 120))
    d.ellipse([486, 26, 514, 46], fill=(244, 240, 230))
    d.rectangle([480, 38, 520, 52], fill=(244, 240, 230))
    d.rectangle([498, 18, 502, 28], fill=(244, 240, 230))


def chicago(img, d):
    clouds(img, 10, (236, 244, 250), [(40, 90), (300, 110), (520, 80)])
    sea(img, 60, (70, 130, 170), (150, 200, 220))
    buildings(img, 0, 640, 64, 14, 40, (90, 104, 126), (170, 190, 210), 21)
    # The tallest tower, black with two antennas.
    d.rectangle([330, 8, 360, 64], fill=(40, 42, 50))
    d.rectangle([336, 0, 354, 8], fill=(40, 42, 50))
    d.line([(340, 0), (340, -10)], fill=(200, 200, 210), width=1)
    d.line([(350, 0), (350, -10)], fill=(200, 200, 210), width=1)
    d.rectangle([180, 14, 200, 64], fill=(60, 64, 76))
    d.line([(190, 14), (190, 2)], fill=(60, 64, 76), width=2)


def london(img, d):
    clouds(img, 10, (200, 206, 214), [(0, 140), (200, 160), (420, 160)])
    sea(img, 62, (90, 100, 100), (140, 150, 150))
    # The Palace of Westminster and its clock tower.
    d.rectangle([90, 40, 300, 62], fill=(196, 170, 120))
    for x in range(90, 300, 10):
        d.rectangle([x, 36, x + 4, 40], fill=(196, 170, 120))
    d.rectangle([250, 6, 272, 62], fill=(200, 172, 120))
    d.polygon([(250, 6), (261, -6), (272, 6)], fill=(70, 80, 90))
    d.rectangle([254, 14, 268, 26], fill=(240, 236, 220))
    d.ellipse([256, 16, 266, 24], fill=(240, 236, 220), outline=(60, 60, 60))
    # The London Eye.
    cx, cy, r = 470, 34, 28
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(230, 232, 236), width=2)
    for k in range(12):
        a = k * math.pi / 6
        d.line([(cx, cy), (cx + r * math.cos(a), cy + r * math.sin(a))], fill=(200, 204, 210))
        d.rectangle([cx + r * math.cos(a) - 1, cy + r * math.sin(a) - 1, cx + r * math.cos(a) + 2, cy + r * math.sin(a) + 2], fill=(230, 232, 236))
    d.line([(cx, cy), (cx - 18, 64)], fill=(200, 204, 210), width=2)
    buildings(img, 540, 640, 66, 8, 24, (150, 140, 130), (90, 90, 100), 31)
    buildings(img, 0, 80, 66, 8, 24, (150, 140, 130), (90, 90, 100), 33)


def newyork(img, d):
    d.ellipse([540, 6, 556, 22], fill=(244, 240, 214))
    buildings(img, 0, 640, 66, 14, 44, (30, 34, 60), (250, 210, 110), 41, lit=True)
    # The Empire State Building, lit at the top.
    cx = 250
    d.rectangle([cx - 20, 22, cx + 20, 66], fill=(44, 50, 80))
    d.rectangle([cx - 12, 10, cx + 12, 22], fill=(56, 62, 96))
    d.rectangle([cx - 6, 2, cx + 6, 10], fill=(240, 200, 110))
    d.line([(cx, 2), (cx, -10)], fill=(220, 220, 230), width=2)
    for y in range(26, 64, 5):
        for x in range(cx - 16, cx + 16, 5):
            d.rectangle([x, y, x + 1, y + 1], fill=(250, 220, 130))
    # Lady Liberty, small across the harbour.
    d.rectangle([440, 50, 452, 66], fill=(70, 120, 110))
    d.rectangle([443, 38, 449, 50], fill=(70, 120, 110))
    d.line([(447, 38), (452, 28)], fill=(70, 120, 110), width=2)
    d.ellipse([450, 24, 456, 30], fill=(250, 210, 110))


def tokyo(img, d):
    d.ellipse([90, 6, 106, 22], fill=(246, 240, 220))
    # Fuji under the moon.
    d.polygon([(380, 66), (480, 22), (500, 22), (600, 66)], fill=(70, 60, 110))
    d.polygon([(468, 28), (480, 22), (500, 22), (512, 28), (500, 34), (490, 30), (480, 34)], fill=(220, 220, 240))
    buildings(img, 0, 640, 68, 10, 34, (40, 30, 70), (240, 120, 200), 51, lit=True)
    # Tokyo Tower: an orange and white lattice, lit.
    cx = 230
    d.polygon([(cx - 30, 68), (cx - 6, 14), (cx + 6, 14), (cx + 30, 68)], fill=(240, 110, 40))
    d.polygon([(cx - 6, 14), (cx - 2, -4), (cx + 2, -4), (cx + 6, 14)], fill=(240, 110, 40))
    for y in (30, 48):
        d.rectangle([cx - 20, y, cx + 20, y + 3], fill=(250, 240, 230))
    d.polygon([(cx - 18, 68), (cx, 50), (cx + 18, 68)], fill=(40, 30, 70))
    # Neon signs.
    for x, c in ((60, (60, 240, 230)), (330, (250, 60, 140)), (560, (250, 230, 60))):
        d.rectangle([x, 40, x + 14, 44], fill=c)


def cairo(img, d):
    d.ellipse([520, 8, 548, 36], fill=(255, 250, 220))
    ground(img, 58, (222, 186, 124))
    # The three pyramids of Giza.
    for cx, h, w in ((200, 46, 60), (300, 40, 54), (380, 24, 32)):
        d.polygon([(cx - w, 62), (cx, 62 - h), (cx + w, 62)], fill=(214, 170, 100))
        d.polygon([(cx, 62 - h), (cx + w, 62), (cx + 6, 62)], fill=(186, 140, 80))
    # A minaret and a dome on the near side.
    d.rectangle([520, 30, 528, 66], fill=(232, 214, 176))
    d.polygon([(518, 30), (524, 18), (530, 30)], fill=(232, 214, 176))
    d.ellipse([540, 44, 590, 76], fill=(232, 214, 176))
    for x in (60, 100, 450, 620):
        palm(img, x, 68, 30, (60, 110, 50), (120, 90, 60))


def madrid(img, d):
    clouds(img, 12, (240, 248, 255), [(500, 80)])
    buildings(img, 0, 640, 68, 8, 20, (226, 196, 160), (160, 120, 90), 61)
    # The Puerta de Alcala: a granite gate of five openings.
    cx = 300
    d.rectangle([cx - 80, 28, cx + 80, 66], fill=(224, 214, 190))
    d.polygon([(cx - 30, 28), (cx, 12), (cx + 30, 28)], fill=(224, 214, 190))
    for k, x in enumerate(range(cx - 70, cx + 71, 32)):
        top = 36 if k == 2 else 42
        d.rectangle([x, top, x + 12, 66], fill=(90, 120, 170))
        d.ellipse([x, top - 6, x + 12, top + 6], fill=(90, 120, 170))
    # The leaning towers of the Puerta de Europa.
    d.polygon([(470, 66), (480, 8), (500, 8), (490, 66)], fill=(120, 140, 160))
    d.polygon([(560, 66), (550, 8), (570, 8), (580, 66)], fill=(120, 140, 160))
    for x in (40, 120, 620):
        tree(img, x, 70, 26, (60, 110, 60), (90, 60, 40))


def barcelona(img, d):
    sea(img, 58, (40, 120, 190), (140, 200, 230))
    d.ellipse([440, 34, 660, 110], fill=(90, 130, 80))        # Montjuic
    buildings(img, 0, 200, 70, 8, 20, (230, 210, 180), (170, 130, 100), 71)
    # The Sagrada Familia: a cluster of spires.
    for k, (x, h) in enumerate(((250, 48), (266, 56), (282, 60), (298, 56), (314, 48), (340, 40), (356, 44))):
        d.polygon([(x - 7, 68), (x - 5, 68 - h + 8), (x, 68 - h), (x + 5, 68 - h + 8), (x + 7, 68)], fill=(176, 150, 110))
        d.ellipse([x - 2, 68 - h - 2, x + 2, 68 - h + 2], fill=(240, 180, 60))
    d.rectangle([240, 50, 366, 68], fill=(160, 134, 96))
    for x in (60, 600):
        palm(img, x, 70, 28, (60, 120, 60), (120, 90, 60))


def berlin(img, d):
    clouds(img, 14, (220, 226, 234), [(0, 120), (300, 140)])
    buildings(img, 0, 640, 68, 10, 24, (170, 170, 176), (110, 116, 130), 81)
    # The Fernsehturm: a needle with a sphere.
    cx = 470
    d.rectangle([cx - 4, 10, cx + 4, 68], fill=(200, 200, 206))
    d.ellipse([cx - 13, 14, cx + 13, 38], fill=(190, 190, 200))
    d.rectangle([cx - 13, 24, cx + 13, 28], fill=(140, 140, 150))
    d.line([(cx, 10), (cx, -6)], fill=(220, 60, 50), width=2)
    # The Brandenburg Gate.
    cx = 230
    d.rectangle([cx - 70, 30, cx + 70, 38], fill=(220, 208, 170))
    d.rectangle([cx - 76, 26, cx + 76, 30], fill=(220, 208, 170))
    for x in range(cx - 66, cx + 67, 22):
        d.rectangle([x, 38, x + 6, 66], fill=(220, 208, 170))
    d.rectangle([cx - 14, 14, cx + 14, 26], fill=(80, 120, 100))       # the quadriga
    d.polygon([(cx - 12, 14), (cx, 6), (cx + 12, 14)], fill=(80, 120, 100))


def venice(img, d):
    d.ellipse([90, 44, 140, 94], fill=(255, 200, 120))           # the sun setting
    sea(img, 58, (60, 90, 140), (240, 160, 110))
    # The campanile of St Mark's.
    cx = 250
    d.rectangle([cx - 9, 12, cx + 9, 60], fill=(180, 90, 70))
    d.rectangle([cx - 11, 8, cx + 11, 18], fill=(230, 210, 180))
    d.polygon([(cx - 10, 8), (cx, -8), (cx + 10, 8)], fill=(90, 130, 110))
    # Domes of the Salute and the palaces along the water.
    d.ellipse([380, 26, 440, 60], fill=(226, 220, 206))
    d.rectangle([406, 16, 414, 28], fill=(226, 220, 206))
    d.rectangle([370, 44, 450, 60], fill=(226, 220, 206))
    buildings(img, 280, 360, 60, 10, 20, (220, 170, 130), (120, 60, 50), 91)
    buildings(img, 470, 640, 60, 8, 20, (230, 180, 140), (120, 60, 50), 93)
    # A gondola.
    d.polygon([(150, 66), (210, 66), (220, 60), (204, 64), (156, 64), (144, 58)], fill=(20, 20, 30))
    d.line([(190, 64), (196, 44)], fill=(20, 20, 30), width=1)


def sydney(img, d):
    clouds(img, 12, (250, 252, 255), [(100, 60)])
    sea(img, 56, (30, 110, 180), (130, 200, 230))
    # The Harbour Bridge.
    d.arc([330, 20, 600, 100], 180, 360, fill=(80, 90, 100), width=4)
    d.line([(330, 56), (600, 56)], fill=(80, 90, 100), width=3)
    for x in range(350, 590, 14):
        y = 60 - math.sqrt(max(0, 135 ** 2 - (x - 465) ** 2)) * 40 / 135
        d.line([(x, y), (x, 56)], fill=(100, 110, 120))
    d.rectangle([322, 40, 336, 60], fill=(200, 190, 170))
    d.rectangle([594, 40, 608, 60], fill=(200, 190, 170))
    # The Opera House: white shells over a podium.
    d.rectangle([110, 56, 290, 62], fill=(210, 190, 160))
    for x, h in ((130, 20), (170, 30), (210, 34), (250, 24)):
        d.polygon([(x, 56), (x + 30, 56 - h), (x + 40, 56)], fill=(246, 246, 240))
        d.line([(x + 30, 56 - h), (x + 40, 56)], fill=(200, 200, 196), width=1)


def athens(img, d):
    clouds(img, 10, (255, 236, 200), [(420, 90)])
    # The Acropolis: a rock, and the Parthenon on top.
    d.polygon([(120, 66), (170, 40), (420, 38), (480, 66)], fill=(176, 150, 110))
    d.rectangle([210, 24, 380, 30], fill=(236, 222, 190))
    d.polygon([(206, 24), (295, 10), (384, 24)], fill=(236, 222, 190))
    for x in range(214, 380, 12):
        d.rectangle([x, 30, x + 5, 40], fill=(236, 222, 190))
    d.rectangle([206, 40, 384, 43], fill=(236, 222, 190))
    buildings(img, 0, 120, 70, 6, 16, (240, 236, 224), (150, 160, 180), 101)
    buildings(img, 490, 640, 70, 6, 16, (240, 236, 224), (150, 160, 180), 103)
    for x in (60, 540, 600):
        tree(img, x, 70, 22, (110, 130, 80), (110, 90, 60))


PAINTERS = [napoli, rome, paris, chicago, london, newyork, tokyo, cairo, madrid, barcelona, berlin, venice,
            sydney, athens]
assert len(PAINTERS) == len(CITIES) == 14


# ---- the other way: what a player at the far end sees over the stands -------------------------

def hill(img, x0, x1, base, top, color) -> None:
    """A smooth hill from x0 to x1, its crest `top` above `base`."""
    d = ImageDraw.Draw(img)
    pts = [(x0, base)]
    for k in range(17):
        x = x0 + (x1 - x0) * k / 16
        pts.append((x, base - top * math.sin(math.pi * k / 16) ** 0.8))
    pts.append((x1, base))
    d.polygon(pts, fill=color)


def dome(img, cx, base, r, color, lantern=None) -> None:
    d = ImageDraw.Draw(img)
    d.rectangle([cx - r, base - r // 2, cx + r, base], fill=color)
    d.pieslice([cx - r, base - r // 2 - r, cx + r, base - r // 2 + r], 180, 360, fill=color)
    if lantern:
        d.rectangle([cx - 2, base - r // 2 - r - 8, cx + 2, base - r // 2 - r], fill=lantern)


def sail(img, x, base, h, color) -> None:
    d = ImageDraw.Draw(img)
    d.polygon([(x, base - 3), (x + 4, base - h), (x + 4, base - 3)], fill=color)
    d.rectangle([x - 4, base - 3, x + 10, base], fill=(60, 60, 70))


def napoli_back(img, d):
    clouds(img, 12, (240, 248, 255), [(380, 90)])
    # The Vomero hill with Castel Sant'Elmo's star-shaped walls, the Certosa below.
    hill(img, 60, 520, 70, 46, (96, 128, 86))
    d.polygon([(250, 30), (340, 30), (352, 40), (238, 40)], fill=(200, 186, 150))
    d.rectangle([262, 22, 328, 30], fill=(210, 196, 160))
    d.rectangle([340, 40, 400, 50], fill=(232, 220, 196))
    d.rectangle([346, 34, 360, 40], fill=(232, 220, 196))
    # Houses climbing the hill, yellow and red.
    buildings(img, 80, 540, 70, 6, 18, (236, 196, 120), (176, 96, 70), 7)
    buildings(img, 150, 300, 70, 14, 26, (224, 150, 110), (150, 80, 60), 13)
    # Posillipo going down to the sea on the right.
    sea(img, 62, (40, 110, 178), (120, 180, 220))
    hill(img, 470, 680, 66, 20, (80, 116, 72))
    pine(img, 560, 64, 24, (46, 96, 50), (90, 60, 40))
    pine(img, 40, 70, 28, (46, 96, 50), (90, 60, 40))


def rome_back(img, d):
    clouds(img, 14, (255, 240, 220), [(120, 80), (520, 70)])
    # The white marble monument with its colonnade and two winged chariots.
    cx = 320
    d.rectangle([cx - 120, 34, cx + 120, 66], fill=(240, 236, 226))
    for x in range(cx - 110, cx + 111, 10):
        d.rectangle([x, 38, x + 4, 56], fill=(206, 200, 188))
    d.rectangle([cx - 124, 30, cx + 124, 34], fill=(250, 248, 240))
    for x in (cx - 112, cx + 100):
        d.rectangle([x, 18, x + 12, 30], fill=(190, 170, 100))
        d.polygon([(x - 4, 22), (x + 6, 10), (x + 16, 22)], fill=(190, 170, 100))
    # Domes and bell towers of the old town.
    dome(img, 120, 66, 18, (180, 150, 120), (180, 150, 120))
    dome(img, 520, 66, 16, (196, 160, 130), (196, 160, 130))
    d.rectangle([570, 24, 582, 66], fill=(200, 150, 110))
    d.polygon([(568, 24), (576, 14), (584, 24)], fill=(160, 110, 80))
    buildings(img, 0, 640, 70, 6, 14, (226, 170, 120), (170, 110, 80), 17)
    for x in (30, 250, 420, 620):
        pine(img, x, 70, 26, (52, 90, 52), (100, 70, 50))


def paris_back(img, d):
    clouds(img, 14, (250, 252, 255), [(260, 120)])
    # The Seine and a stone bridge.
    sea(img, 60, (80, 110, 130), (150, 180, 200))
    d.rectangle([0, 56, 640, 60], fill=(190, 176, 150))
    for x in range(20, 640, 60):
        d.pieslice([x, 56, x + 40, 72], 180, 360, fill=(80, 110, 130))
    # The two towers of the cathedral and its spire.
    cx = 190
    d.rectangle([cx - 50, 22, cx - 18, 56], fill=(200, 190, 166))
    d.rectangle([cx + 18, 22, cx + 50, 56], fill=(200, 190, 166))
    d.rectangle([cx - 18, 34, cx + 18, 56], fill=(190, 180, 156))
    d.ellipse([cx - 9, 38, cx + 9, 50], fill=(110, 100, 120))
    d.polygon([(cx + 60, 34), (cx + 64, 6), (cx + 68, 34)], fill=(100, 96, 90))
    # The arch on its hill of avenues, and a lone dark tower.
    d.rectangle([400, 30, 460, 56], fill=(220, 206, 180))
    d.rectangle([418, 40, 442, 56], fill=(120, 140, 170))
    d.pieslice([418, 32, 442, 48], 180, 360, fill=(120, 140, 170))
    d.rectangle([540, 4, 566, 56], fill=(60, 62, 70))
    buildings(img, 470, 640, 56, 8, 18, (196, 186, 170), (110, 120, 140), 19)
    buildings(img, 0, 120, 56, 8, 18, (196, 186, 170), (110, 120, 140), 23)


def chicago_back(img, d):
    clouds(img, 12, (236, 244, 250), [(80, 100), (420, 120)])
    # Open water to the horizon, a long pier and its wheel.
    sea(img, 46, (60, 120, 170), (150, 200, 220))
    d.rectangle([0, 60, 640, 64], fill=(170, 160, 140))
    d.rectangle([60, 52, 300, 60], fill=(200, 180, 150))
    cx, cy, r = 220, 34, 18
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(220, 60, 60), width=2)
    for k in range(8):
        a = k * math.pi / 4
        d.line([(cx, cy), (cx + r * math.cos(a), cy + r * math.sin(a))], fill=(230, 230, 236))
    d.line([(cx, cy), (cx - 8, 52)], fill=(200, 200, 210), width=2)
    d.line([(cx, cy), (cx + 8, 52)], fill=(200, 200, 210), width=2)
    for x, h in ((380, 18), (460, 14), (540, 22)):
        sail(img, x, 50, h, (250, 250, 250))
    # A lighthouse at the end of the breakwater.
    d.rectangle([600, 30, 608, 60], fill=(240, 240, 236))
    d.rectangle([598, 26, 610, 30], fill=(210, 60, 50))


def london_back(img, d):
    clouds(img, 10, (200, 206, 214), [(60, 160), (380, 180)])
    sea(img, 62, (90, 100, 100), (140, 150, 150))
    # A bascule bridge between two stone towers.
    for x in (110, 230):
        d.rectangle([x, 16, x + 26, 62], fill=(200, 190, 160))
        d.polygon([(x - 2, 16), (x + 13, 4), (x + 28, 16)], fill=(90, 100, 120))
    d.rectangle([136, 22, 230, 26], fill=(110, 150, 190))
    d.rectangle([20, 50, 360, 54], fill=(110, 150, 190))
    # The great dome, and a glass shard over the river.
    dome(img, 440, 62, 24, (180, 180, 176), (200, 190, 140))
    d.rectangle([430, 40, 450, 62], fill=(170, 170, 166))
    d.polygon([(540, 62), (566, -2), (590, 62)], fill=(150, 170, 190))
    d.line([(566, -2), (566, 62)], fill=(190, 206, 220))
    buildings(img, 360, 640, 66, 8, 22, (150, 140, 130), (90, 90, 100), 37)


def newyork_back(img, d):
    d.ellipse([60, 8, 74, 22], fill=(244, 240, 214))
    sea(img, 58, (14, 22, 50), (60, 70, 110))
    # A suspension bridge: two stone towers with pointed arches, and its cables.
    for x in (140, 340):
        d.rectangle([x, 14, x + 24, 58], fill=(110, 96, 90))
        for k in (0, 12):
            d.rectangle([x + 3 + k, 24, x + 9 + k, 40], fill=(14, 22, 50))
    for a, b in ((0, 140), (164, 340), (364, 520)):
        d.line([(a, 50 if a == 0 else 14), ((a + b) / 2, 46), (b, 14 if b != 520 else 50)], fill=(170, 170, 190), width=1)
    d.rectangle([0, 50, 520, 53], fill=(120, 110, 104))
    for x in range(10, 520, 30):
        d.point((x, 51), fill=(250, 220, 130))
    # A spire of steel arches, lit, among the towers behind.
    buildings(img, 400, 640, 58, 14, 40, (30, 34, 60), (250, 210, 110), 43, lit=True)
    cx = 560
    d.rectangle([cx - 10, 14, cx + 10, 58], fill=(70, 76, 100))
    for k in range(4):
        d.pieslice([cx - 10 + k * 2, 6 + k * 4, cx + 10 - k * 2, 22 + k * 4], 180, 360, fill=(200, 200, 220))
    d.line([(cx, 6), (cx, -6)], fill=(220, 220, 230), width=2)


def tokyo_back(img, d):
    d.ellipse([540, 8, 554, 22], fill=(246, 240, 220))
    sea(img, 58, (20, 16, 50), (120, 60, 140))
    # A white suspension bridge over the bay, lit along its deck.
    for x in (170, 330):
        d.rectangle([x, 18, x + 10, 58], fill=(220, 220, 236))
    d.line([(40, 50), (175, 18), (255, 44), (335, 18), (470, 50)], fill=(200, 200, 230), width=1)
    d.rectangle([40, 50, 470, 53], fill=(180, 180, 210))
    for x in range(44, 470, 14):
        d.point((x, 51), fill=(250, 120, 200))
    # A five-storey pagoda on the near shore.
    cx = 560
    for k in range(5):
        w = 26 - k * 4
        y = 62 - k * 9
        d.rectangle([cx - w // 2, y - 6, cx + w // 2, y], fill=(150, 40, 50))
        d.polygon([(cx - w // 2 - 6, y - 6), (cx + w // 2 + 6, y - 6), (cx, y - 10)], fill=(40, 30, 60))
    d.line([(cx, 16), (cx, 6)], fill=(200, 170, 80), width=2)
    buildings(img, 0, 140, 68, 10, 30, (40, 30, 70), (240, 120, 200), 53, lit=True)


def cairo_back(img, d):
    d.ellipse([90, 10, 116, 36], fill=(255, 250, 220))
    # The Nile, with white-sailed boats.
    sea(img, 58, (50, 110, 150), (170, 210, 220))
    for x, h in ((160, 26), (300, 20), (430, 24)):
        d.polygon([(x, 56), (x + 4, 56 - h), (x + 18, 54)], fill=(250, 250, 244))
        d.rectangle([x - 8, 56, x + 22, 59], fill=(120, 80, 50))
    # The lattice tower like a lotus, and the domes and minarets of the citadel.
    cx = 520
    d.polygon([(cx - 8, 64), (cx - 5, 12), (cx + 5, 12), (cx + 8, 64)], fill=(150, 130, 100))
    d.polygon([(cx - 10, 12), (cx, 2), (cx + 10, 12)], fill=(150, 130, 100))
    dome(img, 60, 64, 22, (220, 200, 160), (220, 200, 160))
    for x in (28, 96):
        d.rectangle([x - 3, 18, x + 3, 64], fill=(226, 208, 170))
        d.polygon([(x - 4, 18), (x, 8), (x + 4, 18)], fill=(226, 208, 170))
    for x in (230, 380, 620):
        palm(img, x, 68, 30, (60, 110, 50), (120, 90, 60))


def madrid_back(img, d):
    clouds(img, 12, (240, 248, 255), [(120, 90)])
    # The royal palace: a long white front, and the cathedral's grey dome beside it.
    d.rectangle([60, 32, 360, 66], fill=(236, 230, 214))
    for x in range(70, 352, 14):
        d.rectangle([x, 38, x + 6, 48], fill=(150, 160, 180))
        d.rectangle([x, 52, x + 6, 62], fill=(150, 160, 180))
    d.rectangle([56, 28, 364, 32], fill=(246, 242, 230))
    dome(img, 430, 66, 28, (150, 156, 166), (150, 156, 166))
    d.rectangle([396, 46, 464, 66], fill=(230, 224, 208))
    # The sierra far off, with snow.
    d.polygon([(470, 50), (540, 26), (600, 40), (640, 30), (640, 50)], fill=(150, 160, 190))
    d.polygon([(530, 30), (540, 26), (552, 32)], fill=(250, 250, 255))
    buildings(img, 470, 640, 68, 8, 18, (226, 196, 160), (160, 120, 90), 63)
    for x in (20, 380, 560):
        tree(img, x, 70, 26, (60, 110, 60), (90, 60, 40))


def barcelona_back(img, d):
    clouds(img, 10, (250, 252, 255), [(300, 70)])
    # Tibidabo: a hill with its church, the city spreading below.
    hill(img, 120, 600, 64, 44, (90, 120, 80))
    d.rectangle([330, 20, 350, 34], fill=(220, 210, 190))
    d.polygon([(332, 20), (340, 8), (348, 20)], fill=(220, 210, 190))
    d.line([(340, 8), (340, 2)], fill=(200, 170, 60), width=2)
    buildings(img, 0, 640, 70, 6, 16, (230, 210, 180), (170, 130, 100), 73)
    # The column with the explorer on top, by the port.
    cx = 90
    d.rectangle([cx - 4, 16, cx + 4, 70], fill=(150, 140, 120))
    d.rectangle([cx - 12, 60, cx + 12, 70], fill=(170, 160, 140))
    d.ellipse([cx - 5, 8, cx + 5, 18], fill=(120, 110, 90))
    # A tower like a bullet, in blue and red.
    d.rounded_rectangle([520, 10, 548, 70], radius=12, fill=(90, 110, 170))
    for y in range(18, 66, 6):
        d.line([(522, y), (546, y)], fill=(200, 80, 70))
    palm(img, 600, 70, 28, (60, 120, 60), (120, 90, 60))


def berlin_back(img, d):
    clouds(img, 12, (220, 226, 234), [(220, 140), (500, 120)])
    # The parliament with its glass dome.
    cx = 200
    d.rectangle([cx - 100, 36, cx + 100, 66], fill=(206, 200, 184))
    for x in (cx - 100, cx + 76):
        d.rectangle([x, 26, x + 24, 66], fill=(196, 190, 174))
    for x in range(cx - 60, cx + 61, 12):
        d.rectangle([x, 42, x + 5, 62], fill=(150, 146, 136))
    d.pieslice([cx - 30, 14, cx + 30, 58], 180, 360, fill=(170, 200, 214))
    for k in range(-24, 25, 8):
        d.line([(cx + k, 20), (cx + k * 1.2, 36)], fill=(120, 140, 150))
    # The victory column with its golden figure.
    cx = 470
    d.rectangle([cx - 5, 14, cx + 5, 66], fill=(190, 160, 120))
    d.rectangle([cx - 14, 58, cx + 14, 66], fill=(170, 150, 120))
    d.rectangle([cx - 7, 30, cx + 7, 34], fill=(200, 170, 80))
    d.polygon([(cx - 8, 10), (cx, 2), (cx + 8, 10), (cx, 14)], fill=(230, 190, 60))
    buildings(img, 520, 640, 68, 10, 22, (170, 170, 176), (110, 116, 130), 83)
    for x in (360, 580, 30):
        tree(img, x, 70, 26, (70, 110, 70), (90, 70, 50))


def venice_back(img, d):
    sea(img, 56, (60, 110, 130), (150, 190, 190))
    clouds(img, 10, (255, 230, 200), [(400, 100)])
    # The stone bridge with its arcade over the canal.
    d.pieslice([140, 28, 360, 84], 180, 360, fill=(230, 220, 200))
    d.pieslice([196, 44, 304, 84], 180, 360, fill=(60, 110, 130))
    d.rectangle([200, 26, 300, 36], fill=(230, 220, 200))
    for x in range(206, 296, 14):
        d.rectangle([x, 28, x + 6, 34], fill=(150, 130, 110))
    # Palaces along the water, pink and ochre, with pointed windows.
    for x0, color in ((0, (220, 150, 140)), (380, (230, 190, 120)), (500, (210, 130, 110))):
        d.rectangle([x0, 26, x0 + 120, 58], fill=color)
        for x in range(x0 + 6, x0 + 116, 12):
            d.polygon([(x, 52), (x, 40), (x + 3, 36), (x + 6, 40), (x + 6, 52)], fill=(90, 60, 60))
    for x in (130, 360, 620):
        d.rectangle([x, 40, x + 3, 62], fill=(40, 60, 120))
        d.rectangle([x, 40, x + 3, 44], fill=(240, 240, 240))
    d.polygon([(420, 64), (480, 64), (490, 58), (474, 62), (426, 62), (414, 56)], fill=(20, 20, 30))


def sydney_back(img, d):
    clouds(img, 14, (250, 252, 255), [(380, 90)])
    # The city's tower with its golden turret, among the office blocks.
    buildings(img, 220, 520, 64, 16, 38, (170, 180, 196), (100, 130, 170), 97)
    cx = 380
    d.rectangle([cx - 3, 8, cx + 3, 64], fill=(180, 180, 186))
    d.rectangle([cx - 12, 14, cx + 12, 24], fill=(220, 180, 70))
    d.line([(cx, 8), (cx, -4)], fill=(200, 200, 210), width=2)
    # The sea, a beach and a lighthouse on the headland.
    sea(img, 58, (30, 110, 180), (130, 200, 230))
    d.rectangle([0, 62, 220, 70], fill=(240, 220, 170))
    hill(img, 500, 700, 66, 26, (90, 130, 80))
    d.rectangle([580, 20, 590, 44], fill=(250, 250, 246))
    d.rectangle([578, 16, 592, 20], fill=(230, 200, 80))
    for x in (60, 140, 470):
        tree(img, x, 66, 26, (90, 130, 90), (140, 120, 100))


def athens_back(img, d):
    clouds(img, 10, (255, 236, 200), [(120, 80)])
    # Lycabettus: a steep hill with a white chapel on the top.
    d.polygon([(260, 66), (320, 22), (340, 18), (360, 22), (430, 66)], fill=(130, 140, 90))
    d.rectangle([332, 10, 348, 20], fill=(250, 250, 246))
    d.polygon([(330, 10), (340, 4), (350, 10)], fill=(250, 250, 246))
    # The marble stadium's horseshoe, and the sea of the port beyond.
    sea(img, 56, (40, 110, 180), (140, 200, 230))
    d.rectangle([60, 48, 220, 66], fill=(240, 236, 224))
    for y in range(50, 66, 4):
        d.line([(64, y), (216, y)], fill=(210, 204, 190))
    buildings(img, 420, 640, 70, 6, 16, (240, 236, 224), (150, 160, 180), 107)
    for x in (30, 250, 450, 600):
        cypress(img, x, 70, 30, (60, 90, 60))


BACK_PAINTERS = [napoli_back, rome_back, paris_back, chicago_back, london_back, newyork_back, tokyo_back, cairo_back,
                 madrid_back, barcelona_back, berlin_back, venice_back, sydney_back, athens_back]
assert len(BACK_PAINTERS) == len(CITIES)
