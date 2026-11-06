# Game design

Azzurra's Pro Tennis Challenge is a doubles tennis game in the style of the
broadcast-view arcade tennis games of the late 1980s. The game, its rules
engine, its pictures and its music are all original.

## The tour

Azzurra and her partner Viola play fourteen rounds, one per city, against a
new pair of rivals each time:

| # | City | Surface | Light | Rivals |
|--:|------|---------|-------|--------|
| 1 | Napoli Bay | clay | day | Vesuvio Volleys |
| 2 | Rome Classic | clay | day | Roman Aces |
| 3 | Paris Clay | clay | day | Paris Topspin |
| 4 | Chicago Wind | hard | day | Windy Smash |
| 5 | London Grass | grass | day | Royal Volleys |
| 6 | New York Night | hard | floodlights | Metro Power |
| 7 | Tokyo Lights | hard | floodlights | Neon Servers |
| 8 | Cairo Open | clay | day | Nile Aces |
| 9 | Madrid Masters | clay | day | Castilla Pair |
| 10 | Barcelona Cup | clay | day | Catalan Spin |
| 11 | Berlin Classic | hard | day | Berlin Wall |
| 12 | Venice Canal | clay | day | Lagoon Lobs |
| 13 | Sydney Open | hard | day | Harbour Aces |
| 14 | Athens Final | clay | day | Olympus Pair |

The authoritative table (names, rivals, surfaces, skies, shirt colours) is
`CITIES` in [`tools/art_cities.py`](../tools/art_cities.py); the generated
`city_names`, `rival_names`, `city_surface` and `city_night` arrays in
`src/gen/art.inc` come from it. Each city has its own skyline painted from
geometric primitives (Vesuvius over the bay, the Colosseum, the Eiffel Tower, a
black two-antenna tower, Westminster and its clock tower, the Empire State
Building, Tokyo Tower, the pyramids of Giza, the Puerta de Europa, the Sagrada
Familia, the Fernsehturm, the campanile of St Mark's, the Harbour Bridge and
the Acropolis) and its own court colours.

The round number is the computer players' **level** (0 to 13). With each
level the rivals react sooner after a shot, run faster and serve with less
scatter, and flat drives travel faster (`az_ai_speed`, `az_strike`,
`az_serve` in `src/az_core.h`).

Winning round 14 shows the Grand Slam champions' screen. Losing a round
shows the game-over screen; A replays that round, B returns to the title.

## Modes

The title menu (UP/DOWN chooses, LEFT/RIGHT changes, A starts):

* **START WORLD TOUR**: rounds 1 to 14 in order.
* **EXHIBITION: city**: one match in any city, at that city's level.
* **GAMES PER SET: 1, 2 or 4**:
  * 1 or 2: the first team to that many games wins.
  * 4: a team must win by two games, with a tie-break at 4-4.
* **PLAYERS: 1 or 2**: with 2, the second controller plays Viola.

After 15 s idle on the title, a **demo** match between four computer players
starts in a different city each time. Any key returns to the title.

## Controls

| Input | During a rally | Serving |
|-------|----------------|---------|
| D-pad | run | LEFT/RIGHT: move along the baseline before the toss |
| A | drive; a volley before the bounce; a smash on a high ball | toss, then A again to strike |
| B | lob | toss / strike, as A |
| D-pad while hitting | aim: LEFT/RIGHT across, UP deep, DOWN short | LEFT/RIGHT: wide or to the body |
| START | pause (START resumes, SELECT quits to the title) | |

How the swing works:

* **The swing window.** A swing starts on the press. The racket meets the
  ball if it comes into reach during swing ticks 1 to 8 (`AZ_SWING_OPEN` to
  `AZ_SWING_CLOSE`).
* **Aiming by timing.** Without a direction held, the timing sets the aim:
  struck early, the ball is pulled across the court; struck late, it is pushed.
* **Serve quality.** The serve's accuracy depends on how close to the top of
  the toss the ball is struck.
* **Result screens.** They ignore keys for their first 2 s
  (`RESULT_GUARD_TICKS`), so that a button still pressed from the last rally
  does not skip them.

## Rules

These are real doubles rules, implemented in `src/az_core.h`:

* **Serving order:** Azzurra, a rival, Viola, the other rival. The serve
  changes after every game. The first server of a match alternates by city.
* **Serving sides:**
  * Each point is served from the deuce (right) half, then the ad (left) half,
    in turn.
  * The serve must land in the diagonal service box of the receiving team.
  * The receiver is the opponent standing on that half.
* **Faults:**
  * **Fault:** the serve lands out of the box, hits the net, or is off into the stands.
  * **Let:** the serve clips the tape and still lands in the box; it is played again.
  * **Double fault:** two faults in a row lose the point.
* **Rally:**
  * The ball must bounce once on the far side of the net; a second bounce
    wins the point.
  * The serve must bounce before it is returned; there is no volleying the serve.
  * A ball in the net or out of the doubles lines loses the point.
  * The lines are in: there is a tolerance of one ball radius, 4 cm.
* **Scoring:**
  * 0, 15, 30, 40, deuce and advantage. The umpire's call is said from the
    serving team's side.
  * In the tie-break:
    * Points count 1, 2, 3, and a team needs 7 points with a two-point lead.
    * The first point has one server; after it, the serve changes every two
      points, following the same order.

## Courts

The bounce keeps a share of the ball's vertical and horizontal speed that
depends on the surface (`az_bounce_keep`, `az_bounce_slide`):

* **Clay** bounces high and slow.
* **Grass** skids low and fast.
* **Hard** sits in between.

The court uses real dimensions in centimetres:

| Measurement | Length |
|-------------|--------|
| Half-length | 1189 cm |
| Service line from the net | 640 cm |
| Singles half-width | 411 cm |
| Doubles half-width | 549 cm |
| Net height at the posts | 107 cm |
| Net height in the middle | 91 cm |

Gravity is reduced (an "arcade-slow" `AZ_G`) so that a rally is playable at
30 Hz.

## The computer players

Each computer player:

1. waits a few ticks after a shot (its reaction time, shorter at higher levels);
2. predicts where the ball will be at a hittable height (`az_predict`);
3. runs there;
4. swings when the ball is in reach.

Between shots each player returns to a home position:

* the server goes back to the baseline;
* the server's partner stays at the net;
* the receiver's partner stays at the service line.

In the demo all four players use this code.

## What changed from version 1

Version 1 was a single `game.c`. Its bugs were:

* the net collision was 11 cm off the drawn net;
* the out lines did not match the drawn lines;
* the serving order let one team serve twice in a row;
* SELECT could not be reached;
* physics ran once per drawn frame, so the game speed depended on the frame rate;
* the near baseline was off the screen;
* the screen was repainted in full every frame;
* the network mode was not synchronised;
* sustained chords had no instruments.

Version 2 is a rewrite, listed in the [changelog](../CHANGELOG.md):

* it drops the network mode and keeps local two-player play;
* it moves the rules into a header that the host tests can run.
