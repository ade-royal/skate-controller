"""Stream raw MPU-6050 samples from the Pi to the laptop over UDP.

Usage (on the Pi, from the repo root):
    python3 -m pi.stream --host <laptop-ip>

Samples are batched (default 4 per packet, 50 packets/s at 200 Hz) to keep
overhead low on a phone hotspot. Packet format is JSON:
    {"seq": n, "samples": [[t, ax, ay, az, gx, gy, gz], ...]}
with t in seconds (Pi monotonic clock), accel in g, gyro in deg/s.
"""

from __future__ import annotations

import argparse
import json
import socket
import time

from sensor.mpu6050 import MPU6050

READ_ERROR_BACKOFF_S = 0.2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", required=True, help="laptop IP address")
    parser.add_argument("--port", type=int, default=5005)
    parser.add_argument("--rate", type=float, default=200.0, help="samples per second")
    parser.add_argument("--batch", type=int, default=4, help="samples per packet")
    args = parser.parse_args()

    # Wider ranges than the ±2 g / ±250 deg/s defaults: pops and landings saturate those.
    imu = MPU6050(accel_range_g=8, gyro_range_dps=1000)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = (args.host, args.port)
    period = 1.0 / args.rate
    print(f"streaming {args.rate:.0f} Hz to {target[0]}:{target[1]} (Ctrl+C to stop)")

    seq = 0
    batch: list[list[float]] = []
    next_tick = time.perf_counter()
    try:
        while True:
            try:
                sample = imu.read_all()
            except OSError as exc:
                print(f"I2C read failed: {exc}; retrying")
                time.sleep(READ_ERROR_BACKOFF_S)
                next_tick = time.perf_counter()
                continue

            batch.append([round(time.monotonic(), 5)] + [round(v, 4) for v in sample])
            if len(batch) >= args.batch:
                payload = json.dumps({"seq": seq, "samples": batch}).encode()
                try:
                    sock.sendto(payload, target)
                except OSError as exc:  # network blip on the hotspot; keep reading
                    print(f"send failed: {exc}")
                seq += 1
                batch = []

            next_tick += period
            delay = next_tick - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                next_tick = time.perf_counter()  # fell behind; don't try to catch up
    except KeyboardInterrupt:
        pass
    finally:
        imu.close()
        sock.close()


if __name__ == "__main__":
    main()
