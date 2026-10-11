import math

from controller.orientation import ComplementaryFilter, accel_angles


def test_accel_angles_flat_and_tilted():
    assert accel_angles(0, 0, 1) == (0.0, 0.0)
    roll, _ = accel_angles(0, math.sin(math.radians(20)), math.cos(math.radians(20)))
    assert abs(roll - 20) < 1e-9


def test_filter_converges_to_gravity_angle():
    f = ComplementaryFilter()
    f.update(0, 0, 1, 0, 0, 0, 0.005)
    ay, az = math.sin(math.radians(10)), math.cos(math.radians(10))
    for _ in range(1000):
        roll, _, _ = f.update(0, ay, az, 0, 0, 0, 0.005)
    assert abs(roll - 10) < 0.1


def test_filter_ignores_accel_during_impact():
    f = ComplementaryFilter()
    f.update(0, 0, 1, 0, 0, 0, 0.005)
    roll, _, _ = f.update(0, 2.0, 1.0, 0, 0, 0, 0.005)  # 2.2 g spike, no rotation
    assert roll == 0.0
