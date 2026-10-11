"""Laptop side: receive board samples, show the live dashboard, drive the virtual pad.

Usage (from the repo root):
    python -m laptop.server
then open http://localhost:8000 and start `pi.stream` on the Pi (or tools.fake_board).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import socket
import time
from pathlib import Path

from aiohttp import WSMsgType, web

from controller.mappings import load_config, merge_update, save_config
from controller.movement import angle_to_stick, board_axis, stick_state
from controller.orientation import ComplementaryFilter, accel_angles
from laptop.gamepad import VirtualPad
from sensor.calibration import gyro_bias

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
CONFIG_PATH = ROOT / "board_config.json"
RECORDINGS_DIR = ROOT / "recordings"

CALIBRATION_SAMPLES = 200  # ~1 s at 200 Hz
# A still board shows only sensor noise (a few deg/s). More than this means it
# moved during calibration and the gyro bias would be wrong.
CALIBRATION_MAX_GYRO_SPREAD_DPS = 15.0
MAX_DT_S = 0.05  # ignore gaps (dropped packets) when integrating the gyro
FRAME_INTERVAL_S = 1 / 60
RECORD_HEADER = ["t", "ax", "ay", "az", "gx", "gy", "gz", "roll", "pitch", "yaw", "lean", "nose", "stick_x"]


class Board:
    """All live state: filter, calibration, mapping, recording, virtual pad."""

    def __init__(self):
        self.config = load_config(CONFIG_PATH)
        self.filter = ComplementaryFilter()
        self.bias = (0.0, 0.0, 0.0)
        self.center = {"roll": 0.0, "pitch": 0.0}
        self.last_t: float | None = None
        self.pending: list[list[float]] = []
        self.latest: dict = {}
        self.calibration_message = "not calibrated: hold the board still and press Calibrate"
        self.calibrating: list[tuple] | None = None
        self.pad = VirtualPad()
        self.pad_enabled = False
        self.record_file = None
        self.record_writer = None
        self.record_label = ""
        self.packets = 0
        self.lost = 0
        self.last_seq: int | None = None
        self.last_packet_time = 0.0
        self.packet_rate = 0.0

    # --- input ---------------------------------------------------------
    def handle_packet(self, packet: dict) -> None:
        seq = packet.get("seq")
        if self.last_seq is not None and isinstance(seq, int) and seq > self.last_seq + 1:
            self.lost += seq - self.last_seq - 1
        if isinstance(seq, int):
            if self.last_seq is not None and seq < self.last_seq:
                self.last_t = None  # streamer restarted
            self.last_seq = seq
        self.packets += 1
        self.last_packet_time = time.monotonic()
        for sample in packet.get("samples", []):
            self.handle_sample(sample)
        if self.pad_enabled and self.latest:
            self.pad.set_left_stick(self.latest["stick_x"])

    def handle_sample(self, sample: list[float]) -> None:
        t, ax, ay, az, gx, gy, gz = sample
        if self.calibrating is not None:
            self.calibrating.append((ax, ay, az, gx, gy, gz))
            if len(self.calibrating) >= CALIBRATION_SAMPLES:
                self._finish_calibration()

        bx, by, bz = self.bias
        dt = 0.0 if self.last_t is None else min(max(t - self.last_t, 0.0), MAX_DT_S)
        self.last_t = t
        roll, pitch, yaw = self.filter.update(ax, ay, az, gx - bx, gy - by, gz - bz, dt)

        orientation = {"roll": roll, "pitch": pitch}
        lean_cfg, nose_cfg = self.config["lean"], self.config["nose"]
        lean = board_axis(orientation, lean_cfg["source"], lean_cfg["invert"], self.center[lean_cfg["source"]])
        nose = board_axis(orientation, nose_cfg["source"], nose_cfg["invert"], self.center[nose_cfg["source"]])
        stick_cfg = self.config["left_stick_x"]
        stick_x = angle_to_stick(lean, stick_cfg["deadzone_deg"], stick_cfg["max_deg"])

        row = [t, ax, ay, az, gx, gy, gz, roll, pitch, yaw, lean, nose, stick_x]
        self.pending.append([round(v, 4) for v in row])
        self.latest = {
            "roll": roll, "pitch": pitch, "yaw": yaw, "lean": lean, "nose": nose,
            "stick_x": stick_x, "state": stick_state(stick_x),
        }
        if self.record_writer is not None:
            self.record_writer.writerow([f"{v:.5f}" for v in row])

    # --- commands ------------------------------------------------------
    def start_calibration(self) -> None:
        self.calibrating = []

    def _finish_calibration(self) -> None:
        samples, self.calibrating = self.calibrating, None
        gyro = [s[3:] for s in samples]
        spread = max(max(g[i] for g in gyro) - min(g[i] for g in gyro) for i in range(3))
        if spread > CALIBRATION_MAX_GYRO_SPREAD_DPS:
            self.calibration_message = f"calibration rejected: board moved ({spread:.0f} deg/s), try again"
            return
        self.bias = gyro_bias(gyro)
        n = len(samples)
        mean_acc = [sum(s[i] for s in samples) / n for i in range(3)]
        roll, pitch = accel_angles(*mean_acc)
        self.center = {"roll": roll, "pitch": pitch}
        self.filter.reset()
        self.calibration_message = f"calibrated: center roll {roll:.1f}°, pitch {pitch:.1f}°"

    def set_pad(self, enabled: bool) -> None:
        if enabled and not self.pad.connect():
            self.pad_enabled = False
            return
        if not enabled:
            self.pad.release()
        self.pad_enabled = enabled

    def start_recording(self, label: str) -> None:
        self.stop_recording()
        RECORDINGS_DIR.mkdir(exist_ok=True)
        safe = "".join(c for c in label if c.isalnum() or c in "-_") or "unlabeled"
        path = RECORDINGS_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}_{safe}.csv"
        self.record_file = path.open("w", newline="")
        self.record_writer = csv.writer(self.record_file)
        self.record_writer.writerow(RECORD_HEADER)
        self.record_label = path.name

    def stop_recording(self) -> None:
        if self.record_file is not None:
            self.record_file.close()
        self.record_file = self.record_writer = None
        self.record_label = ""

    def update_config(self, update: dict) -> None:
        merge_update(self.config, update)
        save_config(CONFIG_PATH, self.config)

    def shutdown(self) -> None:
        self.stop_recording()
        self.pad.release()

    # --- output --------------------------------------------------------
    def status(self) -> dict:
        age = time.monotonic() - self.last_packet_time if self.last_packet_time else None
        return {
            "connected": age is not None and age < 1.0,
            "packet_rate": round(self.packet_rate, 1),
            "lost": self.lost,
            "calibrating": self.calibrating is not None,
            "calibration_message": self.calibration_message,
            "bias": [round(b, 3) for b in self.bias],
            "center": {k: round(v, 2) for k, v in self.center.items()},
            "pad_enabled": self.pad_enabled,
            "pad_error": self.pad.error,
            "recording": self.record_label,
        }

    def take_frame(self) -> dict:
        samples, self.pending = self.pending, []
        return {"type": "frame", "samples": samples, "latest": self.latest, "status": self.status()}


class UdpReceiver(asyncio.DatagramProtocol):
    def __init__(self, board: Board):
        self.board = board

    def datagram_received(self, data: bytes, addr) -> None:
        try:
            packet = json.loads(data)
        except ValueError:
            return
        self.board.handle_packet(packet)


async def broadcast_loop(app: web.Application) -> None:
    board: Board = app["board"]
    last_count, last_time = 0, time.monotonic()
    while True:
        await asyncio.sleep(FRAME_INTERVAL_S)
        now = time.monotonic()
        if now - last_time >= 1.0:
            board.packet_rate = (board.packets - last_count) / (now - last_time)
            last_count, last_time = board.packets, now
        frame = json.dumps(board.take_frame())
        for ws in list(app["sockets"]):
            try:
                await ws.send_str(frame)
            except (ConnectionResetError, RuntimeError):
                app["sockets"].discard(ws)


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    board: Board = request.app["board"]
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    request.app["sockets"].add(ws)
    await ws.send_str(json.dumps({"type": "config", "config": board.config, "recordings": list_recordings()}))
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            cmd = json.loads(msg.data)
            kind = cmd.get("cmd")
            if kind == "calibrate":
                board.start_calibration()
            elif kind == "pad":
                board.set_pad(bool(cmd.get("on")))
            elif kind == "record":
                board.start_recording(str(cmd.get("label", "")))
            elif kind == "stop":
                board.stop_recording()
                await ws.send_str(json.dumps({"type": "recordings", "recordings": list_recordings()}))
            elif kind == "config":
                board.update_config(cmd.get("update", {}))
                await ws.send_str(json.dumps({"type": "config", "config": board.config}))
    finally:
        request.app["sockets"].discard(ws)
    return ws


def list_recordings() -> list[str]:
    if not RECORDINGS_DIR.exists():
        return []
    return sorted((p.name for p in RECORDINGS_DIR.glob("*.csv")), reverse=True)[:20]


async def index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC_DIR / "index.html")


def local_ips() -> list[str]:
    try:
        return sorted({info[4][0] for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)})
    except OSError:
        return []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--udp-port", type=int, default=5005)
    parser.add_argument("--http-port", type=int, default=8000)
    args = parser.parse_args()

    board = Board()
    app = web.Application()
    app["board"] = board
    app["sockets"] = set()
    app.router.add_get("/", index)
    app.router.add_get("/ws", websocket_handler)
    app.router.add_static("/static", STATIC_DIR)

    async def on_startup(app: web.Application) -> None:
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: UdpReceiver(board), local_addr=("0.0.0.0", args.udp_port)
        )
        app["udp"] = transport
        app["broadcast"] = asyncio.create_task(broadcast_loop(app))
        print(f"listening for the board on UDP {args.udp_port}; laptop IPs: {', '.join(local_ips())}")
        print(f"dashboard: http://localhost:{args.http_port}")

    async def on_cleanup(app: web.Application) -> None:
        app["broadcast"].cancel()
        app["udp"].close()
        board.shutdown()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    web.run_app(app, port=args.http_port, print=None)


if __name__ == "__main__":
    main()
