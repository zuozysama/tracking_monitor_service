import unittest
from types import SimpleNamespace

from domain.enums import TrackingMode
from domain.models import GeoPoint, OwnShipState, RecommendedPoint, TargetState, TaskArea
from algorithms.track_point_generator import bearing_between_points_deg, generate_simple_tracking_point
from services.tracking_service import TrackingService
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

    def test_front_intercept_normalizes_left_front_to_0(self):
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
        self.assertAlmostEqual(rel_bearing_deg, 0.0, places=6)
        self.assertAlmostEqual(abs_bearing_deg, 90.0, places=1)

    def test_front_intercept_keeps_right_front_as_0(self):
        target = _target(heading_deg=90.0)

        point, rel_bearing_deg = generate_simple_tracking_point(
            mode=TrackingMode.INTERCEPT,
            target=target,
            ownship=None,
            escort_distance_m=800.0,
            intercept_distance_m=500.0,
            expel_distance_m=200.0,
            intercept_stage=2,
            intercept_side="right",
        )

        abs_bearing_deg = bearing_between_points_deg(
            GeoPoint(longitude=target.longitude, latitude=target.latitude),
            point,
        )
        self.assertAlmostEqual(rel_bearing_deg, 0.0, places=6)
        self.assertAlmostEqual(abs_bearing_deg, 90.0, places=1)

    def test_intercept_stage0_rear_uses_nearest_side_without_history(self):
        service = TrackingService()
        target = _target(heading_deg=0.0)
        ownship = OwnShipState(
            platform_id=1001,
            longitude=121.51,
            latitude=31.19,
            heading_deg=0.0,
            speed_mps=0.0,
            timestamp=utc_now(),
        )
        task = SimpleNamespace(
            recommended_point=RecommendedPoint(
                longitude=121.51,
                latitude=31.19,
                ref_type="target",
                ref_id=target.target_id,
                rel_range_m=100.0,
                rel_bearing_deg=180.0,
                expected_heading=target.heading,
                expected_speed=0.0,
                update_time=utc_now(),
            ),
            intercept_stage=0,
            intercept_side=None,
            intercept_arrival_stable_cycles=2,
        )

        service._refresh_intercept_stage(task, ownship, target, TrackingMode.INTERCEPT)

        self.assertEqual(task.intercept_stage, 1)
        self.assertEqual(task.intercept_side, "right")

    def test_intercept_stage0_rear_keeps_previous_side(self):
        service = TrackingService()
        target = _target(heading_deg=0.0)
        ownship = OwnShipState(
            platform_id=1001,
            longitude=121.51,
            latitude=31.19,
            heading_deg=0.0,
            speed_mps=0.0,
            timestamp=utc_now(),
        )
        task = SimpleNamespace(
            recommended_point=RecommendedPoint(
                longitude=121.51,
                latitude=31.19,
                ref_type="target",
                ref_id=target.target_id,
                rel_range_m=100.0,
                rel_bearing_deg=180.0,
                expected_heading=target.heading,
                expected_speed=0.0,
                update_time=utc_now(),
            ),
            intercept_stage=0,
            intercept_side="left",
            intercept_arrival_stable_cycles=2,
        )

        service._refresh_intercept_stage(task, ownship, target, TrackingMode.INTERCEPT)

        self.assertEqual(task.intercept_stage, 1)
        self.assertEqual(task.intercept_side, "left")

    def test_expel_stage0_uses_same_side_rear_point(self):
        target = _target(heading_deg=0.0)

        point, rel_bearing_deg = generate_simple_tracking_point(
            mode=TrackingMode.EXPEL,
            target=target,
            ownship=None,
            escort_distance_m=800.0,
            intercept_distance_m=500.0,
            expel_distance_m=200.0,
            expel_stage=0,
            expel_side="right",
        )

        abs_bearing_deg = bearing_between_points_deg(
            GeoPoint(longitude=target.longitude, latitude=target.latitude),
            point,
        )
        self.assertAlmostEqual(rel_bearing_deg, 135.0, places=6)
        self.assertAlmostEqual(abs_bearing_deg, 135.0, places=1)

    def test_expel_stage1_uses_same_side_beam_point(self):
        target = _target(heading_deg=0.0)

        point, rel_bearing_deg = generate_simple_tracking_point(
            mode=TrackingMode.EXPEL,
            target=target,
            ownship=None,
            escort_distance_m=800.0,
            intercept_distance_m=500.0,
            expel_distance_m=200.0,
            expel_stage=1,
            expel_side="left",
        )

        abs_bearing_deg = bearing_between_points_deg(
            GeoPoint(longitude=target.longitude, latitude=target.latitude),
            point,
        )
        self.assertAlmostEqual(rel_bearing_deg, 270.0, places=6)
        self.assertAlmostEqual(abs_bearing_deg, 270.0, places=1)

    def test_expel_side_uses_task_center_relative_to_target_heading(self):
        service = TrackingService()
        target = _target(heading_deg=0.0)
        ownship = OwnShipState(
            platform_id=1001,
            longitude=121.5,
            latitude=31.19,
            heading_deg=0.0,
            speed_mps=0.0,
            timestamp=utc_now(),
        )
        task = SimpleNamespace(
            task_area=TaskArea(
                area_type="circle",
                center=GeoPoint(longitude=121.51, latitude=31.2),
                radius_m=1000.0,
            ),
            expel_stage=0,
            expel_side=None,
        )

        service._refresh_expel_side(task, ownship, target, TrackingMode.EXPEL)

        self.assertEqual(task.expel_side, "right")

    def test_expel_side_keeps_previous_side_when_center_is_ahead(self):
        service = TrackingService()
        target = _target(heading_deg=0.0)
        ownship = OwnShipState(
            platform_id=1001,
            longitude=121.51,
            latitude=31.19,
            heading_deg=0.0,
            speed_mps=0.0,
            timestamp=utc_now(),
        )
        task = SimpleNamespace(
            task_area=TaskArea(
                area_type="circle",
                center=GeoPoint(longitude=121.5, latitude=31.21),
                radius_m=1000.0,
            ),
            expel_stage=0,
            expel_side="left",
        )

        service._refresh_expel_side(task, ownship, target, TrackingMode.EXPEL)

        self.assertEqual(task.expel_side, "left")

    def test_expel_side_uses_nearest_side_when_center_is_ahead_without_history(self):
        service = TrackingService()
        target = _target(heading_deg=0.0)
        ownship = OwnShipState(
            platform_id=1001,
            longitude=121.51,
            latitude=31.19,
            heading_deg=0.0,
            speed_mps=0.0,
            timestamp=utc_now(),
        )
        task = SimpleNamespace(
            task_area=TaskArea(
                area_type="circle",
                center=GeoPoint(longitude=121.5, latitude=31.21),
                radius_m=1000.0,
            ),
            expel_stage=0,
            expel_side=None,
        )

        service._refresh_expel_side(task, ownship, target, TrackingMode.EXPEL)

        self.assertEqual(task.expel_side, "right")

    def test_tracking_point_switch_requires_five_confirmed_better_cycles(self):
        service = TrackingService()
        task = SimpleNamespace(
            tracking_point_sector="rear",
            tracking_point_switch_candidate_sector=None,
            tracking_point_switch_confirm_cycles=0,
        )
        candidates = [
            {"sector": "left_rear", "point_score": 1.20},
            {"sector": "rear", "point_score": 1.00},
        ]

        for expected_count in range(1, 5):
            selected = service._select_tracking_candidate(task, candidates)
            self.assertEqual(selected["sector"], "rear")
            self.assertEqual(task.tracking_point_sector, "rear")
            self.assertEqual(task.tracking_point_switch_candidate_sector, "left_rear")
            self.assertEqual(task.tracking_point_switch_confirm_cycles, expected_count)

        selected = service._select_tracking_candidate(task, candidates)
        self.assertEqual(selected["sector"], "left_rear")
        self.assertEqual(task.tracking_point_sector, "left_rear")
        self.assertIsNone(task.tracking_point_switch_candidate_sector)
        self.assertEqual(task.tracking_point_switch_confirm_cycles, 0)

    def test_tracking_point_switch_resets_when_advantage_is_not_clear(self):
        service = TrackingService()
        task = SimpleNamespace(
            tracking_point_sector="rear",
            tracking_point_switch_candidate_sector="left_rear",
            tracking_point_switch_confirm_cycles=3,
        )
        candidates = [
            {"sector": "left_rear", "point_score": 1.10},
            {"sector": "rear", "point_score": 1.00},
        ]

        selected = service._select_tracking_candidate(task, candidates)

        self.assertEqual(selected["sector"], "rear")
        self.assertEqual(task.tracking_point_sector, "rear")
        self.assertIsNone(task.tracking_point_switch_candidate_sector)
        self.assertEqual(task.tracking_point_switch_confirm_cycles, 0)


if __name__ == "__main__":
    unittest.main()
