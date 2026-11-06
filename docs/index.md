# Azzurra's Pro Tennis Challenge: documentation

| Document | Contents |
|----------|----------|
| [game-design.md](game-design.md) | The tour, the modes, the controls, the doubles rules, the courts, the computer players |
| [architecture.md](architecture.md) | The source layout, the tick loop, the app states, the row renderer, the memory and size budget |
| [graphics.md](graphics.md) | The indexed colour model, the palette solver, the sprites and backgrounds, the run-length coding |
| [audio.md](audio.md) | The SID-like instruments, the four songs, the effects, stereo on QEMU and on the ESP32-C6 |
| [testing.md](testing.md) | The host tests, the build checks, QEMU, and what has not been tested |
| [reproduce.md](reproduce.md) | How to rebuild everything (art, music, cartridges, preview, bundle) and check it against the published checksums |
| [store_publishing.md](store_publishing.md) | The Cartridge Store bundle, how it is validated, and how it is submitted |

The main facts of release 2.0.0:

* **Target:**
  * a PRG32 portable cartridge, RV32IMAC, 128 KiB profile;
  * variants for `esp32c6` and `qemu`.
* **Size:**
  * a 91.6 KB package;
  * 87,004 of 131,072 bytes of cartridge memory.
* **Screen:**
  * 320 × 200, 8-bit indexed colour;
  * 98-colour palettes, one per city;
  * indexed sprites and backgrounds.
* **Sound:**
  * an SID-like stereo soundtrack, only on the title and the result screens;
  * effects only during play.
* **Store preview:** 60 s, video and audio grabbed from the PRG32 QEMU firmware.
