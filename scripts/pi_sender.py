"""Read the skateboard and send LEFT, CENTER, or RIGHT to the laptop.

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
from network.protocol import DEFAULT_PORT, encode_state
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
) -> tuple[str, dict[str, float] | None, str | None]:
    """Classify one sample. A failed sensor read becomes CENTER."""
    try:
        acceleration = sensor.get_acceleration()
    except OSError as exc:
        return CENTER, None, str(exc)
    return classify_movement(acceleration, config), acceleration, None


def send_forever(sensor: MPU6050, config: MovementConfig, host: str, port: int) -> None:
    while True:
        try:
            print(f"Connecting to {host}:{port}...")
            with socket.create_connection((host, port), timeout=5) as connection:
                connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                print(f"Connected to {host}:{port}")
                _stream(connection, sensor, config, host, port)
        except OSError as exc:
            print(f"Connection to {host}:{port} failed: {exc}")
            print(f"Retrying in {CONNECT_RETRY_SECONDS:.0f}s. Ctrl+C to stop.")
            time.sleep(CONNECT_RETRY_SECONDS)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    config = MovementConfig()
    sensor = MPU6050()
    try:
        send_forever(sensor, config, args.host, args.port)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        sensor.close()


def _stream(
    connection: socket.socket,
    sensor: MPU6050,
    config: MovementConfig,
    host: str,
    port: int,
) -> None:
    while True:
        state, acceleration, error = read_state(sensor, config)
        try:
            connection.sendall(encode_state(state))
        except OSError as exc:
            print(f"\nSend failed: {exc}")
            return
        frame = _format_frame(acceleration, state, config, host, port, error)
        print("\033[H\033[J" + frame, flush=True)
        delay = SAMPLE_INTERVAL_SECONDS if acceleration is not None else READ_RETRY_SECONDS
        time.sleep(delay)


def _format_frame(
    acceleration: dict[str, float] | None,
    state: str,
    config: MovementConfig,
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
    lines = [
        f"Sending {state} to {host}:{port}    Ctrl+C to stop",
        "",
        accel_line,
        steer_line,
        f"STATE      {state}",
    ]
    if error is not None:
        lines.append(f"SENSOR     {error}")
        lines.append(f"Retrying in {READ_RETRY_SECONDS:.1f}s.")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
