#!/usr/bin/env bash
# Host tests for Azzurra's Pro Tennis Challenge (no RISC-V toolchain needed).
#
#   tests/run_tests.sh          palette, rules, cartridge flow, render invariant, metadata
#   tests/run_tests.sh shots    also render every screen to build/shots/*.png (Pillow)
#
# PRG32_REPO points to the PRG32 checkout (default ../PRG32); its public headers
# are used, so a signature that differs from the firmware fails to compile.
# The generated sources (src/gen/*.inc) are committed; run tools/build_art.py and
# tools/build_audio.py first if you changed the art or the music.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
prg32="$(cd "${PRG32_REPO:-$root/../PRG32}" && pwd)"
out="$root/build/tests"
mkdir -p "$out"
cflags=(-std=c99 -Wall -Wextra -Werror -Wno-unused-function -Wno-unused-const-variable -O1 -g -fsanitize=address,undefined
        -I "$root/src" -I "$root/tests" -I "$root/tests/host"
        -I "$prg32/components/prg32/include" -I "$prg32/components/prg32_audio/include")

fail=0
python3 "$root/tools/palette.py" || fail=1

cc "${cflags[@]}" "$root/tests/test_core.c" -o "$out/test_core"
"$out/test_core" || fail=1

cc "${cflags[@]}" "$root/tests/test_game.c" -o "$out/test_game"
if [[ "${1:-}" == "shots" ]]; then
  shots="$root/build/shots"
  mkdir -p "$shots"
  "$out/test_game" "$shots" || fail=1
  python3 - "$shots" <<'PY'
import sys
from pathlib import Path
from PIL import Image
for ppm in sorted(Path(sys.argv[1]).glob("*.ppm")):
    Image.open(ppm).save(ppm.with_suffix(".png"))
    ppm.unlink()
PY
else
  "$out/test_game" || fail=1
fi

# Metadata must parse and the places that carry the version must agree.
python3 - "$root" <<'PY' || fail=1
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
meta = json.loads((root / "metadata/metadata.json").read_text(encoding="utf-8"))
colophon = json.loads((root / "metadata/colophon.json").read_text(encoding="utf-8"))
json.loads((root / "audio/audio.json").read_text(encoding="utf-8"))
errors = []
if meta["version"] != colophon["version"]:
    errors.append("metadata and colophon versions differ")
if meta["abi"] != "prg32-metadata-1.0" or colophon["abi"] != "prg32-colophon-1.0":
    errors.append("unexpected ABI strings")
if meta.get("entry_prefix") != "azzurra":
    errors.append("entry_prefix is not azzurra")
if meta["version"] not in (root / "CHANGELOG.md").read_text(encoding="utf-8"):
    errors.append("CHANGELOG.md has no entry for this version")
for e in errors:
    print("FAIL metadata:", e)
print(f"metadata: version {meta['version']}, {len(errors)} failures")
sys.exit(1 if errors else 0)
PY
exit $fail
