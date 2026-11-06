#!/usr/bin/env python3
"""The stadium and the court, in perspective, as one indexed picture per surface.

Every pixel of the court picture is classified by casting it back to the ground
(geometry.ground_at): inside the doubles court or outside it, on a line or not,
in a stand, on the wind screen. Lines are supersampled 4 x 4, so a far line stays
one clean pixel wide and a near one grows, as it should. The picture holds
palette roles, not colours: the city's SURFACE colours decide whether it is
clay, grass or hard court, by day or under lights.
"""
from __future__ import annotations

import math

from PIL import Image

import geometry as g
import palette as pal

FIX = pal.FIXED_INDEX
SURF = pal.FIXED_COUNT          # the first surface role
IN, IN2, OUT, OUT2, LINE, LINED, WEAR, EDGE = range(SURF, SURF + 8)

CLAY, GRASS, HARD = 0, 1, 2
SIDE_WALL = 1060                # the side wind screens, from the court's centre
SIDE_WALL_H = 120


def h32(*v: int) -> int:
    x = 2166136261
    for k in v:
        x = ((x ^ (k & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return x


# ---- lines ------------------------------------------------------------------------

LINES = []  # (x0, y0, x1, y1) rectangles on the ground, in cm (widths exaggerated a little)
_w, _b = 6, 10
for sgn in (-1, 1):
    LINES.append((sgn * g.DOUBLES - _w, -g.HALF_L, sgn * g.DOUBLES + _w, g.HALF_L))      # doubles sidelines
    LINES.append((sgn * g.SINGLES - _w, -g.HALF_L, sgn * g.SINGLES + _w, g.HALF_L))      # singles sidelines
    LINES.append((-g.DOUBLES, sgn * g.HALF_L - _b, g.DOUBLES, sgn * g.HALF_L + _b))      # baselines
    LINES.append((-g.SINGLES, sgn * g.SERVICE - _w, g.SINGLES, sgn * g.SERVICE + _w))    # service lines
    LINES.append((-_w, sgn * g.HALF_L - 30, _w, sgn * g.HALF_L))                         # centre marks
LINES.append((-_w, -g.SERVICE, _w, g.SERVICE))                                           # centre service line


def on_line(x: float, y: float) -> bool:
    for x0, y0, x1, y1 in LINES:
        if x0 <= x <= x1 and y0 <= y <= y1:
            return True
    return False


# ---- the crowd --------------------------------------------------------------------

SHIRTS = ["red", "white", "shirt", "green", "orange", "navy", "pink", "gold", "purple", "cyan", "cream", "grey"]
HAIRS = ["dark", "brown", "blonde", "dark", "greyd", "dark"]
SKINS = ["skin", "skind", "skinl", "skin"]


def crowd_pixel(x: int, y: int, top: int) -> int:
    """Tiers of seated spectators, 5 pixels a tier: a head (2 x 2) over a shirt."""
    tier = (y - top) // 5
    ry = (y - top) % 5
    seat = (x + tier * 2) // 4
    rx = (x + tier * 2) % 4
    if (seat + tier * 7) % 23 == 0:                # an aisle
        return FIX["standl"] if ry < 4 else FIX["standd"]
    if ry == 4:
        return FIX["standd"]
    hv = h32(seat, tier, 7)
    if hv % 9 == 0:                                # an empty seat
        return FIX["seat"] if (seat + tier) & 1 else FIX["seat2"]
    if ry <= 1:
        if rx in (1, 2):
            if ry == 0:
                return FIX[HAIRS[(hv >> 4) % len(HAIRS)]]
            return FIX[SKINS[(hv >> 8) % len(SKINS)]]
        return FIX["stand"]
    if rx == 3:
        return FIX["stand"]
    return FIX[SHIRTS[(hv >> 12) % len(SHIRTS)]]


# ---- the umpire's chair --------------------------------------------------------------

def chair_pixels() -> dict[tuple[int, int], int]:
    """A tall chair beside the net post, on the left, with the umpire on it."""
    out: dict[tuple[int, int], int] = {}
    cx, cy = -(g.NET_POST + 120), 0

    def box3(x0, x1, z0, z1, color, yy=cy):
        sx0, sy0 = g.project(x0, yy, z1)
        sx1, sy1 = g.project(x1, yy, z0)
        for py in range(int(round(sy0)), int(round(sy1)) + 1):
            for px in range(int(round(sx0)), int(round(sx1)) + 1):
                out[(px, py)] = color

    box3(cx - 40, cx - 34, 0, 190, FIX["chair"])        # legs
    box3(cx + 34, cx + 40, 0, 190, FIX["chair"])
    box3(cx - 40, cx + 40, 100, 108, FIX["chair"])      # a rung
    box3(cx - 46, cx + 46, 186, 196, FIX["chair"])      # the platform
    box3(cx - 22, cx + 22, 196, 262, FIX["navy"])       # the umpire's jacket
    box3(cx - 10, cx + 10, 262, 288, FIX["skin"])       # head
    box3(cx - 11, cx + 11, 282, 292, FIX["dark"])       # hair
    box3(cx - 50, cx + 50, 236, 244, FIX["post"])       # the arm rests
    return out


# ---- the picture --------------------------------------------------------------------

def surface_role(kind: int, x: float, y: float, inside: bool, sx: int, sy: int) -> int:
    n = h32(sx, sy, kind)
    if kind == GRASS:
        stripe = int((y + 4000) // 165) & 1
        worn = inside and abs(y) > g.HALF_L - 260 and abs(x) < 300 + (abs(y) - g.HALF_L + 260)
        if worn and (n & 3):
            return WEAR
        if inside:
            return IN2 if stripe else IN
        return OUT2 if stripe else OUT
    if kind == CLAY:
        # Brushed clay: long streaks across the court, and scuffs behind the baselines.
        streak = h32(int((y + 4000) // 38), kind) & 7
        if abs(y) > g.HALF_L - 120 and abs(y) < g.HALF_L + 260 and abs(x) < 420 and (n & 7) < 3:
            return WEAR
        if inside:
            return IN2 if (streak == 0 or (n & 31) == 0) else IN
        return OUT2 if (streak == 0 or (n & 31) == 0) else OUT
    # Hard court: flat, with a faint speckle.
    if inside:
        return IN2 if (n & 63) == 0 else IN
    return OUT2 if (n & 63) == 0 else OUT


def court_image(kind: int) -> list[list[int]]:
    rows = []
    wall_top = g.project(0, g.WALL_Y, g.WALL_H)[1]
    wall_bottom = g.project(0, g.WALL_Y, 0)[1]
    chair = chair_pixels()
    for sy in range(g.COURT_Y, g.GAME_H):
        row = []
        for sx in range(g.GAME_W):
            c = None
            if (sx, sy) in chair:
                c = chair[(sx, sy)]
            elif sy + 0.5 < wall_top:
                c = crowd_pixel(sx, sy, g.COURT_Y)
            else:
                # Cast the pixel to the ground, if it is below the wall's foot.
                if sy + 0.5 >= wall_bottom:
                    gx, gy = g.ground_at(sx + 0.5, sy + 0.5)
                    if abs(gx) > SIDE_WALL:
                        # Beyond the side screen: the screen itself, or the stand above it.
                        wx = math.copysign(SIDE_WALL, gx)
                        # Where along the side screen is this pixel? Solve for the y that
                        # puts x = wx on this column, then compare heights.
                        d = g.F * wx / (sx + 0.5 - 160)
                        yy = g.CAM_D + g.HALF_L - d
                        top = g.project(wx, yy, SIDE_WALL_H)[1]
                        base = g.project(wx, yy, 0)[1]
                        if sy + 0.5 >= top:
                            c = FIX["wall"] if sy + 0.5 < base - 1 else FIX["walld"]
                        else:
                            c = crowd_pixel(sx, sy, g.COURT_Y)
                    else:
                        inside = abs(gx) <= g.DOUBLES and abs(gy) <= g.HALF_L
                        # Supersampled line coverage.
                        hits = 0
                        for sy4 in range(4):
                            for sx4 in range(4):
                                qx, qy = g.ground_at(sx + (sx4 + 0.5) / 4, sy + (sy4 + 0.5) / 4)
                                hits += on_line(qx, qy)
                        if hits >= 6:
                            c = LINE
                        elif hits >= 3:
                            c = LINED
                        else:
                            c = surface_role(kind, gx, gy, inside, sx, sy)
                        if c in (OUT, OUT2) and abs(gx) > SIDE_WALL - 40:
                            c = EDGE
                else:
                    # The far wind screen, with a trim at top and bottom.
                    if sy + 0.5 < wall_top + 1 or sy + 0.5 >= wall_bottom - 1:
                        c = FIX["walld"]
                    else:
                        c = FIX["wall"]
                    gx = (sx + 0.5 - 160) * g.depth(g.WALL_Y) / g.F
                    if abs(gx) > SIDE_WALL:
                        c = crowd_pixel(sx, sy, g.COURT_Y) if sy + 0.5 < g.project(gx, g.WALL_Y, SIDE_WALL_H)[1] else FIX["walld"]
            row.append(c)
        rows.append(row)
    return rows


# ---- the net, as a sprite drawn in depth order ------------------------------------------

def net_sprite() -> tuple[Image.Image, int, int]:
    """RGBA picture of the net and its posts, and where its top-left corner goes."""
    x0 = int(math.floor(g.project(-g.NET_POST - 8, 0)[0]))
    x1 = int(math.ceil(g.project(g.NET_POST + 8, 0)[0]))
    y0 = int(math.floor(g.project(0, 0, g.NET_H_POST + 8)[1]))
    y1 = int(math.ceil(g.project(0, 0, 0)[1]))
    w, h = x1 - x0 + 1, y1 - y0 + 1
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    from art_common import fixed_rgb
    ink, white, grey, greyd = (fixed_rgb(n) + (255,) for n in ("ink", "white", "grey", "greyd"))
    d = g.depth(0)
    for py in range(h):
        for qx in range(w):
            sx, sy = x0 + qx + 0.5, y0 + py + 0.5
            x = (sx - 160) * d / g.F
            z = g.H - (sy - g.HZ) * d / g.F
            if z < -2:
                continue
            if abs(abs(x) - g.NET_POST) < 8 and z <= g.NET_H_POST + 6:
                px[qx, py] = grey if x < 0 else greyd
                continue
            if abs(x) > g.NET_POST:
                continue
            top = g.net_height(x)
            if z > top:
                continue
            if z > top - 7:
                px[qx, py] = white                   # the tape
            elif abs(x) < 4:
                px[qx, py] = white                   # the centre strap
            elif ((x0 + qx) + (y0 + py)) & 1 or z < 6:
                px[qx, py] = ink                     # the mesh: see-through
    return img, x0, y0


def sponsor_slots() -> list[tuple[int, int, int, int]]:
    """Where the boards hang on the far wind screen: (x, y, w, h) on the screen."""
    top = g.project(0, g.WALL_Y, g.WALL_H - 22)[1]
    bottom = g.project(0, g.WALL_Y, 18)[1]
    y = int(round(top))
    h = int(round(bottom)) - y
    xs = g.project(-g.DOUBLES - 380, g.WALL_Y)[0], g.project(g.DOUBLES + 380, g.WALL_Y)[0]
    left, right = int(round(xs[0])), int(round(xs[1]))
    n = 3
    gap = 4
    w = (right - left - gap * (n - 1)) // n
    return [(left + k * (w + gap), y, w, h) for k in range(n)]
