/*
 * az_core.h - the rules of Azzurra's Pro Tennis Challenge: ball flight, line
 * calls, doubles scoring and serving order, and the computer players.
 *
 * Nothing here calls PRG32: the host tests (tests/test_core.c) run it as is. It
 * needs the geometry constants of src/gen/art.inc (G_*), integer arithmetic only
 * (no floats, no 64-bit division), and advances in fixed 33 ms ticks.
 *
 * Units: centimetres. X across the court (+ to the right of the screen), Y along
 * it (0 at the net, + towards the camera), Z up. The ball keeps 1/16 cm (Q4).
 * Team 0 (Azzurra and her partner) plays the near half, team 1 the far half.
 *
 * Singles uses players 0 and 2 only (players 1 and 3 are inactive) and the singles
 * sidelines. A human player marked `rot` sees the court from her own end (an online
 * player of the far team): her D-pad is turned round before it is applied, so the
 * same inputs give the same game on every console.
 */
#ifndef AZ_CORE_H
#define AZ_CORE_H

#include <stdint.h>

#define AZ_TICK_MS 33u
#define AZ_Q 16                      /* ball sub-units per centimetre */
#define AZ_G 14                      /* gravity, Q4 cm per tick per tick (arcade-slow) */
#define AZ_BALL_R 4                  /* line tolerance: the ball's radius, cm */

/* Input bits seen by the core. */
#define AZ_LEFT 1u
#define AZ_RIGHT 2u
#define AZ_UP 4u
#define AZ_DOWN 8u
#define AZ_A 16u
#define AZ_B 32u

enum { AZ_NEAR = 0, AZ_FAR = 1 };
enum { SHOT_FLAT, SHOT_LOB, SHOT_SMASH, SHOT_SERVE, SHOT_VOLLEY };
enum { PS_SERVE, PS_RALLY, PS_DEAD };
enum {
    EV_TOSS = 1, EV_HIT, EV_BOUNCE, EV_NET, EV_OUT, EV_FAULT, EV_DOUBLE_FAULT, EV_LET,
    EV_POINT, EV_GAME, EV_MATCH, EV_WHIFF, EV_TIEBREAK
};
/* Why a point ended (az_game_t.reason). */
enum { WHY_NONE, WHY_OUT, WHY_NET, WHY_WINNER, WHY_DOUBLE_FAULT, WHY_WRONG_SIDE, WHY_VOLLEYED_SERVE };

#define AZ_SWING_TICKS 12
#define AZ_SWING_OPEN 1              /* the racket can meet the ball from this tick... */
#define AZ_SWING_CLOSE 8             /* ...to this one */
#define AZ_MAX_EVENTS 8

typedef struct {
    int16_t x, y;                    /* feet, cm */
    int16_t home_x, home_y;          /* where the AI returns between shots */
    uint8_t team, side;              /* side: 0 the deuce (right) half, 1 the ad half */
    uint8_t human;
    uint8_t active;                  /* 0: not on court (singles: players 1 and 3) */
    uint8_t rot;                     /* human seeing the court from the far end */
    uint8_t ally;                    /* computer player teamed with a human: steadier */
    uint8_t swing, shot, backhand;   /* swing tick (0 = idle), kind of shot, mirrored */
    uint8_t moving, step;            /* animation */
    uint8_t react;                   /* AI: ticks before it starts to chase */
    uint8_t chasing;
    int16_t tx, ty;                  /* AI: where it is going */
    uint8_t cheer;
} az_player_t;

typedef struct {
    int32_t x, y, z, vx, vy, vz;     /* Q4 */
    uint8_t held;                    /* in the server's hand (before the toss) */
    uint8_t tossed;
    uint8_t live;                    /* the point is being played */
    uint8_t serve;                   /* the shot in the air is a serve */
    uint8_t bounces;                 /* since the last hit */
    uint8_t team;                    /* who hit it last */
    uint8_t hitter;
    uint8_t netted, tape;            /* in the net; grazed the tape */
    uint8_t resting;
} az_ball_t;

typedef struct {
    uint8_t type, value;
    int16_t x;
} az_event_t;

typedef struct {
    az_player_t p[4];                /* 0 Azzurra, 1 her partner, 2 and 3 the rivals */
    az_ball_t ball;
    uint8_t points[2], games[2];
    uint8_t games_to_win;            /* 1, 2 or 4 (4: win by two, tie-break at 4-4) */
    uint8_t singles;
    uint8_t tiebreak;
    uint8_t order;                   /* position in the serving order */
    uint8_t server, receiver;
    uint8_t second_serve;
    uint8_t state;
    uint16_t timer;
    uint8_t level;                   /* 0..13: how good the computer players are */
    uint8_t surface;                 /* 0 clay, 1 grass, 2 hard */
    uint8_t point_winner, reason;
    uint8_t match_over, match_winner;
    uint8_t rally;
    uint32_t rng;
    az_event_t events[AZ_MAX_EVENTS];
    uint8_t event_count;
} az_game_t;

/* Doubles: the serve passes from team to team and, within each team, from one
 * partner to the other. */
static const uint8_t az_serve_order[4] = {0, 2, 1, 3};

static uint32_t az_rand(az_game_t *g) {
    g->rng = g->rng * 1664525u + 1013904223u;
    return g->rng >> 8;
}

static int az_rand_range(az_game_t *g, int lo, int hi) {   /* inclusive */
    return lo + (int)(az_rand(g) % (uint32_t)(hi - lo + 1));
}

static int az_abs(int v) { return v < 0 ? -v : v; }
static int az_clamp(int v, int lo, int hi) { return v < lo ? lo : v > hi ? hi : v; }
static int az_sign(int v) { return v < 0 ? -1 : 1; }

static void az_event(az_game_t *g, int type, int value, int x) {
    if (g->event_count >= AZ_MAX_EVENTS) return;
    az_event_t *e = &g->events[g->event_count++];
    e->type = (uint8_t)type;
    e->value = (uint8_t)value;
    e->x = (int16_t)x;
}

/* ---- geometry -------------------------------------------------------------------- */

/* Screen position of a world point (the same pinhole as tools/geometry.py). */
static int az_depth(int y) { return G_CAM_D + G_HALF_L - y; }
static int az_sx(int x, int y) { return 160 + G_F * x / az_depth(y); }
static int az_sy(int y, int z) { return G_HZ + G_F * (G_H - z) / az_depth(y); }
/* Pixels covered by `cm` centimetres at depth y. */
static int az_px(int cm, int y) { return G_F * cm / az_depth(y); }

static int az_net_height(int x) {
    int ax = az_abs(x);
    if (ax > G_NET_POST) ax = G_NET_POST;
    return G_NET_H_MID + (G_NET_H_POST - G_NET_H_MID) * ax / G_NET_POST;
}

/* The half a team defends: -1 the far half (negative Y), +1 the near one. */
static int az_half(int team) { return team == AZ_NEAR ? 1 : -1; }

/* x sign of a team's deuce (right-hand) half: a near player faces -Y, so her right
 * is +X; a far player faces the camera, so hers is -X. */
static int az_side_sign(int team, int side) {
    int s = team == AZ_NEAR ? 1 : -1;
    return side == 0 ? s : -s;
}

static int az_in_court(const az_game_t *g, int x, int y) {   /* singles or doubles lines, cm */
    int half_w = g->singles ? G_SINGLES : G_DOUBLES;
    return az_abs(x) <= half_w + AZ_BALL_R && az_abs(y) <= G_HALF_L + AZ_BALL_R;
}

/* Is (x, y) in the service box diagonal to a server of `team` serving from `side`? */
static int az_in_service_box(int team, int side, int x, int y) {
    int recv_half = -az_half(team);
    if (y * recv_half < -AZ_BALL_R || az_abs(y) > G_SERVICE + AZ_BALL_R) return 0;
    if (az_abs(x) > G_SINGLES + AZ_BALL_R) return 0;
    /* The diagonal box is the receiving team's own `side`. */
    int want = az_side_sign(1 - team, side);
    return x * want >= -AZ_BALL_R;
}

/* ---- scoring ---------------------------------------------------------------------- */

static int az_points_in_game(const az_game_t *g) { return g->points[0] + g->points[1]; }

static int az_serve_side(const az_game_t *g) { return az_points_in_game(g) & 1; }

static void az_choose_server(az_game_t *g) {
    int pos = g->order;
    if (g->tiebreak) pos += (az_points_in_game(g) + 1) / 2;
    if (g->singles) {                  /* the two players serve a game each */
        g->server = (uint8_t)((pos & 1) ? 2 : 0);
        g->receiver = (uint8_t)(2 - g->server);
        return;
    }
    g->server = az_serve_order[pos & 3];
    int team = g->p[g->server].team, side = az_serve_side(g);
    int recv_team = 1 - team;
    g->receiver = (uint8_t)(recv_team == AZ_NEAR ? (side == 0 ? 0 : 1) : (side == 0 ? 2 : 3));
}

/* Award a point; returns 1 when it ends the match. */
static int az_score_point(az_game_t *g, int team) {
    int other = 1 - team;
    g->points[team]++;
    az_event(g, EV_POINT, team, 0);
    int game_won = 0;
    if (g->tiebreak) {
        game_won = g->points[team] >= 7 && g->points[team] >= g->points[other] + 2;
    } else {
        game_won = g->points[team] >= 4 && g->points[team] >= g->points[other] + 2;
    }
    if (!game_won) return 0;
    g->games[team]++;
    g->points[0] = g->points[1] = 0;
    int n = g->games_to_win;
    int won;
    if (g->tiebreak) {
        won = 1;
    } else if (n >= 4) {
        won = g->games[team] >= n && g->games[team] >= g->games[other] + 2;
    } else {
        won = g->games[team] >= n;
    }
    g->order = (uint8_t)((g->order + 1) & 3);
    g->second_serve = 0;
    if (won) {
        g->match_over = 1;
        g->match_winner = (uint8_t)team;
        az_event(g, EV_MATCH, team, 0);
        return 1;
    }
    az_event(g, EV_GAME, team, 0);
    if (n >= 4 && g->games[0] == n && g->games[1] == n) {
        g->tiebreak = 1;
        az_event(g, EV_TIEBREAK, 0, 0);
    }
    return 0;
}

/* The umpire's call, for the banner: "15-30", "DEUCE", "AD AZZURRA"... `out` holds
 * 20 characters. Points are said from the serving team's side, as umpires do. */
static void az_call(const az_game_t *g, char *out) {
    static const char names[4][3] = {"0", "15", "30", "40"};
    int st = g->p[g->server].team;
    int a = g->points[st], b = g->points[1 - st];
    int k = 0;
    if (g->tiebreak) {
        int v[2] = {a, b};
        for (int i = 0; i < 2; ++i) {
            if (v[i] >= 10) out[k++] = (char)('0' + v[i] / 10);
            out[k++] = (char)('0' + v[i] % 10);
            if (i == 0) out[k++] = '-';
        }
        out[k] = 0;
        return;
    }
    if (a >= 3 && b >= 3) {
        const char *s = a == b ? "DEUCE" : (a > b) == (st == AZ_NEAR) ? "AD AZZURRA" : "AD RIVALS";
        while (*s) out[k++] = *s++;
        out[k] = 0;
        return;
    }
    for (const char *s = names[a > 3 ? 3 : a]; *s; ++s) out[k++] = *s;
    out[k++] = '-';
    if (a == b && a > 0) {
        const char *s = "ALL";
        while (*s) out[k++] = *s++;
    } else {
        for (const char *s = names[b > 3 ? 3 : b]; *s; ++s) out[k++] = *s;
    }
    out[k] = 0;
}

/* ---- setting up a point ------------------------------------------------------------- */

static void az_place(az_player_t *p, int x, int y) {
    p->x = p->home_x = (int16_t)x;
    p->y = p->home_y = (int16_t)y;
    p->tx = (int16_t)x;
    p->ty = (int16_t)y;
    p->swing = 0;
    p->moving = 0;
    p->chasing = 0;
    p->cheer = 0;
}

static void az_ball_to_hand(az_game_t *g) {
    az_player_t *s = &g->p[g->server];
    az_ball_t *b = &g->ball;
    int hand = s->team == AZ_NEAR ? 14 : -14;
    b->x = (s->x + hand) * AZ_Q;
    b->y = (s->y - az_half(s->team) * 6) * AZ_Q;
    b->z = 95 * AZ_Q;
    b->vx = b->vy = b->vz = 0;
}

/* Everyone to their places, the ball in the server's hand. */
static void az_setup_point(az_game_t *g) {
    az_choose_server(g);
    int side = az_serve_side(g);
    int st = g->p[g->server].team, rt = 1 - st;
    for (int i = 0; i < 4; ++i) {
        az_player_t *p = &g->p[i];
        int half = az_half(p->team);
        if (g->singles) {
            /* Server beside the centre mark, receiver on the diagonal; home is the
             * middle of the baseline. */
            int sx = az_side_sign(p->team, side);
            if (!p->active) az_place(p, 0, half * (G_HALF_L + 300));
            else if (i == g->server) az_place(p, sx * 90, half * (G_HALF_L + 45));
            else az_place(p, sx * 260, half * (G_HALF_L + 20));
            p->home_x = 0;
            p->home_y = (int16_t)(half * (G_HALF_L - 30));
            p->react = 0;
            continue;
        }
        int my = p->side == side ? 1 : 0;       /* the player whose half is in play */
        int sx = az_side_sign(p->team, p->side);
        if (p->team == st) {
            if (i == g->server) az_place(p, sx * 230, half * (G_HALF_L + 45));
            else az_place(p, az_side_sign(p->team, 1 - side) * 250, half * 420);
        } else {
            (void)rt;
            if (my) az_place(p, sx * 300, half * (G_HALF_L + 20));
            else az_place(p, sx * 250, half * 650);
        }
        /* Between shots the server goes back to the baseline. */
        if (i == g->server) p->home_y = (int16_t)(half * (G_HALF_L - 40));
        p->react = 0;
    }
    /* The server stands on her own half of the court for this point. */
    az_player_t *s = &g->p[g->server];
    if (!g->singles) s->x = s->home_x = (int16_t)(az_side_sign(st, side) * 230);
    az_ball_t *b = &g->ball;
    b->held = 1;
    b->tossed = 0;
    b->live = 0;
    b->serve = 0;
    b->bounces = 0;
    b->team = (uint8_t)st;
    b->hitter = g->server;
    b->netted = b->tape = 0;
    b->resting = 0;
    az_ball_to_hand(g);
    g->state = PS_SERVE;
    g->timer = 0;
    g->rally = 0;
    g->reason = WHY_NONE;
}

/* A new match. The caller sets p[i].human and p[i].rot first; they are kept. */
static void az_new_match(az_game_t *g, int level, int surface, int games_to_win, uint32_t seed, int first_order,
                         int singles) {
    uint8_t humans[4], rots[4];
    for (int i = 0; i < 4; ++i) {
        humans[i] = g->p[i].human;
        rots[i] = g->p[i].rot;
    }
    uint8_t *raw = (uint8_t *)g;
    for (unsigned i = 0; i < sizeof(*g); ++i) raw[i] = 0;
    g->singles = (uint8_t)(singles ? 1 : 0);
    for (int i = 0; i < 4; ++i) {
        az_player_t *p = &g->p[i];
        p->team = (uint8_t)(i < 2 ? AZ_NEAR : AZ_FAR);
        p->side = (uint8_t)(i & 1);
        p->active = (uint8_t)(!singles || (i & 1) == 0);
        p->human = (uint8_t)(p->active && humans[i]);
        p->rot = (uint8_t)(p->human && rots[i]);
    }
    /* A computer player whose partner is human plays steadier than the rivals. */
    for (int i = 0; i < 4; ++i) g->p[i].ally = (uint8_t)(g->p[i].active && !g->p[i].human && g->p[i ^ 1].human);
    if (singles) first_order &= 1;
    g->level = (uint8_t)level;
    g->surface = (uint8_t)surface;
    g->games_to_win = (uint8_t)games_to_win;
    g->rng = seed | 1u;
    g->order = (uint8_t)(first_order & 3);
    az_setup_point(g);
}

/* ---- the ball --------------------------------------------------------------------- */

/* Launch the ball from where it is to land at (tx, ty) after n ticks. */
static void az_launch(az_ball_t *b, int tx, int ty, int n) {
    if (n < 4) n = 4;
    b->vx = (tx * AZ_Q - b->x) / n;
    b->vy = (ty * AZ_Q - b->y) / n;
    /* z(n) = z0 + n vz - G n (n - 1) / 2 = 0. Rounded down, never towards zero, so
     * that the ball reaches the ground on tick n and not one tick (a metre) late
     * when a smash starts above its own fall. */
    int32_t num = AZ_G * n * (n - 1) / 2 - b->z;
    b->vz = num >= 0 ? num / n : -((-num + n - 1) / n);
}

/* Height (Q4) at which a launched ball passes the net, or a large value if it never
 * crosses. Uses the same stepping as az_ball_step. */
static int32_t az_net_clearance(const az_ball_t *b) {
    int32_t x = b->x, y = b->y, z = b->z, vz = b->vz;
    for (int t = 0; t < 200; ++t) {
        int32_t ny = y + b->vy;
        if ((y > 0) != (ny > 0)) {
            int32_t nz = z + vz;
            int32_t h = az_net_height((x + b->vx / 2) / AZ_Q) * AZ_Q;
            return ((z + nz) >> 1) - h;
        }
        x += b->vx;
        y = ny;
        z += vz;
        vz -= AZ_G;
        if (z < 0) return 1 << 20;
    }
    return 1 << 20;
}

static int az_bounce_keep(int surface) {         /* vertical energy kept, /16 */
    static const uint8_t keep[3] = {11, 9, 12};  /* clay high, grass low, hard in between */
    return keep[surface < 3 ? surface : 0];
}
static int az_bounce_slide(int surface) {        /* horizontal speed kept, /16 */
    static const uint8_t slide[3] = {12, 15, 14};/* clay slow, grass skids */
    return slide[surface < 3 ? surface : 0];
}

static void az_end_point(az_game_t *g, int winner, int why) {
    if (g->state == PS_DEAD) return;
    g->state = PS_DEAD;
    g->timer = 0;
    g->point_winner = (uint8_t)winner;
    g->reason = (uint8_t)why;
    g->ball.live = 0;
    az_score_point(g, winner);
}

static void az_fault(az_game_t *g) {
    int st = g->p[g->server].team;
    if (g->second_serve) {
        az_event(g, EV_DOUBLE_FAULT, st, g->ball.x / AZ_Q);
        g->second_serve = 0;
        az_end_point(g, 1 - st, WHY_DOUBLE_FAULT);
        return;
    }
    az_event(g, EV_FAULT, st, g->ball.x / AZ_Q);
    g->second_serve = 1;
    g->state = PS_DEAD;
    g->timer = 0;
    g->reason = WHY_NONE;
    g->point_winner = 2;               /* no point: the serve is taken again */
    g->ball.live = 0;
}

static void az_ball_step(az_game_t *g) {
    az_ball_t *b = &g->ball;
    if (b->held) {
        az_ball_to_hand(g);
        return;
    }
    if (b->resting) return;
    int32_t py = b->y, pz = b->z;
    b->x += b->vx;
    b->y += b->vy;
    b->z += b->vz;
    b->vz -= AZ_G;
    if (b->tossed) {                   /* the serve toss: straight up and down */
        if (b->z <= 85 * AZ_Q && b->vz < 0) {
            b->tossed = 0;
            b->held = 1;               /* caught: toss again */
            az_ball_to_hand(g);
        }
        return;
    }
    /* The net. */
    if (!b->netted && ((py > 0) != (b->y > 0)) && az_abs(b->x / AZ_Q) <= G_NET_POST) {
        int32_t zc = (pz + b->z) >> 1;
        int32_t h = az_net_height(b->x / AZ_Q) * AZ_Q;
        if (zc < h) {
            b->netted = 1;
            b->y = py > 0 ? 6 * AZ_Q : -6 * AZ_Q;
            b->vy = -b->vy / 8;
            b->vx /= 4;
            if (b->vz > 0) b->vz = 0;
            az_event(g, EV_NET, b->team, b->x / AZ_Q);
            if (b->live) {
                if (b->serve) az_fault(g);
                else az_end_point(g, 1 - b->team, WHY_NET);
            }
        } else if (zc < h + 7 * AZ_Q) {
            b->tape = 1;               /* clipped the tape: slowed, still going */
            b->vy = b->vy * 3 / 4;
            b->vz = b->vz / 2;
        }
    }
    /* The ground. */
    if (b->z <= 0 && b->vz < 0) {
        b->z = 0;
        b->vz = -b->vz * az_bounce_keep(g->surface) / 16;
        b->vx = b->vx * az_bounce_slide(g->surface) / 16;
        b->vy = b->vy * az_bounce_slide(g->surface) / 16;
        if (b->vz < 2 * AZ_G) {
            b->vz = 0;
            b->vx = b->vy = 0;
            b->resting = 1;
        }
        int x = b->x / AZ_Q, y = b->y / AZ_Q;
        az_event(g, EV_BOUNCE, b->bounces, x);
        b->bounces++;
        if (b->live) {
            int hitter_team = b->team;
            if (b->serve && b->bounces == 1) {
                int st = g->p[g->server].team;
                if (az_in_service_box(st, az_serve_side(g), x, y)) {
                    if (b->tape) {
                        az_event(g, EV_LET, st, x);
                        g->state = PS_DEAD;
                        g->timer = 0;
                        g->point_winner = 2;
                        b->live = 0;
                    }
                } else {
                    if (!b->netted) az_event(g, EV_OUT, st, x);
                    az_fault(g);
                }
            } else if (b->bounces == 1) {
                if (y * az_half(hitter_team) > 0 || b->netted) {
                    az_end_point(g, 1 - hitter_team, b->netted ? WHY_NET : WHY_WRONG_SIDE);
                } else if (!az_in_court(g, x, y)) {
                    az_event(g, EV_OUT, hitter_team, x);
                    az_end_point(g, 1 - hitter_team, WHY_OUT);
                }
            } else if (b->bounces >= 2) {
                az_end_point(g, hitter_team, WHY_WINNER);
            }
        }
    }
    /* Off into the stands. */
    if (b->live && (az_abs(b->x / AZ_Q) > 1500 || az_abs(b->y / AZ_Q) > 2400)) {
        if (b->bounces == 0) {
            az_event(g, EV_OUT, b->team, b->x / AZ_Q);
            if (b->serve) az_fault(g);
            else az_end_point(g, 1 - b->team, WHY_OUT);
        } else {
            az_end_point(g, b->team, WHY_WINNER);
        }
    }
    if (az_abs(b->x / AZ_Q) > 1700 || az_abs(b->y / AZ_Q) > 2600) {
        b->vx = b->vy = b->vz = 0;
        b->resting = 1;
    }
}

/* ---- hitting ------------------------------------------------------------------------- */

/* Can player i meet the ball now? Generous for a human, as arcade games are. */
static int az_in_reach(const az_game_t *g, int i) {
    const az_player_t *p = &g->p[i];
    const az_ball_t *b = &g->ball;
    if (!p->active || !b->live || b->held || b->tossed || b->team == p->team || b->netted) return 0;
    if (b->serve && b->bounces == 0) return 0;          /* a serve must bounce first */
    if (b->bounces >= 2) return 0;
    if ((b->y / AZ_Q) * az_half(p->team) < -20) return 0; /* still on the other side */
    int dx = az_abs(b->x / AZ_Q - p->x), dy = az_abs(b->y / AZ_Q - p->y), z = b->z / AZ_Q;
    int rx = p->human ? 130 : 115, ry = p->human ? 120 : 85;
    return dx <= rx && dy <= ry && z <= 250;
}

/* Where to aim and how long to fly, then launch. `aim_x` is -1, 0 or +1 (screen
 * left, centre, right), `depth` -1 short, 0, +1 deep; `err` the scatter in cm. */
static void az_strike(az_game_t *g, int i, int shot, int aim_x, int depth, int err) {
    az_player_t *p = &g->p[i];
    az_ball_t *b = &g->ball;
    int opp = -az_half(p->team);
    int z = b->z / AZ_Q;
    int volley = b->bounces == 0;
    if (shot == SHOT_FLAT && z > 200 && az_abs(b->y / AZ_Q) < 900) shot = SHOT_SMASH;
    else if (shot == SHOT_FLAT && volley) shot = SHOT_VOLLEY;
    int tx, ty, speed;
    switch (shot) {
    case SHOT_LOB:
        tx = aim_x * 280;
        ty = opp * (1000 + depth * 80);
        speed = 30;
        break;
    case SHOT_SMASH:
        tx = aim_x * 360;
        ty = opp * (760 + depth * 200);
        speed = 92;
        break;
    case SHOT_VOLLEY:
        tx = aim_x * 400;
        ty = opp * (620 + depth * 220);
        speed = 54;
        break;
    default:
        tx = aim_x * 330;
        ty = opp * (880 + depth * 220);
        speed = 60 + g->level / 2;
        break;
    }
    if (!aim_x) tx = (int)(az_rand(g) % 241) - 120;
    tx += az_rand_range(g, -err, err);
    ty += az_rand_range(g, -err, err);
    int dx = tx - b->x / AZ_Q, dy = ty - b->y / AZ_Q;
    int dist = az_abs(dx) > az_abs(dy) ? az_abs(dx) + az_abs(dy) / 2 : az_abs(dy) + az_abs(dx) / 2;
    int n = dist / speed;
    if (n < 10) n = 10;
    az_launch(b, tx, ty, n);
    /* Clear the net: a flat ball that would not is given a little more air. */
    for (int k = 0; k < 6 && az_net_clearance(b) < 14 * AZ_Q; ++k) {
        n += 2;
        az_launch(b, tx, ty, n);
    }
    b->team = p->team;
    b->hitter = (uint8_t)i;
    b->bounces = 0;
    b->serve = 0;
    b->tape = 0;
    b->live = 1;
    g->rally++;
    p->shot = (uint8_t)shot;
    if (!p->swing) p->swing = AZ_SWING_OPEN + 2;
    az_event(g, EV_HIT, shot, b->x / AZ_Q);
    /* The other side reacts. */
    for (int k = 0; k < 4; ++k) {
        if (g->p[k].team != p->team) {
            int slow = 9 - g->level / 2;
            g->p[k].react = (uint8_t)(g->p[k].human ? 0 : (slow < 2 ? 2 : slow) + (int)(az_rand(g) & 3));
        }
        g->p[k].chasing = 0;
    }
}

/* The serve itself. `quality` 0..16 (16 = struck at the top of the toss). */
static void az_serve(az_game_t *g, int quality, int aim_x) {
    az_player_t *s = &g->p[g->server];
    az_ball_t *b = &g->ball;
    int st = s->team, side = az_serve_side(g);
    int want = az_side_sign(1 - st, side);       /* the diagonal box's x sign */
    int opp = -az_half(st);
    int tx = want * (aim_x ? (aim_x * want > 0 ? 330 : 90) : 210);
    int ty = opp * 500;
    int err = (16 - quality) * 14 + (g->second_serve ? 25 : 45);
    if (!s->human) err = g->second_serve ? 40 : 95 - g->level * 3;
    tx += az_rand_range(g, -err, err);
    ty += az_rand_range(g, -err, err);
    int dist = az_abs(ty - b->y / AZ_Q) + az_abs(tx - b->x / AZ_Q) / 2;
    int n = dist / (g->second_serve ? 50 : 70);
    b->tossed = 0;
    b->held = 0;
    az_launch(b, tx, ty, n);
    if (g->second_serve) {
        for (int k = 0; k < 6 && az_net_clearance(b) < 24 * AZ_Q; ++k) {
            n += 2;
            az_launch(b, tx, ty, n);
        }
    }
    b->team = (uint8_t)st;
    b->hitter = g->server;
    b->bounces = 0;
    b->serve = 1;
    b->tape = 0;
    b->live = 1;
    s->shot = SHOT_SERVE;
    s->swing = AZ_SWING_OPEN + 2;
    g->state = PS_RALLY;
    g->rally = 0;
    az_event(g, EV_HIT, SHOT_SERVE, b->x / AZ_Q);
    for (int k = 0; k < 4; ++k) {
        if (g->p[k].team != st) g->p[k].react = (uint8_t)(g->p[k].human ? 0 : 3);
        g->p[k].chasing = 0;
    }
}

static void az_toss(az_game_t *g) {
    az_ball_t *b = &g->ball;
    if (!b->held) return;
    b->held = 0;
    b->tossed = 1;
    b->vx = b->vy = 0;
    b->vz = 300;                       /* about two metres up: 0.7 s to the top */
    az_event(g, EV_TOSS, 0, b->x / AZ_Q);
}

/* ---- moving ------------------------------------------------------------------------- */

static void az_clamp_player(az_player_t *p) {
    int half = az_half(p->team);
    int lo = p->team == AZ_NEAR ? 70 : -(G_HALF_L + 420);
    int hi = p->team == AZ_NEAR ? G_HALF_L + 250 : -70;
    (void)half;
    p->y = (int16_t)az_clamp(p->y, lo, hi);
    p->x = (int16_t)az_clamp(p->x, -640, 640);
}

static void az_move_toward(az_player_t *p, int tx, int ty, int speed) {
    int dx = tx - p->x, dy = ty - p->y;
    int mx = az_clamp(dx, -speed, speed), my = az_clamp(dy, -speed, speed);
    /* Diagonals are not faster. */
    if (mx && my) {
        mx = mx * 3 / 4;
        my = my * 3 / 4;
        if (!mx) mx = az_sign(dx);
        if (!my) my = az_sign(dy);
    }
    p->x = (int16_t)(p->x + mx);
    p->y = (int16_t)(p->y + my);
    p->moving = (az_abs(dx) > 3 || az_abs(dy) > 3) ? 1 : 0;
    az_clamp_player(p);
}

static int az_ai_speed(const az_game_t *g, int i) {
    if (g->p[i].ally) return 17;
    return 13 + g->level / 2;
}

/* Run the ball forward to find where player i could meet it: the first tick at which
 * it is hittable and she can be there in time. Returns the tick or -1. */
static int az_predict(const az_game_t *g, int i, int *out_x, int *out_y) {
    const az_player_t *p = &g->p[i];
    az_ball_t b = g->ball;
    int speed = az_ai_speed(g, i);
    int half = az_half(p->team);
    int bounces = b.bounces;
    for (int t = 1; t < 110; ++t) {
        int32_t py = b.y;
        b.x += b.vx;
        b.y += b.vy;
        b.z += b.vz;
        b.vz -= AZ_G;
        if ((py > 0) != (b.y > 0)) {
            int32_t h = az_net_height(b.x / AZ_Q) * AZ_Q;
            if (b.z < h) return -1;    /* it will die in the net */
        }
        if (b.z <= 0 && b.vz < 0) {
            b.z = 0;
            b.vz = -b.vz * az_bounce_keep(g->surface) / 16;
            b.vx = b.vx * az_bounce_slide(g->surface) / 16;
            b.vy = b.vy * az_bounce_slide(g->surface) / 16;
            bounces++;
            if (bounces == 1 && !az_in_court(g, b.x / AZ_Q, b.y / AZ_Q)) return -1;   /* let it go */
            if (bounces >= 2) return -1;
        }
        int x = b.x / AZ_Q, y = b.y / AZ_Q, z = b.z / AZ_Q;
        if (y * half < 40) continue;
        int volley_ok = !g->ball.serve && bounces == 0 && az_abs(y) < 760 && z < 200 && z > 30;
        int ground_ok = bounces == 1 && z < 150 && (b.vz < 0 || z > 70);
        if (!volley_ok && !ground_ok) continue;
        /* Stand beside the ball, on the forehand. */
        int fore = p->team == AZ_NEAR ? -1 : 1;
        int sx = x + fore * 45, sy = y + half * 20;
        int dist = az_abs(sx - p->x) + az_abs(sy - p->y);
        if (dist <= speed * (t + 1) + 40) {
            *out_x = sx;
            *out_y = sy;
            return t;
        }
    }
    return -1;
}

static void az_ai(az_game_t *g, int i) {
    az_player_t *p = &g->p[i];
    az_ball_t *b = &g->ball;
    int speed = az_ai_speed(g, i);
    int half = az_half(p->team);
    if (g->state == PS_SERVE) {
        p->moving = 0;
        if (i == g->server) {
            g->timer++;
            if (b->held && g->timer > 24) az_toss(g);
            if (b->tossed && b->vz <= 20 && b->vz > 20 - AZ_G) {
                /* Strike near the top of the toss. */
                int q = 16 - (int)(az_rand(g) % 4);
                az_serve(g, q, 0);
            }
        }
        return;
    }
    if (g->state == PS_DEAD) {
        p->moving = 0;
        return;
    }
    int coming = b->live && b->team != p->team && !b->netted;
    if (coming) {
        if (p->react) {
            p->react--;
            p->moving = 0;
            return;
        }
        if (!p->chasing) {
            /* Decide who of the pair takes it: the one who gets there first. */
            int mate = i ^ 1;
            int ax, ay, bx = 0, by = 0;
            int ta = az_predict(g, i, &ax, &ay);
            int tb = (g->p[mate].human || !g->p[mate].active) ? -1 : az_predict(g, mate, &bx, &by);
            if (g->p[mate].human) {
                /* A human partner takes what is on her side. */
                int mine = (b->x / AZ_Q) * az_side_sign(p->team, p->side) > 0;
                if (!mine) ta = -1;
            }
            if (ta >= 0 && (tb < 0 || ta <= tb + 2)) {
                p->chasing = 1;
                p->tx = (int16_t)ax;
                p->ty = (int16_t)ay;
            } else {
                p->chasing = 2;        /* cover: drift towards the ball's side of the court */
                p->tx = (int16_t)(p->home_x / 2 + (b->x / AZ_Q) / 3);
                p->ty = p->home_y;
            }
        }
        if (p->chasing == 1) {
            int ax, ay;
            if (az_predict(g, i, &ax, &ay) >= 0) {
                p->tx = (int16_t)ax;
                p->ty = (int16_t)ay;
            }
        }
        az_move_toward(p, p->tx, p->ty, speed);
        if (az_in_reach(g, i) && !p->swing) {
            /* Choose the shot: lob a pair at the net, else drive at the open side. */
            const az_player_t *o0 = &g->p[p->team == AZ_NEAR ? 2 : 0], *o1 = &g->p[p->team == AZ_NEAR ? 3 : 1];
            if (!o1->active) o1 = o0;
            int at_net = az_abs(o0->y) < 500 && az_abs(o1->y) < 500;
            int shot = at_net && (az_rand(g) & 1) ? SHOT_LOB : (az_rand(g) % 9 == 0 ? SHOT_LOB : SHOT_FLAT);
            int gap = (o0->x + o1->x) / 2;
            int aim = gap > 60 ? -1 : gap < -60 ? 1 : (az_rand(g) & 1 ? 1 : -1);
            int depth = (int)(az_rand(g) % 3) - 1;
            int err = p->ally ? 80 : 150 - g->level * 7;
            /* Now and then a real mistake: long, wide or into the net. */
            int blunder = p->ally ? 14 : 8 + g->level;
            if (az_rand(g) % (uint32_t)blunder == 0) err += 260;
            p->backhand = (uint8_t)(((b->x / AZ_Q) - p->x) * (p->team == AZ_NEAR ? 1 : -1) < 0);
            p->swing = 1;
            az_strike(g, i, shot, aim, depth, err);
        }
        (void)half;
    } else {
        /* Back to position, a little towards the ball's side. */
        int tx = p->home_x;
        if (b->live) tx = p->home_x * 2 / 3 + (b->x / AZ_Q) / 4;
        az_move_toward(p, tx, p->home_y, speed - 4);
        p->chasing = 0;
    }
}

/* A human player: the D-pad moves, A drives, B lobs. Swings start on the press and
 * meet the ball if it comes into reach while the racket is moving through. */
/* The D-pad turned round: what a player at the far end means, in the camera's terms. */
static uint32_t az_rotate(uint32_t in) {
    uint32_t out = in & ~(AZ_LEFT | AZ_RIGHT | AZ_UP | AZ_DOWN);
    if (in & AZ_LEFT) out |= AZ_RIGHT;
    if (in & AZ_RIGHT) out |= AZ_LEFT;
    if (in & AZ_UP) out |= AZ_DOWN;
    if (in & AZ_DOWN) out |= AZ_UP;
    return out;
}

static void az_human(az_game_t *g, int i, uint32_t held, uint32_t pressed) {
    az_player_t *p = &g->p[i];
    az_ball_t *b = &g->ball;
    if (p->rot) {
        held = az_rotate(held);
        pressed = az_rotate(pressed);
    }
    /* Towards the net is "deep" whichever end she plays from. */
    uint32_t fwd = p->team == AZ_NEAR ? AZ_UP : AZ_DOWN, back = p->team == AZ_NEAR ? AZ_DOWN : AZ_UP;
    if (g->state == PS_SERVE) {
        p->moving = 0;
        if (i != g->server) return;
        /* Before the toss the server may shuffle along her baseline. */
        if (b->held) {
            int sgn = az_side_sign(p->team, az_serve_side(g));
            int lo = sgn > 0 ? 60 : -500, hi = sgn > 0 ? 500 : -60;
            if (held & AZ_LEFT) p->x = (int16_t)az_clamp(p->x - 8, lo, hi);
            if (held & AZ_RIGHT) p->x = (int16_t)az_clamp(p->x + 8, lo, hi);
            if (pressed & (AZ_A | AZ_B)) az_toss(g);
            return;
        }
        if (b->tossed && (pressed & (AZ_A | AZ_B))) {
            /* Quality: how close to the top of the toss she struck it. */
            int q = 16 - az_abs(b->vz) / 10;
            if (q < 0) q = 0;
            int aim = (held & AZ_LEFT) ? -1 : (held & AZ_RIGHT) ? 1 : 0;
            az_serve(g, q, aim);
        }
        return;
    }
    int speed = 18;
    int mx = 0, my = 0;
    if (held & AZ_LEFT) mx -= speed;
    if (held & AZ_RIGHT) mx += speed;
    if (held & AZ_UP) my -= speed;
    if (held & AZ_DOWN) my += speed;
    if (mx && my) {
        mx = mx * 3 / 4;
        my = my * 3 / 4;
    }
    if (p->swing) {                    /* swinging: half speed */
        mx /= 2;
        my /= 2;
    }
    p->x = (int16_t)(p->x + mx);
    p->y = (int16_t)(p->y + my);
    p->moving = (mx || my) ? 1 : 0;
    az_clamp_player(p);
    if (g->state != PS_RALLY) return;
    if (!p->swing && (pressed & (AZ_A | AZ_B))) {
        p->swing = 1;
        p->shot = (pressed & AZ_B) ? SHOT_LOB : SHOT_FLAT;
        p->backhand = (uint8_t)(((b->x / AZ_Q) - p->x) * (p->team == AZ_NEAR ? 1 : -1) < 0);
    }
    if (p->swing >= AZ_SWING_OPEN && p->swing <= AZ_SWING_CLOSE && az_in_reach(g, i)) {
        int aim = (held & AZ_LEFT) ? -1 : (held & AZ_RIGHT) ? 1 : 0;
        int depth = (held & fwd) ? 1 : (held & back) ? -1 : 0;
        /* Timing: struck early the ball is pulled across, late it is pushed. */
        if (!aim) {
            int t = p->swing;
            aim = t <= 2 ? (p->backhand ? 1 : -1) : t >= 7 ? (p->backhand ? -1 : 1) : 0;
        }
        az_strike(g, i, p->shot, aim, depth, 50);
        p->swing = AZ_SWING_CLOSE + 1;   /* the follow-through */
    }
}

/* ---- one tick ----------------------------------------------------------------------- */

/* `held`/`pressed` per player (only human players read them). */
static void az_tick(az_game_t *g, const uint32_t held[4], const uint32_t pressed[4]) {
    g->event_count = 0;
    if (g->match_over && g->state == PS_DEAD) {
        g->timer++;
        az_ball_step(g);
        for (int i = 0; i < 4; ++i) {
            g->p[i].moving = 0;
            g->p[i].cheer = g->p[i].team == g->match_winner;
        }
        return;
    }
    for (int i = 0; i < 4; ++i) {
        az_player_t *p = &g->p[i];
        if (!p->active) continue;
        if (p->swing) {
            if (++p->swing > AZ_SWING_TICKS) p->swing = 0;
        }
        if (p->human) az_human(g, i, held[i], pressed[i]);
        else az_ai(g, i);
        if (p->moving) p->step++;
    }
    az_ball_step(g);
    if (g->state == PS_DEAD) {
        g->timer++;
    }
}

/* Called by the front end when the banner after a point has been shown. Returns 1 if
 * a new point (or the second serve) is ready. */
static int az_next_point(az_game_t *g) {
    if (g->state != PS_DEAD || g->match_over) return 0;
    if (g->point_winner == 2) {        /* a fault or a let: the same point again */
        int second = g->second_serve;
        az_setup_point(g);
        g->second_serve = (uint8_t)second;
        return 1;
    }
    g->second_serve = 0;
    az_setup_point(g);
    return 1;
}

#endif
