/*
 * test_game.c - the whole cartridge on the host, driven by a scripted player.
 *
 *   tests/run_tests.sh          checks only
 *   tests/run_tests.sh shots    also writes build/shots/<screen>.ppm
 *
 * Checks, on every screen:
 *   - the panel equals a clean repaint of the same state (no stale pixels: a row
 *     that changed was marked dirty);
 *   - the ESP32-C6's indexed framebuffer shows what QEMU's direct one shows (every
 *     colour sits in its own palette cell);
 *   - the flow: title, menu, intro, play, points scored, the demo, pause, results,
 *     and a singles exhibition against the computer.
 */
#define AZ_HOST 1
#include "prg32.h"
#include "host_prg32.h"
#include "../src/azzurra.c"

static int failures;
static const char *shots_dir;
static uint16_t snapshot[HOST_W * HOST_H];

#define CHECK(cond, ...) do { if (!(cond)) { printf("FAIL: " __VA_ARGS__); printf("\n"); failures++; } } while (0)

static void frame(uint32_t input) {
    host_input = input;
    host_ms += 33;
    azzurra_update();
    azzurra_draw();
}

static void frames(int n, uint32_t input) {
    for (int i = 0; i < n; ++i) frame(input);
}

static void tap(uint32_t button) {
    frame(button);
    frame(0);
}

static int same_as_repaint(const char *where) {
    memcpy(snapshot, fb_direct, sizeof snapshot);
    dirty_all();
    v.prev_count = 0;
    azzurra_draw();
    int diff = 0;
    for (int i = 0; i < HOST_W * HOST_H; ++i) diff += snapshot[i] != fb_direct[i];
    CHECK(diff == 0, "%s: %d pixels differ from a clean repaint", where, diff);
    int cells = 0;
    for (int i = 0; i < HOST_W * HOST_H; ++i) {
        if (sys_palette[fb_index[i]] != fb_direct[i]) {
            if (!cells) printf("  first at %d,%d: cell %d shows %04x, drawn %04x\n", i % HOST_W, i / HOST_W, fb_index[i], sys_palette[fb_index[i]], fb_direct[i]);
            cells++;
        }
    }
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

/* Play like a beginner: run to the ball and swing at it. */
static uint32_t autoplayer(void) {
    const az_game_t *g = &v.game;
    const az_player_t *p = &g->p[0];
    const az_ball_t *b = &g->ball;
    uint32_t in = 0;
    if (g->state == PS_SERVE) {
        if (g->server == 0 && (v.app_tick % 24) == 0) in |= PRG32_BTN_A;
        return in;
    }
    int bx = b->x / AZ_Q, by = b->y / AZ_Q;
    if (b->live && b->team == AZ_FAR) {
        if (bx - 45 < p->x - 10) in |= PRG32_BTN_LEFT;
        if (bx - 45 > p->x + 10) in |= PRG32_BTN_RIGHT;
        if (by > 0 && by + 30 < p->y - 40) in |= PRG32_BTN_UP;
        if (by > 0 && by + 30 > p->y + 40) in |= PRG32_BTN_DOWN;
        if (az_in_reach(g, 0) && (v.app_tick & 1)) in |= PRG32_BTN_A;
    }
    return in;
}

int main(int argc, char **argv) {
    shots_dir = argc > 1 ? argv[1] : 0;
    host_ms = 1000;
    azzurra_init();
    frames(30, 0);
    CHECK(v.app == APP_TITLE, "starts on the title");
    CHECK(v.music.playing && v.music.current == SONG_TITLE, "the title has its music");
    shot("title");

    /* The menu: exhibition in London, 2 games. */
    tap(PRG32_BTN_DOWN);
    for (int i = 0; i < 4; ++i) tap(PRG32_BTN_RIGHT);
    tap(PRG32_BTN_DOWN);               /* MATCH */
    tap(PRG32_BTN_DOWN);               /* GAMES PER SET */
    tap(PRG32_BTN_LEFT);
    frames(3, 0);
    shot("menu");
    CHECK(v.exhibition_city == 4 && v.games_to_win == 2 && v.doubles, "menu: city %d, games %d", v.exhibition_city, v.games_to_win);
    tap(PRG32_BTN_UP);
    tap(PRG32_BTN_UP);
    tap(PRG32_BTN_UP);
    tap(PRG32_BTN_A);                  /* START WORLD TOUR */
    frames(5, 0);
    CHECK(v.app == APP_INTRO, "tour starts with the intro");
    CHECK(!v.music.playing, "no music in the intro");
    shot("intro");
    frames(110, 0);
    CHECK(v.app == APP_PLAY, "the intro leads to play");
    frames(10, 0);
    shot("serve");

    int points = 0, shots_taken = 0, music_in_play = 0;
    for (int t = 0; t < 30 * 240 && v.app == APP_PLAY; ++t) {
        uint8_t before = v.game.rally;
        uint8_t pts = (uint8_t)(v.game.points[0] + v.game.points[1] + 4 * (v.game.games[0] + v.game.games[1]));
        frame(autoplayer());
        if (v.music.playing && v.app == APP_PLAY) music_in_play++;
        if (v.game.rally > before) shots_taken++;
        uint8_t now = (uint8_t)(v.game.points[0] + v.game.points[1] + 4 * (v.game.games[0] + v.game.games[1]));
        if (now != pts) points++;
        if (t == 200) shot("rally");
        if ((t % 97) == 0) same_as_repaint("play");
        if (t == 400) {
            tap(PRG32_BTN_START);
            frames(3, 0);
            CHECK(v.app == APP_PAUSE, "START pauses");
            shot("pause");
            tap(PRG32_BTN_START);
            CHECK(v.app == APP_PLAY, "START resumes");
            tap(PRG32_BTN_START);
            frames(2, 0);
            tap(PRG32_BTN_START);
            CHECK(v.app == APP_PLAY, "START pauses and resumes again");
        }
    }
    printf("play: %d points, %d shots, app %d, games %d-%d\n", points, shots_taken, v.app, v.game.games[0], v.game.games[1]);
    CHECK(points >= 8, "points are played (%d)", points);
    CHECK(shots_taken >= 10, "the ball is struck (%d)", shots_taken);
    CHECK(music_in_play == 0, "no music during play (%d ticks)", music_in_play);
    CHECK(v.app == APP_ROUNDWON || v.app == APP_GAMEOVER || v.app == APP_CHAMPION, "the match ends (app %d)", v.app);
    frames(10, 0);
    CHECK(v.music.playing, "the result screen has music");
    shot(v.app == APP_GAMEOVER ? "gameover" : "roundwon");
    tap(PRG32_BTN_B);
    tap(PRG32_BTN_A);
    frames(40, 0);

    /* Singles against the computer: an exhibition, 1 VS 1. */
    azzurra_init();
    frames(3, 0);
    v.menu = MENU_MATCH;
    tap(PRG32_BTN_RIGHT);
    CHECK(!v.doubles, "MATCH: 1 VS 1");
    v.menu = MENU_GAMES;
    tap(PRG32_BTN_LEFT);
    tap(PRG32_BTN_LEFT);
    v.menu = MENU_EXHIBITION;
    for (int i = 0; i < 4; ++i) tap(PRG32_BTN_RIGHT);
    tap(PRG32_BTN_A);
    frames(110, 0);
    CHECK(v.app == APP_PLAY && v.game.singles && !v.game.p[1].active && !v.game.p[3].active, "a singles match starts");
    int singles_points = 0;
    for (int t = 0; t < 30 * 300 && v.app == APP_PLAY; ++t) {
        uint8_t pts = (uint8_t)(v.game.points[0] + v.game.points[1] + 4 * (v.game.games[0] + v.game.games[1]));
        frame(autoplayer());
        if ((uint8_t)(v.game.points[0] + v.game.points[1] + 4 * (v.game.games[0] + v.game.games[1])) != pts) singles_points++;
        if (t == 150) shot("singles");
        if ((t % 89) == 0) same_as_repaint("singles");
        CHECK(!(v.music.playing && v.app == APP_PLAY), "no music in singles play");
        if (v.music.playing && v.app == APP_PLAY) break;
    }
    printf("singles: %d points, app %d, games %d-%d\n", singles_points, v.app, v.game.games[0], v.game.games[1]);
    CHECK(v.app == APP_ROUNDWON || v.app == APP_GAMEOVER, "the singles match ends (app %d)", v.app);

    /* The pause quits to the title with B (SELECT is START on PRG32). */
    v.menu = MENU_EXHIBITION;
    title_screen();
    frames(3, 0);
    tap(PRG32_BTN_A);
    frames(120, 0);
    tap(PRG32_BTN_START);
    CHECK(v.app == APP_PAUSE, "paused again");
    tap(PRG32_BTN_B);
    frames(2, 0);
    CHECK(v.app == APP_TITLE, "B in the pause quits to the title (app %d)", v.app);

    /* Back to the title and wait for the demo. */
    azzurra_init();
    frames(DEMO_IDLE_TICKS + 20, 0);
    CHECK(v.app == APP_DEMO, "the title falls into the demo");
    CHECK(!v.music.playing, "the demo has no music");
    int demo_points = 0;
    for (int t = 0; t < 30 * 120; ++t) {
        uint8_t p0 = v.game.points[0] + v.game.points[1];
        frame(0);
        if (v.game.points[0] + v.game.points[1] != p0) demo_points++;
        if (t == 150) shot("demo");
        if ((t % 101) == 0) same_as_repaint("demo");
    }
    CHECK(demo_points >= 5, "the demo plays points (%d)", demo_points);

    /* Every city, every result screen. */
    for (int c = 0; c < CITY_COUNT; ++c) {
        v.round = (uint8_t)c;
        v.exhibition = 0;
        intro_screen();
        frames(3, 0);
        char name[32];
        snprintf(name, sizeof name, "city%02d", c);
        if (c == 5 || c == 4 || c == 0 || c == 13 || c == 6) shot(name);
        else same_as_repaint(name);
        if (city_night[c] || c == 4) {     /* the floodlit courts and the grass, in play */
            play_screen();
            frames(45, 0);
            snprintf(name, sizeof name, "play%02d", c);
            shot(name);
        }
    }
    v.round = 3;
    v.game.games[0] = 4;
    v.game.games[1] = 2;
    roundwon_screen();
    frames(5, 0);
    shot("roundwon");
    gameover_screen();
    frames(5, 0);
    shot("gameover");
    v.round = 13;
    scene(13);
    champion_screen();
    frames(40, 0);
    shot("champion");
    CHECK(v.music.current == SONG_CHAMPION, "the champions have their song");

    printf("render: %u rect calls, %u row sprites, %u presents, %u pixels\n", host_rects, host_sprites, host_presents, host_pixels);
    printf("%s (%d failures)\n", failures ? "FAILED" : "ok", failures);
    return failures ? 1 : 0;
}
