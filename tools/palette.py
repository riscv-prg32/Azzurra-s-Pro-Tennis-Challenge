#!/usr/bin/env python3
"""The indexed colour model of Azzurra's Pro Tennis Challenge.

PRG32's ESP32-C6 framebuffer holds one 8-bit palette index per pixel. Every
RGB565 colour a cartridge passes to the firmware is quantised to a cell of the
system palette's 6x6x6 cube (`prg32_gfx_index_for_rgb565_unlocked`). The entry
of that cell can be overwritten with `prg32_palette_set`, which gives a free
choice of exact colours under one condition: two colours on screen at the same
time must not fall in the same cell. `solve()` meets that condition for the
FIXED colours below plus each city's own colours, and `check()` proves it.

Adapted from tools/palette.py of The Trerrote Connection and You Have Got
Pizza: Deluxe Edition (PRG32 project family, MIT).
"""
from __future__ import annotations


def rgb565(hex_rgb: str) -> int:
    v = int(hex_rgb.lstrip("#"), 16)
    r, g, b = (v >> 16) & 255, (v >> 8) & 255, v & 255
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def rgb888(value: int) -> tuple[int, int, int]:
    r, g, b = (value >> 11) & 31, (value >> 5) & 63, value & 31
    return ((r * 527 + 23) >> 6, (g * 259 + 33) >> 6, (b * 527 + 23) >> 6)


NAMED = (0x0000, 0xFFFF, 0xF800, 0x07E0, 0x001F, 0xFFE0, 0x07FF, 0xF81F)


def cube_index(color: int) -> int:
    """Exact port of prg32_gfx_index_for_rgb565_unlocked()."""
    if color in NAMED:
        return NAMED.index(color)
    r = ((color >> 11) & 31) * 5 // 31
    g = ((color >> 5) & 63) * 5 // 63
    b = (color & 31) * 5 // 31
    return 16 + r * 36 + g * 6 + b


# Colours shared by every screen. The first 32 are the sprites' colours: sprite
# rows are run-length coded with 5 bits of colour, so a sprite can only use
# these (the last one, "clear", is transparency and is never drawn). The next 16
# belong to the stands, the back wall and the interface, and are drawn by the
# court picture or by code. Each city then adds SURFACE_COLORS for its court and
# up to VIEW_COLORS for its skyline (tools/build_art.py).
SPRITE_FIXED = {
    "ink": "#14121c",     # outlines, text shadow
    "white": "#f6f8f0",   # kit, net tape, lines on the logo
    "cream": "#fff3d6",   # text
    "ball": "#dcf03c",    # optic yellow
    "balld": "#9cb024",
    "gold": "#f2b43a",    # trophy, highlighted text
    "goldd": "#a8701c",
    "goldl": "#ffe49a",
    "skin": "#eaa985",
    "skind": "#b8735a",
    "skinl": "#fdd6b8",
    "blonde": "#f2cc62",  # hair
    "brown": "#6c4024",
    "dark": "#2c1e1a",
    "shirt": "#2f8fe0",   # team colour, swapped per character
    "shirtd": "#1b58a6",
    "grey": "#a9adb6",
    "greyd": "#5c5f6a",
    "red": "#d8322c",
    "redd": "#801c22",
    "green": "#3aa24a",
    "greend": "#1c6232",
    "navy": "#1c2c5c",
    "orange": "#f08a28",
    "purple": "#7242a2",
    "pink": "#ea82aa",
    "racket": "#e04848",  # racket frame
    "shadow": "#2a2c36",  # shadows on the court
    "panel": "#0e1c38",   # interface panels
    "panell": "#2a4c84",
    "cyan": "#62d8ea",
    "clear": "#14121c",   # transparency in sprites: never drawn, same value as ink
}
GROUND_FIXED = {
    "stand": "#6e7380",   # concrete of the stands
    "standd": "#4a4e5c",
    "standl": "#9196a2",
    "seat": "#b03634",
    "seat2": "#2f55a2",
    "board": "#0b1730",   # sponsor boards
    "boardl": "#f4f4ec",
    "wall": "#123c2c",    # the dark green wind screen behind the court
    "walld": "#0a281c",
    "post": "#d8dce2",    # net posts, umpire chair
    "mesh": "#22262e",    # the net
    "meshl": "#4a505c",
    "chair": "#7a5232",
    "tarp": "#1a5a3e",
    "hudbar": "#08101e",
    "hudline": "#f2b43a",
}
FIXED = {**SPRITE_FIXED, **GROUND_FIXED}
SPRITE_COUNT = len(SPRITE_FIXED)
FIXED_COUNT = len(FIXED)
assert SPRITE_COUNT == 32 and FIXED_COUNT == 48
SURFACE_COLORS = 10       # each city: its court (8 roles) and the rival pair's shirt (2)
VIEW_COLORS = 40          # and its skyline, up to this many


def _cell_bounds(cell: int):
    """Inclusive RGB565 channel ranges that quantise to one cube cell."""
    v = cell - 16
    r, g, b = v // 36, (v // 6) % 6, v % 6

    def span(level: int, top: int) -> tuple[int, int]:
        values = [c for c in range(top + 1) if c * 5 // top == level]
        return values[0], values[-1]
    return span(r, 31), span(g, 63), span(b, 31)


def _nearest_in_cell(color: int, cell: int) -> int:
    (r0, r1), (g0, g1), (b0, b1) = _cell_bounds(cell)
    r = min(max((color >> 11) & 31, r0), r1)
    g = min(max((color >> 5) & 63, g0), g1)
    b = min(max(color & 31, b0), b1)
    return (r << 11) | (g << 5) | b


def distance(a: int, b: int) -> int:
    ra, ga, ba = rgb888(a)
    rb, gb, bb = rgb888(b)
    return 2 * (ra - rb) ** 2 + 4 * (ga - gb) ** 2 + 3 * (ba - bb) ** 2


ALIAS_LIMIT = 500


def solve(wanted: list[int], taken: dict[int, int] | None = None) -> list[int]:
    """Give every colour its own cube cell, moving as little as possible.

    A colour whose cell is free keeps its value. A colour nearly equal to the
    holder of its cell becomes that holder. Any other collision moves it to the
    nearest colour of the nearest free cell. Deterministic.
    """
    holders = dict(taken or {})
    out: list[int] = []
    for color in wanted:
        cell = cube_index(color)
        if cell in holders and distance(color, holders[cell]) <= ALIAS_LIMIT:
            out.append(holders[cell])
            continue
        if color in NAMED or cell in holders:
            best = None
            for candidate in range(16, 232):
                if candidate in holders:
                    continue
                moved = _nearest_in_cell(color, candidate)
                if moved in NAMED or cube_index(moved) != candidate:
                    continue
                cost = distance(color, moved)
                if best is None or cost < best[0]:
                    best = (cost, moved, candidate)
            assert best is not None
            color, cell = best[1], best[2]
        holders[cell] = color
        out.append(color)
    return out


FIXED_RGB565 = solve([rgb565(v) for v in FIXED.values()])
FIXED_INDEX = {name: i for i, name in enumerate(FIXED)}


def fixed_holders() -> dict[int, int]:
    return {cube_index(c): c for c in FIXED_RGB565}


def solve_view(colors: list[int], taken: dict[int, int] | None = None) -> list[int]:
    """Final RGB565 values of a city's colours, next to the fixed ones."""
    return solve(colors, {**fixed_holders(), **(taken or {})})


def check(palette: list[int]) -> int:
    """Colours of one screen may share a cube cell only if they are equal."""
    seen: dict[int, int] = {}
    failures = 0
    for value in palette:
        cell = cube_index(value)
        if cell in seen and seen[cell] != value:
            failures += 1
        seen[cell] = value
    return failures


if __name__ == "__main__":
    n = check(FIXED_RGB565)
    print(f"palette: {FIXED_COUNT} fixed colours ({SPRITE_COUNT} for sprites), {n} collisions")
    raise SystemExit(1 if n else 0)
