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
| `tests/test_core.c` | The rules and the lockstep (622 checks). See below. |
| `tests/test_game.c` | The whole cartridge (`src/azzurra.c` as is) on a fake PRG32 (`tests/host/host_prg32.h`). See below. |
| `tests/test_net.c` | Two to four cartridges playing online through a simulated Multiplayer Server. See below. |
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
* **Singles:**
  * the serve alternates between the two players and the receiver is always
    the other one;
  * the singles lines: a ball in the doubles alley is out;
  * singles matches between computer players finish.
* **Ends:** a player with `rot` set runs the same way on screen from the far
  end; a computer partner of a human plays as Viola (`ally`).
* **Lockstep** (`src/az_net.h`):
  * the 36 input symbols, and the match and lobby snapshots, survive packing;
  * two, three and four lockstep rings, with snapshots delivered late, out
    of order or not at all, step the same inputs on every console and never
    report a gap.

### `test_game.c`

The test flow:

1. the title has its music;
2. the menu sets an exhibition in London and 2 games;
3. the tour starts with a silent intro;
4. a scripted beginner plays a whole match (points are scored, the ball is
   struck, no music plays);
5. START does not pause; A + B pauses without striking the ball (also B
   first, then A), START does not resume, A resumes, A + B in the pause
   resumes, and B in the pause quits to the title;
6. the result screen has music;
7. the title falls into the demo, which plays points without music;
8. every city's intro renders, and the grass and the two floodlit courts
   render in play;
9. the round-won, game-over and champions' screens render, the champions with
   their song;
10. a singles exhibition against the computer starts on the singles court
    and points are played.

On every screen, two invariants are checked:

* **No stale pixels.** The incremental frame equals a clean repaint of the
  same state.
* **Same picture on both hosts.** The ESP32-C6's indexed framebuffer, shown
  through the system palette, equals QEMU's direct-colour framebuffer.

Expected output (version 2.1.0, Apple clang 21, macOS):

```
palette: 48 fixed colours (32 for sprites), 0 collisions
  match level  0 surface 0: 2-0 in   8 points,  1.1 min
  ...
core: 622 checks, ok (0 failures)
play: 14 points, 37 shots, app 6, games 1-2
singles: 8 points, app 5, games 1-0
render: ... rect calls, ... row sprites, ... presents, ... pixels
ok (0 failures)
1 vs 1 online, two consoles at 30 fps:
  497 tick states compared, 0 differ, 928 snapshots relayed, 32 s
  ...
ok (0 failures)
metadata: version 2.1.0, 0 failures
```

The core and game tests are deterministic (fixed seeds and a fake clock), so
the numbers above repeat on any host with the same compiler semantics.

### `test_net.c`

Up to four copies of the cartridge run in one process: the test swaps the
whole cartridge state between them, and `host_prg32.h` simulates the server
(admission 200 ms after the join, a publish every 50 ms, a random in-order
latency, peers expiring after 3 s). Each console walks the title menu to
PLAY ONLINE, joins the lobby, picks its team and presses READY. A scripted
player then plays each human place. The test checks:

* every console has the same game state (a hash of `az_game_t`) at every
  tick;
* the near team sees the broadcast view and the far team sees the view from
  the far end, with the city's back skyline;
* no music plays from the intro to the result;
* every console shows the same result, from its own side (won or lost);
* the game keeps at least 85% of real time;
* before the server admits a console, the lobby shows that console's own
  settings.

The seven scenarios, and their output for 2.1.0 (Apple clang 21, macOS):

| Scenario | Tick states compared | Differ | Game speed |
|----------|---------------------:|-------:|-----------:|
| 1 vs 1, two consoles at 30 fps | 497 | 0 | 100% |
| 1 vs 1, one console at 10 fps, 150 ms network | 212 | 0 | 95% |
| 2 vs 2, four consoles, one at 10 fps | 1,270 | 0 | 99% |
| 2 vs 2, three consoles and one CPU | 1,037 | 0 | 100% |
| 2 vs 2, two partners against two CPUs | 687 | 0 | 100% |
| 2 vs 2, one against one with CPU partners | 475 | 0 | 100% |
| 1 vs 1, a console vanishes at tick 601 | 517 | 0 | 88% (the match ends with a message) |

These are measured by the test, on simulated time, so they repeat exactly.
With `shots`, it also writes `build/shots/online_*.png`.

### Bugs these tests found

* `az_launch` truncated the vertical speed towards zero. When a ball started
  above its own fall (a smash, a high volley), it landed one tick late: up to
  1.3 m long, and often out. It now rounds down.
* The lockstep first recorded a console's input before checking that it
  could advance. With three or more consoles, a console could then run
  further ahead than the 11-tick window covers, and a peer saw a gap. It now
  records after the check.
* At the start of a four-console match, a client still saw the host's last
  lobby snapshot and took it for "a player left". A start grace period
  fixed it.
* On PRG32, SELECT is the same key as START, so the 2.0.0 pause's
  "SELECT quits" could never fire. B quits now.
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

### Online, on QEMU consoles

```bash
scripts/qemu_netplay.py --match 2v2 --teams 0,1,0,1 --out build/qemu-netplay-2v2
```

This runs the real PRG32 Multiplayer Server and one PRG32 QEMU firmware per
`--teams` entry (see [reproduce.md](reproduce.md#4b-qemu-online-matches)).
Each console walks the menu to the lobby, joins, and then a random player
plays its place to the result screen. The script reads each console's result
from the screen, and what the server relayed from a silent member of the
room.

Results for 2.1.0, observed on 2026-11-06 on a 16-core Mac. Sets of one
game. The game speed is measured from the relayed ticks against the wall
clock; the other figures are counts from the server's relay:

| Match | Consoles (team) | Computer | City | Ticks | Game speed | Snapshots/s | Input conflicts | Result |
|-------|-----------------|---------:|------|------:|-----------:|------------:|----------------:|--------|
| 2 vs 2 | 4 (0, 1, 0, 1) | 0 | Napoli Bay | 3,358 | 93% | 18.9–19.4 | 0 | team 1 won on both its consoles, team 0 lost on both |
| 2 vs 2 | 3 (0, 1, 1) | 1 | London Grass | 3,465 | 95% | 18.9 | 0 | team 1 won on both its consoles, team 0 lost |
| 2 vs 2 | 2 (0, 0) | 2 | Madrid Masters | 782 | 77% | 17.7–18.5 | 0 | both partners lost, 1-0 |
| 2 vs 2 | 2 (0, 1) | 2 | Tokyo Lights | 3,102 | 95% | 19.1–19.4 | 0 | team 1 won, team 0 lost |
| 1 vs 1 | 2 (0, 1) | 0 | Napoli Bay | 3,090 | 95% | 19.1–19.4 | 0 | team 1 won, team 0 lost |
| 1 vs 1, 2 games | 2 (1, 0) | 0 | Barcelona | 5,783 | 98% | 18.6–18.8 | 0 | team 1 won, team 0 lost |

The 2 vs 2 rows with four consoles and with one human and one computer a side
come from runs before the last two fixes (the audio drain, and the lobby's
settings before the welcome); later runs of those two all stalled (below).

In every run, all consoles reached the result screen within 2 s of each
other, and the near and far views and the skylines were as expected (the
screens are in `OUT/c*_play*.png`).

**The QEMU audio link.** With the firmware paced on the script's audio
credits (`--audio`), each console ran at about 5 frames a second, and the
game at about 26% of real time. Without credits it ran at about 30. All the
runs above are without them.

**Stalls of the QEMU firmware.** When a console stops publishing for 6 s,
the script saves its screen, its CPU registers (`OUT/c*_stalled.txt`) and a
backtrace of every FreeRTOS task (`OUT/c*_tasks.txt`, from QEMU's gdb stub
and `scripts/gdb_tasks.py`). The other consoles then end the match with A
PLAYER WAS LOST, as they should. This happened often (observed):

* After the audio drain was fixed, a console stalled in 10 of 14 runs with
  two to four consoles, after
  20 s to 3 minutes of play. The runs in the table are the ones that did
  not.
* Every dump shows the firmware's scheduler stuck, not the cartridge. Tasks
  are ready but never run, and the current task waits forever in
  `vPortYield` for its cross-core interrupt, or loops in `vListInsert` on
  the wait list of `prg32_usb`'s ring buffer. The cartridge's task (`main`)
  is ready, in `prg32_audio_cartridge_frame`.
* **The same happens with PRG32's own multiplayer cartridge,** Poing Wall
  (`cartridges/poingwall/dist/poingwall-qemu.prg32`), with two consoles on
  the same server: it stalled after 26 s with random keys, after 134 s with
  no keys, and after 271 s with no keys and no screen grabs.
* Without multiplayer traffic, a QEMU console running Azzurra's demo was
  grabbed 3,397 times in 6 minutes and did not stall.
* With the QEMU firmware rebuilt with LAN discovery, three 1 vs 1 runs of
  two consoles all stalled, after 18 s to about 100 s of play, with the same
  dump; the discovery task was asleep in its 500 ms wait, as it is whenever
  the console is connected. Three runs are too few to say whether the rate
  changed.
* In the four runs of the board against one QEMU console (above, on the
  QEMU firmware before the discovery rebuild), the QEMU console never
  stalled: one QEMU console instead of two.

So the stall comes from the PRG32 QEMU firmware's networking (the
`prg32_eth_poll` / `emac_rx` path, which exists only in QEMU) or from QEMU
itself, under multiplayer traffic. It is not in this cartridge, and the
board's firmware uses Wi-Fi instead. It should be reported to PRG32.

A harness bug, fixed during testing, caused other stalls: the audio drain
thread died, because `qemu_netplay.py` did not import `socket`, and the
firmware then blocked on the full audio port.

## ESP32-C6

Release 2.1.0 was run on an ESP32-C6 board on 2026-11-06. The board was the
PRG32 board on USB (`/dev/cu.usbmodem1101`, later `/dev/cu.usbmodem101`), with the PRG32 firmware for the
128 KiB profile, built from PRG32 `1fa8474`.

**Upload.** Slot `cart4` held a second copy of a device demo. It was first
saved with `esptool read_flash 0x290000 0x20000` (SHA-256 `1ce95253…`), then
written over USB:

```bash
python -m prg32 esp32c6 upload ../Azzurra-s-Pro-Tennis-Challenge/dist/azzurra-pro-tennis-esp32c6.prg32 --port /dev/cu.usbmodem1101 --slot cart4 --command run
```

Use the ESP-IDF Python environment for this (`~/.espressif/python_env/idf5.4_py3.12_env/bin/python`).
The keys were pressed with `prg32 esp32c6 key` over USB, and the screens
taken with `prg32 esp32c6 screenshot --url http://BOARD_IP` over Wi-Fi.

**Observed on the board:**

* the title, its menu and the demo, which started on its own in Sydney and
  in Cairo;
* a singles exhibition in Napoli against the computer, played with scripted
  key presses to its game-over screen (2-0 to the computer);
* START paused the match (2.1.0; A + B pauses since), and B in the pause
  returned to the title;
* a doubles exhibition with Viola, with points won and lost;
* PLAY ONLINE opens the lobby, which first showed CONNECTING TO THE SERVER:
  the board's firmware is set to the server `ws://192.168.1.155:8081`, and no
  server was running at that address. With the firmware rebuilt with LAN
  discovery (below), the board found the server on the LAN by itself.

The pictures were the same as in QEMU, by eye. The screens taken on the board
were read from its framebuffer, not photographed.

**Online, the board against a QEMU console.** The board's firmware was
rebuilt with LAN discovery: PRG32 `1fa8474` plus the change committed as
`3a6a9e3` on the branch `feat/multiplayer-lan-discovery` (PRG32
`docs/software/multiplayer_protocol.md`, "LAN Discovery") and flashed over USB with `idf.py --ccache ... flash`, after a backup
of the whole 4 MB flash (`esptool read_flash 0 0x400000`, SHA-256
`4384bcc1…`). The cartridge stayed in slot `cart4`. The board had moved to
another Wi-Fi network (address 192.168.1.163); the Multiplayer Server ran on
the Mac on the same network with discovery on (section 4b of
[reproduce.md](reproduce.md#4b-qemu-online-matches)), and the board's
compiled address was still the old one. The run:

```bash
scripts/qemu_netplay.py --match 1v1 --teams 0 --external-server --port 8081 --board-port /dev/cu.usbmodem101 --board-url http://192.168.1.163 --board-slot cart4 --board-team 1 --out build/qemu-netplay-board
```

Observed on 2026-11-06, a set of one game in Napoli Bay; counts are from the
server's relay, the speed from the relayed ticks against the wall clock:

| Console | Team | Result on its screen | Snapshots/s | Ticks | Inputs recorded | Input conflicts |
|---------|------|----------------------|------------:|------:|----------------:|----------------:|
| ESP32-C6 board | RIVALS (far end) | WELL PLAYED!, 1-0 | 16.0 | 912 | 908 | 0 |
| QEMU | AZZURRA (near end) | GAME OVER, 1-0 | 18.0 | 912 | 908 | 0 |

The game ran at 79% of real time. The board showed the court from the far
end, with the hills behind Napoli, and its own team first in the HUD
(`docs/media/board_online.png`).

Two earlier runs with a scratch driver also played to a result, the board
winning both, at 80–87% and at 43% of real time. The slow one took a
screenshot of the board before every key press: a screenshot slows the
board (it reads the screen over several frames), and in lockstep every
console waits for the slowest. That cause is inferred, not measured. The
script now reads the board's screen only a few times and follows the end
of the match from the board's relayed tick.

Three things went wrong in the first tries, all in the test driver, not in
the cartridge: random keys in the lobby reached LEAVE (UP + A), so the board
left the room; the board's result screen was passed by an A press before it
was read (A on that screen goes back to the lobby); and the screenshot file
was a relative path, which the `prg32` tool resolved in the PRG32 checkout.

**Not done on the board:** no frame rate was measured, the sound was not
recorded, and online play with more than one board was not tried (there is
one board).

The renderer sends only changed rows, in at most two presents per frame. On
an idle court only the ball, its shadow and the players move, which is a few
dozen rows.

To upload over Wi-Fi instead (PRG32 `docs/software/cartridges.md`):

```bash
python3 -m prg32 esp32c6 upload ../Azzurra-s-Pro-Tennis-Challenge/dist/azzurra-pro-tennis-esp32c6.prg32 --url http://192.168.4.1
```
