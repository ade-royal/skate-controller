"""Read the MPU-6050 on Raspberry Pi I2C bus 1.

The board is a GY-521 at address 0x68. These register addresses and scale
factors match the setup that already returned live accelerometer and
gyroscope data. The default full-scale ranges are left unchanged:

- accelerometer ±2 g, scale 16384 LSB/g
- gyroscope ±250 deg/s, scale 131 LSB/(deg/s)

Callers can opt into wider ranges (pi/stream.py uses ±8 g / ±1000 deg/s,
because pops and landings saturate ±2 g). The scale factors are derived from
the requested range, so readings stay in g and deg/s either way.
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

SMPLRT_DIV = 0x19
CONFIG = 0x1A
GYRO_CONFIG = 0x1B
ACCEL_CONFIG = 0x1C

# Full-scale range -> FS_SEL / AFS_SEL value written to bits 4:3.
ACCEL_RANGE_BITS = {2: 0, 4: 1, 8: 2, 16: 3}
GYRO_RANGE_BITS = {250: 0, 500: 1, 1000: 2, 2000: 3}

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

    def __init__(
        self,
        bus: int = I2C_BUS,
        address: int = I2C_ADDRESS,
        accel_range_g: int = 2,
        gyro_range_dps: int = 250,
    ) -> None:
        if accel_range_g not in ACCEL_RANGE_BITS or gyro_range_dps not in GYRO_RANGE_BITS:
            raise ValueError(
                f"accel_range_g must be one of {sorted(ACCEL_RANGE_BITS)} and "
                f"gyro_range_dps one of {sorted(GYRO_RANGE_BITS)}."
            )
        self.bus_number = bus
        self.address = address
        self.accel_range_g = accel_range_g
        self.gyro_range_dps = gyro_range_dps
        self.accel_scale = ACCEL_SCALE * 2 / accel_range_g
        self.gyro_scale = GYRO_SCALE * 250 / gyro_range_dps
        self._bus = self._open_bus(bus)
        try:
            self._wake()
            self._check_who_am_i()
            if (accel_range_g, gyro_range_dps) != (2, 250):
                self._configure_ranges()
        except OSError:
            self.close()
            raise

    def get_acceleration(self) -> dict[str, float]:
        """Return x, y, z acceleration in g."""
        return {
            axis: self._read_scaled(register, self.accel_scale)
            for axis, register in ACCEL_REGISTERS.items()
        }

    def get_gyroscope(self) -> dict[str, float]:
        """Return x, y, z angular rate in degrees per second."""
        return {
            axis: self._read_scaled(register, self.gyro_scale)
            for axis, register in GYRO_REGISTERS.items()
        }

    def read_all(self) -> tuple[float, float, float, float, float, float]:
        """Return (ax, ay, az, gx, gy, gz) in g and deg/s from one 14-byte burst.

        One I2C transaction instead of twelve, so it keeps up at 200 Hz, and all
        six values come from the same sample.
        """
        try:
            d = self._bus.read_i2c_block_data(self.address, ACCEL_XOUT_H, 14)
        except OSError as exc:
            raise OSError(
                f"Failed burst read from MPU-6050 on I2C bus {self.bus_number} "
                f"address 0x{self.address:02X}: {exc}"
            ) from exc
        words = [to_signed_16(d[i], d[i + 1]) for i in range(0, 14, 2)]
        # words[3] is temperature, unused.
        return (
            words[0] / self.accel_scale,
            words[1] / self.accel_scale,
            words[2] / self.accel_scale,
            words[4] / self.gyro_scale,
            words[5] / self.gyro_scale,
            words[6] / self.gyro_scale,
        )

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

    def _configure_ranges(self) -> None:
        # DLPF_CFG=3 (~44 Hz) damps deck vibration and sets the internal rate
        # to 1 kHz, so SMPLRT_DIV=4 gives 200 Hz.
        try:
            self._bus.write_byte_data(self.address, CONFIG, 3)
            self._bus.write_byte_data(self.address, SMPLRT_DIV, 4)
            self._bus.write_byte_data(
                self.address, ACCEL_CONFIG, ACCEL_RANGE_BITS[self.accel_range_g] << 3
            )
            self._bus.write_byte_data(
                self.address, GYRO_CONFIG, GYRO_RANGE_BITS[self.gyro_range_dps] << 3
            )
        except OSError as exc:
            raise OSError(
                f"Could not configure MPU-6050 ranges on I2C bus {self.bus_number}: {exc}"
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
