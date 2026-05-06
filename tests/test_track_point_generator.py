import unittest

from domain.enums import TrackingMode
from domain.models import GeoPoint, TargetState
from algorithms.track_point_generator import bearing_between_points_deg, generate_simple_tracking_point
from utils.time_utils import utc_now


def _target(heading_deg: float) -> TargetState:
    return TargetState(
        target_batch_no=1,
        target_longitude=121.5,
        target_latitude=31.2,
        target_absolute_heading_deg=heading_deg,
        timestamp=utc_now(),
    )


class TrackPointGeneratorTestCase(unittest.TestCase):
    def test_returned_bearing_is_relative_to_target_heading(self):
        target = _target(heading_deg=90.0)

        point, rel_bearing_deg = generate_simple_tracking_point(
            mode=TrackingMode.INTERCEPT,
            target=target,
            ownship=None,
            escort_distance_m=800.0,
            intercept_distance_m=500.0,
            expel_distance_m=200.0,
            intercept_stage=1,
            intercept_side="right",
        )

        abs_bearing_deg = bearing_between_points_deg(
            GeoPoint(longitude=target.longitude, latitude=target.latitude),
            point,
        )
        self.assertAlmostEqual(rel_bearing_deg, 90.0, places=6)
        self.assertAlmostEqual(abs_bearing_deg, 180.0, places=1)

    def test_left_front_relative_bearing_wraps_to_350(self):
        target = _target(heading_deg=90.0)

        point, rel_bearing_deg = generate_simple_tracking_point(
            mode=TrackingMode.INTERCEPT,
            target=target,
            ownship=None,
            escort_distance_m=800.0,
            intercept_distance_m=500.0,
            expel_distance_m=200.0,
            intercept_stage=2,
            intercept_side="left",
        )

        abs_bearing_deg = bearing_between_points_deg(
            GeoPoint(longitude=target.longitude, latitude=target.latitude),
            point,
        )
        self.assertAlmostEqual(rel_bearing_deg, 350.0, places=6)
        self.assertAlmostEqual(abs_bearing_deg, 80.0, places=1)


if __name__ == "__main__":
    unittest.main()
