# Audio: SID-like stereo music and effects

## The rule

| Screen | Music | Effects |
|--------|-------|---------|
| Title (and its menu) | **"Center Court"** | menu clicks |
| Round won | **"Next Stop"** | — |
| Game over | **"Long Way Home"** | — |
| Grand Slam champions | **"Grand Slam"** | — |
| Intro, play, pause, demo | none | racket, bounce, net, line calls, crowd |

During play only effects sound, so that the ball and the crowd carry the game,
as on a real court. `tests/test_game.c` fails if a song plays during a match.

## Instruments

No samples are used. All 21 instruments are oscillators of the PRG32 SID-like
synth, each named by a `PRG32_AUDIO_SYNTH_ID`:

* a waveform: triangle, saw, pulse or noise;
* a pulse width;
* a filter cutoff;
* a resonance.

`tools/build_audio.py` writes them to `audio/audio.json`, and PRG32's
`tools/prg32audio_pack.py` packs them into the cartridge's 208-byte AUD0 block.
The instruments are:

* **Music:** bass, two comping voices, three lead variants (a pulse-width
  sweep), arpeggio, kick, snare, hat, echo and pad.
* **Effects:** pop, thwack, bounce, net, umpire's call, chime, crowd, toss and
  buzz.

## Music

All four songs were composed for this game. Each is a chord chart plus a lead
melody. `build_audio.py` derives the rest of the arrangement from the chart by
fixed rules:

| Voice | What it plays | Stereo |
|-------|---------------|--------|
| bass | roots and fifths | centre |
| comp L / comp R | off-beat chord tones | hard left / hard right (±60) |
| lead | the melody, cycling three pulse widths | centre, slight swing |
| arp | chord arpeggio | ping-pong across the field (±52) |
| perc | kick/snare split by note, fills at phrase ends | centre |
| echo | the lead, three sixteenths late | right (+50) |
| pad | sustained root/top of the chord | left (−46) |

| Song | Key | Bars | Tempo | Voices |
|------|-----|-----:|-------|-------:|
| Center Court (title) | D major | 16 | 3 ticks/step ≈ 150 BPM | 8 |
| Long Way Home (game over) | D minor | 8 | 6 ticks/step ≈ 75 BPM | 7 (no arpeggio) |
| Next Stop (round won) | G major | 8 | 3 ticks/step | 8 |
| Grand Slam (champions) | C major | 16 | 3 ticks/step | 8 |

All four songs loop. `build_audio.py` refuses to write a song whose lead
lands off the chord on a strong beat (`chord_tone_check`), so every edit
keeps the melody consonant.

### The sequencer

The sequencer is `src/az_music.h`, the classic pattern/order design of 8-bit
trackers:

* **Patterns.** A pattern is one bar of 16 sixteenth notes. For each voice,
  a song lists one (pattern, transposition) pair per bar.
* **Sharing.** Identical patterns are stored once.
* **Size.** 123 patterns take 1,968 bytes, and the four songs' order lists
  take 985 bytes.
* **Tempo.** It is a whole number of 33 ms ticks per step.

## Effects

There are 17 effects, each a short list of (instrument, note, ticks) steps.
The racket sounds differ by shot:

* flat drive, lob, serve and volley each have their own racket sound;
* the toss has a sound of its own.

The rest are:

* the bounce;
* the net;
* the line calls: "out" (two falling notes), fault, let;
* point won and point lost chimes, and a game chime;
* applause;
* menu move and select;
* a buzz.

Three effect slots on channels 5, 6 and 7 let a racket, a bounce and a call
overlap. Each effect is **panned by where it happens**: `pan_of(x)` maps the
ball's or the player's screen x to −64…63. A forehand on the left of the
court sounds on the left.

On a menu an effect borrows a channel from the song for its few ticks; during
play no song runs, so the effects have the synth to themselves.

## Stereo on the two hosts

| Host | How stereo reaches the speakers |
|------|---------------------------------|
| **ESP32-C6** | The firmware's I2S output. With I2S MODE = STEREO in SETUP > AUDIO SETUP, the pans above reach the speakers; in MONO the firmware mixes them down. |
| **QEMU** | The firmware streams what its mixer renders over a UART: 22,050 Hz, 16-bit, 2 bytes a frame in mono, 4 bytes interleaved L R in stereo. |

The QEMU firmware is built with `CONFIG_PRG32_AUDIO_MODE_MONO`, so
`scripts/qemu_preview.py` first switches I2S MODE to STEREO in the setup
menu, the same as a player would. The setting is saved in the NVS of a
temporary copy of the flash image.

The captured `audio.wav`, and the preview's AAC track, are therefore real
stereo. In the 25.6 s smoke capture (title, menu and play), 30% of the
samples differ between left and right.
