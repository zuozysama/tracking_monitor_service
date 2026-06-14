import os
import unittest

from config.settings import load_settings
from utils.config_utils import (
    get_tracking_escort_distance_m,
    get_tracking_expel_distance_m,
    get_tracking_intercept_distance_m,
    get_patrol_boundary_clearance_m,
    get_patrol_num_passes,
)


class SettingsEnvOverridesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_arrival_tolerance = os.environ.get("TRACKING_ARRIVAL_TOLERANCE_M")
        self._orig_tracking_escort_distance = os.environ.get("TRACKING_ESCORT_DISTANCE_M")
        self._orig_tracking_intercept_distance = os.environ.get("TRACKING_INTERCEPT_DISTANCE_M")
        self._orig_tracking_expel_distance = os.environ.get("TRACKING_EXPEL_DISTANCE_M")
        self._orig_fixed_tracking_region_radius = os.environ.get("FIXED_TRACKING_REGION_RADIUS_M")
        self._orig_patrol_num_passes = os.environ.get("PATROL_NUM_PASSES")
        self._orig_patrol_boundary_clearance = os.environ.get("PATROL_BOUNDARY_CLEARANCE_M")

    def tearDown(self) -> None:
        if self._orig_arrival_tolerance is None:
            os.environ.pop("TRACKING_ARRIVAL_TOLERANCE_M", None)
        else:
            os.environ["TRACKING_ARRIVAL_TOLERANCE_M"] = self._orig_arrival_tolerance
        if self._orig_tracking_escort_distance is None:
            os.environ.pop("TRACKING_ESCORT_DISTANCE_M", None)
        else:
            os.environ["TRACKING_ESCORT_DISTANCE_M"] = self._orig_tracking_escort_distance
        if self._orig_tracking_intercept_distance is None:
            os.environ.pop("TRACKING_INTERCEPT_DISTANCE_M", None)
        else:
            os.environ["TRACKING_INTERCEPT_DISTANCE_M"] = self._orig_tracking_intercept_distance
        if self._orig_tracking_expel_distance is None:
            os.environ.pop("TRACKING_EXPEL_DISTANCE_M", None)
        else:
            os.environ["TRACKING_EXPEL_DISTANCE_M"] = self._orig_tracking_expel_distance
        if self._orig_fixed_tracking_region_radius is None:
            os.environ.pop("FIXED_TRACKING_REGION_RADIUS_M", None)
        else:
            os.environ["FIXED_TRACKING_REGION_RADIUS_M"] = self._orig_fixed_tracking_region_radius
        if self._orig_patrol_num_passes is None:
            os.environ.pop("PATROL_NUM_PASSES", None)
        else:
            os.environ["PATROL_NUM_PASSES"] = self._orig_patrol_num_passes
        if self._orig_patrol_boundary_clearance is None:
            os.environ.pop("PATROL_BOUNDARY_CLEARANCE_M", None)
        else:
            os.environ["PATROL_BOUNDARY_CLEARANCE_M"] = self._orig_patrol_boundary_clearance

    def test_tracking_arrival_tolerance_can_be_overridden_by_env(self):
        os.environ["TRACKING_ARRIVAL_TOLERANCE_M"] = "123.5"
        settings = load_settings()
        self.assertAlmostEqual(settings.tracking.arrival.tolerance_m, 123.5)

    def test_patrol_env_fallback_and_override(self):
        os.environ["PATROL_NUM_PASSES"] = "6"
        os.environ["PATROL_BOUNDARY_CLEARANCE_M"] = "1200"
        self.assertEqual(get_patrol_num_passes(), 6)
        self.assertEqual(get_patrol_boundary_clearance_m(), 1200.0)

        os.environ["PATROL_NUM_PASSES"] = "0"
        os.environ["PATROL_BOUNDARY_CLEARANCE_M"] = "invalid"
        self.assertEqual(get_patrol_num_passes(), 4)
        self.assertEqual(get_patrol_boundary_clearance_m(), 500.0)

    def test_tracking_distances_can_be_overridden_by_env(self):
        os.environ["TRACKING_ESCORT_DISTANCE_M"] = "610"
        os.environ["TRACKING_INTERCEPT_DISTANCE_M"] = "180"
        os.environ["TRACKING_EXPEL_DISTANCE_M"] = "240"
        self.assertEqual(get_tracking_escort_distance_m(), 610.0)
        self.assertEqual(get_tracking_intercept_distance_m(), 180.0)
        self.assertEqual(get_tracking_expel_distance_m(), 240.0)

    def test_fixed_tracking_region_radius_can_be_overridden_by_env(self):
        os.environ["FIXED_TRACKING_REGION_RADIUS_M"] = "1000"
        settings = load_settings()
        self.assertEqual(settings.fixed_tracking.default_region_radius_m, 1000.0)


if __name__ == "__main__":
    unittest.main()
