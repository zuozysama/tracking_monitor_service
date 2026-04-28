import unittest

from algorithms.patrol_planner import generate_simple_patrol_waypoints
from domain.models import GeoPoint, TaskArea


class PatrolPlannerTestCase(unittest.TestCase):
    def test_route_keeps_input_order_even_when_ownship_is_near_last_point(self):
        route_points = [
            GeoPoint(longitude=121.5000, latitude=31.2200),
            GeoPoint(longitude=121.5100, latitude=31.2200),
            GeoPoint(longitude=121.5200, latitude=31.2200),
        ]
        task_area = TaskArea(area_type="route", points=route_points)

        waypoints = generate_simple_patrol_waypoints(
            task_area=task_area,
            expected_speed=6.0,
            ownship_point=GeoPoint(longitude=121.5201, latitude=31.2200),
            ownship_heading_deg=270.0,
            start_turn_penalty_m_per_deg=2.0,
        )

        self.assertEqual(len(waypoints), 3)
        self.assertAlmostEqual(waypoints[0].longitude, route_points[0].longitude, places=7)
        self.assertAlmostEqual(waypoints[0].latitude, route_points[0].latitude, places=7)

    def test_circle_reorders_start_point_to_nearest_ownship_position(self):
        center = GeoPoint(longitude=121.5000, latitude=31.2200)
        task_area = TaskArea(area_type="circle", center=center, radius_m=1000.0)
        ownship_north = GeoPoint(longitude=121.5000, latitude=31.2290)

        waypoints = generate_simple_patrol_waypoints(
            task_area=task_area,
            expected_speed=6.0,
            ownship_point=ownship_north,
        )

        self.assertGreater(len(waypoints), 0)
        self.assertGreater(waypoints[0].latitude, center.latitude)

    def test_inside_radius_strategy_falls_back_when_polygon_is_too_narrow(self):
        task_area = TaskArea(
            area_type="polygon",
            points=[
                GeoPoint(longitude=121.0000, latitude=31.0000),
                GeoPoint(longitude=121.0003, latitude=31.0000),
                GeoPoint(longitude=121.0003, latitude=31.0030),
                GeoPoint(longitude=121.0000, latitude=31.0030),
            ],
        )

        waypoints = generate_simple_patrol_waypoints(
            task_area=task_area,
            expected_speed=6.0,
            num_passes=4,
            scan_radius_m=120.0,
        )

        self.assertGreater(len(waypoints), 1)

    def test_scan_radius_overrides_num_passes_for_polygon_spacing(self):
        task_area = TaskArea(
            area_type="polygon",
            points=[
                GeoPoint(longitude=121.0000, latitude=31.0000),
                GeoPoint(longitude=121.0100, latitude=31.0000),
                GeoPoint(longitude=121.0100, latitude=31.0200),
                GeoPoint(longitude=121.0000, latitude=31.0200),
            ],
        )
        waypoints_pass_4 = generate_simple_patrol_waypoints(
            task_area=task_area,
            expected_speed=6.0,
            num_passes=4,
            scan_radius_m=100.0,
        )
        waypoints_pass_8 = generate_simple_patrol_waypoints(
            task_area=task_area,
            expected_speed=6.0,
            num_passes=8,
            scan_radius_m=100.0,
        )

        self.assertEqual(len(waypoints_pass_4), len(waypoints_pass_8))

    def test_polygon_prepends_nearest_vertex_as_start_waypoint(self):
        polygon_points = [
            GeoPoint(longitude=121.0000, latitude=31.0000),
            GeoPoint(longitude=121.0100, latitude=31.0000),
            GeoPoint(longitude=121.0100, latitude=31.0100),
            GeoPoint(longitude=121.0000, latitude=31.0100),
        ]
        task_area = TaskArea(area_type="polygon", points=polygon_points)
        ownship_near_top_left = GeoPoint(longitude=120.9998, latitude=31.0102)

        waypoints = generate_simple_patrol_waypoints(
            task_area=task_area,
            expected_speed=6.0,
            num_passes=4,
            scan_radius_m=300.0,
            ownship_point=ownship_near_top_left,
        )

        self.assertGreater(len(waypoints), 0)
        self.assertAlmostEqual(waypoints[0].longitude, polygon_points[3].longitude, places=6)
        self.assertAlmostEqual(waypoints[0].latitude, polygon_points[3].latitude, places=6)

    def test_circle_prepends_boundary_intersection_as_start_waypoint(self):
        center = GeoPoint(longitude=121.5000, latitude=31.2200)
        task_area = TaskArea(area_type="circle", center=center, radius_m=1000.0)
        ownship_east = GeoPoint(longitude=121.5600, latitude=31.2200)

        waypoints = generate_simple_patrol_waypoints(
            task_area=task_area,
            expected_speed=6.0,
            ownship_point=ownship_east,
        )

        self.assertGreater(len(waypoints), 0)
        self.assertGreater(waypoints[0].longitude, center.longitude)


if __name__ == "__main__":
    unittest.main()
