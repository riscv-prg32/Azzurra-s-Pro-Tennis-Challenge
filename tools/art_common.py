#!/usr/bin/env python3
"""Shared helpers of the art tools: colours, palette reduction, run-length rows, font.

reduce_view(), _dither() and encode_rows() are adapted from tools/build_art.py of
The Trerrote Connection (PRG32 project family, MIT).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from PIL import Image

import palette as pal

ROOT = Path(__file__).resolve().parents[1]
PRG32 = Path(os.environ.get("PRG32_REPO", ROOT.parent / "PRG32")).resolve()

TRANSPARENT = pal.FIXED_INDEX["clear"]


def hexrgb(h: str) -> tuple[int, int, int]:
    v = int(h.lstrip("#"), 16)
    return (v >> 16) & 255, (v >> 8) & 255, v & 255


def to565(rgb) -> int:
    return ((rgb[0] >> 3) << 11) | ((rgb[1] >> 2) << 5) | (rgb[2] >> 3)


def fixed_rgb(name: str) -> tuple[int, int, int]:
    """The exact colour a fixed palette entry shows on the panel."""
    return pal.rgb888(pal.FIXED_RGB565[pal.FIXED_INDEX[name]])


def mix(a, b, t: float):
    return tuple(int(round(a[k] + (b[k] - a[k]) * t)) for k in range(3))


# ---- reducing a painting to the firmware's cube ---------------------------------

def reduce_view(img: Image.Image, count: int, taken: dict[int, int], dither: bool = True):
    """Choose at most `count` colours that each own one cube cell, and map the picture.

    Pixels are grouped by the cell they fall in, so every group's mean is an exact
    colour of that cell. A group in a cell already held (by a fixed colour or by the
    city's court) becomes that colour. The cheapest groups are then merged into
    their nearest neighbour until `count` remain. No colour crosses a cell, so no
    hue changes. Returns (colours as RGB565, pixels as indices into colours).
    """
    w, h = img.size
    px = img.convert("RGB").load()
    groups: dict[int, list[int]] = {}
    cell_of = [[0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            rgb = px[x, y]
            cell = pal.cube_index(to565(rgb))
            if cell < 16:
                cell = 16 + (rgb[0] * 6 // 256) * 36 + (rgb[1] * 6 // 256) * 6 + rgb[2] * 6 // 256
            cell_of[y][x] = cell
            g = groups.setdefault(cell, [0, 0, 0, 0])
            g[0] += 1
            g[1] += rgb[0]
            g[2] += rgb[1]
            g[3] += rgb[2]

    def color(cell: int) -> int:
        if cell in taken:
            return taken[cell]
        g = groups[cell]
        mean = to565((g[1] // g[0], g[2] // g[0], g[3] // g[0]))
        value = pal._nearest_in_cell(mean, cell)
        return value if value not in pal.NAMED else value ^ 1

    merged: dict[int, int] = {}
    live = sorted(groups)
    # Cells already held cost nothing: they are counted apart.
    own = [c for c in live if c not in taken]
    while len(own) > count:
        best = None
        for a in own:
            ca = color(a)
            for b in live:
                if a == b:
                    continue
                cost = groups[a][0] * pal.distance(ca, color(b))
                if best is None or cost < best[0]:
                    best = (cost, a, b)
        _, a, b = best
        merged[a] = b
        for k in range(4):
            groups[b][k] += groups[a][k]
        live.remove(a)
        own.remove(a)

    def final(cell: int) -> int:
        while cell in merged:
            cell = merged[cell]
        return cell

    live = sorted(live, key=lambda c: -groups[c][0])
    index = {cell: i for i, cell in enumerate(live)}
    colors = [color(c) for c in live]
    pixels = [[index[final(cell_of[y][x])] for x in range(w)] for y in range(h)]
    if dither:
        _dither(px, pixels, colors)
    return colors, pixels


BAYER = ((0.2, 0.6), (0.8, 0.4))


def _dither(px, pixels, colors) -> None:
    """Ordered 2 x 2 dither between two neighbouring colours where the painted tone
    lies between them, so that a sky's gradient does not collapse into flat bands."""
    rgb = [pal.rgb888(c) for c in colors]
    n = len(rgb)
    h, w = len(pixels), len(pixels[0])
    for y in range(h):
        for x in range(w):
            o = px[x, y]
            if any(max(abs(o[k] - q[k]) for k in range(3)) > 10
                   for q in (px[max(x - 1, 0), y], px[min(x + 1, w - 1), y], px[x, max(y - 1, 0)],
                             px[x, min(y + 1, h - 1)])):
                continue
            a = pixels[y][x]
            ca = rgb[a]
            best = None
            for b in range(n):
                if b == a:
                    continue
                cb = rgb[b]
                d = [cb[k] - ca[k] for k in range(3)]
                span = d[0] * d[0] + d[1] * d[1] + d[2] * d[2]
                if span == 0 or span > 60 * 60:
                    continue
                t = sum((o[k] - ca[k]) * d[k] for k in range(3)) / span
                if not 0.3 <= t <= 0.7:
                    continue
                miss = sum((o[k] - ca[k] - t * d[k]) ** 2 for k in range(3))
                if miss < span * 0.05 and (best is None or miss < best[0]):
                    best = (miss, b, t)
            if best and best[2] > BAYER[y & 1][x & 1]:
                pixels[y][x] = best[1]


# ---- run-length rows ------------------------------------------------------------

def encode_rows(rows: list[list[int]], bits: int, data: list[int], seen: dict) -> list[int]:
    """Append rows to `data`: (index << (8 - bits)) | run, run 1..2^(8-bits)-1; run 0
    means the next byte holds a longer run. Identical rows share one encoding.
    Returns the offset of every row."""
    offsets = []
    shift = 8 - bits
    for row in rows:
        key = tuple(row)
        if key in seen:
            offsets.append(seen[key])
            continue
        seen[key] = len(data)
        offsets.append(len(data))
        x = 0
        while x < len(row):
            run = 1
            while x + run < len(row) and row[x + run] == row[x] and run < 255:
                run += 1
            assert 0 <= row[x] < (1 << bits), row[x]
            if run < (1 << shift):
                data.append((row[x] << shift) | run)
            else:
                data += [row[x] << shift, run]
            x += run
    return offsets


def c_bytes(data, per: int = 24) -> str:
    data = list(data)
    return "\n".join("    " + ",".join(str(v) for v in data[i:i + per]) + "," for i in range(0, len(data), per))


def array(ctype: str, name: str, values) -> str:
    values = list(values)
    return f"static const {ctype} {name}[{len(values)}] = {{\n{c_bytes(values)}\n}};"


# ---- the font: PRG32's own 8 x 8 glyphs -----------------------------------------

def firmware_font() -> dict[str, list[int]]:
    """The 8 x 8 font of the PRG32 firmware, read from its source, so that the text the
    cartridge composes matches the console's own lettering."""
    src = (PRG32 / "components/prg32/prg32_display_qemu_rgb.c").read_text(encoding="utf-8")
    block = re.search(r"static const uint8_t g_font8\[96\]\[8\][^{]*\{(.*?)\n\};", src, re.S).group(1)
    font: dict[str, list[int]] = {}
    for m in re.finditer(r"\['(\\.|.)' - 32\]\s*=\s*\{([^}]*)\}", block):
        ch = m.group(1)
        if ch.startswith("\\"):
            ch = ch[1]
        font[ch] = [int(v, 16) for v in m.group(2).split(",")]
    return font
