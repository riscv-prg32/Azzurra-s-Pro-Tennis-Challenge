/*
 * test_core.c - the rules of src/az_core.h, on the host, without PRG32.
 *
 *   scoring: 15-30-40, deuce and advantage, games, sets of 1, 2 and 4 games
 *            (win by two, tie-break at 4-4 to 7 by two);
 *   serving: the doubles order (Azzurra, a rival, Viola, the other rival), the
 *            deuce/ad sides, the tie-break rotation;
 *   courts:  the service boxes and the doubles lines;
 *   ball:    az_launch lands where it aims, the net stops a low ball, a ball
 *            into the wrong box is a fault, two faults lose the point;
 *   play:    four computer players finish a match, the same seed replays it
 *            exactly, and no player leaves the arena.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "../src/gen/art.inc"
#include "../src/az_core.h"

static int failures, checks;
#define CHECK(cond, ...) do { checks++; if (!(cond)) { printf("FAIL %s:%d: ", __FILE__, __LINE__); printf(__VA_ARGS__); printf("\n"); failures++; } } while (0)

static az_game_t g;

static void fresh(int games_to_win, int order) {
    memset(&g, 0, sizeof g);
    az_new_match(&g, 5, 0, games_to_win, 12345u, order);
}

static void win_points(int team, int n) {
    for (int i = 0; i < n && !g.match_over; ++i) az_score_point(&g, team);
}

static void test_scoring(void) {
    char call[24];
    fresh(4, 0);
    az_call(&g, call);
    CHECK(strcmp(call, "0-0") == 0, "start call '%s'", call);
    az_score_point(&g, 0);
    az_score_point(&g, 1);
    az_call(&g, call);
    CHECK(strcmp(call, "15-ALL") == 0, "15-all call '%s'", call);
    az_score_point(&g, 0);
    az_score_point(&g, 1);
    az_score_point(&g, 0);
    az_score_point(&g, 1);
    az_call(&g, call);
    CHECK(strcmp(call, "DEUCE") == 0, "deuce call '%s'", call);
    az_score_point(&g, 0);
    az_call(&g, call);
    CHECK(strcmp(call, "AD AZZURRA") == 0, "advantage call '%s'", call);
    az_score_point(&g, 1);
    CHECK(g.games[0] == 0 && g.games[1] == 0, "deuce again is not a game");
    az_score_point(&g, 1);
    az_call(&g, call);
    CHECK(strcmp(call, "AD RIVALS") == 0, "advantage rivals '%s'", call);
    az_score_point(&g, 1);
    CHECK(g.games[1] == 1 && g.points[0] == 0 && g.points[1] == 0, "advantage then point wins the game");
    CHECK(g.order == 1, "the serve passes on after a game (order %d)", g.order);

    /* First to 1 and first to 2. */
    fresh(1, 0);
    win_points(0, 4);
    CHECK(g.match_over && g.match_winner == 0, "a 1-game set ends after one game");
    fresh(2, 0);
    win_points(0, 4);
    win_points(1, 4);
    CHECK(!g.match_over, "1-1 in a 2-game set goes on");
    win_points(1, 4);
    CHECK(g.match_over && g.match_winner == 1 && g.games[1] == 2, "first to 2 games");

    /* 4 games: 4-3 is not enough, 5-3 is; 4-4 is a tie-break. */
    fresh(4, 0);
    for (int k = 0; k < 3; ++k) { win_points(0, 4); win_points(1, 4); }
    win_points(0, 4);
    CHECK(!g.match_over && g.games[0] == 4 && g.games[1] == 3, "4-3 goes on");
    win_points(0, 4);
    CHECK(g.match_over && g.match_winner == 0 && g.games[0] == 5, "5-3 wins");

    fresh(4, 0);
    for (int k = 0; k < 4; ++k) { win_points(0, 4); win_points(1, 4); }
    CHECK(g.tiebreak && !g.match_over, "4-4 starts a tie-break");
    win_points(0, 6);
    win_points(1, 6);
    az_call(&g, call);
    CHECK(strcmp(call, "6-6") == 0, "tie-break call '%s'", call);
    win_points(0, 1);
    CHECK(!g.match_over, "7-6 in a tie-break goes on");
    win_points(0, 1);
    CHECK(g.match_over && g.match_winner == 0 && g.games[0] == 5, "8-6 wins the tie-break and the set");
}

static void test_serving(void) {
    /* Order: Azzurra (0), rival 2, Viola (1), rival 3, then again. */
    fresh(4, 0);
    static const int want[8] = {0, 2, 1, 3, 0, 2, 1, 3};
    for (int k = 0; k < 8; ++k) {
        az_setup_point(&g);
        CHECK(g.server == want[k], "game %d served by %d, want %d", k, g.server, want[k]);
        int before = g.server;
        win_points(k & 1, 4);
        CHECK(g.order == ((k + 1) & 3), "order after game %d", k);
        az_setup_point(&g);
        CHECK(g.p[g.server].team != g.p[before].team, "the serve changes team after game %d", k);
        if (g.match_over) break;
    }
    /* Sides: the first point from the deuce side, the next from the ad side. */
    fresh(4, 0);
    az_setup_point(&g);
    int st = g.p[g.server].team;
    CHECK(az_serve_side(&g) == 0, "first point from the deuce side");
    CHECK(g.p[g.receiver].team == 1 - st, "the receiver is on the other team");
    int r0 = g.receiver;
    az_score_point(&g, 0);
    az_setup_point(&g);
    CHECK(az_serve_side(&g) == 1 && g.receiver != r0, "second point from the ad side, to the other receiver");
    CHECK(g.p[g.server].x * az_side_sign(st, 1) > 0, "the server stands on the ad half");

    /* Tie-break: one serve, then two each, round the order. */
    fresh(4, 0);
    for (int k = 0; k < 4; ++k) { win_points(0, 4); win_points(1, 4); }
    int servers[5];
    for (int k = 0; k < 5; ++k) {
        az_setup_point(&g);
        servers[k] = g.server;
        az_score_point(&g, k & 1);
    }
    CHECK(servers[1] == servers[2] && servers[3] == servers[4] && servers[0] != servers[1] && servers[2] != servers[3],
          "tie-break serves %d %d %d %d %d", servers[0], servers[1], servers[2], servers[3], servers[4]);
}

static void test_courts(void) {
    /* Team 0 serves towards -Y. Deuce side (0): the far team's deuce half is -X. */
    CHECK(az_in_service_box(AZ_NEAR, 0, -200, -300), "near deuce serve into far deuce box");
    CHECK(!az_in_service_box(AZ_NEAR, 0, 200, -300), "near deuce serve into the wrong box");
    CHECK(az_in_service_box(AZ_NEAR, 1, 200, -300), "near ad serve into far ad box");
    CHECK(!az_in_service_box(AZ_NEAR, 0, -200, 300), "a serve into its own half");
    CHECK(!az_in_service_box(AZ_NEAR, 0, -200, -(G_SERVICE + 20)), "a long serve");
    CHECK(az_in_service_box(AZ_NEAR, 0, -G_SINGLES, -G_SERVICE), "the lines are in");
    CHECK(!az_in_service_box(AZ_NEAR, 0, -(G_SINGLES + 30), -300), "wide of the singles line");
    CHECK(az_in_service_box(AZ_FAR, 0, 200, 300), "far deuce serve into near deuce box");
    CHECK(!az_in_service_box(AZ_FAR, 0, -200, 300), "far deuce serve into the wrong box");
    CHECK(az_in_court(G_DOUBLES, G_HALF_L), "the corner is in");
    CHECK(!az_in_court(G_DOUBLES + 20, 0), "wide of the doubles line");
    CHECK(!az_in_court(0, G_HALF_L + 20), "past the baseline");
}

static void test_ball(void) {
    /* az_launch lands within a few cm of the target. */
    int worst = 0;
    for (int n = 10; n <= 50; n += 5) {
        for (int tx = -400; tx <= 400; tx += 200) {
            az_ball_t b;
            memset(&b, 0, sizeof b);
            b.x = 100 * AZ_Q;
            b.y = 1100 * AZ_Q;
            b.z = 100 * AZ_Q;
            az_launch(&b, tx, -800, n);
            for (int t = 0; t < 200 && !(b.z <= 0 && b.vz < 0); ++t) {
                b.x += b.vx;
                b.y += b.vy;
                b.z += b.vz;
                b.vz -= AZ_G;
            }
            int e = az_abs(b.x / AZ_Q - tx) + az_abs(b.y / AZ_Q + 800);
            if (e > worst) worst = e;
        }
    }
    CHECK(worst <= 8, "az_launch lands within 8 cm (worst %d)", worst);

    /* A low rally ball into the net loses the point for the hitter. */
    fresh(4, 0);
    g.state = PS_RALLY;
    az_ball_t *b = &g.ball;
    b->held = b->tossed = b->serve = 0;
    b->live = 1;
    b->team = AZ_NEAR;
    b->x = 0;
    b->y = 300 * AZ_Q;
    b->z = 30 * AZ_Q;
    b->vx = 0;
    b->vy = -40 * AZ_Q;
    b->vz = 0;
    for (int t = 0; t < 40 && g.state != PS_DEAD; ++t) az_ball_step(&g);
    CHECK(g.state == PS_DEAD && g.point_winner == AZ_FAR && g.reason == WHY_NET, "netted ball: winner %d why %d", g.point_winner, g.reason);

    /* A serve into the wrong box: a fault, then a double fault. */
    fresh(4, 0);
    for (int pass = 0; pass < 2; ++pass) {
        az_ball_t *s = &g.ball;
        int st = g.p[g.server].team;
        s->held = s->tossed = 0;
        s->live = 1;
        s->serve = 1;
        s->bounces = 0;
        s->team = (uint8_t)st;
        s->z = 250 * AZ_Q;
        int want = az_side_sign(1 - st, az_serve_side(&g));
        az_launch(s, -want * 250, -az_half(st) * 400, 30);
        g.state = PS_RALLY;
        for (int t = 0; t < 80 && g.state != PS_DEAD; ++t) az_ball_step(&g);
        if (pass == 0) {
            CHECK(g.state == PS_DEAD && g.point_winner == 2 && g.second_serve, "first fault");
            az_next_point(&g);
            CHECK(g.second_serve && g.state == PS_SERVE, "second serve set up");
        } else {
            CHECK(g.state == PS_DEAD && g.point_winner == 1 - st && g.reason == WHY_DOUBLE_FAULT, "double fault");
        }
    }
}

/* Four computer players, one whole match; returns a fingerprint. */
static uint32_t play_match(uint32_t seed, int level, int surface, int *points_out, int *ticks_out, int *escaped) {
    memset(&g, 0, sizeof g);
    az_new_match(&g, level, surface, 2, seed, (int)(seed & 3));
    uint32_t held[4] = {0}, pressed[4] = {0};
    uint32_t hash = 2166136261u;
    int points = 0, t;
    for (t = 0; t < 30 * 60 * 30 && !g.match_over; ++t) {
        az_tick(&g, held, pressed);
        for (int i = 0; i < 4; ++i) {
            if (az_abs(g.p[i].x) > 1400 || az_abs(g.p[i].y) > 2200) (*escaped)++;
            hash = (hash ^ (uint32_t)(g.p[i].x * 7 + g.p[i].y)) * 16777619u;
        }
        hash = (hash ^ (uint32_t)(g.ball.x ^ g.ball.y ^ g.ball.z)) * 16777619u;
        if (g.state == PS_DEAD && g.timer > 40) {
            if (g.point_winner != 2) points++;
            az_next_point(&g);
        }
    }
    *points_out = points;
    *ticks_out = t;
    return hash ^ (uint32_t)(g.games[0] << 8 | g.games[1]);
}

static void test_matches(void) {
    for (int k = 0; k < 9; ++k) {
        int points = 0, ticks = 0, escaped = 0, p2 = 0, t2 = 0, e2 = 0;
        uint32_t seed = 1000u + 77u * (uint32_t)k;
        uint32_t h1 = play_match(seed, k, k % 3, &points, &ticks, &escaped);
        uint32_t h2 = play_match(seed, k, k % 3, &p2, &t2, &e2);
        CHECK(g.match_over, "match %d finishes (%d ticks, %d points)", k, ticks, points);
        CHECK(h1 == h2 && points == p2, "match %d replays exactly", k);
        CHECK(escaped == 0, "match %d: a player left the arena", k);
        CHECK(points >= 8, "match %d: %d points", k, points);
        printf("  match level %2d surface %d: %d-%d in %3d points, %4.1f min\n", k, k % 3, g.games[0], g.games[1], points, ticks * 0.033 / 60);
    }
}

int main(void) {
    test_scoring();
    test_serving();
    test_courts();
    test_ball();
    test_matches();
    printf("core: %d checks, %s (%d failures)\n", checks, failures ? "FAILED" : "ok", failures);
    return failures ? 1 : 0;
}
