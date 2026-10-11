"""Send synthetic board data in the Pi's packet format, for testing without hardware.

Usage:
    python -m tools.fake_board [--host 127.0.0.1]

Simulates slow side-to-side leaning plus a tail pop every few seconds.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import socket
import time


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5005)
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rate, batch_size = 200.0, 4
    seq, batch, t0 = 0, [], time.monotonic()
    print(f"fake board -> {args.host}:{args.port}")
    while True:
        t = time.monotonic() - t0
        lean = math.radians(15 * math.sin(t * 0.8))  # +-15 deg lean
        lean_rate = math.degrees(math.radians(15) * 0.8 * math.cos(t * 0.8))
        pop = (t % 4.0) < 0.12  # short tail snap every 4 s
        noise = lambda s: random.gauss(0, s)  # noqa: E731
        ax = noise(0.02) + (0.9 if pop else 0.0)
        ay = math.sin(lean) + noise(0.02)
        az = math.cos(lean) + noise(0.02) + (2.5 if pop else 0.0)
        gx = lean_rate + noise(0.5)
        gy = noise(0.5) + (-400 if pop else 0.0)
        gz = noise(0.5)
        batch.append([round(time.monotonic(), 5), ax, ay, az, gx, gy, gz])
        if len(batch) >= batch_size:
            sock.sendto(json.dumps({"seq": seq, "samples": batch}).encode(), (args.host, args.port))
            seq, batch = seq + 1, []
        time.sleep(1.0 / rate)


if __name__ == "__main__":
    main()
