# Reproducing the cartridge

This page lets anyone:

* **Reproduce** release 2.2.0: rebuild the same files from this repository,
  and check them against the published checksums.
* **Replicate** it: rebuild the cartridge from its generators and sources,
  on another machine, and get a working cartridge even where the bytes differ.

Everything that the build uses is in this repository or in the PRG32
repository, except four tools: the RISC-V compiler, QEMU, Python with Pillow,
and ffmpeg.

## 1. The environment used for 2.2.0

| Component | Version used | Needed for |
|-----------|--------------|------------|
| This repository | the commit tagged/merged as 2.2.0 | everything |
| [PRG32](https://github.com/riscv-prg32/PRG32) | `1fa8474427bb3998a79d2b350550efdb2578b3be` (2026-11-04), checked out next to this repository as `../PRG32` | cartridge ABI, build tool, Store tool, audio packer, QEMU firmware, firmware font |
| RISC-V compiler | `riscv32-esp-elf-gcc` 14.2.0, crosstool-NG `esp-14.2.0_20241119` (ESP-IDF 5.4 tools, in `~/.espressif/tools/riscv32-esp-elf/`) | cartridges |
| ESP-IDF | v5.4 | building PRG32's QEMU firmware |
| [PRG32 Multiplayer Server](https://github.com/riscv-prg32/PRG32-Multiplayer-Server) | 1.0.0, `6349b4bda14388ca35ca8da72dcc59d49ad23422` (2026-11-05) with LAN discovery added (`9d1e6d5` on the branch `feat/lan-discovery`), next to this repository as `../PRG32-Multiplayer-Server`, with its `npm install` done | online tests in QEMU and on the board |
| Node.js | 26.12.0 | the Multiplayer Server |
| Python `websockets` | 17.1 | the online test's observer |
| QEMU | Espressif `qemu-system-riscv32` 9.0.0 (`esp_develop_9.0.0_20240606`, in `~/.espressif/tools/qemu-riscv32/`) | screenshots, audio, preview |
| Python | 3.12.10 | generators, tools |
| Pillow | 13.0.0 | art generators, screenshots |
| ffmpeg | 9.0.2, with libx264 and AAC | preview video |
| Host C compiler | Apple clang 21.0.0 (any C99 compiler with ASan/UBSan) | host tests |
| OS | macOS 26.6 on arm64 | — |

Notes:

* The PRG32 checkout had two local changes: `dependencies.lock` (ESP-IDF
  component versions for the firmware), and LAN discovery in the firmware's
  multiplayer client, committed afterwards as `3a6a9e3` on the branch
  `feat/multiplayer-lan-discovery`. Neither affects the cartridge build.
* The QEMU firmware was built from that checkout, in ESP-IDF's environment
  (`. ~/esp-idf/export.sh`), with `python3 -m prg32 qemu build`, which
  regenerates `build-qemu/sdkconfig` and writes `build-qemu/qemu_flash.bin`,
  `qemu_efuse.bin` and `PRG32.elf`. It was configured with multiplayer on
  and the server URL `ws://192.168.1.155:8081`
  (`CONFIG_PRG32_MULTIPLAYER_SERVER_URL` in `build-qemu/sdkconfig`). The
  online test reads that address and redirects it, so the address itself
  does not matter.

## 2. Get the sources

```bash
git clone https://github.com/riscv-prg32/PRG32.git
```

```bash
git -C PRG32 checkout 1fa8474427bb3998a79d2b350550efdb2578b3be
```

```bash
git clone https://github.com/riscv-prg32/Azzurra-s-Pro-Tennis-Challenge.git
```

```bash
cd Azzurra-s-Pro-Tennis-Challenge
```

Install the ESP-IDF 5.4 tools (`install.sh esp32c6` in ESP-IDF installs the
compiler; `idf_tools.py install qemu-riscv32` installs QEMU) and Pillow:

```bash
python3 -m pip install Pillow==13.0.0
```

## 3. Rebuild

### Step 1: art and music (optional; the results are committed)

`scripts/build.sh` runs both generators first. To run them on their own:

```bash
python3 tools/build_art.py
```

```bash
python3 tools/build_audio.py
```

They are deterministic: no clock and no unseeded randomness. With Pillow
13.0.0 they reproduce the committed files byte for byte:

| File | SHA-256 |
|------|---------|
| `src/gen/art.inc` | `758e2d5b6496a63f2381635ba652eac51a2e7cc4bcde6dbde057f98079f26b0d` |
| `src/gen/music.inc` | `bf0a236ecc5293184edfb160c913a689405ad9a1429406b81632074f2fc4068c` |
| `audio/audio.json` | `a1b235eddafac21993570a86b296bfe79ec88621a97e08931aa5f9b37dc479d4` |

A different Pillow version may rasterise an ellipse or a box filter slightly
differently. The art would then differ by a few pixels, and so would every
checksum below. The game itself is the same. `git diff --stat src/gen` shows
whether your generators reproduced the committed files.

### Step 2: the cartridges

```bash
scripts/build.sh
```

The steps, all visible in the script:

1. regenerate the art and music;
2. pack the AUD0 instrument block with PRG32's
   `tools/prg32audio_pack.py`;
3. prove there are no relocations;
4. run `prg32 cartridge build --portable --cart-ram-kib 128 --entry-prefix
   azzurra` for `esp32c6` and `qemu`;
5. attach the Store trailer (metadata, icon, screenshot, colophon) with
   `prg32 store attach-metadata`;
6. check the 128 KiB package limit;
7. write `dist/SHA256SUMS`.

Expected output:

```
art: 14 cities, views 24361 B, courts 15490 B, 35 sprites 7600 B, palette 98 entries
audio: 21 instruments, 123 patterns (1968 B), 4 songs (985 B), 17 effects (125 B)
position independent: runs unchanged at any load address
[INFO] code=116928 mem=123576 audio=208
.../dist/azzurra-pro-tennis-esp32c6.prg32: package 127959/131072, RAM 123576/131072
[INFO] code=116928 mem=123576 audio=208
.../dist/azzurra-pro-tennis-qemu.prg32: package 127960/131072, RAM 123576/131072
```

Running the build twice gives byte-identical packages.

### Step 3: the tests

```bash
tests/run_tests.sh shots
```

The tests should end with `core: 622 checks, ok`, then `ok (0 failures)`
twice (the game, then the online tests), then
`metadata: version 2.2.0, 0 failures`. See [testing.md](testing.md).

### Step 4: the Store bundle

```bash
scripts/pack-store-bundle.sh
```

This writes `dist/azzurra-pro-tennis-2.2.0-store.zip`. It validates the
bundle with the CartridgeStore's ingestion code when `../CartridgeStore` is
present, and prints `READY for submission (store-ingest)`. The ZIP's
timestamps are pinned to the release date, so it is byte-reproducible too.

### Checksums of release 2.2.0

These are the checksums in `dist/SHA256SUMS`:

```
d05e479e0343135278e3a27bbce5c001cd833698d847bfe5b49f527374ff1672  azzurra-pro-tennis-esp32c6.prg32
ecdd3e72d3437a5fe46d5e021a5ec5c2e707493e918ef2afdd0b4fb46f9c7790  azzurra-pro-tennis-qemu.prg32
58629b080ba435aa9ec98684c0b323bea6a8719cf39d418ee7066dc86c127838  azzurra-pro-tennis-2.2.0-store.zip
```

Two things make the packages' checksums depend on more than the source:

* **The Store trailer embeds `assets/store/screenshot.png`.**
* **The bundle embeds `assets/store/preview.mp4`.**

The trailer and the bundle use the committed files. Re-recording the
preview, or regenerating the screenshot (steps 5 and 6), changes these
checksums, but not the code: `code=` and `mem=` stay the same.

| Committed asset | SHA-256 |
|-----------------|---------|
| `assets/store/icon.png` | `d378e05d66861bea379775c3eee7971aa1762ddde867d0e02e35cf5bb51ea67d` |
| `assets/store/screenshot.png` | `60844fee42205d687ad69a8b60fae2acdedd69fcbc95cdfe8694de855e576a47` |
| `assets/store/preview.mp4` | `d2abe8c2449fec79a78a44337013afe35e6419dea40b4c635e748c3d7c90dc2e` |

## 4. QEMU: screenshots and stereo audio

```bash
scripts/qemu_preview.py --script smoke --out build/qemu-smoke
```

The script:

1. copies PRG32's `build-qemu/qemu_flash.bin` and `qemu_efuse.bin` to a
   temporary directory (the PRG32 checkout is never written);
2. uploads `dist/azzurra-pro-tennis-qemu.prg32` into the copy with
   `prg32 qemu upload`;
3. boots QEMU headless (SDL's offscreen driver);
4. drives the console's UART keyboard: `w/s/a/d` for the D-pad, `h` for A,
   `j` for B, Enter for START, space for SELECT.

Boot sequence:

1. SETUP > AUDIO SETUP, where I2S MODE is switched to STEREO (the screenshot
   `_audio_menu.png` shows it);
2. back to the main menu;
3. RUN CARTRIDGE > cart0.

Outputs:

* **Frames:** read from the firmware's framebuffer (the `g_fb` pointer, found
  with `riscv32-esp-elf-nm` in `PRG32.elf`) with QMP `pmemsave`.
* **Audio:** the firmware's UART audio stream: 22,050 Hz, 16-bit,
  interleaved stereo.
* **Saved files** in `build/qemu-smoke/`: `title.png`, `menu.png`,
  `intro.png`, `serve.png`, `rally*.png`, `pause.png`, `audio.wav`
  (2 channels) and `console.log`.

## 4b. QEMU: online matches

```bash
scripts/qemu_netplay.py --match 1v1 --teams 0,1 --out build/qemu-netplay-1v1
scripts/qemu_netplay.py --match 2v2 --teams 0,1,0,1 --out build/qemu-netplay-2v2
```

The script:

1. starts the Multiplayer Server (`node src/server.js`) on a local port, with
   its data in `OUT/server-data`;
2. joins the room `azzurra-tennis:v2` itself, as a silent observer that
   records every relayed message to `OUT/observer.jsonl`;
3. starts one QEMU console per `--teams` entry, each with its own copy of
   the flash and its NVS erased, so that each has its own device identity.
   Each console's network is QEMU's user network, with a `guestfwd` rule
   that sends the firmware's server address to the local server;
4. on each console: boots the cartridge, walks the title menu to PLAY ONLINE
   (each key is checked on the screen and repeated if it was lost), sets the
   team and READY in the lobby, then plays random moves until the result
   screen;
5. writes `OUT/report.json`: each console's events and result (won or lost,
   read from the result screen's colours), and, per console, what the server
   relayed: the snapshot rate, the game speed and whether any two snapshots
   ever disagreed about an input.

`--audio` paces each firmware on audio credits, as `qemu_preview.py` does.
It is off by default. With credits, two or four consoles each ran at about
5 frames per second; without them, at 30 (both observed, from the frame
counter that the server relays). The cause is most likely the script's credit
threads, not the cartridge, but this has not been confirmed.

**With the ESP32-C6 board.** The board joins as one more console. Its
firmware needs LAN discovery (PRG32 with the change described in PRG32's
`docs/software/multiplayer_protocol.md`, "LAN Discovery"), or a server URL
compiled in that reaches this computer. Run the server on the LAN with
discovery on, from `../PRG32-Multiplayer-Server`:

```bash
HOST=0.0.0.0 PORT=8081 DATA_DIR=$PWD/../Azzurra-s-Pro-Tennis-Challenge/build/lan-server node src/server.js
```

Then, with the cartridge already in the board's slot `cart4` (the script
uploads nothing):

```bash
scripts/qemu_netplay.py --match 1v1 --teams 0 --external-server --port 8081 --board-port /dev/cu.usbmodem101 --board-url http://BOARD_IP --board-slot cart4 --board-team 1 --out build/qemu-netplay-board
```

The script restarts the cartridge on the board (`prg32 esp32c6 run`), walks
its menus with `prg32 esp32c6 key`, and starts the QEMU consoles only once the
board is READY. During the match it presses no key in the lobby and reads the
board's screen only a few times: each screenshot slows the board, and in
lockstep every console with it. The match end is seen when the board's
relayed tick stops; the result is then read from the board's screen. The
QEMU consoles reach the LAN server through the same `guestfwd` rule as above.

## 5. The 60-second preview

```bash
scripts/qemu_preview.py --script preview --video --seconds 150 --cut 0:14,28:56,RESULT-10:RESULT+8 --out build/qemu-preview
```

```bash
cp build/qemu-preview/preview.mp4 assets/store/preview.mp4
```

What the script does:

1. **Records 150 s of QEMU,** with picture and sound kept together.
   * Frames are taken on the audio clock (frame *n* is grabbed once *n*/12 s
     of audio has arrived), so the picture stays on the sound however fast
     QEMU runs.
   * The scripted player sets the menu to a one-game set, starts the world
     tour, serves, and runs and swings in a fixed pattern.
   * The recorder watches each frame for the result screen's panel (the
     round-won or game-over screen; `is_result_screen`). From that frame on,
     the player stops pressing keys, so the screen and its music play
     undisturbed.
   * The time of that frame is written to `capture.json` as
     `result_seconds`.
2. **Encodes the recording** to `raw.mp4`:
   * the 320 × 200 game area, scaled ×3 to 960 × 600 with nearest-neighbour;
   * H.264 (`libx264 -crf 24 -preset slow`, yuv420p, faststart);
   * AAC 128 kb/s, stereo, at 12 fps.
3. **Cuts and joins three spans of the recording** into `preview.mp4`, with
   a 0.15 s audio fade-in and a 0.25 s fade-out at each join:

   | Span | Length | Shows |
   |------|-------:|-------|
   | 0–14 s | 14 s | the title with its music, the menu, the intro |
   | 28–56 s | 28 s | rallies, effects only |
   | RESULT−10 s to RESULT+8 s | 18 s | the final point, then the result screen and its music |

   That is 60 s in total. `--recut --cut …` cuts `raw.mp4` again without
   QEMU.

Every frame and every sample in the preview comes from the QEMU firmware
running the cartridge; nothing is drawn or mixed afterwards.

QEMU's timing relative to the host varies from run to run, so a new
recording shows a different match. For 2.1.0 the result screen, round won 1-0
by Azzurra and Viola, appeared at 70.7 s (observed). 2.2.0 ships the same
recording: its only change is the pause key, and the preview never pauses. The final cut is 60.0 s:

* video: H.264 960 × 600 at 12 fps;
* audio: AAC stereo, 22,050 Hz;
* size: 1,444,561 bytes.

If the run prints `warning: no audio for 10 s`, the host was too busy for
QEMU's audio link (for 2.0.0 this happened once, while host tests ran at the
same time). Run it again on an otherwise idle machine.

## 6. The splash screenshot

```bash
python3 tools/make_store_art.py build/qemu-smoke/rally2.png
```

This writes:

* `assets/store/icon.png`: 64 × 64, drawn from the game's own sprites.
* `assets/store/screenshot.png`: a QEMU frame without the firmware's status
  bands, palettised to 64 colours.

Rebuild the cartridges afterwards (step 2): the screenshot goes into their
Store trailer.

## 7. Replicating on another machine

These steps run on any OS that has the tools above, Linux included. The host
tests need only a C99 compiler and Python. Without the RISC-V tools you can
still:

* run every rule and screen through the host tests;
* regenerate all art and music.

With them, you can rebuild the cartridges; with QEMU, repeat the captures.

The README's **host render** screenshots come from `tests/run_tests.sh
shots`. They are produced by the cartridge's own code, which the tests check
against both framebuffer models.
