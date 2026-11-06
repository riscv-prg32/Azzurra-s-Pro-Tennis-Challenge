/*
 * az_net.h - online matches over the PRG32 Multiplayer Server: the snapshot
 * format and the lockstep that keeps every console's match identical.
 *
 * Nothing here calls PRG32 (tests/test_core.c runs it on the host); azzurra.c
 * moves the snapshots in and out of prg32_multiplayer_*.
 *
 * The server relays one small snapshot per console, about 20 times a second, and
 * a newer one replaces an older one: what a cartridge can rely on is that the
 * latest snapshot arrives. The fields it may fill are x, y (int16), sprite, flags
 * (uint16) and input (7 bits): 71 bits.
 *
 * So the consoles exchange only their inputs, and each runs the whole match:
 *
 *   - the match is a sequence of 33 ms ticks; every console runs tick t with the
 *     same inputs, so the rules (az_core.h: integers only, one seeded random
 *     generator) give the same game everywhere;
 *   - a console runs tick t only when it holds every human's input for tick t;
 *   - as it runs tick t, it reads its own controller and records that as its input
 *     for tick t + NET_D (input delay); the inputs of ticks 0 .. NET_D-1 are
 *     "nothing";
 *   - each snapshot carries the console's inputs for its last NET_W ticks.
 *
 * Why NET_W = 2 * NET_D + 1 ticks are enough, so that a snapshot lost or replaced
 * on the way never matters. When A runs tick t it holds B's input for t, so B has
 * run tick t - D or later, and B holds A's inputs up to that tick at least. A's
 * newest input is t + D: at most 2D ticks past what B holds, inside A's latest
 * snapshot (tests/test_core.c checks this with snapshots that arrive late or never).
 * The latest snapshot always arrives, so the match never stops for good while the
 * consoles stay connected. (Recording the input before knowing the tick can run
 * would need one tick more.)
 *
 * An input of one tick is one of 36 symbols (left/right/none, up/down/none, A, B).
 * Three symbols pack into 16 bits (36^3 = 46,656) and two into 11 bits.
 *
 * MATCH snapshot (phase 2):
 *   flags  bits 0-1 phase, 2-7 newest tick mod 64, 8-15 low byte of the pair
 *   x, y, sprite   three symbols each, ticks T-10..T-8, T-7..T-5, T-4..T-2
 *   input  bits 0-2 high bits of the pair (ticks T-1, T), 3-6 the match tag
 * LOBBY snapshot (phase 1):
 *   flags  bits 0-1 phase, 2 team, 3 ready, 4 start, 5 doubles, 6-7 games code,
 *          8-11 city
 *   x      the match seed (host)        y      the roster hash (host)
 *   sprite four slots of 4 bits: the roster index playing it, or 15 for the CPU
 *   input  bits 0-2 roster size, 3-6 the match tag (host)
 */
#ifndef AZ_NET_H
#define AZ_NET_H

#include <stdint.h>

#define NET_SIGNATURE "azzurra-tennis:v2"
#define NET_D 5                        /* input delay, ticks (165 ms) */
#define NET_W 11                       /* ticks of inputs in a snapshot: 2 * NET_D + 1 */
#define NET_RING 64                    /* inputs kept per console */
#define NET_MAX 4                      /* consoles in one match */
#define NET_CPU 15u                    /* slot map: a computer player */
#define NET_SYMBOLS 36u

enum { NET_PHASE_NONE, NET_PHASE_LOBBY, NET_PHASE_MATCH };

typedef struct {
    int16_t x, y;
    uint16_t sprite, flags;
    uint8_t input;                     /* 7 bits on the wire */
} net_snap_t;

/* What the lobby says about one console (and, for the host, about the match). */
typedef struct {
    uint8_t team, ready, start, doubles, games, city;
    uint16_t seed, hash, map;
    uint8_t count, tag;
} net_lobby_t;

/* ---- one tick of input as a symbol ------------------------------------------------ */

/* AZ_* bits (az_core.h) to a symbol and back. Opposite directions cancel. */
static unsigned net_sym(uint32_t in) {
    unsigned h = 0, vv = 0;
    if ((in & 1u) && !(in & 2u)) h = 1;            /* AZ_LEFT */
    else if ((in & 2u) && !(in & 1u)) h = 2;       /* AZ_RIGHT */
    if ((in & 4u) && !(in & 8u)) vv = 1;           /* AZ_UP */
    else if ((in & 8u) && !(in & 4u)) vv = 2;      /* AZ_DOWN */
    return h + 3u * vv + 9u * ((in >> 4) & 1u) + 18u * ((in >> 5) & 1u);
}

static uint32_t net_unsym(unsigned s) {
    if (s >= NET_SYMBOLS) return 0;
    static const uint8_t hb[3] = {0, 1, 2}, vb[3] = {0, 4, 8};
    return (uint32_t)hb[s % 3u] | vb[(s / 3u) % 3u] | (((s / 9u) & 1u) << 4) | (((s / 18u) & 1u) << 5);
}

/* ---- snapshots --------------------------------------------------------------------- */

static uint16_t net_three(const uint8_t *s) { return (uint16_t)(s[0] + NET_SYMBOLS * s[1] + NET_SYMBOLS * NET_SYMBOLS * s[2]); }

static void net_unthree(unsigned v, uint8_t *s) {
    s[0] = (uint8_t)(v % NET_SYMBOLS);
    s[1] = (uint8_t)((v / NET_SYMBOLS) % NET_SYMBOLS);
    s[2] = (uint8_t)(v / (NET_SYMBOLS * NET_SYMBOLS));
}

/* sym[k] is the input of tick newest - (NET_W - 1) + k. */
static void net_pack_match(net_snap_t *o, uint32_t newest, const uint8_t sym[NET_W], unsigned tag) {
    unsigned pair = sym[9] + NET_SYMBOLS * sym[10];
    o->x = (int16_t)net_three(sym);
    o->y = (int16_t)net_three(sym + 3);
    o->sprite = net_three(sym + 6);
    o->flags = (uint16_t)(NET_PHASE_MATCH | ((newest & 63u) << 2) | ((pair & 0xFFu) << 8));
    o->input = (uint8_t)((pair >> 8) | ((tag & 15u) << 3));
}

/* Returns the newest tick mod 64; fills sym[] and the tag. -1 if not a valid MATCH snapshot. */
static int net_unpack_match(const net_snap_t *s, uint8_t sym[NET_W], unsigned *tag) {
    if ((s->flags & 3u) != NET_PHASE_MATCH) return -1;
    unsigned a = (uint16_t)s->x, b = (uint16_t)s->y, c = s->sprite;
    unsigned pair = (s->flags >> 8) | ((unsigned)(s->input & 7u) << 8);
    unsigned lim = NET_SYMBOLS * NET_SYMBOLS * NET_SYMBOLS;
    if (a >= lim || b >= lim || c >= lim || pair >= NET_SYMBOLS * NET_SYMBOLS) return -1;
    net_unthree(a, sym);
    net_unthree(b, sym + 3);
    net_unthree(c, sym + 6);
    sym[9] = (uint8_t)(pair % NET_SYMBOLS);
    sym[10] = (uint8_t)(pair / NET_SYMBOLS);
    *tag = (s->input >> 3) & 15u;
    return (s->flags >> 2) & 63u;
}

static unsigned net_games_code(int games) { return games == 1 ? 0u : games == 2 ? 1u : 2u; }
static int net_games_of(unsigned code) { return code == 0 ? 1 : code == 1 ? 2 : 4; }

static void net_pack_lobby(net_snap_t *o, const net_lobby_t *l) {
    o->flags = (uint16_t)(NET_PHASE_LOBBY | ((l->team & 1u) << 2) | ((l->ready & 1u) << 3) | ((l->start & 1u) << 4) |
                          ((l->doubles & 1u) << 5) | (net_games_code(l->games) << 6) | ((unsigned)(l->city & 15u) << 8));
    o->x = (int16_t)l->seed;
    o->y = (int16_t)l->hash;
    o->sprite = l->map;
    o->input = (uint8_t)((l->count & 7u) | ((l->tag & 15u) << 3));
}

static int net_unpack_lobby(const net_snap_t *s, net_lobby_t *l) {
    if ((s->flags & 3u) != NET_PHASE_LOBBY) return -1;
    l->team = (uint8_t)((s->flags >> 2) & 1u);
    l->ready = (uint8_t)((s->flags >> 3) & 1u);
    l->start = (uint8_t)((s->flags >> 4) & 1u);
    l->doubles = (uint8_t)((s->flags >> 5) & 1u);
    l->games = (uint8_t)net_games_of((s->flags >> 6) & 3u);
    l->city = (uint8_t)((s->flags >> 8) & 15u);
    l->seed = (uint16_t)s->x;
    l->hash = (uint16_t)s->y;
    l->map = s->sprite;
    l->count = (uint8_t)(s->input & 7u);
    l->tag = (uint8_t)((s->input >> 3) & 15u);
    return 0;
}

/* A short fingerprint of the players in a match, in order. */
static uint16_t net_roster_hash(const uint32_t *ids, int n) {
    uint32_t h = 2166136261u;
    for (int i = 0; i < n; ++i) {
        for (int k = 0; k < 4; ++k) {
            h ^= (ids[i] >> (8 * k)) & 0xFFu;
            h *= 16777619u;
        }
    }
    return (uint16_t)(h ^ (h >> 16));
}

/* ---- the lockstep ---------------------------------------------------------------- */

typedef struct {
    uint32_t tick;                     /* the next tick to run */
    uint32_t known[NET_MAX];           /* inputs of ticks < known[k] are held */
    uint8_t ring[NET_MAX][NET_RING];
    uint8_t count, me;                 /* consoles in the match; this one's index */
    uint8_t tag;
} net_lock_t;

static void net_lock_start(net_lock_t *n, int count, int me, unsigned tag) {
    uint8_t *raw = (uint8_t *)n;
    for (unsigned i = 0; i < sizeof(*n); ++i) raw[i] = 0;
    n->count = (uint8_t)count;
    n->me = (uint8_t)me;
    n->tag = (uint8_t)(tag & 15u);
    for (int k = 0; k < NET_MAX; ++k) n->known[k] = NET_D;   /* ticks 0..D-1: no input */
}

/* Record this console's input for tick n->tick + NET_D: call it once net_lock_ready()
 * says the tick can run, just before running it. */
static void net_lock_local(net_lock_t *n, uint32_t in) {
    uint32_t t = n->tick + NET_D;
    if (n->known[n->me] != t) return;  /* already recorded */
    n->ring[n->me][t % NET_RING] = (uint8_t)net_sym(in);
    n->known[n->me] = t + 1;
}

/* Has every console's input for the next tick arrived? */
static int net_lock_ready(const net_lock_t *n) {
    for (int k = 0; k < n->count; ++k)
        if (n->known[k] <= n->tick) return 0;
    return 1;
}

/* The input (AZ_* bits) of console k at tick t, and its new presses. */
static uint32_t net_lock_held(const net_lock_t *n, int k, uint32_t t) {
    if (t < NET_D) return 0;
    return net_unsym(n->ring[k][t % NET_RING]);
}

static uint32_t net_lock_pressed(const net_lock_t *n, int k, uint32_t t) {
    uint32_t now = net_lock_held(n, k, t);
    return t == 0 ? now : now & ~net_lock_held(n, k, t - 1);
}

/* This console's snapshot. */
static void net_lock_snapshot(const net_lock_t *n, net_snap_t *out) {
    uint32_t newest = n->known[n->me] - 1;
    uint8_t sym[NET_W];
    for (int k = 0; k < NET_W; ++k) {
        uint32_t t = newest - (NET_W - 1) + (uint32_t)k;
        sym[k] = (t < NET_D || t > newest + NET_W) ? 0 : n->ring[n->me][t % NET_RING];
    }
    net_pack_match(out, newest, sym, n->tag);
}

/* A peer's MATCH snapshot. Returns 0 if taken (or old news), -1 if it is not part of
 * this match, -2 if it skips ticks this console never saw (cannot happen while the
 * bound above holds; the match is abandoned rather than run differently). */
static int net_lock_receive(net_lock_t *n, int k, const net_snap_t *s) {
    uint8_t sym[NET_W];
    unsigned tag;
    int t6 = net_unpack_match(s, sym, &tag);
    if (t6 < 0 || tag != n->tag) return -1;
    /* Widen the tick to 32 bits: the one nearest to what is already known. */
    uint32_t ref = n->known[k] - 1;
    uint32_t newest = (ref & ~63u) | (uint32_t)t6;
    if ((int32_t)(newest - ref) > 32) newest -= 64;
    else if ((int32_t)(newest - ref) < -32) newest += 64;
    if ((int32_t)(newest - ref) <= 0) return 0;
    uint32_t first = newest - (NET_W - 1);
    if ((int32_t)(first - n->known[k]) > 0) return -2;
    for (uint32_t t = n->known[k]; (int32_t)(t - newest) <= 0; ++t) n->ring[k][t % NET_RING] = sym[t - first];
    n->known[k] = newest + 1;
    return 0;
}

#endif
