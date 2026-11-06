#!/usr/bin/env python3
"""The court and the camera: one source of truth for tools/ and, through
src/gen/art.inc, for the cartridge.

World units are centimetres. X runs across the court (positive to the right of
the screen), Y along it (0 at the net, positive towards the camera: the near
baseline is at Y = +HALF_L), Z is height above the ground.

The camera is a pinhole behind and above the near baseline, looking along -Y:

    d  = CAM_D + HALF_L - Y           distance from the camera plane
    sx = 160 + F * X / d
    sy = HZ + F * (H - Z) / d

so that the far half of the court is drawn smaller than the near half, as in a
television broadcast. The cartridge evaluates the same integer formulas
(src/az_core.h: az_project).
"""
from __future__ import annotations

# The court: ITF dimensions in centimetres.
HALF_L = 1189          # net to baseline
SERVICE = 640          # net to service line
SINGLES = 411          # half width, singles (411.5)
DOUBLES = 549          # half width, doubles (548.5)
NET_POST = 640         # the posts stand 91.4 cm outside the doubles lines
NET_H_POST = 107
NET_H_MID = 91

# The camera (chosen so that the near baseline is at y = 182, the far one at 98,
# and the near doubles court is 262 pixels wide).
F = 852
H = 879
CAM_D = 3567
HZ = -28

# The screen.
GAME_W, GAME_H = 320, 200
HUD_H = 10             # score bar
VIEW_Y = 10            # the city skyline
VIEW_H = 40
COURT_Y = VIEW_Y + VIEW_H   # the stands, the wall and the court, to the bottom
COURT_IMG_H = GAME_H - COURT_Y
WALL_Y = -HALF_L - 640      # the wind screen behind the far baseline
WALL_H = 130


def depth(y: float) -> float:
    return CAM_D + HALF_L - y


def project(x: float, y: float, z: float = 0.0) -> tuple[float, float]:
    d = depth(y)
    return 160 + F * x / d, HZ + F * (H - z) / d


def ground_at(sx: float, sy: float) -> tuple[float, float]:
    """The point of the ground (z = 0) seen at screen position (sx, sy)."""
    d = F * H / (sy - HZ)
    return (sx - 160) * d / F, CAM_D + HALF_L - d


def net_height(x: float) -> float:
    ax = min(abs(x), NET_POST)
    return NET_H_MID + (NET_H_POST - NET_H_MID) * ax / NET_POST


if __name__ == "__main__":
    for name, y in (("far baseline", -HALF_L), ("far service", -SERVICE), ("net", 0),
                    ("near service", SERVICE), ("near baseline", HALF_L), ("wall", WALL_Y)):
        print(f"{name:14s} y={project(0, y)[1]:6.1f}  doubles x={project(-DOUBLES, y)[0]:6.1f}..{project(DOUBLES, y)[0]:6.1f}")
    print("net top", project(0, 0, NET_H_MID)[1], "player 175cm near", F * 175 / depth(HALF_L), "far", F * 175 / depth(-HALF_L))
