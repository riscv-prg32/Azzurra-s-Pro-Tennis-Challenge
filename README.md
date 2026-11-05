# Azzurra's Pro Tennis Challenge

A classical doubles-tennis cartridge for the PRG32 128K profile. Azzurra and her
partner face fourteen increasingly strong pairs on hard, clay, grass, and night
courts, with the Grand Slam Challenge Cup waiting at the end.

The world tour visits Napoli, Rome, Paris, Chicago, London, New York, Tokyo,
Cairo, Madrid, Barcelona, Berlin, Venice, Sydney, and Athens. Each indexed-color
venue has its own landmark skyline and rotating RISC-V, UNIPARTHENOPE, PRG32,
OPEN-HW, and OPEN-SW courtside sponsorship. Players, rackets, and the ball use
compact indexed sprite assets.

## Play

- D-pad: move Azzurra
- A: flat drive / serve
- B: lob / lob serve
- Player 2 controller: control Azzurra's partner
- Network peer: controls a rival; all empty seats use deterministic AI

The cartridge uses a 320x200 indexed framebuffer, stereo panning, and all eight
SID-like synth voices. It supports local multiplayer, network multiplayer with
an offline AI fallback, tennis scoring, four tournament rounds, and a cup ending.

## Build

Set `PRG32_REPO` if the PRG32 SDK is not in `../PRG32`, then run:

```sh
./build.sh
```

The QEMU and ESP32-C6 portable cartridges are written to `dist/`. Both are
compiled with `--cart-ram-kib 128` and require the audio and multiplayer APIs.
