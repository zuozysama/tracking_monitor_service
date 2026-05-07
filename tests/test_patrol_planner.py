import unittest

from algorithms.patrol_planner import (
    _LocalPoint,
    _build_scan_positions,
    _normalize_polygon_boundary,
    _polygon_has_self_intersection,
    _polygon_signed_area,
    _project_point_to_local,
    _project_to_local,
    generate_simple_patrol_waypoints,
)
from domain.models import GeoPoint, TaskArea


class PatrolPlannerTestCase(unittest.TestCase):
    def test_polygon_boundary_normalization_makes_clockwise(self):
        counterclockwise = [
            _LocalPoint(0.0, 0.0),
            _LocalPoint(10.0, 0.0),
            _LocalPoint(10.0, 10.0),
            _LocalPoint(0.0, 10.0),
        ]

        normalized = _normalize_polygon_boundary(counterclockwise)

        self.assertLess(_polygon_signed_area(normalized), 0.0)
        self.assertEqual([(point.x, point.y) for point in normalized], [(0.0, 10.0), (10.0, 10.0), (10.0, 0.0), (0.0, 0.0)])

    def test_polygon_boundary_normalization_repairs_bow_tie_rectangle(self):
        bow_tie = [
            _LocalPoint(0.0, 10.0),
            _LocalPoint(10.0, 10.0),
            _LocalPoint(0.0, 0.0),
            _LocalPoint(10.0, 0.0),
        ]

        normalized = _normalize_polygon_boundary(bow_tie)

        self.assertFalse(_polygon_has_self_intersection(normalized))
        self.assertLess(_polygon_signed_area(normalized), 0.0)

    def test_polygon_boundary_normalization_preserves_concave_adjacency(self):
        concave_counterclockwise = [
            _LocalPoint(0.0, 0.0),
            _LocalPoint(8.0, 0.0),
            _LocalPoint(8.0, 8.0),
            _LocalPoint(4.0, 4.0),
            _LocalPoint(0.0, 8.0),
        ]

        normalized = _normalize_polygon_boundary(concave_counterclockwise)

        self.assertFalse(_polygon_has_self_intersection(normalized))
        self.assertLess(_polygon_signed_area(normalized), 0.0)
        self.assertEqual(
            [(point.x, point.y) for point in normalized],
            [(0.0, 8.0), (4.0, 4.0), (8.0, 8.0), (8.0, 0.0), (0.0, 0.0)],
        )

    def test_send_task_rectangle_point_order_is_accepted(self):
        task_area = TaskArea(
            area_type="polygon",
            points=[
                GeoPoint(longitude=124.20, latitude=21.53),
                GeoPoint(longitude=124.79, latitude=21.53),
                GeoPoint(longitude=124.20, latitude=21.30),
                GeoPoint(longitude=124.79, latitude=21.30),
            ],
        )

        waypoints = generate_simple_patrol_waypoints(
            task_area=task_area,
            expected_speed=12.0,
            num_passes=8,
            scan_radius_m=5000.0,
            boundary_clearance_m=500.0,
            ownship_point=GeoPoint(longitude=124.05, latitude=21.42),
            ownship_heading_deg=90.0,
        )

        self.assertGreater(len(waypoints), 1)

    def test_polygon_entry_chooses_nearby_coverage_start_after_prepending_entry(self):
        task_area = TaskArea(
            area_type="polygon",
            points=[
                GeoPoint(longitude=124.20, latitude=21.53),
                GeoPoint(longitude=124.79, latitude=21.53),
                GeoPoint(longitude=124.50, latitude=21.60),
                GeoPoint(longitude=124.20, latitude=21.30),
                GeoPoint(longitude=124.79, latitude=21.30),
            ],
        )

        waypoints = generate_simple_patrol_waypoints(
            task_area=task_area,
            expected_speed=12.0,
            num_passes=8,
            scan_radius_m=2500.0,
            boundary_clearance_m=200.0,
            ownship_point=GeoPoint(longitude=124.05, latitude=21.42),
            ownship_heading_deg=90.0,
        )

        self.assertGreater(len(waypoints), 2)
        self.assertGreater(waypoints[1].latitude, 21.50)

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

    def test_scan_radius_uses_sensor_diameter_minimum_lane_count_not_num_passes(self):
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
            scan_radius_m=500.0,
        )
        waypoints_pass_8 = generate_simple_patrol_waypoints(
            task_area=task_area,
            expected_speed=6.0,
            num_passes=8,
            scan_radius_m=500.0,
        )

        self.assertEqual(len(waypoints_pass_8), len(waypoints_pass_4))

    def test_scan_positions_are_evenly_distributed_after_minimum_lane_count(self):
        positions = _build_scan_positions(
            min_y=0.0,
            max_y=6500.0,
            scan_margin=500.0,
            spacing=1800.0,
        )
        gaps = [b - a for a, b in zip(positions, positions[1:])]

        self.assertEqual(len(positions), 5)
        self.assertTrue(all(abs(gap - gaps[0]) <= 1e-6 for gap in gaps))
        self.assertLess(gaps[0], 1800.0)

    def test_polygon_scan_radius_spacing_is_no_wider_than_sensor_diameter(self):
        polygon_points = [
            GeoPoint(longitude=121.0000, latitude=31.0000),
            GeoPoint(longitude=121.0200, latitude=31.0000),
            GeoPoint(longitude=121.0200, latitude=31.0200),
            GeoPoint(longitude=121.0000, latitude=31.0200),
        ]
        task_area = TaskArea(area_type="polygon", points=polygon_points)

        waypoints = generate_simple_patrol_waypoints(
            task_area=task_area,
            expected_speed=6.0,
            num_passes=2,
            scan_radius_m=300.0,
            boundary_clearance_m=50.0,
        )

        local_ys = sorted(
            {
                round(
                    _project_point_to_local(
                        GeoPoint(longitude=waypoint.longitude, latitude=waypoint.latitude),
                        121.0100,
                        31.0100,
                    ).y,
                    1,
                )
                for waypoint in waypoints
            }
        )
        lane_gaps = [b - a for a, b in zip(local_ys, local_ys[1:]) if b - a > 1.0]

        self.assertTrue(lane_gaps)
        self.assertLessEqual(max(lane_gaps), 600.0 + 1e-6)

    def test_polygon_endpoints_use_half_radius_boundary_inset(self):
        polygon_points = [
            GeoPoint(longitude=121.0000, latitude=31.0000),
            GeoPoint(longitude=121.0200, latitude=31.0000),
            GeoPoint(longitude=121.0200, latitude=31.0200),
            GeoPoint(longitude=121.0000, latitude=31.0200),
        ]
        task_area = TaskArea(area_type="polygon", points=polygon_points)

        waypoints = generate_simple_patrol_waypoints(
            task_area=task_area,
            expected_speed=6.0,
            num_passes=8,
            scan_radius_m=500.0,
            boundary_clearance_m=50.0,
        )

        local_polygon, ref_lon, ref_lat = _project_to_local(polygon_points)
        min_polygon_x = min(point.x for point in local_polygon)
        waypoint_xs = [
            _project_point_to_local(GeoPoint(longitude=waypoint.longitude, latitude=waypoint.latitude), ref_lon, ref_lat).x
            for waypoint in waypoints
        ]

        self.assertGreater(min(waypoint_xs) - min_polygon_x, 200.0)
        self.assertLess(min(waypoint_xs) - min_polygon_x, 350.0)

    def test_polygon_scan_lines_use_half_radius_boundary_inset(self):
        polygon_points = [
            GeoPoint(longitude=121.0000, latitude=31.0000),
            GeoPoint(longitude=121.0200, latitude=31.0000),
            GeoPoint(longitude=121.0200, latitude=31.0200),
            GeoPoint(longitude=121.0000, latitude=31.0200),
        ]
        task_area = TaskArea(area_type="polygon", points=polygon_points)

        waypoints = generate_simple_patrol_waypoints(
            task_area=task_area,
            expected_speed=6.0,
            num_passes=8,
            scan_radius_m=500.0,
            boundary_clearance_m=50.0,
        )

        local_polygon, ref_lon, ref_lat = _project_to_local(polygon_points)
        min_polygon_y = min(point.y for point in local_polygon)
        waypoint_ys = [
            _project_point_to_local(GeoPoint(longitude=waypoint.longitude, latitude=waypoint.latitude), ref_lon, ref_lat).y
            for waypoint in waypoints
        ]

        self.assertLess(min(waypoint_ys) - min_polygon_y, 350.0)

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

    def test_polygon_inside_ownship_starts_from_current_position(self):
        polygon_points = [
            GeoPoint(longitude=121.0000, latitude=31.0000),
            GeoPoint(longitude=121.0200, latitude=31.0000),
            GeoPoint(longitude=121.0200, latitude=31.0200),
            GeoPoint(longitude=121.0000, latitude=31.0200),
        ]
        task_area = TaskArea(area_type="polygon", points=polygon_points)
        ownship_inside = GeoPoint(longitude=121.0067, latitude=31.0063)

        waypoints = generate_simple_patrol_waypoints(
            task_area=task_area,
            expected_speed=6.0,
            num_passes=8,
            scan_radius_m=300.0,
            ownship_point=ownship_inside,
            ownship_heading_deg=45.0,
        )

        self.assertGreater(len(waypoints), 1)
        self.assertAlmostEqual(waypoints[0].longitude, ownship_inside.longitude, places=7)
        self.assertAlmostEqual(waypoints[0].latitude, ownship_inside.latitude, places=7)
        self.assertLess(
            _project_point_to_local(
                GeoPoint(longitude=waypoints[1].longitude, latitude=waypoints[1].latitude),
                ownship_inside.longitude,
                ownship_inside.latitude,
            ).x
            ** 2
            + _project_point_to_local(
                GeoPoint(longitude=waypoints[1].longitude, latitude=waypoints[1].latitude),
                ownship_inside.longitude,
                ownship_inside.latitude,
            ).y
            ** 2,
            500.0**2,
        )

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
