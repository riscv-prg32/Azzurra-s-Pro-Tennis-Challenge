# AGENTS.md

Guidance for automated coding agents and maintainers of Azzurra's Pro Tennis
Challenge, a PRG32 portable cartridge for the 128 KiB profile.

## Rules that are easy to break

### Code

- **Rules live in `src/az_core.h`, with no PRG32 calls.** Anything that
  decides a score, a serve, a line call, a bounce or a computer player's move
  goes there, and gets a test in `tests/test_core.c`.
- **One source per build.** `src/azzurra.c` includes the rest. Do not add
  compiler flags to `scripts/build.sh`.
- **No pointers in initialised static data.** Portable cartridges have no
  relocations; `tools/check_relocatable.py` enforces this on every build.
- **No libc, no floats, no 64-bit division** in cartridge code. `memset` and
  `memcpy` are defined in `azzurra.c`.
- **Everything advances on the 33 ms tick.** Physics, AI, music and effects
  run in `update_step`; drawing never changes game state.

### Online play

- **The rules must stay deterministic.** Online consoles run in lockstep:
  each one runs `az_core.h` on the same seed and the same inputs. Anything
  that changes the game state must depend only on the game state and the
  four players' inputs: no clock, no frame count, no draw state, no
  `prg32_*` call. `tests/test_net.c` compares a hash of the game state on
  every console at every tick.
- **The far end is drawing only.** The view from the far team's end (`v.rev`)
  mirrors coordinates in the renderer and the HUD. Only `p[i].rot`, which
  turns a far human's D-pad, reaches the rules.
- **The wire format is in `src/az_net.h`** and fits 71 bits (`x`, `y`,
  `sprite`, `flags`: 16 bits each; `input`: 7). If you change it, change
  `NET_SIGNATURE`, so that old and new cartridges never meet in one room.
- **One controller per console.** `prg32_input_read_player(1)` returns
  player 0's keys, so there is no second local player.

### Keys that are easy to get wrong

- **`PRG32_BTN_SELECT == PRG32_BTN_START`.** Never give SELECT its own
  meaning; the pause uses B to quit.
- **START never pauses.** It is the joystick's centre click. A + B together
  pauses (online: opens the leave prompt); A resumes, B quits.
- **A + B + DOWN restarts the firmware.** Scripts that press random keys
  must not hold B with a direction (`scripts/qemu_netplay.py` presses no B).

### Generated files

- **These are generated:** `src/gen/*`, `audio/audio.json` and
  `assets/png/*`. Edit `tools/` and run `tools/build_art.py` and
  `tools/build_audio.py`, which `scripts/build.sh` also runs. Commit the
  regenerated files.

### Pictures and text

- **Indexed colour only.** Every picture is palette indices:
  - sprites use the 32 sprite colours (5 bits);
  - backgrounds use 6-bit indices.
  New colours go through `tools/palette.py`: two colours on one screen may
  not share a cube cell. `build_art.py` asserts this.
- **Text is capitals and ASCII 32–95** (the firmware font as stored in
  `font_bits`), at most 40 characters per line.
- **A row that changes must be marked dirty.** `tests/test_game.c` compares
  the panel with a clean repaint, and the indexed framebuffer with the direct
  one.

### Sound

- **Music only on the title, round-won, game-over and champions' screens.**
  During play (and in the intro, pause and demo) there are only effects.
  `tests/test_game.c` fails if a song plays in a match.
- **Original material only.** Music, pictures and names are written for this
  game. Do not copy or imitate a melody, sprite, logo or layout from an
  existing game or song.

### Releases

- **The version is in `metadata/metadata.json`, `metadata/colophon.json` and
  `CHANGELOG.md`.** `tests/run_tests.sh` checks that they agree.

### Never do

- **Never publish** to the Cartridge Store from a script or an agent. No
  credentials (tokens, passwords, Store URLs with keys) in the repository.
- **Do not modify the PRG32 checkout** (`../PRG32`).
  `scripts/qemu_preview.py` works on a temporary copy of the flash image.
- **Do not test on an attached board without asking.** An upload overwrites a
  cartridge slot. When asked, back up the slot first
  (`esptool read_flash`) and say which slot was used.

### Honest claims

- **Every number in `docs/` is measured, observed or estimated, and says
  which.** On the ESP32-C6 board, 2.1.0 was observed running (screens,
  local matches); no frame rate was measured there. Do not write that
  something was measured when it was not.

## Workflow

Tests, with screenshots to `build/shots/`:

```bash
tests/run_tests.sh shots
```

Build the packages, then pack and validate the Store bundle:

```bash
scripts/build.sh && scripts/pack-store-bundle.sh
```

QEMU screenshots and stereo audio:

```bash
scripts/qemu_preview.py --script smoke --out build/qemu-smoke
```

The 60 s Store preview, then copy `build/qemu-preview/preview.mp4` to
`assets/store/preview.mp4`:

```bash
scripts/qemu_preview.py --script preview --video --seconds 150 --cut 0:14,28:56,RESULT-10:RESULT+8 --out build/qemu-preview
```

Online, with the real PRG32 Multiplayer Server (`../PRG32-Multiplayer-Server`)
and two to four QEMU consoles; `--teams` gives each console's team:

```bash
scripts/qemu_netplay.py --match 2v2 --teams 0,1,0,1 --out build/qemu-netplay-2v2
```

With the board as one more console (only when asked; the cartridge must
already be in the slot, and the server must run on the LAN with discovery on,
as in `docs/reproduce.md` section 4b):

```bash
scripts/qemu_netplay.py --match 1v1 --teams 0 --external-server --port 8081 --board-port /dev/cu.usbmodem101 --board-url http://BOARD_IP --board-slot cart4 --board-team 1 --out build/qemu-netplay-board
```

The board must not get keys in the lobby: a stray UP + A reaches LEAVE.

The exact environment, the versions and the expected checksums are in
[docs/reproduce.md](docs/reproduce.md). When gameplay, art or audio change,
update the numbers quoted in `docs/`, the README screenshots
(`docs/media/`), and the preview.

## Where things are

| Topic | File |
|-------|------|
| Rules, controls, the tour | `docs/game-design.md` |
| Source layout, renderer, budgets | `docs/architecture.md` |
| Palette, sprites, backgrounds | `docs/graphics.md` |
| Music and effects | `docs/audio.md` |
| Tests | `docs/testing.md` |
| Rebuilding bit for bit | `docs/reproduce.md` |
| Store bundle | `docs/store_publishing.md` |
