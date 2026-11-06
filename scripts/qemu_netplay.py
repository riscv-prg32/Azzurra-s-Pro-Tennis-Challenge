#!/usr/bin/env python3
"""Online matches between PRG32 QEMU consoles through a PRG32 Multiplayer Server.

  scripts/qemu_netplay.py --match 1v1 --teams 0,1 --out build/qemu-netplay-1v1
  scripts/qemu_netplay.py --match 2v2 --teams 0,1,0,1 --out build/qemu-netplay-2v2
  scripts/qemu_netplay.py --match 2v2 --teams 0,1,1 --out build/qemu-netplay-3p

Starts the server from the PRG32-Multiplayer-Server checkout ($MP_SERVER_REPO,
default ../PRG32-Multiplayer-Server) on --port, with its data in OUT/server-data,
and one QEMU console per team in --teams (0 Azzurra's side, 1 the rivals').
Each console runs on its own copy of the PRG32 QEMU flash image, with its NVS
erased so that it gets its own multiplayer identity, as `prg32 qemu run
--instance N` does; the PRG32 checkout is never modified.

The QEMU firmware connects to the server address compiled into it
(CONFIG_PRG32_MULTIPLAYER_SERVER_URL in $PRG32_REPO/build-qemu/sdkconfig). The
script does not rebuild the firmware: it gives QEMU's user network the subnet of
that address and forwards that address and port to the local server
(`guestfwd`), so the consoles reach this server whatever address was compiled in.

Every console walks the menus as a player would (MATCH, GAMES PER SET, PLAY
ONLINE, its team, READY), then plays with scripted key presses until a result
screen appears. A silent observer joins the room and records every snapshot the
server relays (OUT/observer.jsonl). The report (OUT/report.json, and printed):

  - each console's screenshots: lobby, play, result (OUT/c<N>_*.png);
  - which result each console showed (won or lost), which must be one of each
    side;
  - from the observer: every console's lockstep progress (ticks per second, so
    the game speed), its publish rate, and that the inputs each console sent for
    a tick never changed from one snapshot to the next.

An ESP32-C6 board can join the same match as one more console (--board-port,
--board-url, --board-slot, --board-team). The script uploads nothing: the
cartridge must already be in --board-slot. It restarts that cartridge over USB
(`prg32 esp32c6 run`), walks the same menus with `prg32 esp32c6 key`, reads the
screen with `prg32 esp32c6 screenshot` over Wi-Fi, and starts the QEMU consoles
once the board is READY, so that no console starts alone against the computer.
The board must reach this server: with its compiled address, or by LAN
discovery when the server runs with discovery on (use --external-server for a
server already running on the LAN).

  scripts/qemu_netplay.py --match 1v1 --teams 0 --external-server --port 8081 \
      --board-port /dev/cu.usbmodem101 --board-url http://192.168.1.163 \
      --board-slot cart4 --board-team 1 --out build/qemu-netplay-board
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qemu_preview as qp  # noqa: E402

ROOT = qp.ROOT
PRG32 = qp.PRG32
SERVER = Path(os.environ.get("MP_SERVER_REPO", ROOT.parent / "PRG32-Multiplayer-Server")).resolve()
SIGNATURE = "azzurra-tennis:v2"          # src/az_net.h: NET_SIGNATURE
NVS_OFFSET, NVS_SIZE = 0x9000, 0x6000      # PRG32 profiles/partitions_prg32.csv
BASE_PORT = 4600


# ---- the snapshot format of src/az_net.h -------------------------------------------------------

def unthree(v: int) -> list[int]:
    return [v % 36, (v // 36) % 36, v // 1296]


def decode(msg: dict) -> dict | None:
    flags = msg["flags"]
    phase = flags & 3
    if phase == 1:
        return {"phase": "lobby", "team": (flags >> 2) & 1, "ready": (flags >> 3) & 1, "start": (flags >> 4) & 1,
                "doubles": (flags >> 5) & 1, "city": (flags >> 8) & 15, "tag": (msg["input"] >> 3) & 15}
    if phase == 2:
        x, y, s = msg["x"] & 0xFFFF, msg["y"] & 0xFFFF, msg["sprite"]
        pair = (flags >> 8) | ((msg["input"] & 7) << 8)
        sym = unthree(x) + unthree(y) + unthree(s) + [pair % 36, pair // 36]
        return {"phase": "match", "tick6": (flags >> 2) & 63, "sym": sym, "tag": (msg["input"] >> 3) & 15}
    return None


# ---- the server and the observer -----------------------------------------------------------------

def start_server(port: int, data: Path, public: bool) -> subprocess.Popen:
    if not (SERVER / "src/server.js").exists():
        raise SystemExit(f"no PRG32 Multiplayer Server at {SERVER} (set MP_SERVER_REPO)")
    if not (SERVER / "node_modules/ws").exists():
        raise SystemExit(f"run `npm install` in {SERVER} first")
    data.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PORT=str(port), HOST="0.0.0.0" if public else "127.0.0.1", DATA_DIR=str(Path(data).resolve()), DISCOVERY_PORT="0")
    log = open(data / "server.out", "wb")
    proc = subprocess.Popen(["node", "src/server.js"], cwd=SERVER, env=env, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(100):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1) as r:
                if r.status == 200:
                    return proc
        except OSError:
            time.sleep(0.1)
    proc.kill()
    raise SystemExit("the multiplayer server did not start")


LATEST: dict[int, dict] = {}              # player ID -> the latest decoded snapshot


def observer(port: int, out: Path, stop: threading.Event) -> None:
    """A silent member of the room: it joins, never publishes, records what is relayed."""
    import websockets

    async def run():
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({"type": "join", "signature": SIGNATURE, "protocol": "prg32-multiplayer-1.0"}))
            with out.open("w") as f:
                t0 = time.monotonic()
                pinged = time.monotonic()
                while not stop.is_set():
                    if time.monotonic() - pinged > 4.0:      # the server drops a silent client
                        await ws.send(json.dumps({"type": "ping"}))
                        pinged = time.monotonic()
                    try:
                        raw = await asyncio.wait_for(ws.recv(), 0.5)
                    except asyncio.TimeoutError:
                        continue
                    msg = json.loads(raw)
                    msg["t"] = round(time.monotonic() - t0, 3)
                    f.write(json.dumps(msg) + "\n")
                    if msg.get("type") == "peer":
                        snap = decode(msg)
                        if snap:
                            snap["seen"] = time.monotonic()
                            snap["platform"] = msg.get("platform")
                            LATEST[msg["player_id"]] = snap

    try:
        asyncio.run(run())
    except Exception as e:  # the report says what the observer saw, even if it stops early
        print(f"observer stopped: {e!r}", file=sys.stderr)


# ---- one QEMU console -------------------------------------------------------------------------

def compiled_server_url() -> tuple[str, int]:
    cfg = (PRG32 / "build-qemu/sdkconfig").read_text()
    m = re.search(r'CONFIG_PRG32_MULTIPLAYER_SERVER_URL="ws://([0-9.]+):(\d+)', cfg)
    if not m:
        raise SystemExit("the QEMU firmware has no ws://IP:PORT multiplayer server address")
    return m.group(1), int(m.group(2))


def drain(sock, stop: threading.Event, pcm: bytearray) -> None:
    """An audio port that grants no credits: the firmware then stops pacing on it."""
    sock.settimeout(0.2)
    while not stop.is_set():
        try:
            if not sock.recv(65536):
                return
        except (TimeoutError, socket.timeout):
            continue
        except OSError:
            return


class Console:
    def __init__(self, index: int, team: int, args, tmp: Path, url: tuple[str, int]):
        self.i, self.team, self.args = index, team, args
        self.dir = tmp / f"c{index}"
        self.dir.mkdir()
        self.flash, self.efuse = self.dir / "flash.bin", self.dir / "efuse.bin"
        shutil.copy2(PRG32 / "build-qemu/qemu_flash.bin", self.flash)
        shutil.copy2(PRG32 / "build-qemu/qemu_efuse.bin", self.efuse)
        with self.flash.open("r+b") as f:      # a new installation identity
            f.seek(NVS_OFFSET)
            f.write(b"\xff" * NVS_SIZE)
        subprocess.run([sys.executable, "-m", "prg32", "qemu", "upload", str(args.cart.resolve()),
                        "--flash", str(self.flash)], cwd=PRG32, check=True, stdout=subprocess.DEVNULL)
        port = BASE_PORT + 10 * index
        self.ports = (port, port + 1, port + 2, port + 3)    # console, audio, qmp, gdb
        ip, sport = url
        net = ".".join(ip.split(".")[:3])
        host = f"{net}.2" if not ip.endswith(".2") else f"{net}.3"
        nic = (f"user,model=open_eth,net={net}.0/24,host={host},dhcpstart={net}.{100 + index},"
               f"guestfwd=tcp:{ip}:{sport}-cmd:nc 127.0.0.1 {args.port}")
        cmd = [qp.find_qemu(), "-M", "esp32c3", "-m", "4M",
               "-drive", f"file={self.flash},if=mtd,format=raw",
               "-drive", f"file={self.efuse},if=none,format=raw,id=efuse",
               "-global", "driver=nvram.esp32c3.efuse,property=drive,value=efuse",
               "-global", "driver=timer.esp32c3.timg,property=wdt_disable,value=true",
               "-nic", nic, "-display", "sdl",
               "-qmp", f"tcp:127.0.0.1:{self.ports[2]},server=on,wait=off",
               "-gdb", f"tcp:127.0.0.1:{self.ports[3]}",
               "-serial", f"tcp::{self.ports[0]},server=on,wait=off,nodelay=on",
               "-serial", f"tcp::{self.ports[1]},server=on,wait=on,nodelay=on"]
        self.log = open(self.dir / "qemu.log", "wb")
        env = dict(os.environ, SDL_VIDEODRIVER=os.environ.get("SDL_VIDEODRIVER", "offscreen"))
        self.proc = subprocess.Popen(cmd, stdout=self.log, stderr=subprocess.STDOUT, env=env)
        self.stop = threading.Event()
        self.pcm, self.transcript = bytearray(), bytearray()
        audio = qp.connect(self.ports[1], self.proc)
        reader = qp.audio_reader if args.audio else drain
        threading.Thread(target=reader, args=(audio, self.stop, self.pcm), daemon=True).start()
        self.console = qp.connect(self.ports[0], self.proc)
        threading.Thread(target=qp.console_reader, args=(self.console, self.stop, self.transcript), daemon=True).start()
        self.qmp = qp.Qmp(qp.connect(self.ports[2], self.proc))
        self.qmp_lock = threading.Lock()
        self.result: str | None = None
        self.shots: list[str] = []
        self.events: list[tuple[float, str]] = []

    def grab(self, name: str | None = None):
        dump = self.dir / "fb.raw"
        with self.qmp_lock:
            self.qmp.execute("stop")
            self.qmp.execute("pmemsave", val=FB_ADDR[0], size=4, filename=str(dump))
            pointer = int.from_bytes(dump.read_bytes(), "little")
            self.qmp.execute("pmemsave", val=pointer, size=320 * 240 * 2, filename=str(dump))
            self.qmp.execute("cont")
        img = qp.rgb565_image(dump.read_bytes())
        if name:
            path = self.args.out / f"c{self.i}_{name}.png"
            img.crop((0, 20, 320, 220)).save(path)
            self.shots.append(path.name)
        return img

    def tap(self, key: str, seconds: float = 0.12):
        end = time.monotonic() + seconds
        while True:
            self.console.sendall(qp.KEYS[key].encode())
            time.sleep(0.03)
            if time.monotonic() >= end:
                break

    def chord(self, keys, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            for k in keys:
                self.tap(k, 0.0)

    def player_id(self) -> int | None:
        found = re.findall(rb"prg32_mp: joined \S+ as player (\d+)", bytes(self.transcript))
        return int(found[-1]) if found else None

    def snapshot(self) -> dict | None:
        pid = self.player_id()
        return LATEST.get(pid) if pid else None

    def close(self):
        self.stop.set()
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.log.close()
        (self.args.out / f"c{self.i}_console.log").write_bytes(self.transcript)


class Board:
    """The ESP32-C6 board as one more console: keys over USB, the screen over Wi-Fi.
    Its screenshots have the same 320x240 frame as a QEMU framebuffer grab."""

    def __init__(self, index: int, args):
        self.i, self.team, self.args = index, args.board_team, args
        found = sorted(Path.home().glob(".espressif/python_env/*/bin/python"))
        self.python = os.environ.get("PRG32_PYTHON") or (str(found[-1]) if found else sys.executable)
        self.result: str | None = None
        self.shots: list[str] = []
        self.events: list[tuple[float, str]] = []
        self.ready = threading.Event()

    def prg32(self, *argv: str) -> subprocess.CompletedProcess:
        return subprocess.run([self.python, "-m", "prg32", "esp32c6", *argv], cwd=PRG32,
                              capture_output=True, text=True, timeout=90)

    def grab(self, name: str | None = None):
        bmp = (self.args.out / "board.bmp").resolve()      # the prg32 tool runs in the PRG32 checkout
        bmp.unlink(missing_ok=True)
        self.prg32("screenshot", "--url", self.args.board_url, "--out", str(bmp))
        try:
            img = qp.Image.open(bmp).convert("RGB")
        except Exception:                             # Wi-Fi hiccup: no picture this time
            return None
        if img.size != (320, 240):
            return None
        if name:
            path = self.args.out / f"c{self.i}_{name}.png"
            img.crop((0, 20, 320, 220)).save(path)
            self.shots.append(path.name)
        return img

    def keys(self, *keys: str, gap_ms: int = 500):
        """Each argument is one press; "LEFT+A" holds both."""
        self.prg32("key", "--port", self.args.board_port, "--hold-ms", "120", "--gap-ms", str(gap_ms),
                   *[k.upper() for k in keys])

    def close(self):
        pass


def board_wait(b: Board, test, seconds: float):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        img = b.grab()
        if img is not None and test(img):
            return img
        time.sleep(1.0)
    return None


def play_board(b: Board, args, t0: float, deadline: float):
    try:
        board_match(b, args, t0, deadline)
    except Exception as e:                           # in the report, not only on stderr
        b.events.append((time.monotonic() - t0, f"error: {e!r}"))
        b.ready.set()


def board_match(b: Board, args, t0: float, deadline: float):
    rnd = random.Random(2000 + b.i)
    try:
        b.prg32("run", "--port", args.board_port, "--slot", args.board_slot)   # a fresh title menu
        if not board_wait(b, is_title, 40):
            b.events.append((time.monotonic() - t0, "no title"))
            return
        time.sleep(1.5)
        b.grab("title")
        b.keys(*menu_keys(args))
        if not board_wait(b, is_lobby, 15):
            b.grab("nolobby")
            b.events.append((time.monotonic() - t0, "never reached the lobby"))
            return
        b.events.append((time.monotonic() - t0, "lobby"))
        time.sleep(2.0)
        b.keys(*(["right"] if b.team else []), "a")    # TEAM (the first row), then READY
        time.sleep(1.5)
        b.grab("lobby")
        b.events.append((time.monotonic() - t0, "ready"))
    finally:
        b.ready.set()
    # From here on no key until the match: a key in the lobby could leave it.
    if not board_wait(b, lambda img: not is_lobby(img), args.lobby_wait + 90):
        b.events.append((time.monotonic() - t0, "no match"))
        return
    b.events.append((time.monotonic() - t0, "match"))
    time.sleep(1.5)
    b.grab("intro")
    played = time.monotonic()
    shots = {12.0: "play1", 30.0: "play2", 60.0: "play3"}
    # The board's own snapshots, as the server relays them, say when the match
    # ends: its lockstep tick stops (the phase stays "match" on the result
    # screen). The screen is read only a few times, because a screenshot slows
    # the board, and in lockstep the whole match. No B, as for the QEMU consoles.
    moves = ["left+a", "right+a", "up+a", "down+a", "a", "left", "right", "up"]
    def mine():
        found = [snap for snap in LATEST.values() if snap.get("platform") == "esp32c6"]
        return max(found, key=lambda snap: snap["seen"]) if found else {}
    tick, moved = None, time.monotonic()
    while time.monotonic() < deadline:
        snap = mine()
        if snap.get("tick6") != tick:
            tick, moved = snap.get("tick6"), time.monotonic()
        if snap.get("phase") != "match" or time.monotonic() - moved > 0.8:
            # The tick stopped: the result screen, which A would leave at once,
            # or only a late snapshot. No key until the screen says which.
            img = b.grab()
            if img is not None and qp.is_result_screen(img) and not is_lobby(img):
                b.events.append((time.monotonic() - t0, "result"))
                time.sleep(2.0)
                img = b.grab("result") or img
                b.result = classify_result(img)
                return
            if img is not None and (is_lobby(img) or is_title(img)):
                b.grab("left_match")
                b.events.append((time.monotonic() - t0, "left the match"))
                return
            moved = time.monotonic()
            continue
        now = time.monotonic() - played
        for at, name in list(shots.items()):
            if now >= at:
                b.grab(name)
                del shots[at]
        b.keys(rnd.choice(moves), gap_ms=100)
    b.events.append((time.monotonic() - t0, "timeout"))


FB_ADDR = [0]


def classify_result(img) -> str:
    """Round won ("WELL PLAYED!" in gold) or game over (in red): the big text, game
    rows 48..63, framebuffer rows 68..83."""
    gold = red = 0
    for y in range(68, 84):
        for x in range(32, 288):
            r, g, b = img.getpixel((x, y))
            if r > 200 and g > 150 and b < 120:
                gold += 1
            elif r > 180 and g < 110 and b < 110:
                red += 1
    return "won" if gold > red else "lost"


def menu_keys(args) -> list[str]:
    """Title menu: EXHIBITION city, MATCH, GAMES PER SET, then PLAY ONLINE. Every
    console sets the same, so whichever is the host (the lowest player ID) plays it."""
    keys = ["down"] + ["right"] * args.city          # EXHIBITION: the city
    keys += ["down"] + (["right"] if args.match == "1v1" else [])   # MATCH (default 2 VS 2)
    keys += ["down"] + {1: ["left", "left"], 2: ["left"], 4: []}[args.games]
    keys += ["down", "a"]                             # PLAY ONLINE
    return keys


def panel_at(img, points) -> bool:
    """The cartridge's text panel fill, (58, 28, 58), at every game (x, y) of points."""
    return all(max(abs(a - b) for a, b in zip(img.getpixel((x, 20 + y)), (58, 28, 58))) <= 2 for x, y in points)


def is_title(img) -> bool:
    return panel_at(img, [(30, 19 * 8 + 3), (290, 23 * 8 + 3)])    # the menu panel, rows 19..23


def is_lobby(img) -> bool:
    return panel_at(img, [(20, 5 * 8 + 3), (300, 13 * 8 + 3), (20, 22 * 8 + 3)])   # rows 5..22, cols 2..38


def wait_for(c: Console, test, seconds: float) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if test(c.grab()):
            return True
        time.sleep(0.4)
    return False


def menu_rows(img) -> bytes:
    return img.crop((0, 20 + 19 * 8, 320, 20 + 24 * 8)).tobytes()


def menu_tap(c: Console, key: str) -> bool:
    """Tap a key on the title menu until the menu rows change: a key can be lost
    while the console is busy. A on the last row leaves the menu."""
    before = menu_rows(c.grab())
    for _ in range(4):
        c.tap(key)
        end = time.monotonic() + 1.2
        while time.monotonic() < end:
            time.sleep(0.25)
            if menu_rows(c.grab()) != before:
                time.sleep(0.3)
                return True
    return False


def to_lobby(c: Console, args) -> bool:
    """Boot to the cartridge, walk the title menu, and check the lobby is on screen.
    On a failure, restart the console (A+B+DOWN, the firmware's restart keys) and
    try again."""
    for attempt in range(3):
        time.sleep(7.0)                               # the firmware's own menu
        c.tap("a")
        time.sleep(1.5)
        c.tap("a")                                    # run cart0
        if not wait_for(c, is_title, 20):
            c.events.append((0, f"no title, attempt {attempt}"))
        else:
            time.sleep(1.0)
            if attempt == 0:
                c.grab("title")
            for k in menu_keys(args):
                if not menu_tap(c, k):
                    c.events.append((0, f"key {k} had no effect"))
                    break
            if wait_for(c, is_lobby, 6):
                return True
            c.grab(f"nolobby{attempt}")
            c.events.append((0, f"no lobby, attempt {attempt}"))
        c.chord(("a", "b", "down"), 0.6)              # restart, and walk the menus again
        time.sleep(1.0)
    return False


def play_console(c: Console, args, t0: float, deadline: float):
    rnd = random.Random(1000 + c.i)
    if not to_lobby(c, args):
        c.events.append((time.monotonic() - t0, "never reached the lobby"))
        return
    c.events.append((time.monotonic() - t0, "lobby"))
    # Admitted, on the chosen team, and ready: as the server relays it.
    end = time.monotonic() + args.lobby_wait + 30
    while time.monotonic() < end:
        snap = c.snapshot()
        if snap and snap["phase"] == "match":
            break
        if snap and snap["phase"] == "lobby":
            if snap["team"] != c.team:
                c.tap("right")                        # TEAM, the first row
            elif not snap["ready"]:
                c.tap("a")                            # READY
            elif "lobby" not in [s.split("_", 1)[1][:-4] for s in c.shots]:
                time.sleep(1.0)
                c.grab("lobby")
                c.events.append((time.monotonic() - t0, "ready"))
        time.sleep(1.2)
    # The match: the lockstep snapshots reach the server.
    while time.monotonic() < end and not (c.snapshot() or {}).get("phase") == "match":
        time.sleep(0.3)
    c.events.append((time.monotonic() - t0, "match"))
    time.sleep(1.5)
    c.grab("intro")
    time.sleep(args.start_wait)
    played = time.monotonic()
    # No B: it would make A+B+DOWN, the firmware's restart keys, with a held key.
    moves = [("left", "a"), ("right", "a"), ("up", "a"), ("down", "a"), ("a",), ("left",), ("right",), ("up",)]
    shots = {12.0: "play1", 30.0: "play2", 60.0: "play3"}
    if args.profile and c.i == 0:
        # A sampling profile of the CPU: the program counter, as often as QMP answers.
        pcs = []
        end_p = time.monotonic() + args.profile
        while time.monotonic() < end_p:
            with c.qmp_lock:
                regs = c.qmp.execute("human-monitor-command", **{"command-line": "info registers"})
            m = re.search(r"\bpc\s+([0-9a-f]+)", regs)
            if m:
                pcs.append(m.group(1))
            time.sleep(0.01)
        (args.out / "c0_pcs.txt").write_text("\n".join(pcs) + "\n")
    last_check = 0.0
    while time.monotonic() < deadline:
        c.chord(rnd.choice(moves), rnd.choice((0.3, 0.5, 0.8)))
        now = time.monotonic() - played
        for at, name in list(shots.items()):
            if now >= at:
                c.grab(name)
                del shots[at]
        if now - last_check > 1.5:
            last_check = now
            snap = c.snapshot() or {}
            if time.monotonic() - snap.get("seen", time.monotonic()) > 6.0:
                # Silent for 6 s: say where the CPU is, for the report.
                with c.qmp_lock:
                    status = c.qmp.execute("query-status")
                    regs = c.qmp.execute("human-monitor-command", **{"command-line": "info registers"})
                (args.out / f"c{c.i}_stalled.txt").write_text(json.dumps(status) + "\n" + regs)
                gdb = shutil.which("riscv32-esp-elf-gdb") or next(
                    iter(sorted(Path.home().glob(".espressif/tools/riscv32-esp-elf-gdb/*/riscv32-esp-elf-gdb/bin/riscv32-esp-elf-gdb"))), None)
                if gdb:                                   # every task's backtrace
                    with c.qmp_lock:
                        bt = subprocess.run([str(gdb), "-batch", "-nx", "-ex", f"target remote 127.0.0.1:{c.ports[3]}",
                                             "-x", str(ROOT / "scripts/gdb_tasks.py"), "-ex", "detach",
                                             str(PRG32 / "build-qemu/PRG32.elf")],
                                            capture_output=True, text=True, timeout=120)
                    (args.out / f"c{c.i}_tasks.txt").write_text(bt.stdout + bt.stderr)
                c.grab("stalled")
                c.events.append((time.monotonic() - t0, "stalled"))
                return
            if snap.get("phase") != "match" and not qp.is_result_screen(c.grab()):
                time.sleep(1.0)
                if not qp.is_result_screen(c.grab()):
                    c.grab("left_match")              # a lost console's message: hands off
                    c.events.append((time.monotonic() - t0, "left the match"))
                    return
            img = c.grab()
            if qp.is_result_screen(img):
                c.events.append((time.monotonic() - t0, "result"))
                time.sleep(2.5)
                img = c.grab("result")
                c.result = classify_result(img)
                return
    c.events.append((time.monotonic() - t0, "timeout"))


def analyse(observer_log: Path) -> dict:
    """What the server relayed, per console."""
    per: dict[int, dict] = {}
    for line in observer_log.read_text().splitlines():
        msg = json.loads(line)
        if msg.get("type") != "peer":
            continue
        pid = msg["player_id"]
        d = per.setdefault(pid, {"platform": msg.get("platform"), "count": 0, "first": msg["t"], "last": msg["t"],
                                 "phases": {}, "inputs": {}, "conflicts": 0, "ticks": []})
        d["count"] += 1
        d["last"] = msg["t"]
        snap = decode(msg)
        if not snap:
            continue
        d["phases"][snap["phase"]] = d["phases"].get(snap["phase"], 0) + 1
        if snap["phase"] != "match":
            continue
        # widen the 6-bit tick
        prev = d["ticks"][-1][1] if d["ticks"] else 0
        newest = (prev & ~63) | snap["tick6"]
        if newest - prev > 32:
            newest -= 64
        elif newest - prev < -32:
            newest += 64
        d["ticks"].append((msg["t"], newest))
        for k, s in enumerate(snap["sym"]):
            t = newest - 10 + k
            if t < 5:
                continue
            if t in d["inputs"] and d["inputs"][t] != s:
                d["conflicts"] += 1
            d["inputs"][t] = s
    report = {}
    for pid, d in per.items():
        ticks = d["ticks"]
        speed = None
        if len(ticks) > 20:
            # the steady part of the match: from tick 100 (after the intro) to the last
            steady = [(t, k) for t, k in ticks if k >= 100]
            if len(steady) > 10:
                (ta, ka), (tb, kb) = steady[0], steady[-1]
                speed = (kb - ka) / (tb - ta) / (1000 / 33) if tb > ta else None
        report[str(pid)] = {
            "platform": d["platform"], "snapshots": d["count"],
            "publish_rate": round(d["count"] / max(0.1, d["last"] - d["first"]), 1),
            "phases": d["phases"], "last_tick": ticks[-1][1] if ticks else None,
            "game_speed": round(speed, 3) if speed else None,
            "inputs_recorded": len(d["inputs"]), "input_conflicts": d["conflicts"],
        }
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cart", type=Path, default=ROOT / "dist/azzurra-pro-tennis-qemu.prg32")
    ap.add_argument("--match", choices=("1v1", "2v2"), default="1v1")
    ap.add_argument("--teams", default="0,1", help="one team per QEMU console: 0 Azzurra's side, 1 the rivals'")
    ap.add_argument("--games", type=int, choices=(1, 2, 4), default=1)
    ap.add_argument("--city", type=int, default=0, help="0..13: the host's city")
    ap.add_argument("--port", type=int, default=18081, help="the local server's port")
    ap.add_argument("--seconds", type=float, default=420.0, help="give up after this long")
    ap.add_argument("--lobby-wait", type=float, default=10.0, help="extra time for the lobby")
    ap.add_argument("--start-wait", type=float, default=3.0, help="from the match start to the play")
    ap.add_argument("--external-server", action="store_true",
                    help="use a server already listening on --port (for example the LAN server a board "
                         "found by discovery) instead of starting one")
    ap.add_argument("--audio", action="store_true",
                    help="pace the firmware on audio credits, as qemu_preview.py does. With two or more "
                         "consoles this slows each cartridge to about 5 frames a second (observed), so by "
                         "default no credits are granted and the firmware runs unpaced, at about 30")
    ap.add_argument("--profile", type=float, default=0.0, help="seconds of PC sampling on console 0")
    ap.add_argument("--board-port", help="also play on an ESP32-C6 board: its USB serial port")
    ap.add_argument("--board-url", help="the board's HTTP address, for its screenshots")
    ap.add_argument("--board-slot", default="cart4", help="the slot that already holds the cartridge")
    ap.add_argument("--board-team", type=int, choices=(0, 1), default=1)
    ap.add_argument("--out", type=Path, default=ROOT / "build/qemu-netplay")
    args = ap.parse_args()
    teams = [int(t) for t in args.teams.split(",")]
    board_n = 1 if args.board_port else 0
    if args.board_port and not args.board_url:
        raise SystemExit("--board-port needs --board-url")
    if not 2 <= len(teams) + board_n <= 4 and not (len(teams) == 1 and (args.match == "2v2" or args.external_server)):
        raise SystemExit("--teams: one to four consoles")
    args.out.mkdir(parents=True, exist_ok=True)
    for old in args.out.glob("c*_*.png"):
        old.unlink()
    FB_ADDR[0] = qp.framebuffer_address()
    url = compiled_server_url()
    print(f"server: local port {args.port}; QEMU firmware dials ws://{url[0]}:{url[1]}, forwarded here")
    server = None if args.external_server else start_server(args.port, args.out / "server-data", public=False)
    stop = threading.Event()
    obs_log = args.out / "observer.jsonl"
    obs = threading.Thread(target=observer, args=(args.port, obs_log, stop), daemon=True)
    obs.start()
    consoles: list = []
    t0 = time.monotonic()
    deadline = t0 + args.seconds
    threads = []
    try:
        with tempfile.TemporaryDirectory(prefix="azzurra-net-") as tmp_s:
            tmp = Path(tmp_s)
            if board_n:                                 # the board first: it is READY before QEMU
                board = Board(len(teams), args)
                consoles.append(board)
                threads.append(threading.Thread(target=play_board, args=(board, args, t0, deadline)))
                threads[-1].start()
                board.ready.wait(120)
            qemu = [Console(i, team, args, tmp, url) for i, team in enumerate(teams)]
            consoles = qemu + consoles
            qemu_threads = [threading.Thread(target=play_console, args=(c, args, t0, deadline)) for c in qemu]
            threads += qemu_threads
            for th in qemu_threads:
                th.start()
                time.sleep(0.7)                 # different player IDs, different moments
            for th in threads:
                th.join()
            time.sleep(1.0)
            for c in consoles:
                c.close()
    finally:
        stop.set()
        obs.join(timeout=5)
        if server:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
    report = {"match": args.match, "teams": teams, "board_team": args.board_team if board_n else None,
              "games": args.games, "city": args.city,
              "seconds": round(time.monotonic() - t0, 1),
              "consoles": [{"index": c.i, "team": c.team, "result": c.result, "events": c.events,
                            "shots": c.shots} for c in consoles],
              "relayed": analyse(obs_log) if obs_log.exists() else {}}
    all_teams = [c.team for c in consoles]
    results = [c.result for c in consoles]
    ok = all(results)
    if ok:
        won = {c.team for c in consoles if c.result == "won"}
        lost = {c.team for c in consoles if c.result == "lost"}
        ok = not (won & lost)                     # partners agree
        if len(set(all_teams)) == 2:              # with both teams online: one won, one lost
            ok = ok and len(won) == 1 and len(lost) == 1
    conflicts = sum(r["input_conflicts"] for r in report["relayed"].values())
    ok = ok and conflicts == 0 and len(report["relayed"]) == len(consoles)
    report["ok"] = ok
    (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    print("ok" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
