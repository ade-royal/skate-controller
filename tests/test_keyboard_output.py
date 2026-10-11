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

    def type(self, text: str) -> None:
        self.events.append(("type", text))


class KeyboardOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.keyboard = RecordingKeyboard()
        self.output = KeyboardOutput(KeyBindings("a", "d"), keyboard=self.keyboard)

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
            [("press", "a"), ("release", "a"), ("release", "d")],
        )
        self.output.close()
        self.assertEqual(self.keyboard.events[-2:], [("release", "a"), ("release", "d")])

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


class PhraseBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.keyboard = RecordingKeyboard()
        self.output = KeyboardOutput(keyboard=self.keyboard)

    def test_defaults_are_hack_and_lanta(self) -> None:
        self.assertEqual((self.output.bindings.left, self.output.bindings.right), ("hack", "lanta_"))

    def test_left_types_hack_once(self) -> None:
        self.assertTrue(self.output.apply_state("LEFT"))
        self.assertFalse(self.output.apply_state("LEFT"))
        self.assertEqual(self.keyboard.events, [("type", "hack")])
        self.assertEqual(self.output.status_line(), "LEFT  typed hack")

    def test_right_types_lanta_with_underscore(self) -> None:
        self.output.apply_state("RIGHT")
        self.assertEqual(self.keyboard.events, [("type", "lanta_")])
        self.assertEqual(self.output.status_line(), "RIGHT  typed lanta_")

    def test_left_then_right_types_each_phrase_once(self) -> None:
        self.output.apply_state("LEFT")
        self.output.apply_state("RIGHT")
        self.assertEqual(self.keyboard.events, [("type", "hack"), ("type", "lanta_")])

    def test_center_does_not_type_again(self) -> None:
        self.output.apply_state("LEFT")
        self.output.apply_state("CENTER")
        self.assertEqual(self.keyboard.events, [("type", "hack")])
        self.assertEqual(self.output.status_line(), "CENTER  keys released")

    def test_close_does_not_release_the_phrase_as_a_key(self) -> None:
        self.output.apply_state("RIGHT")
        self.output.close()
        self.assertEqual(self.keyboard.events, [("type", "lanta_")])

    def test_phrase_with_a_space_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            KeyBindings("hack", "lanta _")


if __name__ == "__main__":
    unittest.main()
