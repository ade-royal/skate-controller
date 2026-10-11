"""Laptop backend for the Skate Controller app (started by the Tauri shell).

    python -m backend.server

- Starts the Pi agent over SSH (backend/pi_link.py) and receives its readings.
- Classifies lean with controller/movement.py and holds keys with
  laptop/keyboard_output.py, the same code as scripts/laptop_receiver.py.
- Runs the keyboard -> Xbox pad bridge (tools/keyboard_pad.py) when enabled.
- Pushes live state to the UI over ws://127.0.0.1:8765/ws.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import math
import os
import time
from collections import deque
from pathlib import Path

from aiohttp import WSMsgType, web

from backend import phone_routes, pi_link
from backend.bridge import Bridge
from backend.phone import PhoneRemote
from controller.movement import CENTER, MovementConfig, adjusted_steering, classify_movement, select_steering
from controller.pop import PopDetector
from laptop.keyboard_output import KeyBindings, KeyboardOutput, KeyPulseOutput, pynput_keyboard

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"  # local only, holds the Pi password
DEFAULTS = {
    "pi_host": "172.20.10.6",
    "pi_user": "royal",
    "pi_password": "",
    "left_key": "a",
    "right_key": "d",
    "pop_key": "space",
    "pop_enabled": True,
}
UDP_PORT = 5006
CAM_PORT = 8081
TICK_S = 1 / 30
DATA_TIMEOUT_S = 1.5  # no packet for this long -> sensor shown as offline
FIRST_DATA_TIMEOUT_S = 6.0
CALIBRATION_WINDOW = 25  # samples (~0.5 s at 50 Hz)
POP_AVAILABLE = True


def load_config() -> dict:
    config = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        config.update(json.loads(CONFIG_PATH.read_text()))
    return config


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(config, indent=2))


class App:
    def __init__(self, config: dict):
        self.config = {**DEFAULTS, **config}
        self.movement = MovementConfig()
        self.keys_enabled = True
        self.keys = self._make_keys()
        self.pop_output = KeyPulseOutput(keyboard=pynput_keyboard())
        self.pop_detector = PopDetector()
        self.phone = PhoneRemote()
        self.http_port = 8765
        self.bridge = Bridge()
        self.pi_state = "idle"  # idle | starting | live | error
        self.alert = ""
        self.laptop_ip = ""
        self.last_packet = 0.0
        self.started_at = 0.0
        self.camera = "none"
        self.sensor_error = ""
        self.recent_steer: deque[float] = deque(maxlen=CALIBRATION_WINDOW)
        self.recent_x: deque[float] = deque(maxlen=CALIBRATION_WINDOW)
        self.center_x = 0.0
        self.tele: dict = {}
        self.state = CENTER
        self.pop_flash_until = 0.0
        self._start_task: asyncio.Task | None = None
        self._shut_down = False

    # --- keys -----------------------------------------------------------
    def _make_keys(self) -> KeyboardOutput:
        bindings = KeyBindings(self.config["left_key"], self.config["right_key"])
        return KeyboardOutput(bindings, keyboard=pynput_keyboard())

    def set_keys_enabled(self, on: bool) -> None:
        self.keys_enabled = on
        self.reset_pop()
        if not on:
            self.keys.close()
            self.phone.stop()

    def reset_pop(self) -> None:
        self.pop_detector.reset()
        self.pop_output.close()
        self.pop_flash_until = 0.0

    def set_pop_enabled(self, on: bool) -> None:
        self.reset_pop()
        self.config["pop_enabled"] = on
        save_config(self.config)
        self.alert = ""

    def rebind(self, action: str, key: str) -> None:
        key = "space" if key == " " else key.lower()
        if action == "pop":
            if key != "space" and not (len(key) == 1 and key.isascii() and key.isalpha()):
                self.alert = "Use Space or a single letter for pop."
                return
            if key in (self.config["left_key"], self.config["right_key"]):
                self.alert = "Pop and steering need different keys."
                return
            self.reset_pop()
            self.config["pop_key"] = key
            save_config(self.config)
            self.alert = ""
            return
        if action not in ("left", "right") or len(key) != 1 or not key.isalpha():
            self.alert = "Use a single letter key."
            return
        other = self.config["right_key" if action == "left" else "left_key"]
        if key.lower() == other:
            self.alert = "Left and right need different keys."
            return
        if key == self.config["pop_key"]:
            self.alert = "Pop and steering need different keys."
            return
        self.keys.close()
        self.config[f"{action}_key"] = key.lower()
        save_config(self.config)
        self.keys = self._make_keys()
        self.alert = ""

    # --- pi -------------------------------------------------------------
    def start_pi(self) -> None:
        if self._start_task is None or self._start_task.done():
            self._start_task = asyncio.create_task(self._start_pi())

    async def _start_pi(self) -> None:
        cfg = self.config
        if not cfg["pi_password"]:
            self.pi_state, self.alert = "error", "Pi password missing in backend/config.json."
            return
        self.pi_state, self.alert = "starting", ""
        try:
            self.laptop_ip = await asyncio.to_thread(
                pi_link.start_agent, cfg["pi_host"], cfg["pi_user"], cfg["pi_password"], UDP_PORT, CAM_PORT
            )
        except pi_link.PiError as exc:
            self.pi_state, self.alert = "error", str(exc)
            return
        deadline = time.monotonic() + FIRST_DATA_TIMEOUT_S
        while time.monotonic() < deadline:
            if self.last_packet and time.monotonic() - self.last_packet < DATA_TIMEOUT_S:
                self.pi_state, self.started_at = "live", time.monotonic()
                return
            await asyncio.sleep(0.2)
        hint = ""
        try:
            hint = await asyncio.to_thread(pi_link.agent_log_tail, cfg["pi_host"], cfg["pi_user"], cfg["pi_password"])
        except pi_link.PiError:
            pass
        self.pi_state = "error"
        self.alert = "Pi started but no data reached the laptop. Check the firewall."
        if hint:
            self.alert = f"Pi agent error: {hint[:90]}"

    def on_packet(self, packet: dict) -> None:
        self.last_packet = time.monotonic()
        self.camera = packet.get("cam", "none")
        if packet.get("err"):
            self.sensor_error = packet["err"]
            self.reset_pop()
            return
        self.sensor_error = ""
        ax, ay, az = packet["a"]
        gx, gy, gz = packet["g"]
        acceleration = {"x": ax, "y": ay, "z": az}
        self.recent_steer.append(select_steering(acceleration, self.movement))
        self.recent_x.append(ax)
        state = classify_movement(acceleration, self.movement)
        if self.keys_enabled:
            self.keys.apply_state(state)
        self.state = state
        steer = adjusted_steering(acceleration, self.movement)
        # The IMU is mounted upside down, so angles come from the gravity share on
        # each axis relative to neutral rather than from atan2 of the raw vector.
        self.tele = {
            "a": [ax, ay, az], "g": [gx, gy, gz],
            "lean": _tilt_deg(steer),
            "pitch": _tilt_deg(ax - self.center_x),
            "gtotal": math.sqrt(ax * ax + ay * ay + az * az),
            "steer": steer,
        }

    def update_pop(self, now: float | None = None) -> None:
        """Use the latest sample at the UI broadcast cadence, matching the preview."""
        now = time.monotonic() if now is None else now
        fresh = self.last_packet and now - self.last_packet < DATA_TIMEOUT_S
        if not (fresh and not self.sensor_error and self.keys_enabled
                and self.config["pop_enabled"] and not self._shut_down):
            self.reset_pop()
            return
        gyro = self.tele.get("g")
        if not isinstance(gyro, (list, tuple)) or len(gyro) != 3:
            self.reset_pop()
            return
        if self.pop_detector.update(now, gyro[1]):
            try:
                self.pop_output.tap(self.config["pop_key"])
            except Exception as exc:
                self.reset_pop()
                self.config["pop_enabled"] = False
                self.alert = f"Pop input stopped: {exc}"
                return
            self.pop_flash_until = now + 0.4

    def calibrate(self) -> None:
        self.reset_pop()
        if len(self.recent_steer) < CALIBRATION_WINDOW // 2:
            self.alert = "No board data to calibrate."
            return
        center = sum(self.recent_steer) / len(self.recent_steer)
        self.center_x = sum(self.recent_x) / len(self.recent_x)
        self.movement = dataclasses.replace(self.movement, center_offset=round(center, 4))
        self.alert = ""

    # --- status ---------------------------------------------------------
    def snapshot(self) -> dict:
        now = time.monotonic()
        fresh = self.last_packet and now - self.last_packet < DATA_TIMEOUT_S
        if self.pi_state == "live" and not fresh:
            self.pi_state, self.alert = "error", "Lost the board. Check the Pi and hotspot."
        if self.pi_state == "error" and fresh:
            self.pi_state, self.alert = "live", ""
        bridge_on = self.bridge.running
        held = self.keys._held if self.keys_enabled else None
        return {
            "type": "tick",
            "pi": self.pi_state,
            "alert": self.alert or self.bridge.error or (self.sensor_error if fresh else ""),
            "sensor": bool(fresh) and not self.sensor_error,
            "camera": self.camera if fresh else "none",
            "cam_url": f"http://{self.config['pi_host']}:{CAM_PORT}/stream",
            "keys": self.keys_enabled,
            "bridge": bridge_on,
            "pop_available": POP_AVAILABLE,
            "pop_enabled": bool(self.config["pop_enabled"]),
            "pop": now < self.pop_flash_until,
            "state": self.state if fresh else CENTER,
            "held": held,
            "bindings": {"left": self.config["left_key"], "right": self.config["right_key"],
                         "pop": self.config["pop_key"]},
            "center": self.movement.center_offset,
            "ride_s": round(now - self.started_at, 1) if self.pi_state == "live" else 0,
            "tele": self.tele if fresh else {},
            "phone": self.phone.status(),
            "phone_url": f"http://{self.laptop_ip}:{self.http_port}/phone" if self.laptop_ip else "",
        }

    def shutdown(self) -> None:
        if self._shut_down:
            return
        self._shut_down = True
        self.reset_pop()
        self.keys.close()
        self.bridge.stop()
        cfg = self.config
        if cfg["pi_password"]:
            try:
                pi_link.stop_agent(cfg["pi_host"], cfg["pi_user"], cfg["pi_password"])
            except pi_link.PiError:
                pass


def _tilt_deg(g_share: float) -> float:
    return math.degrees(math.asin(max(-1.0, min(1.0, g_share))))


class Receiver(asyncio.DatagramProtocol):
    def __init__(self, app: App):
        self.app = app

    def datagram_received(self, data: bytes, addr) -> None:
        try:
            self.app.on_packet(json.loads(data))
        except (ValueError, KeyError, TypeError):
            pass


async def ticker(webapp: web.Application) -> None:
    app: App = webapp["app"]
    while True:
        await asyncio.sleep(TICK_S)
        app.update_pop()
        message = json.dumps(app.snapshot())
        for ws in list(webapp["sockets"]):
            try:
                await ws.send_str(message)
            except (ConnectionResetError, RuntimeError):
                webapp["sockets"].discard(ws)


def _local_only(request: web.Request) -> None:
    # The server listens on the hotspot for the phone; desktop controls stay laptop-only.
    if request.remote not in ("127.0.0.1", "::1"):
        raise web.HTTPForbidden()


async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    _local_only(request)
    app: App = request.app["app"]
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    request.app["sockets"].add(ws)
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            cmd = json.loads(msg.data)
            kind = cmd.get("cmd")
            if kind == "retry":
                app.start_pi()
            elif kind == "calibrate":
                app.calibrate()
            elif kind == "keys":
                app.set_keys_enabled(bool(cmd.get("on")))
            elif kind == "pop":
                app.set_pop_enabled(bool(cmd.get("on")))
            elif kind == "bridge":
                app.bridge.start() if cmd.get("on") else app.bridge.stop()
            elif kind == "bind":
                app.rebind(str(cmd.get("action")), str(cmd.get("key", "")))
            elif kind == "dismiss":
                app.alert = ""
    finally:
        request.app["sockets"].discard(ws)
    return ws


async def shutdown_handler(request: web.Request) -> web.Response:
    """Called by the Tauri shell on exit: release keys, stop bridge and Pi agent, then quit."""
    _local_only(request)
    request.app["app"].phone.stop()
    await asyncio.to_thread(request.app["app"].shutdown)
    asyncio.get_running_loop().call_later(0.2, os._exit, 0)
    return web.Response(text="bye")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    app = App(load_config())
    app.http_port = args.port
    webapp = web.Application()
    webapp["app"] = app
    webapp["port"] = args.port
    webapp["sockets"] = set()
    webapp.router.add_get("/ws", ws_handler)
    webapp.router.add_post("/shutdown", shutdown_handler)
    phone_routes.add_routes(webapp)

    async def on_startup(webapp: web.Application) -> None:
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(lambda: Receiver(app), local_addr=("0.0.0.0", UDP_PORT))
        webapp["udp"] = transport
        webapp["ticker"] = asyncio.create_task(ticker(webapp))
        app.bridge.start()
        app.start_pi()

    async def on_cleanup(webapp: web.Application) -> None:
        webapp["ticker"].cancel()
        webapp["udp"].close()
        app.phone.stop()
        await asyncio.to_thread(app.shutdown)

    webapp.on_startup.append(on_startup)
    webapp.on_cleanup.append(on_cleanup)
    # 0.0.0.0 so the phone on the hotspot can reach /phone; desktop routes check _local_only.
    web.run_app(webapp, host="0.0.0.0", port=args.port, print=None)


if __name__ == "__main__":
    main()
