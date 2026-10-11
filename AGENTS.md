# AGENTS.md

## Project Goal

Build a motion-controlled game controller using a physical skateboard.

A GY-521 breakout board containing an MPU-6050 accelerometer/gyroscope is mounted to the skateboard.

The MPU-6050 connects to a Raspberry Pi over I2C.

The Raspberry Pi is responsible for reading and interpreting physical skateboard movement.

The Raspberry Pi will eventually send high-level controller states to a Windows laptop.

The Windows laptop is responsible for converting those controller states into configurable keyboard inputs for games.

The project should remain game-agnostic. Do not hard-code behavior for a particular game.

---

## System Architecture

The intended architecture is:

Physical skateboard movement
→ MPU-6050
→ Raspberry Pi
→ sensor processing
→ movement classification
→ network communication
→ Windows laptop
→ keyboard mapping
→ game

Keep these responsibilities separated in the code.

---

## Hardware

Current hardware:

- Raspberry Pi
- GY-521 breakout board
- MPU-6050 accelerometer and gyroscope
- Windows laptop
- Physical skateboard
- Wi-Fi/mobile hotspot used to put the Raspberry Pi and laptop on the same network

---

## Verified Hardware State

The following has already been manually tested successfully.

Do not treat these items as unverified or redesign them unnecessarily.

- Raspberry Pi successfully boots.
- SSH from the Windows laptop to the Raspberry Pi works.
- Raspberry Pi I2C is enabled.
- `/dev/i2c-1` has been successfully created and used.
- MPU-6050 is connected through I2C bus 1.
- MPU-6050 responds at address `0x68`.
- The MPU-6050 `WHO_AM_I` register returned `0x68`.
- Raw accelerometer measurements have been successfully read.
- Raw gyroscope measurements have been successfully read.
- Accelerometer measurements change when the physical sensor moves.
- Gyroscope measurements change when the physical sensor rotates.
- The IMU is now positioned on the skateboard approximately where it will be used.

A simple experimental Python script named `mpu_test.py` was previously created directly on the Raspberry Pi and successfully produced live sensor measurements.

---

## Current Objective

The current milestone is movement detection.

Build the simplest reliable pipeline that converts skateboard movement into:

- LEFT
- CENTER
- RIGHT

Do not implement advanced gesture recognition yet.

Do not implement machine learning for movement classification unless explicitly requested.

Do not attempt tricks, jumps, spins, or complex gestures until basic steering works reliably.

The development order should be:

1. Read accelerometer and gyroscope measurements.
2. Determine which physical IMU axes correspond to skateboard lean.
3. Calculate useful board orientation / tilt information.
4. Establish a neutral center position.
5. Detect LEFT / CENTER / RIGHT.
6. Add a configurable dead zone around CENTER.
7. Add basic filtering/smoothing if actual sensor testing shows it is necessary.
8. Send controller state from Raspberry Pi to laptop.
9. Convert controller state into keyboard input on the laptop.
10. Add forward/backward controls.
11. Only then consider additional movements.

Do not skip ahead unless explicitly requested.

---

## Code Architecture

Prefer a structure similar to:

skate-controller/
├── sensor/
│   ├── __init__.py
│   └── mpu6050.py
├── controller/
│   ├── __init__.py
│   └── movement.py
├── laptop/
│   ├── __init__.py
│   └── keyboard_output.py
├── tests/
├── requirements.txt
├── README.md
└── AGENTS.md

The exact structure can evolve if there is a strong reason, but preserve separation of responsibilities.

---

## Raspberry Pi Responsibilities

Raspberry Pi code should handle:

- I2C communication with the MPU-6050
- Reading raw accelerometer measurements
- Reading raw gyroscope measurements
- Sensor initialization
- Sensor calibration
- Sensor filtering when needed
- Calculating useful orientation information
- Classifying physical movement
- Producing controller states such as LEFT, CENTER, and RIGHT
- Eventually transmitting controller state to the Windows laptop

Raspberry Pi code should NOT generate Windows keyboard events.

---

## Laptop Responsibilities

Laptop code should eventually handle:

- Receiving controller states from the Raspberry Pi
- Mapping controller states to configurable keyboard keys
- Pressing/releasing those keyboard keys
- Preventing stuck keys
- Changing key bindings without modifying sensor logic

Networking and keyboard output should remain independent of MPU-6050 hardware access.

---

## MPU-6050 Information

Current I2C bus:

1

Current I2C address:

0x68

Registers already used successfully:

PWR_MGMT_1 = 0x6B

ACCEL_XOUT_H = 0x3B
ACCEL_YOUT_H = 0x3D
ACCEL_ZOUT_H = 0x3F

GYRO_XOUT_H = 0x43
GYRO_YOUT_H = 0x45
GYRO_ZOUT_H = 0x47

WHO_AM_I = 0x75

The previously tested raw sensor implementation used:

- accelerometer scale factor: 16384.0
- gyroscope scale factor: 131.0

Do not silently change sensor ranges or scale factors.

If changing sensor configuration becomes necessary, explain why and update the corresponding conversion logic.

---

## Movement Detection Design

Movement detection must not directly generate keyboard presses.

The desired interface is conceptually:

detect_movement(sensor_data) -> controller_state

Initially, valid controller states should be:

LEFT
CENTER
RIGHT

Thresholds must be configurable rather than scattered throughout the code as magic numbers.

For example:

LEFT_THRESHOLD
RIGHT_THRESHOLD
DEAD_ZONE

The actual values must come from physical testing of the skateboard.

Do not assume which MPU-6050 axis represents left/right movement until measurements from the mounted sensor establish it.

---

## Calibration

Assume the skateboard may not sit at a mathematically perfect zero angle.

The software should eventually support calibration of the rider's neutral position.

Do not assume:

sensor angle 0 == rider center

Instead, structure movement detection so a center offset can be applied.

---

## Filtering

Favor the simplest approach that works.

Start with raw or lightly averaged accelerometer measurements.

Only introduce more advanced filtering when physical testing demonstrates a problem that the filter solves.

If accelerometer noise becomes problematic, simple smoothing may be introduced.

If orientation needs both accelerometer stability and gyroscope responsiveness, a complementary filter may be considered.

Do not introduce a Kalman filter unless there is a demonstrated need.

---

## Keyboard Mapping

Do not implement keyboard mapping until LEFT / CENTER / RIGHT detection is reliable.

Keyboard bindings must eventually be configurable.

Possible default mappings may include:

LEFT -> A or Left Arrow
RIGHT -> D or Right Arrow
FORWARD -> W or Up Arrow
BACKWARD -> S or Down Arrow

Do not assume these mappings are final.

Keyboard code must correctly release a key when the controller returns to CENTER or switches direction.

Avoid designs that can leave keys permanently held down after an exception.

---

## Testing

Separate hardware-independent logic from hardware-dependent logic.

Movement classification should be testable using synthetic sensor/angle values without requiring the physical MPU-6050.

Examples that should eventually be testable:

negative lean -> LEFT
small lean -> CENTER
positive lean -> RIGHT

Tests should verify behavior at threshold boundaries.

Hardware tests should remain separate from unit tests.

---

## Development Style

Prefer:

- Small modules
- Small functions
- Clear naming
- Type hints where useful
- Constants/configuration instead of unexplained numbers
- Incremental changes
- Testable pure functions for movement classification
- Useful error messages
- Comments explaining hardware-specific decisions

Avoid:

- Premature abstractions
- Large frameworks
- Unnecessary dependencies
- Huge single-file implementations
- Mixing sensor access with keyboard control
- Rewriting working hardware code without a reason
- Premature machine-learning solutions
- Complex filtering before basic movement detection works

---

## Hardware Safety / Robustness

Code must handle sensor communication failures gracefully.

Do not continuously retry hardware operations in a tight loop without delay.

Do not modify operating-system networking configuration unless explicitly requested.

Do not automatically reboot or shut down the Raspberry Pi.

Do not automatically alter Raspberry Pi boot configuration.

Do not assume the Raspberry Pi IP address is permanently `172.20.10.6`.

---

## Git Workflow

GitHub is the source of truth for project code.

Development normally happens on the Windows laptop using Cursor.

Do not require editing source code directly on the Raspberry Pi with nano.

The intended workflow is:

Windows/Cursor
→ Git commit
→ GitHub
→ Raspberry Pi git pull
→ Run/test on physical hardware

Code that depends on the MPU-6050 must ultimately be tested on the Raspberry Pi.

Code that does not depend on physical hardware should be testable locally whenever practical.

---

## Current Milestone

Focus only on achieving:

mounted skateboard
→ MPU-6050 readings
→ board tilt
→ LEFT / CENTER / RIGHT

Do not proceed to networking or keyboard injection until this works reliably on the physical skateboard.