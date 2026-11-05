#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
sdk="${PRG32_REPO:-$here/../PRG32}"
mkdir -p "$here/build" "$here/dist"
for arch in qemu esp32c6; do
  (cd "$sdk" && python3 -m prg32 cartridge build "$here/game.c" \
    --portable --entry-prefix azzurra_tennis --name "Azzurra's Pro Tennis Challenge" \
    --architecture "$arch" --cart-ram-kib 128 --required-feature audio \
    --required-feature multiplayer --multiplayer --build-dir "$here/build/$arch" \
    --out "$here/dist/azzurra-pro-tennis-$arch.prg32")
done
echo "Built dist/azzurra-pro-tennis-{qemu,esp32c6}.prg32"
