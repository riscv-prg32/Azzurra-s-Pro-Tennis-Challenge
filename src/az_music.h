/*
 * az_music.h - the cartridge's sequencer and its effects player.
 *
 * Music: the classic pattern/order design of the 8-bit trackers. A pattern is one
 * 4/4 bar of 16 sixteenth notes; for each voice a song lists one (pattern,
 * transposition) pair per bar. The tempo is a whole number of 33 ms ticks per
 * step. Songs play only on the title, round-won, champion and game-over screens,
 * on up to eight stereo voices.
 *
 * Effects: three slots on channels 5, 6 and 7, each a short list of (instrument,
 * note, ticks) steps with its own stereo pan, so that a racket, a bounce and the
 * line judge can sound together. During play no song runs, so the effects have the
 * synth to themselves; on a menu an effect borrows a slot's channel from the song.
 *
 * No PRG32 call is made directly: the includer defines AZ_NOTE_ON and AZ_NOTE_OFF,
 * so the host tests can log what would be played.
 *
 * Adapted from src/tr_music.h of The Trerrote Connection (PRG32 family, MIT).
 */
#ifndef AZ_MUSIC_H
#define AZ_MUSIC_H

#include <stdint.h>

#define AZ_MUSIC_VOICES 8
#define AZ_VOICE_HEADER 7
#define AZ_SFX_SLOTS 3
#define AZ_SFX_FIRST_CHANNEL 5

typedef struct {
    const uint8_t *data;
    uint8_t ticks;
    int8_t pan;
    int8_t transpose;
} az_sfx_slot_t;

typedef struct {
    const uint8_t *song;
    uint8_t playing, bars, voices, loop;
    uint8_t fps;
    uint8_t bar, step, frames;
    uint8_t note_count[AZ_MUSIC_VOICES];
    int8_t swing[AZ_MUSIC_VOICES];
    uint8_t finished;
    int8_t current;                    /* the song playing, or -1 */
    az_sfx_slot_t sfx[AZ_SFX_SLOTS];
    uint8_t next_slot;
} az_music_t;

static void az_music_init(az_music_t *m) {
    uint8_t *raw = (uint8_t *)m;
    for (unsigned i = 0; i < sizeof(*m); ++i) raw[i] = 0;
    m->current = -1;
}

static void az_music_stop(az_music_t *m) {
    if (m->playing) {
        for (int v = 0; v < m->voices; ++v) AZ_NOTE_OFF(v);
    }
    m->playing = 0;
    m->current = -1;
}

/* Start a song (a song already playing carries on). */
static void az_music_play(az_music_t *m, int song) {
    if (m->playing && m->current == song) return;
    az_music_stop(m);
    const uint8_t *d = song_data + song_offsets[song];
    m->song = d;
    m->fps = d[0];
    m->bars = d[1];
    m->voices = d[2];
    m->loop = d[3];
    m->bar = 0;
    m->step = 0;
    m->frames = 1;
    m->playing = 1;
    m->finished = 0;
    m->current = (int8_t)song;
    for (int v = 0; v < AZ_MUSIC_VOICES; ++v) {
        m->note_count[v] = 0;
        m->swing[v] = 1;
    }
}

static const uint8_t *az_voice(const az_music_t *m, int v) {
    return m->song + 4 + v * (AZ_VOICE_HEADER + m->bars * 2);
}

static int az_sfx_busy(const az_music_t *m, int channel) {
    int k = channel - AZ_SFX_FIRST_CHANNEL;
    return k >= 0 && k < AZ_SFX_SLOTS && m->sfx[k].data;
}

static void az_music_step(az_music_t *m) {
    for (int v = 0; v < m->voices; ++v) {
        const uint8_t *h = az_voice(m, v);
        const uint8_t *order = h + AZ_VOICE_HEADER + m->bar * 2;
        uint8_t value = music_patterns[order[0] * MUSIC_STEPS + m->step];
        if (az_sfx_busy(m, v)) continue;
        if (value == MUSIC_OFF) {
            AZ_NOTE_OFF(v);
        } else if (value != MUSIC_HOLD) {
            int note = value;
            int instrument = h[0];
            if (h[2] && value >= h[2]) instrument = h[1];          /* drum split */
            if (h[2] == 0) note += (int8_t)order[1];                /* transposition */
            if (h[3] > 1) instrument += m->note_count[v] % h[3];    /* pulse-width sweep */
            m->note_count[v]++;
            int pan = (int8_t)h[5];
            if (h[6]) {                                             /* ping-pong */
                m->swing[v] = (int8_t)-m->swing[v];
                pan += m->swing[v] * (int)h[6];
            }
            AZ_NOTE_ON(v, instrument, note, h[4], pan);
        }
    }
    if (++m->step >= MUSIC_STEPS) {
        m->step = 0;
        if (++m->bar >= m->bars) {
            m->bar = 0;
            if (!m->loop) {
                az_music_stop(m);
                m->finished = 1;
            }
        }
    }
}

/* Play an effect on the next free slot (or the oldest one), panned -64..63. */
static void az_sfx_play(az_music_t *m, int sfx, int pan, int transpose) {
    int k = -1;
    for (int i = 0; i < AZ_SFX_SLOTS; ++i) {
        int s = (m->next_slot + i) % AZ_SFX_SLOTS;
        if (!m->sfx[s].data) {
            k = s;
            break;
        }
    }
    if (k < 0) k = m->next_slot;
    m->next_slot = (uint8_t)((k + 1) % AZ_SFX_SLOTS);
    m->sfx[k].data = sfx_data + sfx_offsets[sfx];
    m->sfx[k].ticks = 1;
    m->sfx[k].pan = (int8_t)(pan < -64 ? -64 : pan > 63 ? 63 : pan);
    m->sfx[k].transpose = (int8_t)transpose;
}

/* Call once per 33 ms tick. */
static void az_music_tick(az_music_t *m) {
    if (m->playing && --m->frames == 0) {
        m->frames = m->fps;
        az_music_step(m);
    }
    for (int k = 0; k < AZ_SFX_SLOTS; ++k) {
        az_sfx_slot_t *s = &m->sfx[k];
        if (!s->data || --s->ticks) continue;
        if (s->data[0] == 255) {
            AZ_NOTE_OFF(AZ_SFX_FIRST_CHANNEL + k);   /* release a sustained effect */
            s->data = 0;
            continue;
        }
        AZ_NOTE_ON(AZ_SFX_FIRST_CHANNEL + k, s->data[0], s->data[1] + s->transpose, 235, s->pan);
        s->ticks = s->data[2];
        s->data += 3;
    }
}

#endif
