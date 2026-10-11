import unittest

from controller.pop import PopDetector


class PopDetectorTests(unittest.TestCase):
    def test_dip_then_rebound_triggers_once(self):
        detector = PopDetector()
        values = [(1.0, -60), (1.2, -20), (1.4, 0), (1.6, 50), (1.7, 60)]
        self.assertEqual([detector.update(t, y) for t, y in values],
                         [False, False, False, True, False])

    def test_single_spike_or_wrong_order_does_not_trigger(self):
        detector = PopDetector()
        for t, y in [(1.0, 80), (1.2, 0), (1.4, -100), (1.6, 20), (1.8, 0)]:
            self.assertFalse(detector.update(t, y))

    def test_cooldown_suppresses_second_bounce(self):
        detector = PopDetector()
        detector.update(1.0, -60)
        self.assertTrue(detector.update(1.2, 60))
        self.assertFalse(detector.update(1.3, -60))
        self.assertFalse(detector.update(1.4, 60))
        detector.update(2.3, -60)
        self.assertTrue(detector.update(2.5, 60))

    def test_expired_reversal_does_not_trigger(self):
        detector = PopDetector()
        detector.update(1.0, -60)
        for t in (1.2, 1.4, 1.6, 1.8, 2.0):
            self.assertFalse(detector.update(t, 0))
        self.assertFalse(detector.update(2.1, 60))

    def test_gap_reset_and_invalid_data_clear_pending_dip(self):
        for interruption in ('gap', 'reset', 'nan'):
            with self.subTest(interruption=interruption):
                detector = PopDetector()
                detector.update(1.0, -60)
                if interruption == 'reset':
                    detector.reset()
                elif interruption == 'nan':
                    detector.update(1.1, float('nan'))
                self.assertFalse(detector.update(1.4 if interruption == 'gap' else 1.2, 60))
