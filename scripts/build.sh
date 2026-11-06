#!/usr/bin/env bash
# Build the Azzurra's Pro Tennis Challenge cartridges for every PRG32 target.
#
#   scripts/build.sh            # esp32c6 + qemu
#   scripts/build.sh qemu       # one architecture
#
# Environment:
#   PRG32_REPO   path to the PRG32 repository (default ../PRG32)
#   IDF_EXPORT   ESP-IDF export script, sourced when riscv32-esp-elf-gcc is
#                neither on PATH nor under ~/.espressif (default
#                $HOME/esp-idf/export.sh)
#
# Outputs dist/azzurra-pro-tennis-<arch>.prg32 (Store-ready: metadata, icon,
# screenshot and colophon attached), dist/SHA256SUMS, and prints the budgets.
#
# Adapted from scripts/build.sh of The Trerrote Connection and Drumfight Napoli 97
# (PRG32 family, MIT).
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
prg32_repo="$(cd "${PRG32_REPO:-"$repo_dir/../PRG32"}" && pwd)"
name="azzurra-pro-tennis"
cart_ram_kib=128         # PRG32's large profile, the default on ESP32-C6 and QEMU
package_limit=131072     # one 128 KiB cartridge slot: code + audio + Store trailer

if ! command -v riscv32-esp-elf-gcc >/dev/null 2>&1; then
  # The toolchain alone is enough; prefer it to the whole ESP-IDF environment.
  toolchain="$(ls -d "$HOME"/.espressif/tools/riscv32-esp-elf/*/riscv32-esp-elf/bin 2>/dev/null | tail -1 || true)"
  if [[ -n "$toolchain" ]]; then
    export PATH="$toolchain:$PATH"
  else
    idf_export="${IDF_EXPORT:-$HOME/esp-idf/export.sh}"
    # shellcheck disable=SC1090
    [[ -f "$idf_export" ]] && source "$idf_export" >/dev/null 2>&1
  fi
fi
command -v riscv32-esp-elf-gcc >/dev/null 2>&1 || {
  echo "error: riscv32-esp-elf-gcc not found; install ESP-IDF or source its export.sh" >&2
  exit 2
}

archs=("$@")
[[ ${#archs[@]} -eq 0 ]] && archs=(esp32c6 qemu)

build_dir="$repo_dir/build"
dist_dir="$repo_dir/dist"
mkdir -p "$build_dir" "$dist_dir"

prg32() { (cd "$prg32_repo" && python3 -m prg32 "$@"); }

# 1. Regenerate art and music (deterministic; the results are committed).
python3 "$repo_dir/tools/build_art.py"
python3 "$repo_dir/tools/build_audio.py"

# 2. AUDIO block: the SID-like instruments. The music itself is cartridge data.
python3 "$prg32_repo/tools/prg32audio_pack.py" "$repo_dir/audio/audio.json" \
  --out "$build_dir/audio.block" >/dev/null

# 3. Prove position independence (no relocations: hosts load anywhere).
PRG32_REPO="$prg32_repo" python3 "$repo_dir/tools/check_relocatable.py" | tail -1

for arch in "${archs[@]}"; do
  raw="$build_dir/$name-$arch.raw.prg32"
  out="$dist_dir/$name-$arch.prg32"
  log="$build_dir/$name-$arch.build.log"
  # 4. Portable cartridge. Sprites are required; audio and multiplayer are optional,
  # so the same image still runs, silently or offline, on a host without them.
  prg32 cartridge build "$repo_dir/src/azzurra.c" \
    --portable \
    --required-feature sprites \
    --optional-feature audio \
    --optional-feature audio_plus \
    --optional-feature multiplayer \
    --entry-prefix azzurra \
    --name "Azzurra's Pro Tennis Challenge" \
    --architecture "$arch" \
    --cart-ram-kib "$cart_ram_kib" \
    --audio-block "$build_dir/audio.block" \
    --out "$raw" | tee "$log" | grep -E "code=|error" || true
  sizes="$(grep -o 'code=[0-9]* mem=[0-9]* audio=[0-9]*' "$log" | tail -1)"
  mem="$(sed -E 's/.*mem=([0-9]+).*/\1/' <<< "$sizes")"

  # 5. Store trailer: metadata, icon, screenshot and colophon.
  prg32 store attach-metadata "$raw" --out "$out" \
    --metadata "$repo_dir/metadata/metadata.json" \
    --icon "$repo_dir/assets/store/icon.png" \
    --screenshot "$repo_dir/assets/store/screenshot.png" \
    --colophon "$repo_dir/metadata/colophon.json" \
    --architecture "$arch" >/dev/null

  size=$(wc -c < "$out" | tr -d ' ')
  echo "$out: package $size/$package_limit, RAM $mem/$(( cart_ram_kib * 1024 ))"
  (( size <= package_limit )) || { echo "error: package too large" >&2; exit 1; }
  (( mem <= cart_ram_kib * 1024 )) || { echo "error: executable RAM exceeded" >&2; exit 1; }
done

# 6. Inspect what was produced.
for f in "$dist_dir"/$name-*.prg32; do
  prg32 cartridge summary "$f" > "$build_dir/$(basename "$f").summary.txt"
  prg32 store inspect-metadata "$f" > "$build_dir/$(basename "$f").metadata.txt"
done
(cd "$dist_dir" && shasum -a 256 $name-*.prg32 > SHA256SUMS)
echo "summaries in build/*.summary.txt; checksums in dist/SHA256SUMS"
