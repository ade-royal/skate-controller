"""Read the MPU-6050 on Raspberry Pi I2C bus 1.

The board is a GY-521 at address 0x68. These register addresses and scale
factors match the setup that already returned live accelerometer and
gyroscope data. The default full-scale ranges are left unchanged:

- accelerometer ±2 g, scale 16384 LSB/g
- gyroscope ±250 deg/s, scale 131 LSB/(deg/s)
"""

from __future__ import annotations

import time

# I2C bus 1 is /dev/i2c-1. The sensor answers at 0x68 with AD0 low.
I2C_BUS = 1
I2C_ADDRESS = 0x68

PWR_MGMT_1 = 0x6B
WHO_AM_I = 0x75
WHO_AM_I_VALUE = 0x68

# Each axis is a high byte followed by a low byte.
ACCEL_XOUT_H = 0x3B
ACCEL_YOUT_H = 0x3D
ACCEL_ZOUT_H = 0x3F
GYRO_XOUT_H = 0x43
GYRO_YOUT_H = 0x45
GYRO_ZOUT_H = 0x47

ACCEL_REGISTERS = {
    "x": ACCEL_XOUT_H,
    "y": ACCEL_YOUT_H,
    "z": ACCEL_ZOUT_H,
}
GYRO_REGISTERS = {
    "x": GYRO_XOUT_H,
    "y": GYRO_YOUT_H,
    "z": GYRO_ZOUT_H,
}

# Default ±2 g and ±250 deg/s scales. Do not change these without also
# writing ACCEL_CONFIG / GYRO_CONFIG and updating the conversion below.
ACCEL_SCALE = 16384.0
GYRO_SCALE = 131.0

# The chip needs a moment after sleep is cleared before readings are valid.
WAKE_SETTLE_SECONDS = 0.05


def to_signed_16(high: int, low: int) -> int:
    """Combine a register pair into a signed 16-bit value.

    The MPU-6050 sends the high byte first. Bit 15 is the sign bit.
    """
    raw = ((high & 0xFF) << 8) | (low & 0xFF)
    if raw >= 0x8000:
        raw -= 0x10000
    return raw


class MPU6050:
    """Minimal accelerometer and gyroscope reader for the mounted GY-521."""

    def __init__(self, bus: int = I2C_BUS, address: int = I2C_ADDRESS) -> None:
        self.bus_number = bus
        self.address = address
        self._bus = self._open_bus(bus)
        try:
            self._wake()
            self._check_who_am_i()
        except OSError:
            self.close()
            raise

    def get_acceleration(self) -> dict[str, float]:
        """Return x, y, z acceleration in g."""
        return {
            axis: self._read_scaled(register, ACCEL_SCALE)
            for axis, register in ACCEL_REGISTERS.items()
        }

    def get_gyroscope(self) -> dict[str, float]:
        """Return x, y, z angular rate in degrees per second."""
        return {
            axis: self._read_scaled(register, GYRO_SCALE)
            for axis, register in GYRO_REGISTERS.items()
        }

    def close(self) -> None:
        bus = getattr(self, "_bus", None)
        if bus is not None:
            bus.close()
            self._bus = None

    def __enter__(self) -> "MPU6050":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def _open_bus(self, bus: int):
        try:
            from smbus2 import SMBus
        except ImportError as exc:
            raise ImportError(
                "smbus2 is required to read the MPU-6050. "
                "On the Raspberry Pi run: pip install -r requirements.txt"
            ) from exc

        try:
            return SMBus(bus)
        except OSError as exc:
            raise OSError(
                f"Could not open I2C bus {bus}. "
                "Confirm I2C is enabled and /dev/i2c-1 exists."
            ) from exc

    def _wake(self) -> None:
        # 0x00 clears the sleep bit and leaves the clock and scale registers
        # at the defaults used by the earlier working reads.
        try:
            self._bus.write_byte_data(self.address, PWR_MGMT_1, 0x00)
        except OSError as exc:
            raise OSError(
                f"Could not wake MPU-6050 at 0x{self.address:02X} "
                f"on I2C bus {self.bus_number}: {exc}"
            ) from exc
        time.sleep(WAKE_SETTLE_SECONDS)

    def _check_who_am_i(self) -> None:
        try:
            who = self._bus.read_byte_data(self.address, WHO_AM_I)
        except OSError as exc:
            raise OSError(
                f"MPU-6050 did not respond at 0x{self.address:02X} "
                f"on I2C bus {self.bus_number}: {exc}"
            ) from exc
        if who != WHO_AM_I_VALUE:
            raise OSError(
                f"Unexpected WHO_AM_I value 0x{who:02X} at address "
                f"0x{self.address:02X}; expected 0x{WHO_AM_I_VALUE:02X}."
            )

    def _read_word(self, register: int) -> int:
        try:
            high = self._bus.read_byte_data(self.address, register)
            low = self._bus.read_byte_data(self.address, register + 1)
        except OSError as exc:
            raise OSError(
                f"Failed to read MPU-6050 register 0x{register:02X} "
                f"on I2C bus {self.bus_number} address 0x{self.address:02X}: {exc}"
            ) from exc
        return to_signed_16(high, low)

    def _read_scaled(self, register: int, scale: float) -> float:
        return self._read_word(register) / scale
