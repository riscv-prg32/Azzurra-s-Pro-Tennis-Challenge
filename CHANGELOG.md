# Changelog

## Unreleased

### Changed

* **A + B pauses; START never does.** START is the joystick's centre click,
  pressed by accident while running. Pressing A and B together now pauses a
  local match (that tick is not played, so the chord strikes nothing); in
  the pause A resumes and B quits to the title. Online, A + B opens the
  prompt, where B leaves the match and A plays on; the match keeps running,
  and the console sends neither A nor B until both are released. START does
  nothing during a match.

## 2.1.0 — 2026-11-06

Singles, and online play through the PRG32 Multiplayer Server.

### Game

* **MATCH: 1 VS 1 or 2 VS 2.** Singles is played on the singles court, with
  singles serving and lines (`az_new_match(..., singles)` in
  `src/az_core.h`). Doubles is Azzurra and Viola, as before.
* **PLAY ONLINE.** A lobby on the title menu. Consoles join the room, pick a
  team and press READY; the lowest player ID is the host and sets the match,
  the city and the games. The match starts when every console is ready, after
  a 3 s countdown:
  * 1 vs 1 between two consoles;
  * 2 vs 2 with two to four consoles, and the computer in each free place
    (one to three computer players);
  * 2 vs 2 with four consoles, all human.
* **Each console sees the match from its own end.** The far team's consoles
  see the court turned round: the players, the ball and the umpire's chair
  change sides, the HUD lists the console's own team first, the sound panning
  is mirrored, and the D-pad is turned so that UP always runs towards the net.
* **Lockstep.** The consoles exchange only their inputs, five ticks ahead,
  through the server's fields `x`, `y`, `sprite`, `flags` and `input`
  (`src/az_net.h`). Every console runs the same rules on the same inputs, so
  every console shows the same match. A console that goes silent for 2.5 s,
  or leaves, ends the match for all of them, with a message.
* **No pause online.** START shows a prompt: B leaves the match, START plays
  on.

### Fixed

* **The pause's quit key.** On PRG32, SELECT is the same key as START, so
  2.0.0's "SELECT quits to the title" could never work. B quits now.
* **PLAYERS: 2 is removed.** PRG32 has one controller per console
  (`prg32_input_read_player(1)` returns the first controller's keys), so
  the second local player was the first one twice. Two people now play on
  two consoles, online.

### Graphics

* **A back view of every city.** Each of the fourteen cities has a second
  skyline, the one behind the other end of the court, with its own palette:
  for example the hills behind the Napoli court, instead of the bay. The
  tools that paint them are in `tools/art_cities.py`; the preview sheet is
  `assets/png/cities_back.png`.

### Tests

* `tests/test_net.c`: two to four consoles on a simulated relay with random
  latency. It checks that every console has the same game state on every
  tick, the view from each end, that no music plays, that all consoles agree
  on the result, and that a console that drops out ends the match cleanly.
* `scripts/qemu_netplay.py`: the real Multiplayer Server and two to four
  PRG32 QEMU consoles, played to the result screen. With `--board-port`
  and `--board-url`, an ESP32-C6 board plays as one more console.
* The cartridge was run on an ESP32-C6 board (see `docs/testing.md`).

### Known issues

* **In QEMU, an online console can stall** after a few minutes: the PRG32
  QEMU firmware's scheduler stops under multiplayer traffic. PRG32's own
  Poing Wall stalls the same way, so the cause is outside this cartridge
  (`docs/testing.md`, "Stalls of the QEMU firmware"). The other consoles end
  the match with A PLAYER WAS LOST.
* **Online on a board needs a PRG32 firmware that can reach the server:**
  one built with the server's address, or one with LAN discovery (PRG32
  `3a6a9e3`, on the branch `feat/multiplayer-lan-discovery`, not yet merged). A board
  against a QEMU console was played to its result (`docs/testing.md`).

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
