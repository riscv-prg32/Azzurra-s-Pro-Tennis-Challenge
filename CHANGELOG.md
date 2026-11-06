# Changelog

## 2.0.0 — 2026-11-06

A rewrite for the PRG32 128 KiB cartridge profile.

### Game

* Real doubles rules, in `src/az_core.h`:
  * the serving order Azzurra, rival, Viola, rival;
  * serves from the deuce and ad sides into the diagonal box;
  * faults, lets, double faults, deuce and advantage;
  * sets to 1, 2 or 4 games, with a tie-break at 4-4.
* Fourteen cities on clay, grass and hard courts, two of them at night. Each
  has its own skyline, rivals and court colours. The computer players get
  quicker and steadier round by round.
* Shots and controls:
  * drives, lobs, volleys and smashes, aimed with the D-pad or by timing;
  * serve quality depends on the toss;
  * the surfaces bounce differently.
* Modes:
  * exhibition mode in any city;
  * a demo on the idle title;
  * two local players (the second controller plays Viola).
* Result screens ignore keys for their first 2 s, so a button held from the
  rally does not skip them.
* The game runs on fixed 33 ms ticks with catch-up, so it keeps the same
  speed at any frame rate.

### Graphics

* All sprites and backgrounds are indexed colour:
  * 98-entry palettes, solved so that every colour owns its own cell of the
    firmware's colour cube (the ESP32-C6's indexed framebuffer shows exactly
    what QEMU shows);
  * 5-bit sprites and 6-bit backgrounds, coded as run-length rows.
* A broadcast view with a perspective court that matches the rules' own
  projection, depth-sorted players and net, and sponsor boards.
* The renderer sends only the rows that changed, in at most two presents per
  frame.

### Audio

* An original SID-like stereo soundtrack plays on the title, round-won,
  game-over and champions' screens. It has four songs on up to eight voices,
  with hard-panned comping, a ping-pong arpeggio and an echo.
* During play there is no music, only 17 stereo-panned effects: racket by
  shot type, bounce, net, line calls, chimes and the crowd.

### Tooling and documentation

* Deterministic art and music generators: `tools/build_art.py` and
  `tools/build_audio.py`.
* Host tests:
  * `tests/test_core.c`: the rules, 99 checks;
  * `tests/test_game.c`: the whole cartridge, the repaint invariant, and the
    indexed and direct framebuffers.
* `scripts/qemu_preview.py`: QEMU screenshots, stereo audio capture and the
  60 s Store preview.
* A reproducible Store bundle with the preview, checked by the Store's own
  ingestion code.
* Documentation in `docs/`, including a full reproduction guide.

### Fixed (compared with 1.x)

* The net collision was at the wrong height and position.
* The out lines did not match the drawn lines.
* A team could serve twice in a row.
* SELECT could not be reached.
* Physics ran once per drawn frame.
* The near baseline was off the screen.
* The screen was repainted in full every frame.
* Sustained chords had no instruments.
* Removed: the unsynchronised network mode.

## 1.0.0 — 2026-11-05

* First version: a single `game.c`.
