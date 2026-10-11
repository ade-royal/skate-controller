"""Keyboard mapping tests. No pynput and no MPU-6050 required."""

from __future__ import annotations

import unittest

from laptop.keyboard_output import KeyBindings, KeyboardOutput


class RecordingKeyboard:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def press(self, key: str) -> None:
        self.events.append(("press", key))

    def release(self, key: str) -> None:
        self.events.append(("release", key))


class KeyboardOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.keyboard = RecordingKeyboard()
        self.output = KeyboardOutput(keyboard=self.keyboard)

    def test_left_holds_a(self) -> None:
        self.assertTrue(self.output.apply_state("LEFT"))
        self.assertEqual(self.keyboard.events, [("press", "a")])
        self.assertEqual(self.output.status_line(), "LEFT  holding a")

    def test_right_holds_d(self) -> None:
        self.output.apply_state("RIGHT")
        self.assertEqual(self.keyboard.events, [("press", "d")])

    def test_repeated_left_does_not_press_again(self) -> None:
        self.output.apply_state("LEFT")
        self.assertFalse(self.output.apply_state("LEFT"))
        self.assertFalse(self.output.apply_state("LEFT"))
        self.assertEqual(self.keyboard.events, [("press", "a")])

    def test_left_to_center_releases_a_and_d(self) -> None:
        self.output.apply_state("LEFT")
        self.output.apply_state("CENTER")
        self.assertEqual(
            self.keyboard.events,
            [("press", "a"), ("release", "a"), ("release", "d")],
        )
        self.assertEqual(self.output.status_line(), "CENTER  keys released")

    def test_right_to_center_releases_d_and_a(self) -> None:
        self.output.apply_state("RIGHT")
        self.output.apply_state("CENTER")
        self.assertEqual(
            self.keyboard.events,
            [("press", "d"), ("release", "d"), ("release", "a")],
        )

    def test_left_to_right_releases_a_before_holding_d(self) -> None:
        self.output.apply_state("LEFT")
        self.output.apply_state("RIGHT")
        self.assertEqual(
            self.keyboard.events,
            [("press", "a"), ("release", "a"), ("press", "d")],
        )

    def test_right_to_left_releases_d_before_holding_a(self) -> None:
        self.output.apply_state("RIGHT")
        self.output.apply_state("LEFT")
        self.assertEqual(
            self.keyboard.events,
            [("press", "d"), ("release", "d"), ("press", "a")],
        )

    def test_center_while_idle_does_nothing(self) -> None:
        self.assertFalse(self.output.apply_state("CENTER"))
        self.assertEqual(self.keyboard.events, [])

    def test_close_releases_held_key_and_both_bindings(self) -> None:
        self.output.apply_state("LEFT")
        self.output.close()
        self.assertEqual(
            self.keyboard.events,
            [("press", "a"), ("release", "a"), ("release", "d"), ("release", "space")],
        )
        self.output.close()
        self.assertEqual(
            self.keyboard.events[-3:],
            [("release", "a"), ("release", "d"), ("release", "space")],
        )

    def test_custom_bindings(self) -> None:
        output = KeyboardOutput(KeyBindings("j", "l"), keyboard=self.keyboard)
        output.apply_state("LEFT")
        output.apply_state("RIGHT")
        self.assertEqual(
            self.keyboard.events,
            [("press", "j"), ("release", "j"), ("press", "l")],
        )

    def test_uppercase_binding_is_stored_as_lowercase(self) -> None:
        bindings = KeyBindings("A", "D")
        self.assertEqual((bindings.left, bindings.right), ("a", "d"))

    def test_same_key_for_both_directions_raises(self) -> None:
        with self.assertRaises(ValueError):
            KeyBindings("a", "a")

    def test_unknown_state_does_not_press(self) -> None:
        with self.assertRaises(ValueError):
            self.output.apply_state("FORWARD")
        self.assertEqual(self.keyboard.events, [])

    def test_ollie_taps_space_and_leaves_d_held(self) -> None:
        self.output.apply_state("RIGHT")
        self.assertTrue(self.output.apply_state("OLLIE"))
        self.assertEqual(
            self.keyboard.events,
            [("press", "d"), ("press", "space"), ("release", "space")],
        )
        self.assertEqual(self.output.status_line(), "OLLIE  tapped space    RIGHT  holding d")
        self.assertEqual(self.output.status_line(), "RIGHT  holding d")
        self.assertFalse(self.output.apply_state("RIGHT"))
        self.assertEqual(self.keyboard.events[-1], ("release", "space"))

    def test_each_ollie_event_taps_space_again(self) -> None:
        self.output.apply_state("OLLIE")
        self.output.apply_state("OLLIE")
        self.assertEqual(
            self.keyboard.events,
            [
                ("press", "space"),
                ("release", "space"),
                ("press", "space"),
                ("release", "space"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
