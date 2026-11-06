# Testing

## Host tests

```bash
tests/run_tests.sh
```

`tests/run_tests.sh shots` does the same and also writes every screen to
`build/shots/*.png` (this needs Pillow).

The host tests need only a C99 compiler with AddressSanitizer/UBSan (clang or
gcc), Python 3 and the PRG32 checkout, for its public headers. They do not
need the RISC-V toolchain or a board. Compiling against the firmware's
headers means that a call whose signature differs from the firmware's fails
to compile.

| Step | What it proves |
|------|----------------|
| `tools/palette.py` | The 48 fixed colours occupy 48 different cells of the firmware's colour cube. |
| `tests/test_core.c` | The rules (99 checks). See below. |
| `tests/test_game.c` | The whole cartridge (`src/azzurra.c` as is) on a fake PRG32 (`tests/host/host_prg32.h`). See below. |
| metadata check | The metadata, colophon and audio JSON parse; the versions agree; the ABI strings are right; `CHANGELOG.md` has the version. |

### `test_core.c`

* **Scoring:**
  * 15-all, deuce, advantage both ways;
  * sets to 1, 2 and 4 games;
  * 4-3 goes on, 5-3 wins;
  * the tie-break at 4-4: 6-6 is called, 7-6 goes on, 8-6 wins.
* **Serving:**
  * the order Azzurra, rival, Viola, rival over eight games;
  * deuce then ad side, with the receiver changing;
  * the tie-break rotation (1, 2, 2).
* **Courts:**
  * every service box, for both teams and both sides;
  * the lines are in;
  * wide and long balls are out.
* **Ball:**
  * `az_launch` lands within 8 cm of its target for every flight time from
    10 to 50 ticks;
  * a low ball is stopped by the net and loses the point;
  * a serve into the wrong box is a fault, then a double fault.
* **Matches:**
  * nine matches between computer players, at levels 0 to 8 on all three
    surfaces, each finish;
  * each replays bit for bit from its seed;
  * no player ever leaves the arena.

### `test_game.c`

The test flow:

1. the title has its music;
2. the menu sets an exhibition in London and 2 games;
3. the tour starts with a silent intro;
4. a scripted beginner plays a whole match (points are scored, the ball is
   struck, no music plays);
5. START pauses and resumes;
6. the result screen has music;
7. the title falls into the demo, which plays points without music;
8. every city's intro renders, and the grass and the two floodlit courts
   render in play;
9. the round-won, game-over and champions' screens render, the champions with
   their song.

On every screen, two invariants are checked:

* **No stale pixels.** The incremental frame equals a clean repaint of the
  same state.
* **Same picture on both hosts.** The ESP32-C6's indexed framebuffer, shown
  through the system palette, equals QEMU's direct-colour framebuffer.

Expected output (version 2.0.0, Apple clang 21, macOS):

```
palette: 48 fixed colours (32 for sprites), 0 collisions
  match level  0 surface 0: 2-0 in   8 points,  1.1 min
  ...
core: 99 checks, ok (0 failures)
play: 14 points, 37 shots, app 6, games 1-2
render: ... rect calls, ... row sprites, ... presents, ... pixels
ok (0 failures)
metadata: version 2.0.0, 0 failures
```

The core and game tests are deterministic (fixed seeds and a fake clock), so
the numbers above repeat on any host with the same compiler semantics.

### Bugs these tests found

* `az_launch` truncated the vertical speed towards zero. When a ball started
  above its own fall (a smash, a high volley), it landed one tick late: up to
  1.3 m long, and often out. It now rounds down.
* The sprite row buffer was 64 bytes: the net, the logo and the boards are
  wider, and they overwrote memory. UBSan found it, and the buffer is now
  `W + 64` bytes.

## Build checks

`scripts/build.sh` also runs:

* `tools/check_relocatable.py`, which fails the build if the image has any
  relocation, such as a pointer in initialised data;
* the 128 KiB package limit, on both packages;
* `prg32 store attach-metadata`, which validates the metadata.

## QEMU

```bash
scripts/qemu_preview.py --script smoke --out build/qemu-smoke
```

This boots the real PRG32 QEMU firmware and does the following:

1. switches the audio to stereo in the setup menu;
2. runs the cartridge;
3. goes through the title, menu, intro, serve, rally, pause and resume;
4. saves a PNG of each screen and the stereo `audio.wav`.

The Store preview is made the same way (see [reproduce.md](reproduce.md)).

## ESP32-C6

The ESP32-C6 package is the same code built for that architecture. The host
test proves that its indexed framebuffer shows the same picture as QEMU, but
**it has not been run on a board for this release**. The frame rate on the
board's SPI panel has not been measured.

The renderer sends only changed rows, in at most two presents per frame. On
an idle court only the ball, its shadow and the players move, which is a few
dozen rows.

To try it on a board running the PRG32 firmware, upload the cartridge over
Wi-Fi from the PRG32 checkout (PRG32 `docs/software/cartridges.md`):

```bash
python3 -m prg32 esp32c6 upload ../Azzurra-s-Pro-Tennis-Challenge/dist/azzurra-pro-tennis-esp32c6.prg32 --url http://192.168.4.1
```
