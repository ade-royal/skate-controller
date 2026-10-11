"""Print live skateboard lean from the MPU-6050.

Run this on the Raspberry Pi from the repository root:

    python3 scripts/test_controller.py

Steering uses accelerometer Y from the first mounted-board test.
Negative Y is left and positive Y is right. Change the thresholds in
controller/movement.py if a later lean test should turn sooner or later.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from controller.movement import MovementConfig, adjusted_steering, classify_movement
from sensor.mpu6050 import MPU6050

# Slow enough to read while leaning, and slow enough that a failed I2C read
# is not retried in a tight loop.
SAMPLE_INTERVAL_SECONDS = 0.1
READ_RETRY_SECONDS = 0.5


def format_frame(
    acceleration: dict[str, float],
    gyroscope: dict[str, float],
    steering: float,
    state: str,
    config: MovementConfig,
) -> str:
    return "\n".join(
        [
            "Skate lean test    Ctrl+C to stop",
            (
                f"axis {config.steering_axis:<2}  "
                f"offset {config.center_offset:+.3f}  "
                f"LEFT <= {config.left_threshold:+.3f}  "
                f"dead zone +/- {config.dead_zone:.3f}  "
                f"RIGHT >= {config.right_threshold:+.3f}"
            ),
            "",
            (
                f"ACCEL g    "
                f"X {acceleration['x']:+8.3f}   "
                f"Y {acceleration['y']:+8.3f}   "
                f"Z {acceleration['z']:+8.3f}"
            ),
            (
                f"GYRO dps   "
                f"X {gyroscope['x']:+8.2f}   "
                f"Y {gyroscope['y']:+8.2f}   "
                f"Z {gyroscope['z']:+8.2f}"
            ),
            f"STEER      {steering:+8.3f}",
            f"STATE      {state}",
        ]
    )


def main() -> None:
    config = MovementConfig()
    sensor = MPU6050()
    try:
        while True:
            try:
                acceleration = sensor.get_acceleration()
                gyroscope = sensor.get_gyroscope()
            except OSError as exc:
                print(f"\nSensor read failed: {exc}")
                print(f"Retrying in {READ_RETRY_SECONDS:.1f}s. Ctrl+C to stop.")
                time.sleep(READ_RETRY_SECONDS)
                continue

            steering = adjusted_steering(acceleration, config)
            state = classify_movement(acceleration, config)
            frame = format_frame(acceleration, gyroscope, steering, state, config)
            # Redraw in place so the numbers stay still while the board leans.
            print("\033[H\033[J" + frame, flush=True)
            time.sleep(SAMPLE_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        sensor.close()


if __name__ == "__main__":
    main()
