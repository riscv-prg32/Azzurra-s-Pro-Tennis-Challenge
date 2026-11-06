#!/usr/bin/env python3
"""Compose and encode the soundtrack and the sound effects of Azzurra's Pro Tennis Challenge.

  python3 tools/build_audio.py

Outputs (deterministic; both are committed):
  audio/audio.json   the SID-like instruments, for PRG32's AUD0 packer
  src/gen/music.inc  patterns, order lists and effects for src/az_music.h

Music plays only on the menus: the title, the round-won screen, the Grand Slam
champion screen and the game-over screen. Play itself has no music, only
effects (racket, bounce, net, line calls, crowd), so that the sound of the ball
carries the game, as on a real court.

Every melody below was written for this game. The arrangement (bass, two
off-beat comping voices panned hard left and right, a pulse-width-swept lead,
an arpeggio that ping-pongs across the stereo field, drums, an echo voice and a
pad) is derived from each song's chord chart by the fixed rules further down.
No sample is used: every sound is an oscillator of the PRG32 SID-like synth.

The pattern/order encoding and the chord-tone check are adapted from
tools/build_audio.py of The Trerrote Connection (PRG32 project family, MIT).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = 16   # one pattern: a bar of 4/4 in sixteenth notes
HOLD, OFF = 0, 1

NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6,
        "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}


def synth(wave: int, width: int, cutoff: int, resonance: int) -> int:
    """PRG32_AUDIO_SYNTH_ID: waveform 0 triangle, 1 saw, 2 pulse, 3 noise."""
    return 0x8000 | (resonance << 10) | (cutoff << 6) | (width << 2) | wave


TRI, SAW, PULSE, NOISE = 0, 1, 2, 3

# name, wave, pulse width, cutoff, resonance, attack, decay, sustain, release.
# Envelope bytes follow the firmware law: time_ms = 1 + v * v * 2000 / 65025.
INSTRUMENTS = [
    ("bass", PULSE, 6, 9, 1, 0, 60, 90, 20),
    ("comp_l", PULSE, 4, 12, 1, 0, 40, 0, 16),
    ("comp_r", PULSE, 11, 12, 1, 0, 40, 0, 16),
    ("lead_a", PULSE, 3, 15, 2, 2, 70, 160, 34),
    ("lead_b", PULSE, 5, 15, 2, 2, 70, 160, 34),
    ("lead_c", PULSE, 7, 15, 2, 2, 70, 160, 34),
    ("arp", TRI, 8, 15, 0, 0, 34, 0, 14),
    ("kick", NOISE, 8, 2, 3, 0, 38, 0, 10),
    ("snare", NOISE, 8, 12, 0, 0, 30, 0, 12),
    ("hat", NOISE, 8, 15, 0, 0, 12, 0, 6),
    ("echo", PULSE, 8, 11, 1, 3, 56, 0, 26),
    ("pad", SAW, 8, 7, 1, 30, 90, 150, 80),
    # Effects.
    ("sfx_pop", PULSE, 2, 15, 1, 0, 14, 0, 6),      # the strings of the racket
    ("sfx_thwack", NOISE, 8, 10, 2, 0, 22, 0, 8),   # and the body of the shot
    ("sfx_bounce", NOISE, 8, 4, 2, 0, 20, 0, 8),    # the ball on the court
    ("sfx_net", NOISE, 8, 6, 1, 0, 50, 0, 20),      # the ball in the net
    ("sfx_call", PULSE, 8, 13, 1, 0, 70, 120, 18),  # the line judge's "out!"
    ("sfx_chime", TRI, 8, 15, 0, 0, 62, 0, 40),
    ("sfx_crowd", NOISE, 8, 9, 0, 70, 120, 140, 110),
    ("sfx_toss", TRI, 8, 15, 0, 0, 30, 0, 10),
    ("sfx_buzz", SAW, 8, 8, 2, 0, 60, 60, 16),
]
INST = {row[0]: i for i, row in enumerate(INSTRUMENTS)}

CHORDS = {"Am": (9, "min"), "Dm": (2, "min"), "Gm": (7, "min"), "Em": (4, "min"), "Bm": (11, "min"),
          "A7": (9, "dom"), "G7": (7, "dom"),
          "C": (0, "maj"), "F": (5, "maj"), "G": (7, "maj"), "D": (2, "maj"), "A": (9, "maj"),
          "Bb": (10, "maj")}
TONES = {"min": (0, 3, 7), "maj": (0, 4, 7), "dom": (0, 4, 7, 10)}


def midi(token: str) -> int:
    name, octave = token[:-1], int(token[-1])
    return 12 * (octave + 1) + NOTE[name]


def melody(line: str) -> list[int]:
    """'A4:2 C5:2 -:4' into one byte per step: a note, HOLD while it lasts, OFF for a rest."""
    out: list[int] = []
    for token in line.split():
        name, _, dur = token.partition(":")
        length = int(dur or 1)
        if name == "-":
            out += [OFF] + [HOLD] * (length - 1)
        else:
            out += [midi(name)] + [HOLD] * (length - 1)
    if len(out) != STEPS:
        raise SystemExit(f"pattern {line!r} has {len(out)} steps, not {STEPS}")
    return out


# ---- the themes ----------------------------------------------------------------

# "Center Court": the title. Bright and quick, in D major, like the opening
# titles of a sports broadcast on a summer afternoon.
TITLE = {
    "fps": 3, "loop": True,
    "chart": ["D", "A", "Bm", "G", "D", "A", "G", "A", "Bm", "G", "D", "A", "G", "A7", "D", "D"],
    "lead": [
        "F#5:2 A5:2 D6:4 A5:2 F#5:2 A5:4",
        "E5:2 A5:2 C#6:4 E6:2 C#6:2 A5:4",
        "D6:2 C#6:2 B5:4 F#5:2 B5:2 D6:4",
        "B5:2 A5:2 G5:4 D5:2 G5:2 B5:4",
        "A5:3 F#5:1 A5:2 D6:2 F#6:4 E6:2 D6:2",
        "E6:3 C#6:1 A5:2 C#6:2 E6:4 A5:4",
        "D6:3 B5:1 G5:2 B5:2 D6:4 C6:2 B5:2",
        "C#6:4 B5:2 A5:2 E5:4 -:4",
        "F#5:2 B5:2 D6:4 F#6:2 D6:2 B5:4",
        "G5:2 B5:2 D6:4 G6:2 D6:2 B5:4",
        "A5:2 D6:2 F#6:4 A6:2 F#6:2 D6:4",
        "E6:2 C#6:2 A5:4 E5:2 A5:2 C#6:4",
        "B5:2 D6:2 G6:4 G6:2 F#6:2 D6:4",
        "C#6:2 E6:2 A6:4 G6:2 E6:2 C#6:4",
        "D6:4 A5:2 F#5:2 D6:4 F#6:4",
        "D6:6 -:2 A5:2 B5:2 C#6:4",
    ],
}

# "Long Way Home": the game-over screen. Slow, in D minor, with a sigh in every bar.
GAMEOVER = {
    "fps": 6, "loop": True,
    "chart": ["Dm", "Bb", "Gm", "A7", "Dm", "Gm", "A7", "Dm"],
    "lead": [
        "A5:6 F5:2 D5:8",
        "F5:6 D5:2 Bb4:8",
        "G5:4 Bb5:4 D6:6 C6:2",
        "C#6:6 A5:2 E5:4 G5:4",
        "F5:4 E5:2 D5:2 A5:6 G5:2",
        "Bb5:4 A5:2 G5:2 D5:6 E5:2",
        "E5:4 G5:4 C#6:4 A5:4",
        "D5:12 -:4",
    ],
}

# "Next Stop": a round won, in G, a fanfare and its answer.
ROUNDWON = {
    "fps": 3, "loop": True,
    "chart": ["G", "C", "D", "G", "Em", "C", "D", "G"],
    "lead": [
        "D5:2 G5:2 B5:2 D6:2 G6:6 -:2",
        "E6:2 C6:2 G5:2 C6:2 E6:4 G6:4",
        "F#6:2 D6:2 A5:2 D6:2 F#6:4 A6:4",
        "G6:8 D6:4 -:4",
        "G6:2 E6:2 B5:2 E6:2 G6:4 B5:4",
        "E6:2 C6:2 G5:2 C6:2 E6:4 C6:4",
        "D6:2 F#6:2 A6:2 F#6:2 D6:4 A5:4",
        "G6:6 D6:2 B5:4 -:4",
    ],
}

# "Grand Slam": the champions lift the cup. C major, the full band.
CHAMPION = {
    "fps": 3, "loop": True,
    "chart": ["C", "G", "Am", "F", "C", "G7", "F", "G", "Am", "Em", "F", "C", "Dm", "G7", "C", "C"],
    "lead": [
        "E5:2 G5:2 C6:4 G5:2 C6:2 E6:4",
        "D6:2 B5:2 G5:4 B5:2 D6:2 G6:4",
        "C6:2 A5:2 E5:4 A5:2 C6:2 E6:4",
        "F6:4 E6:2 D6:2 C6:4 A5:4",
        "G5:3 C6:1 E6:4 G6:4 E6:4",
        "F6:3 D6:1 B5:4 D6:4 G6:4",
        "A6:4 F6:2 C6:2 A5:4 C6:4",
        "G6:4 D6:4 B5:4 -:4",
        "A5:2 C6:2 E6:4 A6:4 E6:4",
        "G5:2 B5:2 E6:4 G6:4 E6:4",
        "F5:2 A5:2 C6:4 F6:4 C6:4",
        "E6:2 C6:2 G5:4 C6:4 E6:4",
        "F6:2 D6:2 A5:4 D6:4 F6:4",
        "G6:2 F6:2 D6:4 B5:4 G5:4",
        "C6:4 E6:4 G6:4 C7:4",
        "C7:8 G6:4 -:4",
    ],
}

ALL_SONGS = {"title": TITLE, "gameover": GAMEOVER, "roundwon": ROUNDWON, "champion": CHAMPION}


def chord_tone_check(name: str, song: dict) -> list[str]:
    """The notes on beats 1 and 3 must belong to the chord: a checked rule of the style."""
    problems = []
    for bar, (chart, line) in enumerate(zip(song["chart"], song["lead"])):
        root, quality = CHORDS[chart]
        allowed = {(root + t) % 12 for t in TONES[quality]}
        steps = melody(line)
        for strong in (0, 8):
            note = steps[strong]
            if note >= 12 and note % 12 not in allowed:
                problems.append(f"{name} bar {bar + 1} step {strong}: {note} not in {chart}")
    return problems


class Encoder:
    def __init__(self) -> None:
        self.patterns: list[tuple[int, ...]] = []

    def add(self, steps: list[int]) -> int:
        key = tuple(steps)
        if key not in self.patterns:
            self.patterns.append(key)
        return self.patterns.index(key)


# ---- accompaniment, derived from the chart by fixed rules --------------------------

def bass_pattern(variant: int, approach: int) -> list[int]:
    """Written on D, transposed with the chord. Variant 0 pumps eighth notes on the
    root, with the octave on the off-beat of beat 4; variant 1 bounces root-fifth-
    octave-fifth. Both lead into the next bar's root by a step on the last eighth."""
    d = midi("D2")
    p = [HOLD] * STEPS
    if variant == 0:
        for k in range(0, 14, 2):
            p[k], p[k + 1] = d, OFF
        p[6] = p[10] = d
        p[12] = d + 12
    else:
        for k, v in zip((0, 2, 4, 6, 8, 10, 12), (0, 7, 12, 7, 0, 7, 12)):
            p[k], p[k + 1] = d + v, OFF
    target = d + approach
    while target - d > 6:
        target -= 12
    while target - d < -6:
        target += 12
    p[14] = target - 2 if target > d else target + 2
    p[15] = OFF
    return p


def comp_pattern(tone: int, held: bool) -> list[int]:
    """A comping voice, written on D and transposed: a stab on every off-beat eighth
    (the "skank" of a pop-rock rhythm guitar), or the chord held on 1 and pushed on
    the and of 2, for the second half of a song."""
    n = midi("D4") + tone
    p = [HOLD] * STEPS
    if held:
        p[0], p[5], p[6], p[13] = n, OFF, n, OFF
    else:
        for k in (2, 6, 10, 14):
            p[k], p[k + 1] = n, OFF
    return p


def arp_pattern(tones: tuple[int, ...], down: bool) -> list[int]:
    """Sixteenths up the chord and back: root, third, fifth, octave."""
    d = midi("D5")
    t = list(tones)[:3]
    seq = [t[0], t[1], t[2], t[0] + 12, t[2], t[1]] if not down else [t[0] + 12, t[2], t[1], t[0], t[1], t[2]]
    out = (seq * 3)[:STEPS]
    return [d + v for v in out]


KICK, SNARE, HAT, CRASH = 40, 74, 92, 98


def drum_pattern(kind: int) -> list[int]:
    """Kick on 1 and 3 (and the and of 3), snare on 2 and 4, hats on the eighths.
    Kind 1 ends a phrase with a fill, 2 opens one with a crash, 3 is the half-time
    groove of a slow song."""
    p = [KICK, OFF, HAT, OFF, SNARE, OFF, HAT, OFF, KICK, OFF, KICK, OFF, SNARE, OFF, HAT, HAT]
    if kind == 1:
        p[8:] = [KICK, OFF, SNARE, SNARE, SNARE, OFF, SNARE, SNARE]
    elif kind == 2:
        p[0] = CRASH
    elif kind == 3:
        p = [KICK, OFF, OFF, OFF, HAT, OFF, OFF, OFF, SNARE, OFF, OFF, OFF, HAT, OFF, HAT, OFF]
    return p


def transpose_for(root: int) -> int:
    t = (root - 2) % 12
    return t - 12 if t > 6 else t


def encode_song(enc: Encoder, song: dict, voices: list[str]) -> dict:
    orders: dict[str, list[tuple[int, int]]] = {v: [] for v in voices}
    leads = [melody(line) for line in song["lead"]]
    bars = len(song["chart"])
    slow = song["fps"] >= 5
    for bar, chart in enumerate(song["chart"]):
        root, quality = CHORDS[chart]
        t = transpose_for(root)
        tones = TONES[quality]
        nxt = CHORDS[song["chart"][(bar + 1) % bars]][0]
        second = bars >= 8 and bar >= bars // 2
        phrase_end = bar % 4 == 3
        for v in voices:
            if v == "bass":
                orders[v].append((enc.add(bass_pattern(1 if second else 0, (nxt - root) % 12)), t))
            elif v == "comp_l":
                orders[v].append((enc.add(comp_pattern(tones[1], slow or (second and not phrase_end))), t))
            elif v == "comp_r":
                orders[v].append((enc.add(comp_pattern(tones[2], slow or (second and not phrase_end))), t))
            elif v == "lead":
                orders[v].append((enc.add(leads[bar]), 0))
            elif v == "arp":
                orders[v].append((enc.add(arp_pattern(tones, second)), t))
            elif v == "perc":
                if slow:
                    kind = 3
                else:
                    kind = 1 if phrase_end else 2 if bar % 8 == 0 else 0
                orders[v].append((enc.add(drum_pattern(kind)), 0))
            elif v == "echo":
                prev = leads[bar - 1] if bar else [HOLD] * STEPS
                delayed = prev[-3:] + leads[bar][:-3]
                orders[v].append((enc.add([HOLD if n == OFF else n for n in delayed]), 0))
            elif v == "pad":
                p = [midi("D3") + tones[0]] + [HOLD] * 7 + [midi("D3") + tones[-1] - (12 if tones[-1] > 7 else 0)] + [HOLD] * 7
                orders[v].append((enc.add(p), t))
    return orders


# Voice table: instrument, alternate instrument at or above `split` (drums), how many
# consecutive instruments its notes cycle through (pulse-width sweep), volume, pan,
# auto-pan swing (ping-pong).
VOICES = {
    "bass": ("bass", 0, 0, 1, 210, 0, 0),
    "comp_l": ("comp_l", 0, 0, 1, 132, -60, 0),
    "comp_r": ("comp_r", 0, 0, 1, 132, 60, 0),
    "lead": ("lead_a", 0, 0, 3, 176, 0, 12),
    "arp": ("arp", 0, 0, 1, 92, 0, 52),
    "perc": ("kick", "snare", 60, 1, 150, 0, 0),
    "echo": ("echo", 0, 0, 1, 100, 50, 0),
    "pad": ("pad", 0, 0, 1, 96, -46, 0),
}
FULL = ["bass", "comp_l", "comp_r", "lead", "arp", "perc", "echo", "pad"]
SLOW = ["bass", "comp_l", "comp_r", "lead", "perc", "echo", "pad"]
SONGS = [("TITLE", TITLE, FULL), ("GAMEOVER", GAMEOVER, SLOW), ("ROUNDWON", ROUNDWON, FULL),
         ("CHAMPION", CHAMPION, FULL)]

# Effects: (instrument, note, frames) steps, played on one of the effect channels.
SFX = {
    "toss": [("sfx_toss", 72, 1), ("sfx_toss", 79, 2)],
    "flat": [("sfx_pop", 84, 1), ("sfx_thwack", 60, 2)],
    "lob": [("sfx_pop", 76, 1), ("sfx_thwack", 52, 2)],
    "serve": [("sfx_pop", 88, 1), ("sfx_thwack", 64, 1), ("sfx_thwack", 56, 2)],
    "volley": [("sfx_pop", 91, 1), ("sfx_thwack", 66, 1)],
    "bounce": [("sfx_bounce", 50, 2)],
    "net": [("sfx_net", 44, 2), ("sfx_net", 38, 4)],
    "out": [("sfx_call", 76, 3), ("sfx_call", 69, 6)],
    "fault": [("sfx_call", 72, 6)],
    "let": [("sfx_call", 74, 2), ("sfx_call", 74, 4)],
    "won": [("sfx_chime", 72, 2), ("sfx_chime", 76, 2), ("sfx_chime", 79, 2), ("sfx_chime", 84, 4)],
    "lost": [("sfx_chime", 67, 2), ("sfx_chime", 63, 2), ("sfx_chime", 60, 5)],
    "applause": [("sfx_crowd", 64, 20), ("sfx_crowd", 62, 18)],
    "game": [("sfx_chime", 79, 2), ("sfx_chime", 84, 2), ("sfx_chime", 88, 2), ("sfx_chime", 91, 6)],
    "menu": [("sfx_chime", 84, 1)],
    "select": [("sfx_chime", 79, 1), ("sfx_chime", 91, 2)],
    "buzz": [("sfx_buzz", 40, 6)],
}


def bytes_c(data, indent: str = "    ") -> str:
    data = list(data)
    return "\n".join(indent + ",".join(str(v) for v in data[i:i + 24]) + "," for i in range(0, len(data), 24))


def main() -> int:
    problems = []
    for name, song in ALL_SONGS.items():
        if len(song["chart"]) != len(song["lead"]):
            problems.append(f"{name}: chart and lead lengths differ")
        problems += chord_tone_check(name, song)
    if problems:
        print("\n".join(problems))
        return 1

    enc = Encoder()
    blob: list[int] = []
    offsets: list[int] = []
    for name, song, voices in SONGS:
        orders = encode_song(enc, song, voices)
        offsets.append(len(blob))
        bars = len(song["chart"])
        blob += [song["fps"], bars, len(voices), 1 if song["loop"] else 0]
        for v in voices:
            inst, alt, split, cycle, volume, pan, swing = VOICES[v]
            blob += [INST[inst], INST[alt] if alt else INST[inst], split, cycle, volume, pan & 255, swing]
            for pattern, transpose in orders[v]:
                blob += [pattern, transpose & 255]
    assert len(enc.patterns) < 256

    sfx_blob: list[int] = []
    sfx_offsets: list[int] = []
    for name, steps in SFX.items():
        sfx_offsets.append(len(sfx_blob))
        for inst, note, frames in steps:
            sfx_blob += [INST[inst], note, frames]
        sfx_blob.append(255)
    assert len(sfx_blob) < 256

    out = ["/* Generated by tools/build_audio.py. Do not edit: change the score. */"]
    for i, (name, *_rest) in enumerate(SONGS):
        out.append(f"#define SONG_{name} {i}")
    out.append(f"#define SONG_COUNT {len(SONGS)}\n#define MUSIC_STEPS {STEPS}\n#define MUSIC_HOLD {HOLD}\n#define MUSIC_OFF {OFF}")
    for i, name in enumerate(SFX):
        out.append(f"#define SFX_{name.upper()} {i}")
    out.append(f"#define SFX_COUNT {len(SFX)}")
    flat = [b for p in enc.patterns for b in p]
    out.append(f"static const uint8_t music_patterns[{len(flat)}] = {{\n" + bytes_c(flat) + "\n};")
    out.append(f"static const uint16_t song_offsets[{len(offsets)}] = {{" + ",".join(map(str, offsets)) + "};")
    out.append(f"static const uint8_t song_data[{len(blob)}] = {{\n" + bytes_c(blob) + "\n};")
    out.append(f"static const uint8_t sfx_offsets[{len(sfx_offsets)}] = {{" + ",".join(map(str, sfx_offsets)) + "};")
    out.append(f"static const uint8_t sfx_data[{len(sfx_blob)}] = {{\n" + bytes_c(sfx_blob) + "\n};")
    (ROOT / "src/gen").mkdir(parents=True, exist_ok=True)
    (ROOT / "src/gen/music.inc").write_text("\n".join(out) + "\n", encoding="utf-8")

    instruments = []
    for name, wave, width, cutoff, res, a, d, s, r in INSTRUMENTS:
        instruments.append({"name": name, "sample_id": synth(wave, width, cutoff, res), "default_volume": 255,
                            "default_pan": 0, "attack": a, "decay": d, "sustain": s, "release": r})
    audio = {"samples": [], "instruments": instruments, "tracks": []}
    (ROOT / "audio").mkdir(exist_ok=True)
    (ROOT / "audio/audio.json").write_text(json.dumps(audio, indent=2) + "\n", encoding="utf-8")
    print(f"audio: {len(INSTRUMENTS)} instruments, {len(enc.patterns)} patterns ({len(flat)} B), "
          f"{len(SONGS)} songs ({len(blob)} B), {len(SFX)} effects ({len(sfx_blob)} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
