import os
import unittest

from config.settings import load_settings


class SettingsEnvOverridesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_arrival_tolerance = os.environ.get("TRACKING_ARRIVAL_TOLERANCE_M")

    def tearDown(self) -> None:
        if self._orig_arrival_tolerance is None:
            os.environ.pop("TRACKING_ARRIVAL_TOLERANCE_M", None)
        else:
            os.environ["TRACKING_ARRIVAL_TOLERANCE_M"] = self._orig_arrival_tolerance

    def test_tracking_arrival_tolerance_can_be_overridden_by_env(self):
        os.environ["TRACKING_ARRIVAL_TOLERANCE_M"] = "123.5"
        settings = load_settings()
        self.assertAlmostEqual(settings.tracking.arrival.tolerance_m, 123.5)


if __name__ == "__main__":
    unittest.main()
