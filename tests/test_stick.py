from controller.movement import CENTER, LEFT, RIGHT, angle_to_stick, board_axis, stick_state


def test_inside_dead_zone_is_zero():
    assert angle_to_stick(2.9, dead_zone=3, max_angle=15) == 0.0
    assert angle_to_stick(-3.0, dead_zone=3, max_angle=15) == 0.0


def test_ramps_from_dead_zone_edge_and_saturates():
    assert angle_to_stick(9.0, dead_zone=3, max_angle=15) == 0.5
    assert angle_to_stick(-9.0, dead_zone=3, max_angle=15) == -0.5
    assert angle_to_stick(40.0, dead_zone=3, max_angle=15) == 1.0
    assert angle_to_stick(-40.0, dead_zone=3, max_angle=15) == -1.0


def test_stick_state():
    assert stick_state(-0.2) == LEFT
    assert stick_state(0.0) == CENTER
    assert stick_state(0.01) == RIGHT


def test_board_axis_applies_center_and_invert():
    orientation = {"roll": 12.0, "pitch": -4.0}
    assert board_axis(orientation, "roll", False, center=2.0) == 10.0
    assert board_axis(orientation, "roll", True, center=2.0) == -10.0
    assert board_axis(orientation, "pitch", False) == -4.0
