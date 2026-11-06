#!/usr/bin/env python3
"""Store art, from the game's own sprites and from a real emulator frame.

  python3 tools/make_store_art.py [frame.png]

assets/store/icon.png        64 x 64: Azzurra serving on a clay court
assets/store/screenshot.png  320 x 200: a frame captured from the QEMU firmware
                             (scripts/qemu_preview.py), palettised so that it stays
                             small in the cartridge's Store trailer
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from PIL import Image, ImageDraw  # noqa: E402

import art_sprites as sp  # noqa: E402
from art_common import fixed_rgb  # noqa: E402


def icon() -> Image.Image:
    img = Image.new("RGB", (64, 64))
    d = ImageDraw.Draw(img)
    for y in range(64):
        t = y / 63
        d.line([(0, y), (63, y)], fill=(int(40 + 150 * t), int(120 + 100 * t), int(210 + 30 * t)))
    d.polygon([(0, 64), (64, 64), (64, 44), (0, 44)], fill=(200, 100, 58))
    d.line([(0, 52), (64, 48)], fill=(244, 244, 236), width=1)
    frames = dict(zip(sp.FRAMES, sp.draw_player("back")))
    serve = frames["smash"]
    img.paste(serve, (16, 6), serve)
    ball = sp.ball_sprite().resize((8, 8), Image.NEAREST)
    img.paste(ball, (40, 2), ball)
    d.rectangle([0, 0, 63, 63], outline=fixed_rgb("gold"))
    return img


def main() -> int:
    out = ROOT / "assets/store"
    out.mkdir(parents=True, exist_ok=True)
    icon().quantize(32, dither=Image.Dither.NONE).save(out / "icon.png", optimize=True)
    if len(sys.argv) > 1:
        frame = Image.open(sys.argv[1]).convert("RGB")
        if frame.size == (320, 240):   # strip the firmware's status bands
            frame = frame.crop((0, 20, 320, 220))
        frame.quantize(64, dither=Image.Dither.NONE).save(out / "screenshot.png", optimize=True)
    print({p.name: p.stat().st_size for p in out.glob("*.png")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
