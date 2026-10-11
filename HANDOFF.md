# Handoff: `board-dashboard` branch

Read this first, then explain it to your teammate.

## What changed and why

This branch is built on top of commit `1531d79`. `MovementConfig`, `tests/test_movement.py` and
`scripts/test_controller.py` are unchanged and still work.

It adds:

- **`pi/stream.py`** reads the MPU-6050 at 200 Hz with one 14-byte burst read and sends the
  samples to the laptop over UDP.
- **`laptop/server.py` + `laptop/static/`** is a live dashboard at http://localhost:8000:
  - accel, gyro and orientation plots
  - a 3D board that tilts with the real one
  - calibration (rejected if the board moves)
  - axis, invert, dead zone and full-lean mapping, saved to `board_config.json`
  - labeled CSV recording to `recordings/`
- **`laptop/gamepad.py`** is a virtual Xbox 360 controller (vgamepad / ViGEmBus). Lean drives the
  left stick proportionally.
- **`controller/orientation.py`** is a complementary filter (roll/pitch/yaw).
- **`controller/movement.py`** adds `board_axis`, `angle_to_stick` and `stick_state`. Nothing
  existing was changed.
- **`tools/fake_board.py`** simulates the board, so you can work without the Pi.

### Agreed departures from AGENTS.md (decided by the team; don't revert them)

1. **Virtual Xbox pad instead of keyboard keys.** The target game is skate. (via the ReSkate mod).
   Its controls are analog sticks (right-stick flicks for ollies and flips), so keys can't express
   them. A virtual pad is still game-agnostic.
2. **Orientation and mapping run on the laptop, not the Pi.** The Pi streams raw samples, so tuning
   doesn't need a Pi redeploy during the hackathon.
3. **Networking and controller output were built before LEFT/CENTER/RIGHT was verified on
   hardware.** The dashboard is the tool for verifying it.
4. **Sensor range.** The streamer explicitly opts into ±8 g / ±1000 deg/s
   (`MPU6050(accel_range_g=8, gyro_range_dps=1000)`), because pops and landings saturate ±2 g. The
   class default is still ±2 g / ±250 deg/s, and the scale factors follow the chosen range.

## How to run it

1. Put the Pi and the laptop on the **phone hotspot**. GSU-Guest wifi probably blocks
   device-to-device traffic.
2. Laptop:
   ```
   git checkout board-dashboard
   pip install aiohttp vgamepad
   python -m laptop.server
   ```
   Open http://localhost:8000. The server prints the laptop's IPs.
3. Pi:
   ```
   git pull && git checkout board-dashboard
   pip install smbus2
   python3 -m pi.stream --host <laptop-ip>
   ```
4. No Pi handy? Run `python -m tools.fake_board` on the laptop instead.

## Your task: configure the board

1. Hold the board still in its neutral position and click **Calibrate**.
2. Lean heel and toe:
   - If the 3D board tips the wrong way, or the wrong line moves, change **Lean axis** or tick
     **invert**.
   - Do the same for **Nose axis** with nose and tail presses.
3. Tune **Dead zone** and **Full lean** until steering feels right.
4. Turn on **Virtual pad**. Lean should move the left stick. Check it at https://hardwaretester.com/gamepad.
5. **Record labeled clips** using the Record box. Do about 10 of each: `ollie`, `push`,
   `nose-press`, `tail-press`, `lean-left`, `lean-right`. Note what each looks like in the plots,
   e.g. the gyro spike on a tail snap or the accel spike on a landing.
6. Next code step: detect those motions from the recordings and map them to pad outputs:
   - ollie becomes a right-stick flick (down, then up)
   - push becomes a button
   - Add these as new entries in `controller/mappings.py` and pure, tested functions in
     `controller/movement.py`, following the existing style.

Tests: `python -m pytest -q` (no hardware needed).
