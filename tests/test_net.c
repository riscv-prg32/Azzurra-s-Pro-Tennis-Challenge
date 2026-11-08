/*
 * test_net.c - online matches: two to four whole cartridges in one process, talking
 * through the simulated Multiplayer Server of tests/host/host_prg32.h.
 *
 *   tests/run_tests.sh          checks only
 *   tests/run_tests.sh shots    also writes build/shots/online_*.ppm
 *
 * Each console is the real cartridge (src/azzurra.c), with its own state, screen,
 * controller and frame rate; the test swaps them in and out of the one copy the
 * cartridge code sees. Every console walks the menus, enters the lobby, picks a team
 * and gets ready, as a player would. Then the scripted players play the match. The
 * test checks:
 *   - every console runs the same match: at every tick the game states are equal;
 *   - every console sees the court from behind its own team (the far team's from
 *     the far end, with the back skyline), and its own screen passes the repaint
 *     and the indexed/direct framebuffer checks of test_game.c;
 *   - no music plays during the match; the result screens agree on the winner;
 *   - a console that disappears in the middle of a match ends it for the others.
 * Consoles run at 30 or 10 frames per second; the network adds 20 to 150 ms.
 */
#define AZ_HOST 1
#include "prg32.h"
#include "host_prg32.h"
#include "../src/azzurra.c"

#define MAXC 4
#define HIST 8192

static int failures;
static const char *shots_dir;
#define CHECK(cond, ...) do { if (!(cond)) { printf("FAIL: " __VA_ARGS__); printf("\n"); failures++; } } while (0)

typedef struct {
    unsigned char state[sizeof(v)];
    uint16_t fb[HOST_W * HOST_H];
    uint8_t fbi[HOST_W * HOST_H];
    uint16_t pal[256];
    uint32_t input, period, next;
    int alive;
    /* the script: menu taps, then the lobby */
    int want_team, want_doubles, want_games, host;
    int stage, wait;
    uint32_t taps[32];
    int ntaps, tap_i, tap_phase;
    uint32_t hash[HIST];
    uint8_t has[HIST];
    int music_in_play, ticks_played, saw_rev, saw_back, shot_taken;
    int unadmitted_games;      /* GAMES PER SET shown in the lobby before the welcome (-1 not seen) */
    uint32_t play_ms0, play_ms1, play_t0, play_t1;
} console_t;

static console_t con[MAXC];
static int prompt_test, prompt_frame, prompt_done;   /* the leave prompt, on console 0 */
static int ncon;
static uint16_t snapshot[HOST_W * HOST_H];

static void swap_in(int k) {
    memcpy(&v, con[k].state, sizeof v);
    memcpy(fb_direct, con[k].fb, sizeof fb_direct);
    memcpy(fb_index, con[k].fbi, sizeof fb_index);
    memcpy(sys_palette, con[k].pal, sizeof sys_palette);
    host_input = con[k].input;
    host_mp_cur = k;
}

static void swap_out(int k) {
    memcpy(con[k].state, &v, sizeof v);
    memcpy(con[k].fb, fb_direct, sizeof fb_direct);
    memcpy(con[k].fbi, fb_index, sizeof fb_index);
    memcpy(con[k].pal, sys_palette, sizeof sys_palette);
}

static uint32_t game_hash(const az_game_t *g) {
    const uint8_t *raw = (const uint8_t *)g;
    uint32_t h = 2166136261u;
    for (unsigned i = 0; i < sizeof *g; ++i) h = (h ^ raw[i]) * 16777619u;
    return h;
}

static int same_as_repaint(const char *where) {
    memcpy(snapshot, fb_direct, sizeof snapshot);
    dirty_all();
    v.prev_count = 0;
    azzurra_draw();
    int diff = 0, cells = 0;
    for (int i = 0; i < HOST_W * HOST_H; ++i) {
        diff += snapshot[i] != fb_direct[i];
        cells += sys_palette[fb_index[i]] != fb_direct[i];
    }
    CHECK(diff == 0, "%s: %d pixels differ from a clean repaint", where, diff);
    CHECK(cells == 0, "%s: %d pixels differ between the indexed and direct framebuffers", where, cells);
    return diff == 0 && cells == 0;
}

static void shot(const char *name) {
    same_as_repaint(name);
    if (!shots_dir) return;
    char path[512];
    snprintf(path, sizeof path, "%s/%s.ppm", shots_dir, name);
    host_write_ppm(path, fb_direct);
}

static uint32_t to_buttons(uint32_t in) {
    uint32_t b = 0;
    if (in & AZ_LEFT) b |= PRG32_BTN_LEFT;
    if (in & AZ_RIGHT) b |= PRG32_BTN_RIGHT;
    if (in & AZ_UP) b |= PRG32_BTN_UP;
    if (in & AZ_DOWN) b |= PRG32_BTN_DOWN;
    if (in & AZ_A) b |= PRG32_BTN_A;
    if (in & AZ_B) b |= PRG32_BTN_B;
    return b;
}

/* A beginner playing slot i, pressing what she sees on her own screen. */
static uint32_t autoplayer(int i) {
    const az_game_t *g = &v.game;
    const az_player_t *p = &g->p[i];
    const az_ball_t *b = &g->ball;
    uint32_t in = 0;
    if (g->state == PS_SERVE) {
        if (g->server == i && (v.app_tick % 24) == 0) in |= AZ_A;
    } else if (b->live && b->team != p->team) {
        int bx = b->x / AZ_Q, by = b->y / AZ_Q;
        int fore = p->team == AZ_NEAR ? -45 : 45, half = p->team == AZ_NEAR ? 30 : -30;
        if (bx + fore < p->x - 10) in |= AZ_LEFT;
        if (bx + fore > p->x + 10) in |= AZ_RIGHT;
        if (by + half < p->y - 40) in |= AZ_UP;
        if (by + half > p->y + 40) in |= AZ_DOWN;
        if (az_in_reach(g, i) && (v.app_tick & 1)) in |= AZ_A;
    }
    if (p->rot) in = az_rotate(in);     /* she sees the court turned round */
    return to_buttons(in);
}

static int my_slot(void) {
    for (int s = 0; s < 4; ++s)
        if (v.net.slot[s] == v.net.lock.me && v.game.p[s].human) return s;
    return -1;
}

static void script_menu(console_t *c) {
    /* title: MATCH row, set singles/doubles; GAMES row, set games; ONLINE */
    c->ntaps = 0;
    c->taps[c->ntaps++] = PRG32_BTN_DOWN;
    c->taps[c->ntaps++] = PRG32_BTN_DOWN;           /* MATCH */
    if (!c->want_doubles) c->taps[c->ntaps++] = PRG32_BTN_RIGHT;
    c->taps[c->ntaps++] = PRG32_BTN_DOWN;           /* GAMES: 4 -> 2 -> 1 */
    for (int k = 0; k < (c->want_games == 1 ? 2 : c->want_games == 2 ? 1 : 0); ++k) c->taps[c->ntaps++] = PRG32_BTN_LEFT;
    c->taps[c->ntaps++] = PRG32_BTN_DOWN;           /* PLAY ONLINE */
    c->taps[c->ntaps++] = PRG32_BTN_A;
    if (c->want_team) c->taps[c->ntaps++] = PRG32_BTN_RIGHT;   /* TEAM: RIVALS */
    c->taps[c->ntaps++] = PRG32_BTN_A;                         /* ready */
    c->tap_i = 0;
    c->tap_phase = 0;
}

/* The digit after "GAMES PER SET: " on the screen, or -1. */
static int shown_games(void) {
    static const char key[] = "GAMES PER SET: ";
    for (int cy = 0; cy < TEXT_ROWS; ++cy)
        for (int x = 0; x + (int)sizeof key <= TEXT_COLS; ++x) {
            int i = 0;
            while (key[i] && v.text[cy][x + i] == key[i]) ++i;
            if (!key[i]) return v.text[cy][x + i] - '0';
        }
    return -1;
}

/* One frame of console k. */
static void console_frame(int k) {
    console_t *c = &con[k];
    swap_in(k);
    uint32_t in = 0;
    if (v.app == APP_TITLE || v.app == APP_LOBBY) {
        /* the script; wait a little in the lobby for the server's welcome */
        if (c->tap_i < c->ntaps && v.app == APP_LOBBY && !v.net.my_id) c->wait = 10;
        if (c->wait > 0) c->wait--;
        else if (c->tap_i < c->ntaps) {
            if (c->tap_phase == 0) in = c->taps[c->tap_i];
            if (++c->tap_phase >= 4) {
                c->tap_phase = 0;
                c->tap_i++;
                if (c->tap_i < c->ntaps && c->taps[c->tap_i - 1] == PRG32_BTN_A && v.app == APP_TITLE) c->wait = 8;
            }
        }
    } else if (v.app == APP_PLAY && v.online) {
        int s = my_slot();
        if (s >= 0) in = autoplayer(s);
    }
    /* The leave prompt: START does nothing, A + B opens it, A closes it, and the
     * console sends no A or B from the chord until both are released. */
    int prompting = prompt_test && k == 0 && !prompt_done && v.app == APP_PLAY && v.net.lock.tick > 300;
    if (prompting) {
        static const uint32_t script[] = {PRG32_BTN_START, 0, PRG32_BTN_A | PRG32_BTN_B, PRG32_BTN_A | PRG32_BTN_B,
                                          PRG32_BTN_A | PRG32_BTN_B, 0, 0, PRG32_BTN_A, 0};
        in = script[prompt_frame];
    }
    host_input = in;
    c->input = in;
    uint32_t before = v.net.lock.tick;
    int was_match = v.net.in_match && !v.net.finished;
    azzurra_update();
    azzurra_draw();
    if (prompting) {
        int f = prompt_frame++;
        uint32_t newest = net_lock_held(&v.net.lock, v.net.lock.me, v.net.lock.known[v.net.lock.me] - 1);
        if (f <= 1) CHECK(!v.net.prompt && v.app == APP_PLAY, "online: START opens nothing (frame %d)", f);
        if (f >= 2 && f <= 6) CHECK(v.net.prompt && v.net.mute_ab, "online: A + B opens the prompt (frame %d)", f);
        if (f == 3) shot("online_prompt");
        if (f == 7) CHECK(!v.net.prompt && v.net.mute_ab, "online: A plays on, still muted while held");
        if (f >= 2 && f <= 7) CHECK(!(newest & (AZ_A | AZ_B)), "online: the prompt's keys are not sent (frame %d)", f);
        if (f == 8) {
            CHECK(!v.net.prompt && !v.net.mute_ab && v.app == APP_PLAY, "online: released, play on");
            prompt_done = 1;
        }
    }
    if (v.app == APP_LOBBY && !v.net.my_id && c->unadmitted_games < 0) c->unadmitted_games = shown_games();
    if (was_match) {
        /* The game after T ticks, whichever frame ran them. */
        if (v.net.lock.tick != before && v.net.lock.tick < HIST) {
            c->hash[v.net.lock.tick] = game_hash(&v.game);
            c->has[v.net.lock.tick] = 2;
        }
        if (v.app == APP_PLAY) {
            if (!c->play_ms0) {
                c->play_ms0 = host_ms;
                c->play_t0 = v.net.lock.tick;
            }
            c->play_ms1 = host_ms;
            c->play_t1 = v.net.lock.tick;
            c->ticks_played++;
            if (v.music.playing) c->music_in_play++;
            if (v.rev) c->saw_rev = 1;
            if (v.scene_city == v.city * 2 + 1) c->saw_back = 1;
        }
    }
    swap_out(k);
}

typedef struct {
    const char *name;
    int n, doubles, games;
    int team[MAXC];
    uint32_t period[MAXC];
    uint32_t lat_min, lat_max;
    int drop;                  /* console that vanishes in the middle (-1 none) */
    int prompt;                /* console 0 opens and closes the leave prompt */
} scenario_t;

static void run(const scenario_t *sc) {
    printf("%s:\n", sc->name);
    prompt_test = sc->prompt;
    prompt_frame = prompt_done = 0;
    host_mp_reset();
    host_mp_lat_min = sc->lat_min;
    host_mp_lat_max = sc->lat_max;
    host_ms = 1000;
    ncon = sc->n;
    memset(con, 0, sizeof con);
    for (int k = 0; k < ncon; ++k) {
        console_t *c = &con[k];
        c->want_team = sc->team[k];
        c->want_doubles = sc->doubles;
        c->want_games = sc->games;
        c->period = sc->period[k];
        c->next = host_ms + (uint32_t)k * 7u;
        c->alive = 1;
        c->unadmitted_games = -1;
        script_menu(c);
        host_mp_cur = k;
        host_input = 0;
        azzurra_init();
        swap_out(k);
    }
    int dropped = 0;
    static int lobby_shot, lobby_shot2;
    uint32_t end = host_ms + 30u * 60u * 1000u;
    for (; host_ms < end; host_ms++) {
        int all_done = 1;
        for (int k = 0; k < ncon; ++k) {
            console_t *c = &con[k];
            if (!c->alive) continue;
            if (host_ms >= c->next) {
                c->next += c->period;
                console_frame(k);
            }
        }
        /* progress */
        for (int k = 0; k < ncon; ++k) {
            if (!con[k].alive) continue;
            swap_in(k);
            int done = v.app == APP_ROUNDWON || v.app == APP_GAMEOVER || v.app == APP_NETMSG;
            if (!done) all_done = 0;
            if (k == 0 && sc->n == 4 && v.app == APP_LOBBY && v.net.countdown_on && v.net.countdown < 60 && !lobby_shot) {
                shot("online_lobby");
                lobby_shot = 1;
                swap_out(k);
            }
            if (k == 3 && sc->n == 4 && v.app == APP_LOBBY && v.net.mine.ready && !lobby_shot2) {
                shot("online_lobby_guest");
                lobby_shot2 = 1;
                swap_out(k);
            }
            /* pictures from both ends, once play is well on */
            if (!con[k].shot_taken && v.app == APP_PLAY && v.net.lock.tick > 700 && sc->drop < 0) {
                char name[64];
                snprintf(name, sizeof name, "online_%s_%s", sc->doubles ? "2v2" : "1v1", v.rev ? "far" : "near");
                shot(name);
                con[k].shot_taken = 1;
                swap_out(k);
            }
            if (sc->drop == k && !dropped && v.app == APP_PLAY && v.net.lock.tick > 600) {
                /* this console's player pulls the plug */
                prg32_multiplayer_leave();
                con[k].alive = 0;
                dropped = 1;
                printf("  console %d vanishes at tick %u\n", k, v.net.lock.tick);
            }
        }
        if (all_done) break;
    }
    /* Every console ran the same match. */
    int compared = 0, differ = 0, first_diff = -1;
    for (int t = 0; t < HIST; ++t) {
        int ref = -1;
        for (int k = 0; k < ncon; ++k) {
            if (con[k].has[t] != 2) continue;           /* the state of tick t exactly */
            if (ref < 0) ref = k;
            else {
                compared++;
                if (con[k].hash[t] != con[ref].hash[t]) {
                    differ++;
                    if (first_diff < 0) first_diff = t;
                }
            }
        }
    }
    printf("  %d tick states compared, %d differ%s, %u snapshots relayed, %.0f s\n", compared, differ,
           first_diff >= 0 ? " (first shown)" : "", host_mp_sent, (host_ms - 1000) / 1000.0);
    if (first_diff >= 0) printf("  first difference at tick %d\n", first_diff);
    CHECK(differ == 0, "%s: the consoles ran different matches", sc->name);
    CHECK(!sc->prompt || prompt_done, "%s: the leave prompt was tried", sc->name);
    CHECK(sc->drop >= 0 || compared > 150, "%s: too few states compared (%d)", sc->name, compared);
    int winner = -1;
    for (int k = 0; k < ncon; ++k) {
        if (!con[k].alive) continue;
        swap_in(k);
        double secs = (con[k].play_ms1 - con[k].play_ms0) / 1000.0;
        double speed = secs > 0 ? (con[k].play_t1 - con[k].play_t0) / secs / (1000.0 / AZ_TICK_MS) : 0;
        printf("  console %d: team %d, %s, app %d, games %d-%d, %d frames in play, game speed %.0f%%\n", k, v.my_team,
               v.rev ? "view from the far end" : "broadcast view", v.app, v.game.games[0], v.game.games[1],
               con[k].ticks_played, 100 * speed);
        if (sc->drop < 0) CHECK(speed > 0.85, "%s: console %d plays at %.0f%% of full speed", sc->name, k, 100 * speed);
        CHECK(con[k].music_in_play == 0, "%s: music during play on console %d", sc->name, k);
        CHECK(v.my_team == (uint8_t)sc->team[k], "%s: console %d plays for team %d", sc->name, k, v.my_team);
        if (sc->drop >= 0) {
            CHECK(v.app == APP_NETMSG, "%s: console %d told the match is over (app %d)", sc->name, k, v.app);
            continue;
        }
        CHECK(v.app == APP_ROUNDWON || v.app == APP_GAMEOVER, "%s: console %d reached a result (app %d)", sc->name, k, v.app);
        CHECK(v.music.playing, "%s: the result screen has music on console %d", sc->name, k);
        CHECK(con[k].saw_rev == (sc->team[k] == AZ_FAR), "%s: console %d view", sc->name, k);
        CHECK(con[k].saw_back == (sc->team[k] == AZ_FAR), "%s: console %d skyline", sc->name, k);
        CHECK(con[k].unadmitted_games == sc->games,
              "%s: console %d showed GAMES PER SET %d before the server's welcome, not its own %d",
              sc->name, k, con[k].unadmitted_games, sc->games);
        int w = v.game.match_winner;
        if (winner < 0) winner = w;
        CHECK(w == winner, "%s: the consoles disagree on the winner", sc->name);
        CHECK((v.app == APP_ROUNDWON) == (w == v.my_team), "%s: console %d's result screen", sc->name, k);
        same_as_repaint("result");
        if (k == 0) {
            char name[64];
            snprintf(name, sizeof name, "online_%s_result", sc->doubles ? "2v2" : "1v1");
            if (sc->n == 2) shot(name);
        }
    }
}

int main(int argc, char **argv) {
    shots_dir = argc > 1 ? argv[1] : 0;
    static const scenario_t scenarios[] = {
        {"1 vs 1 online, two consoles at 30 fps", 2, 0, 1, {0, 1}, {33, 33}, 20, 90, -1, 1},
        {"1 vs 1 online, a 10 fps console, 150 ms network", 2, 0, 1, {0, 1}, {33, 100}, 40, 150, -1, 0},
        {"2 vs 2 online, four consoles, one at 10 fps", 4, 1, 1, {0, 1, 0, 1}, {33, 33, 100, 33}, 20, 120, -1, 0},
        {"2 vs 2 online, three consoles and one CPU", 3, 1, 1, {0, 1, 1, 0}, {33, 33, 33, 33}, 20, 90, -1, 0},
        {"2 vs 2 online, two partners against two CPUs", 2, 1, 1, {0, 0, 0, 0}, {33, 33, 33, 33}, 20, 90, -1, 0},
        {"2 vs 2 online, one against one with CPU partners", 2, 1, 1, {0, 1, 0, 0}, {33, 33, 33, 33}, 20, 90, -1, 0},
        {"1 vs 1 online, a console vanishes", 2, 0, 2, {0, 1}, {33, 33}, 20, 90, 1, 0},
    };
    for (unsigned i = 0; i < sizeof scenarios / sizeof scenarios[0]; ++i) run(&scenarios[i]);

    /* Offline consoles say so instead of hanging in the lobby. */
    host_mp_reset();
    host_mp_available = 0;
    host_mp_cur = 0;
    azzurra_init();
    v.menu = MENU_ONLINE;
    host_input = PRG32_BTN_A;
    for (int i = 0; i < 4; ++i) {
        host_ms += 33;
        azzurra_update();
        azzurra_draw();
        host_input = 0;
    }
    CHECK(v.app == APP_NETMSG && !v.net.joined, "no network: a message, not a lobby (app %d)", v.app);
    host_mp_available = 1;

    printf("%s (%d failures)\n", failures ? "FAILED" : "ok", failures);
    return failures ? 1 : 0;
}
