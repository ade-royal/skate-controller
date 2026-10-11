"""Read the skateboard and send LEFT, CENTER, or RIGHT to the laptop.

An ollie is an extra OLLIE line beside the steering state. It does not
replace LEFT, CENTER, or RIGHT.

Run this on the Raspberry Pi from the repository root:

    python3 scripts/pi_sender.py --host <laptop-ip>

The host is the Windows laptop's IPv4 address on the shared hotspot.
Stop scripts/test_controller.py before starting this script so only one
program reads the MPU-6050.
"""

from __future__ import annotations

import argparse
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from controller.movement import (
    CENTER,
    MovementConfig,
    adjusted_steering,
    classify_movement,
)
from controller.ollie import OllieConfig, OllieDetector
from network.protocol import DEFAULT_PORT, encode_update
from sensor.mpu6050 import MPU6050

SAMPLE_INTERVAL_SECONDS = 0.1
READ_RETRY_SECONDS = 0.5
CONNECT_RETRY_SECONDS = 1.0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send skateboard steering to the laptop.")
    parser.add_argument("--host", required=True, help="Windows laptop IPv4 address.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser.parse_args(argv)


def read_state(
    sensor: MPU6050,
    config: MovementConfig,
    ollie: OllieDetector | None = None,
    now: float = 0.0,
) -> tuple[str, dict[str, float] | None, str | None, str | None]:
    """Classify one sample. A failed sensor read becomes CENTER and no ollie."""
    try:
        acceleration = sensor.get_acceleration()
    except OSError as exc:
        return CENTER, None, str(exc), None
    event = None
    if ollie is not None:
        event = ollie.update(float(acceleration["x"]), now)
    return classify_movement(acceleration, config), acceleration, None, event


def send_forever(
    sensor: MPU6050,
    config: MovementConfig,
    host: str,
    port: int,
    ollie_config: OllieConfig | None = None,
) -> None:
    ollie_config = ollie_config or OllieConfig()
    ollie = OllieDetector(ollie_config)
    while True:
        try:
            print(f"Connecting to {host}:{port}...")
            with socket.create_connection((host, port), timeout=5) as connection:
                connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                print(f"Connected to {host}:{port}")
                _stream(connection, sensor, config, ollie, ollie_config, host, port)
        except OSError as exc:
            print(f"Connection to {host}:{port} failed: {exc}")
            print(f"Retrying in {CONNECT_RETRY_SECONDS:.0f}s. Ctrl+C to stop.")
            time.sleep(CONNECT_RETRY_SECONDS)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    config = MovementConfig()
    ollie_config = OllieConfig()
    sensor = MPU6050()
    try:
        send_forever(sensor, config, args.host, args.port, ollie_config)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        sensor.close()


def _stream(
    connection: socket.socket,
    sensor: MPU6050,
    config: MovementConfig,
    ollie: OllieDetector,
    ollie_config: OllieConfig,
    host: str,
    port: int,
) -> None:
    last_notice = "none yet"
    while True:
        now = time.monotonic()
        state, acceleration, error, event = read_state(sensor, config, ollie, now)
        payload = encode_update(state, event)
        try:
            connection.sendall(payload)
        except OSError as exc:
            print(f"\nSend failed: {exc}")
            return
        if event is not None and acceleration is not None:
            last_notice = (
                f"FIRED and SENT  X {acceleration['x']:+.3f} g  "
                + payload.decode("ascii").replace("\n", " | ")
            )
        frame = _format_frame(
            acceleration,
            state,
            event,
            config,
            ollie_config,
            ollie.arm_status(now, _above_gate(acceleration, ollie_config)),
            last_notice,
            host,
            port,
            error,
        )
        print("\033[H\033[J" + frame, flush=True)
        delay = SAMPLE_INTERVAL_SECONDS if acceleration is not None else READ_RETRY_SECONDS
        time.sleep(delay)


def _above_gate(acceleration: dict[str, float] | None, ollie_config: OllieConfig) -> bool:
    return acceleration is not None and acceleration["x"] >= ollie_config.threshold


def _format_frame(
    acceleration: dict[str, float] | None,
    state: str,
    event: str | None,
    config: MovementConfig,
    ollie_config: OllieConfig,
    arm: str,
    last_notice: str,
    host: str,
    port: int,
    error: str | None = None,
) -> str:
    if acceleration is None:
        accel_line = "ACCEL g    unavailable"
        steer_line = "STEER      unavailable"
    else:
        steering = adjusted_steering(acceleration, config)
        accel_line = (
            f"ACCEL g    "
            f"X {acceleration['x']:+8.3f}   "
            f"Y {acceleration['y']:+8.3f}   "
            f"Z {acceleration['z']:+8.3f}"
        )
        steer_line = f"STEER      {steering:+8.3f}"
    if acceleration is None:
        x_line = "X          unavailable"
    else:
        gate = "ABOVE" if acceleration["x"] >= ollie_config.threshold else "below"
        x_line = f"X          {acceleration['x']:+8.3f} g   {gate} {ollie_config.threshold:.3f}"
    if event is None:
        this_line = "THIS       no ollie"
    else:
        this_line = "THIS       OLLIE fired and sent"
    lines = [
        f"Sending {state} to {host}:{port}    Ctrl+C to stop",
        "",
        accel_line,
        steer_line,
        f"STATE      {state}",
        "",
        x_line,
        f"ARM        {arm}",
        this_line,
        f"LAST       {last_notice}",
    ]
    if error is not None:
        lines.append(f"SENSOR     {error}")
        lines.append(f"Retrying in {READ_RETRY_SECONDS:.1f}s.")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
