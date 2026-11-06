/*
 * host_prg32.h - the few PRG32 calls the cartridge makes, for the host tests.
 *
 * Two framebuffers are kept, as the two kinds of console do:
 *   fb_direct  RGB565, what QEMU shows (rect_indexed draws palette[cell], a sprite
 *              draws its palette's RGB565 as is);
 *   fb_index   8-bit cells, what the ESP32-C6 keeps (an RGB565 colour is quantised
 *              to its cube cell, exactly as prg32_gfx_index_for_rgb565_unlocked does)
 *              and shows through the system palette.
 * The tests require both to show the same picture.
 */
#ifndef HOST_PRG32_H
#define HOST_PRG32_H

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define HOST_W 320
#define HOST_H 200

static uint16_t fb_direct[HOST_W * HOST_H];
static uint8_t fb_index[HOST_W * HOST_H];
static uint16_t sys_palette[256];
static uint32_t host_input, host_input2, host_ms;
static unsigned host_rects, host_sprites, host_presents, host_pixels;
static unsigned host_notes;

static uint8_t host_cube(uint16_t color) {
    static const uint16_t named[8] = {0x0000, 0xffff, 0xf800, 0x07e0, 0x001f, 0xffe0, 0x07ff, 0xf81f};
    for (uint8_t i = 0; i < 8; ++i)
        if (color == named[i]) return i;
    unsigned r = ((color >> 11) & 31u) * 5u / 31u;
    unsigned g = ((color >> 5) & 63u) * 5u / 63u;
    unsigned b = (color & 31u) * 5u / 31u;
    return (uint8_t)(16u + r * 36u + g * 6u + b);
}

uint32_t prg32_input_read(void) { return host_input; }
uint32_t prg32_input_read_player(uint8_t player) { return player == 1 ? host_input2 : 0; }
uint32_t prg32_ticks_ms(void) { return host_ms; }
void prg32_palette_set(uint8_t index, uint16_t rgb565) { sys_palette[index] = rgb565; }
void prg32_gfx_present(void) { host_presents++; }

void prg32_gfx_rect_indexed(int x, int y, int w, int h, uint8_t index) {
    host_rects++;
    for (int yy = y; yy < y + h; ++yy)
        for (int xx = x; xx < x + w; ++xx) {
            if (xx < 0 || yy < 0 || xx >= HOST_W || yy >= HOST_H) continue;
            fb_direct[yy * HOST_W + xx] = sys_palette[index];
            fb_index[yy * HOST_W + xx] = index;
            host_pixels++;
        }
}

void prg32_sprite_draw_indexed(int x, int y, const prg32_indexed_sprite_t *s, uint32_t frame) {
    (void)frame;
    host_sprites++;
    for (int py = 0; py < s->height; ++py)
        for (int px = 0; px < s->width; ++px) {
            uint8_t i = s->pixels[py * s->width + px];
            int dx = x + px, dy = y + py;
            if ((int)i == s->transparent_index || dx < 0 || dy < 0 || dx >= HOST_W || dy >= HOST_H) continue;
            fb_direct[dy * HOST_W + dx] = s->palette[i];
            fb_index[dy * HOST_W + dx] = host_cube(s->palette[i]);
            host_pixels++;
        }
}

void prg32_audio_note_on_pan(uint8_t c, uint8_t i, uint8_t n, uint8_t v, int8_t p) {
    (void)c; (void)i; (void)n; (void)v; (void)p;
    host_notes++;
}
void prg32_audio_note_off(uint8_t c) { (void)c; }

/* ---- multiplayer: a relay among consoles simulated in one process (tests/test_net.c) --------
 * Like the firmware and the PRG32 Multiplayer Server: a console is admitted (gets a
 * player ID) a moment after it joins; it publishes its latest snapshot every 50 ms
 * from prg32_multiplayer_tick(); each snapshot reaches every other console after a
 * random latency, in order; a peer silent for 3 s, or gone, is dropped. */
#define HOST_MP_MAX 6
#define HOST_MP_QUEUE 8192
typedef struct {
    int joined;
    uint32_t id, join_ms, last_send_ms;
    prg32_player_state_t local;
    prg32_player_state_t seen[HOST_MP_MAX];     /* the latest delivered from each console */
    uint32_t seen_ms[HOST_MP_MAX], last_due[HOST_MP_MAX];
    int has[HOST_MP_MAX];
} host_mp_console_t;
typedef struct {
    int from, to;
    uint32_t due;
    prg32_player_state_t st;
} host_mp_msg_t;
static int host_mp_available = 1, host_mp_cur;
static host_mp_console_t host_mp[HOST_MP_MAX];
static host_mp_msg_t host_mp_q[HOST_MP_QUEUE];
static int host_mp_qn;
static uint32_t host_mp_lat_min = 20, host_mp_lat_max = 90, host_mp_rng = 12345u, host_mp_sent;

static uint32_t host_mp_rand(void) {
    host_mp_rng = host_mp_rng * 1103515245u + 12345u;
    return host_mp_rng >> 8;
}

static void host_mp_reset(void) {
    memset(host_mp, 0, sizeof host_mp);
    host_mp_qn = 0;
    host_mp_sent = 0;
}

static int host_mp_admitted(int k) { return host_mp[k].joined && host_ms >= host_mp[k].join_ms + 200u; }

static void host_mp_deliver(void) {
    int w = 0;
    for (int i = 0; i < host_mp_qn; ++i) {
        host_mp_msg_t *m = &host_mp_q[i];
        if (m->due <= host_ms) {
            host_mp_console_t *r = &host_mp[m->to];
            if (r->joined && host_mp[m->from].joined) {
                if (!r->has[m->from] || (int32_t)(m->st.frame - r->seen[m->from].frame) > 0) r->seen[m->from] = m->st;
                r->has[m->from] = 1;
                r->seen_ms[m->from] = host_ms;
            }
        } else {
            host_mp_q[w++] = *m;
        }
    }
    host_mp_qn = w;
}

void prg32_multiplayer_init(void) {}
bool prg32_multiplayer_available(void) { return host_mp_available != 0; }
int prg32_multiplayer_join(const char *signature, uint32_t flags) {
    (void)signature; (void)flags;
    host_mp_console_t *c = &host_mp[host_mp_cur];
    if (!c->joined) {
        memset(c, 0, sizeof *c);
        c->joined = 1;
        c->join_ms = host_ms;
        c->id = 0x1000u * (uint32_t)(host_mp_cur + 1) + (host_mp_rand() & 0xFFFu);
    }
    return 0;
}
int prg32_multiplayer_leave(void) {
    host_mp[host_mp_cur].joined = 0;
    for (int k = 0; k < HOST_MP_MAX; ++k) host_mp[k].has[host_mp_cur] = 0;   /* "leave" reaches the room */
    return 0;
}
uint32_t prg32_multiplayer_local_player_id(void) { return host_mp_admitted(host_mp_cur) ? host_mp[host_mp_cur].id : 0; }
int prg32_multiplayer_set_local_state(int16_t x, int16_t y, uint16_t sprite, uint16_t flags) {
    host_mp_console_t *c = &host_mp[host_mp_cur];
    if (!c->joined) return -1;
    c->local.x = x;
    c->local.y = y;
    c->local.sprite = sprite;
    c->local.flags = flags;
    c->local.frame++;
    return 0;
}
int prg32_multiplayer_set_input(uint32_t input) {
    host_mp[host_mp_cur].local.input = input & 0x7FFu;
    return 0;
}
void prg32_multiplayer_tick(void) {
    host_mp_console_t *c = &host_mp[host_mp_cur];
    if (!host_mp_admitted(host_mp_cur) || host_ms - c->last_send_ms < 50u) return;
    c->last_send_ms = host_ms;
    c->local.player_id = c->id;
    prg32_player_state_t st = c->local;
    st.input &= 0x7Fu;                          /* the wire carries 7 bits */
    for (int k = 0; k < HOST_MP_MAX; ++k) {
        if (k == host_mp_cur || !host_mp_admitted(k) || host_mp_qn >= HOST_MP_QUEUE) continue;
        uint32_t due = host_ms + host_mp_lat_min + host_mp_rand() % (host_mp_lat_max - host_mp_lat_min + 1u);
        if (due < c->last_due[k]) due = c->last_due[k];     /* TCP keeps the order */
        c->last_due[k] = due;
        host_mp_q[host_mp_qn].from = host_mp_cur;
        host_mp_q[host_mp_qn].to = k;
        host_mp_q[host_mp_qn].due = due;
        host_mp_q[host_mp_qn].st = st;
        host_mp_qn++;
        host_mp_sent++;
    }
}
static int host_mp_listed(int r, int k) {
    return k != r && host_mp[r].has[k] && host_mp[k].joined && host_ms - host_mp[r].seen_ms[k] <= 3000u;
}
int prg32_multiplayer_get_peer_count(void) {
    host_mp_deliver();
    int n = 0;
    if (!host_mp_admitted(host_mp_cur)) return 0;
    for (int k = 0; k < HOST_MP_MAX; ++k) n += host_mp_listed(host_mp_cur, k);
    return n;
}
int prg32_multiplayer_get_peer(int index, prg32_player_state_t *out) {
    for (int k = 0; k < HOST_MP_MAX; ++k) {
        if (!host_mp_listed(host_mp_cur, k)) continue;
        if (index-- == 0) {
            *out = host_mp[host_mp_cur].seen[k];
            out->last_seen_ms = host_mp[host_mp_cur].seen_ms[k];
            return 0;
        }
    }
    return -1;
}

static void host_write_ppm(const char *path, const uint16_t *fb) {
    FILE *f = fopen(path, "wb");
    if (!f) return;
    fprintf(f, "P6\n%d %d\n255\n", HOST_W, HOST_H);
    for (int i = 0; i < HOST_W * HOST_H; ++i) {
        uint16_t q = fb[i];
        int r = (q >> 11) & 31, g = (q >> 5) & 63, b = q & 31;
        fputc((r * 527 + 23) >> 6, f);
        fputc((g * 259 + 33) >> 6, f);
        fputc((b * 527 + 23) >> 6, f);
    }
    fclose(f);
}

#endif
