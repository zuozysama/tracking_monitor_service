import unittest
from datetime import datetime, timezone
import time

from fastapi.testclient import TestClient

from app import app
from services.task_service import task_service
from store.collaboration_store import collaboration_store
from store.situation_store import situation_store
from store.task_store import task_store


class ApiContractTestCase(unittest.TestCase):
    def setUp(self) -> None:
        task_store.reset()
        situation_store.reset()
        collaboration_store.reset()
        self.client = TestClient(app)

    def _post_ownship(self):
        return self.client.post(
            "/mock/dds/navigation",
            json={
                "platform_id": 1001,
                "speed_mps": 6.2,
                "heading_deg": 90.0,
                "longitude": 121.5000000,
                "latitude": 31.2200000,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _post_targets(self, targets: list[dict]):
        return self.client.post(
            "/mock/dds/perception",
            json={
                "target_count": len(targets),
                "sync_mode": "replace",
                "source_id": "test-api-contract",
                "targets": targets,
            },
        )

    @staticmethod
    def _target(
        target_id: str,
        batch_no: int,
        longitude: float,
        latitude: float,
        threat_level: int,
        target_position_attr: int,
        target_type_code: int = 106,
        target_length_m: float = 50.0,
    ) -> dict:
        return {
            "source_platform_id": 2001,
            "target_id": target_id,
            "target_batch_no": batch_no,
            "target_bearing_deg": 35.0,
            "target_distance_m": 3000.0,
            "target_absolute_speed_mps": 6.2,
            "target_absolute_heading_deg": 90.0,
            "target_longitude": longitude,
            "target_latitude": latitude,
            "target_type_code": target_type_code,
            "target_position_attr": target_position_attr,
            "target_length_m": target_length_m,
            "military_civil_attr": 1,
            "enemy_friend_attr": 1,
            "target_name": target_id,
            "threat_level": threat_level,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "active": True,
        }

    def _wait_until(self, predicate, timeout_sec: float = 3.0, interval_sec: float = 0.1):
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(interval_sec)
        return False

    def test_healthz_contract(self):
        resp = self.client.get("/api/v1/healthz")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["code"], 200)
        self.assertEqual(body["message"], "success")
        self.assertIsNone(body["data"])

    def test_create_task_and_query_status_output(self):
        task_id = "task-contract-001"
        create_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "escort",
                "task_name": "contract-test",
                "task_area": {
                    "area_type": "polygon",
                    "points": [
                        {"longitude": 121.49, "latitude": 31.21},
                        {"longitude": 121.52, "latitude": 31.21},
                        {"longitude": 121.52, "latitude": 31.23},
                    ],
                },
                "end_condition": {"duration_sec": 300},
            },
        )
        self.assertEqual(create_resp.status_code, 200)
        create_body = create_resp.json()
        self.assertEqual(create_body["code"], 200)
        self.assertEqual(create_body["data"]["task_id"], task_id)

        status_resp = self.client.get(f"/api/v1/{task_id}/status")
        self.assertEqual(status_resp.status_code, 200)
        status_body = status_resp.json()
        self.assertEqual(status_body["code"], 200)
        self.assertIn(status_body["data"]["task_status"], ["created", "running", "completed", "terminated", "failed"])

        output_resp = self.client.get(f"/api/v1/{task_id}/output")
        self.assertEqual(output_resp.status_code, 200)
        output_body = output_resp.json()
        self.assertEqual(output_body["code"], 200)
        self.assertEqual(output_body["data"]["task_id"], task_id)

    def test_create_preplan_task_returns_preplan_result(self):
        task_id = "task-preplan-contract-001"
        resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "preplan",
                "task_name": "preplan-contract-test",
                "task_area": {
                    "area_type": "polygon",
                    "points": [
                        {"longitude": 121.49, "latitude": 31.21},
                        {"longitude": 121.52, "latitude": 31.21},
                        {"longitude": 121.52, "latitude": 31.23},
                    ],
                },
                "expected_speed": 10.0,
                "end_condition": {"duration_sec": 120},
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["code"], 200)
        self.assertEqual(body["data"]["task_id"], task_id)
        self.assertEqual(body["data"]["task_type"], "preplan")
        self.assertIn("preplan_result", body["data"])
        self.assertNotIn("preplan_output", body["data"])

        preplan_result = body["data"]["preplan_result"]
        self.assertEqual(preplan_result["plan_type"], "preplan")
        self.assertGreater(preplan_result["waypoint_count"], 0)
        self.assertEqual(preplan_result["waypoint_count"], len(preplan_result["planned_route"]))

        first = preplan_result["planned_route"][0]
        self.assertIn("longitude", first)
        self.assertIn("latitude", first)
        self.assertIn("expected_speed", first)
        self.assertEqual(first["point_type"], "start")
        self.assertEqual(first["eta_sec"], 0)

    def test_preplan_task_is_one_shot_and_completed(self):
        task_id = "task-preplan-one-shot-001"
        self._post_ownship()
        resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "preplan",
                "task_name": "preplan-one-shot-test",
                "task_area": {
                    "area_type": "polygon",
                    "points": [
                        {"longitude": 121.49, "latitude": 31.21},
                        {"longitude": 121.52, "latitude": 31.21},
                        {"longitude": 121.52, "latitude": 31.23},
                    ],
                },
                "expected_speed": 8.0,
                "end_condition": {"duration_sec": 300},
            },
        )
        self.assertEqual(resp.status_code, 200)
        first_route_full = resp.json()["data"]["preplan_result"]["planned_route"]
        self.assertGreater(len(first_route_full), 0)
        first_route = [
            {
                "longitude": point["longitude"],
                "latitude": point["latitude"],
                "expected_speed": point["expected_speed"],
            }
            for point in first_route_full
        ]

        status_resp = self.client.get(f"/api/v1/{task_id}/status")
        self.assertEqual(status_resp.status_code, 200)
        status_data = status_resp.json()["data"]
        self.assertEqual(status_data["task_status"], "completed")
        self.assertEqual(status_data["execution_phase"], "completed")

        self.client.post(
            "/mock/dds/navigation",
            json={
                "platform_id": 1001,
                "speed_mps": 4.0,
                "heading_deg": 240.0,
                "longitude": 121.7000000,
                "latitude": 31.4000000,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        for _ in range(3):
            task_service.tick_task(task_id)

        output_resp = self.client.get(f"/api/v1/{task_id}/output")
        self.assertEqual(output_resp.status_code, 200)
        output_data = output_resp.json()["data"]
        preplan_output = output_data["preplan_output"]
        self.assertIsNotNone(preplan_output)

        later_route = [
            {
                "longitude": point["longitude"],
                "latitude": point["latitude"],
                "expected_speed": point["expected_speed"],
            }
            for point in preplan_output["planned_route"]
        ]
        self.assertEqual(later_route, first_route)

    def test_create_new_task_auto_replaces_active_old_task(self):
        old_task_id = "task-replace-old-001"
        new_task_id = "task-replace-new-001"

        old_create_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": old_task_id,
                "task_type": "escort",
                "task_area": {
                    "area_type": "polygon",
                    "points": [
                        {"longitude": 121.49, "latitude": 31.21},
                        {"longitude": 121.52, "latitude": 31.21},
                        {"longitude": 121.52, "latitude": 31.23},
                    ],
                },
                "end_condition": {"duration_sec": 300},
            },
        )
        self.assertEqual(old_create_resp.status_code, 200)

        new_create_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": new_task_id,
                "task_type": "patrol",
                "task_area": {
                    "area_type": "polygon",
                    "points": [
                        {"longitude": 121.60, "latitude": 31.30},
                        {"longitude": 121.63, "latitude": 31.30},
                        {"longitude": 121.63, "latitude": 31.33},
                    ],
                },
                "end_condition": {"duration_sec": 300},
            },
        )
        self.assertEqual(new_create_resp.status_code, 200)

        old_status_resp = self.client.get(f"/api/v1/{old_task_id}/status")
        self.assertEqual(old_status_resp.status_code, 200)
        old_status = old_status_resp.json()["data"]
        self.assertEqual(old_status["task_status"], "terminated")
        self.assertEqual(old_status["finish_reason"], "manual_terminated")
        self.assertEqual(old_status["execution_phase"], "completed")

    def test_create_new_task_replaces_old_even_if_manual_terminate_not_allowed(self):
        old_task_id = "task-replace-disabled-old-001"
        new_task_id = "task-replace-disabled-new-001"

        old_create_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": old_task_id,
                "task_type": "escort",
                "task_area": {
                    "area_type": "polygon",
                    "points": [
                        {"longitude": 121.49, "latitude": 31.21},
                        {"longitude": 121.52, "latitude": 31.21},
                        {"longitude": 121.52, "latitude": 31.23},
                    ],
                },
                "end_condition": {
                    "duration_sec": 300,
                    "manual_terminate_allowed": False,
                },
            },
        )
        self.assertEqual(old_create_resp.status_code, 200)

        new_create_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": new_task_id,
                "task_type": "patrol",
                "task_area": {
                    "area_type": "polygon",
                    "points": [
                        {"longitude": 121.60, "latitude": 31.30},
                        {"longitude": 121.63, "latitude": 31.30},
                        {"longitude": 121.63, "latitude": 31.33},
                    ],
                },
                "end_condition": {"duration_sec": 300},
            },
        )
        self.assertEqual(new_create_resp.status_code, 200)

        old_status_resp = self.client.get(f"/api/v1/{old_task_id}/status")
        self.assertEqual(old_status_resp.status_code, 200)
        old_status = old_status_resp.json()["data"]
        self.assertEqual(old_status["task_status"], "terminated")
        self.assertEqual(old_status["finish_reason"], "manual_terminated")

    def test_preplan_then_execute_can_reuse_same_task_id(self):
        task_id = "task-preplan-then-execute-001"

        preplan_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "preplan",
                "task_area": {
                    "area_type": "polygon",
                    "points": [
                        {"longitude": 121.49, "latitude": 31.21},
                        {"longitude": 121.52, "latitude": 31.21},
                        {"longitude": 121.52, "latitude": 31.23},
                    ],
                },
                "end_condition": {"duration_sec": 300},
            },
        )
        self.assertEqual(preplan_resp.status_code, 200)
        self.assertIn("preplan_result", preplan_resp.json()["data"])

        execute_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "escort",
                "task_area": {
                    "area_type": "polygon",
                    "points": [
                        {"longitude": 121.60, "latitude": 31.30},
                        {"longitude": 121.63, "latitude": 31.30},
                        {"longitude": 121.63, "latitude": 31.33},
                    ],
                },
                "end_condition": {"duration_sec": 300},
            },
        )
        self.assertEqual(execute_resp.status_code, 200)
        self.assertEqual(execute_resp.json()["data"]["task_id"], task_id)
        self.assertEqual(execute_resp.json()["data"]["task_type"], "escort")

    def test_execute_patrol_before_target_reuses_confirmed_preplan_route(self):
        task_id = "task-preplan-confirmed-route-001"
        area = {
            "area_type": "polygon",
            "points": [
                {"longitude": 121.49, "latitude": 31.21},
                {"longitude": 121.52, "latitude": 31.21},
                {"longitude": 121.52, "latitude": 31.23},
            ],
        }

        self.client.post(
            "/mock/dds/navigation",
            json={
                "platform_id": 1001,
                "speed_mps": 6.2,
                "heading_deg": 10.0,
                "longitude": 121.5000000,
                "latitude": 31.2200000,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        preplan_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "preplan",
                "task_area": area,
                "expected_speed": 8.5,
                "end_condition": {"duration_sec": 300},
            },
        )
        self.assertEqual(preplan_resp.status_code, 200)
        confirmed_route = preplan_resp.json()["data"]["preplan_result"]["planned_route"]
        self.assertGreater(len(confirmed_route), 0)

        self.client.post(
            "/mock/dds/navigation",
            json={
                "platform_id": 1001,
                "speed_mps": 5.1,
                "heading_deg": 210.0,
                "longitude": 121.6400000,
                "latitude": 31.3500000,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        execute_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "escort",
                "task_area": area,
                "expected_speed": 3.0,
                "end_condition": {"duration_sec": 300},
            },
        )
        self.assertEqual(execute_resp.status_code, 200)

        output_resp = self.client.get(f"/api/v1/{task_id}/output")
        self.assertEqual(output_resp.status_code, 200)
        output_data = output_resp.json()["data"]
        patrol_output = output_data["patrol_plan_output"]
        self.assertIsNotNone(patrol_output)

        executed_waypoints = patrol_output["waypoints"]
        self.assertEqual(len(executed_waypoints), len(confirmed_route))
        for idx, waypoint in enumerate(executed_waypoints):
            confirmed = confirmed_route[idx]
            self.assertAlmostEqual(waypoint["longitude"], confirmed["longitude"], places=7)
            self.assertAlmostEqual(waypoint["latitude"], confirmed["latitude"], places=7)
            self.assertAlmostEqual(waypoint["expected_speed"], confirmed["expected_speed"], places=7)

    def test_execute_underwater_before_target_reuses_confirmed_preplan_route(self):
        task_id = "task-preplan-confirmed-underwater-001"
        area = {
            "area_type": "polygon",
            "points": [
                {"longitude": 121.49, "latitude": 31.21},
                {"longitude": 121.52, "latitude": 31.21},
                {"longitude": 121.52, "latitude": 31.23},
            ],
        }

        self.client.post(
            "/mock/dds/navigation",
            json={
                "platform_id": 1001,
                "speed_mps": 6.2,
                "heading_deg": 15.0,
                "longitude": 121.5000000,
                "latitude": 31.2200000,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        preplan_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "preplan",
                "task_area": area,
                "expected_speed": 8.5,
                "end_condition": {"duration_sec": 300},
            },
        )
        self.assertEqual(preplan_resp.status_code, 200)
        confirmed_route = preplan_resp.json()["data"]["preplan_result"]["planned_route"]
        self.assertGreater(len(confirmed_route), 0)

        self.client.post(
            "/mock/dds/navigation",
            json={
                "platform_id": 1001,
                "speed_mps": 5.3,
                "heading_deg": 230.0,
                "longitude": 121.6500000,
                "latitude": 31.3600000,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        execute_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "underwater_search",
                "task_area": area,
                "expected_speed": 3.0,
                "end_condition": {"duration_sec": 300},
            },
        )
        self.assertEqual(execute_resp.status_code, 200)

        output_resp = self.client.get(f"/api/v1/{task_id}/output")
        self.assertEqual(output_resp.status_code, 200)
        output_data = output_resp.json()["data"]
        patrol_output = output_data["patrol_plan_output"]
        self.assertIsNotNone(patrol_output)

        executed_waypoints = patrol_output["waypoints"]
        self.assertEqual(len(executed_waypoints), len(confirmed_route))
        for idx, waypoint in enumerate(executed_waypoints):
            confirmed = confirmed_route[idx]
            self.assertAlmostEqual(waypoint["longitude"], confirmed["longitude"], places=7)
            self.assertAlmostEqual(waypoint["latitude"], confirmed["latitude"], places=7)
            self.assertAlmostEqual(waypoint["expected_speed"], confirmed["expected_speed"], places=7)

    def test_recreate_preplan_same_task_id_returns_conflict_409(self):
        task_id = "task-preplan-conflict-001"
        area = {
            "area_type": "polygon",
            "points": [
                {"longitude": 121.49, "latitude": 31.21},
                {"longitude": 121.52, "latitude": 31.21},
                {"longitude": 121.52, "latitude": 31.23},
            ],
        }

        first_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "preplan",
                "task_area": area,
                "end_condition": {"duration_sec": 300},
            },
        )
        self.assertEqual(first_resp.status_code, 200)

        second_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "preplan",
                "task_area": area,
                "end_condition": {"duration_sec": 300},
            },
        )
        self.assertEqual(second_resp.status_code, 409)

    def test_preplan_then_fixed_tracking_same_task_id_is_not_allowed(self):
        task_id = "task-preplan-fixed-deny-001"

        preplan_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "preplan",
                "task_area": {
                    "area_type": "polygon",
                    "points": [
                        {"longitude": 121.49, "latitude": 31.21},
                        {"longitude": 121.52, "latitude": 31.21},
                        {"longitude": 121.52, "latitude": 31.23},
                    ],
                },
                "end_condition": {"duration_sec": 300},
            },
        )
        self.assertEqual(preplan_resp.status_code, 200)

        fixed_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "fixed_tracking",
                "task_area": {
                    "area_type": "point",
                    "points": [
                        {"longitude": 121.55, "latitude": 31.25},
                    ],
                },
                "end_condition": {"duration_sec": 300},
            },
        )
        self.assertEqual(fixed_resp.status_code, 400)

    def test_manual_feedback_contract(self):
        task_id = "task-manual-001"
        self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "escort",
                "task_area": {
                    "area_type": "polygon",
                    "points": [
                        {"longitude": 121.49, "latitude": 31.21},
                        {"longitude": 121.52, "latitude": 31.21},
                        {"longitude": 121.52, "latitude": 31.23},
                    ],
                },
                "end_condition": {"duration_sec": 120},
            },
        )

        feedback_resp = self.client.post(
            "/api/v1/manual_selection/feedback",
            json={
                "task_id": task_id,
                "selected_target_id": "target-001",
                "feedback_time": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.assertEqual(feedback_resp.status_code, 200)
        self.assertEqual(feedback_resp.json()["code"], 200)
        self.assertTrue(feedback_resp.json()["data"]["feedback_received"])

    def test_create_escort_task_with_circle_area(self):
        task_id = "task-circle-001"
        create_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "escort",
                "task_name": "circle-contract-test",
                "task_area": {
                    "area_type": "circle",
                    "center": {"longitude": 121.50, "latitude": 31.22},
                    "radius_m": 3000,
                },
                "end_condition": {"duration_sec": 300},
            },
        )
        self.assertEqual(create_resp.status_code, 200)
        self.assertEqual(create_resp.json()["code"], 200)
        self.assertEqual(create_resp.json()["data"]["task_id"], task_id)

    def test_create_escort_task_with_circle_missing_center_should_fail(self):
        resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": "task-circle-invalid-001",
                "task_type": "escort",
                "task_area": {
                    "area_type": "circle",
                    "radius_m": 1200,
                },
            },
        )
        self.assertEqual(resp.status_code, 422)

    def test_create_fixed_tracking_task_with_point_area(self):
        task_id = "task-fixed-point-001"
        resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "fixed_tracking",
                "task_area": {
                    "area_type": "point",
                    "points": [
                        {"longitude": 121.50, "latitude": 31.22},
                    ],
                },
                "end_condition": {"duration_sec": 300},
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["code"], 200)
        self.assertEqual(resp.json()["data"]["task_id"], task_id)

    def test_create_fixed_tracking_task_with_non_point_area_should_fail(self):
        resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": "task-fixed-invalid-area-001",
                "task_type": "fixed_tracking",
                "task_area": {
                    "area_type": "polygon",
                    "points": [
                        {"longitude": 121.49, "latitude": 31.21},
                        {"longitude": 121.52, "latitude": 31.21},
                        {"longitude": 121.52, "latitude": 31.23},
                    ],
                },
            },
        )
        self.assertEqual(resp.status_code, 422)

    def test_create_non_fixed_task_with_point_area_should_fail(self):
        resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": "task-escort-point-invalid-001",
                "task_type": "escort",
                "task_area": {
                    "area_type": "point",
                    "points": [
                        {"longitude": 121.50, "latitude": 31.22},
                    ],
                },
            },
        )
        self.assertEqual(resp.status_code, 422)

    def test_create_fixed_tracking_task_with_multiple_point_items_should_fail(self):
        resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": "task-fixed-multi-point-invalid-001",
                "task_type": "fixed_tracking",
                "task_area": {
                    "area_type": "point",
                    "points": [
                        {"longitude": 121.50, "latitude": 31.22},
                        {"longitude": 121.51, "latitude": 31.23},
                    ],
                },
            },
        )
        self.assertEqual(resp.status_code, 422)

    def test_create_fixed_tracking_task_with_point_center_or_radius_should_fail(self):
        resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": "task-fixed-point-extra-invalid-001",
                "task_type": "fixed_tracking",
                "task_area": {
                    "area_type": "point",
                    "points": [
                        {"longitude": 121.50, "latitude": 31.22},
                    ],
                    "center": {"longitude": 121.51, "latitude": 31.23},
                    "radius_m": 300,
                },
            },
        )
        self.assertEqual(resp.status_code, 422)

    def test_openapi_and_docs_routes(self):
        openapi_resp = self.client.get("/api/swagger.json")
        self.assertEqual(openapi_resp.status_code, 200)
        data = openapi_resp.json()
        self.assertIn("/api/v1/tasks", data["paths"])
        self.assertIn("/api/v1/healthz", data["paths"])

        docs_resp = self.client.get("/api/swagger_ui/index.html")
        self.assertEqual(docs_resp.status_code, 200)

    def test_dds_subscribe_logs_endpoint(self):
        resp = self.client.get("/mock/collaboration/dds/subscribe-logs")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["code"], 200)
        self.assertIn("items", body["data"])

    def test_dds_debug_status_endpoint(self):
        resp = self.client.get("/mock/collaboration/dds/debug-status")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["code"], 200)
        self.assertIn("adapter_class", body["data"])
        self.assertIn("adapter_runtime", body["data"])
        self.assertIn("log_stats", body["data"])

    def test_tracking_default_surface_threat_filter_and_manual_selection_flow(self):
        self.assertEqual(self._post_ownship().status_code, 200)
        targets = [
            # should be filtered out: not surface target (target_position_attr != 3)
            self._target("target-001", 1, 121.5100, 31.2210, threat_level=5, target_position_attr=2),
            # should be filtered out: threat_level < 2
            self._target("target-002", 2, 121.5120, 31.2210, threat_level=1, target_position_attr=3),
            # valid surface targets
            self._target("target-003", 3, 121.5350, 31.2220, threat_level=4, target_position_attr=3),
            self._target("target-004", 4, 121.5220, 31.2210, threat_level=4, target_position_attr=3),
            self._target("target-005", 5, 121.5050, 31.2205, threat_level=3, target_position_attr=3),
        ]
        self.assertEqual(self._post_targets(targets).status_code, 200)

        task_id = "task-manual-default-filter-001"
        create_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "escort",
                "task_area": {
                    "area_type": "polygon",
                    "points": [
                        {"longitude": 121.48, "latitude": 31.20},
                        {"longitude": 121.56, "latitude": 31.20},
                        {"longitude": 121.56, "latitude": 31.26},
                        {"longitude": 121.48, "latitude": 31.26},
                    ],
                },
                "end_condition": {"duration_sec": 120},
            },
        )
        self.assertEqual(create_resp.status_code, 200)

        result_resp = self.client.get(f"/api/v1/{task_id}/result")
        self.assertEqual(result_resp.status_code, 200)
        # Same threat level between target-003 and target-004, should pick the nearer target-004.
        self.assertEqual(result_resp.json()["data"]["current_target_id"], "target-004")

        def _has_manual_selection_request() -> bool:
            req_resp = self.client.get("/mock/collaboration/manual-selection/requests")
            if req_resp.status_code != 200:
                return False
            items = req_resp.json()["data"]["items"]
            return any(item.get("task_id") == task_id for item in items)

        self.assertTrue(self._wait_until(_has_manual_selection_request))
        req_items = self.client.get("/mock/collaboration/manual-selection/requests").json()["data"]["items"]
        task_items = [x for x in req_items if x.get("task_id") == task_id]
        self.assertTrue(task_items)
        latest_req = task_items[-1]
        candidate_ids = [item.get("target_id") for item in latest_req.get("candidate_targets", [])]
        # Only surface targets with threat>=2 should remain.
        self.assertEqual(candidate_ids, ["target-004", "target-003", "target-005"])

        # Simulate command-side explicit selection and verify target switch.
        feedback_resp = self.client.post(
            "/api/v1/manual_selection/feedback",
            json={
                "task_id": task_id,
                "selected_target_id": "target-005",
                "feedback_time": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.assertEqual(feedback_resp.status_code, 200)

        switched_result = self.client.get(f"/api/v1/{task_id}/result").json()["data"]
        self.assertEqual(switched_result["current_target_id"], "target-005")

    def test_tracking_default_surface_threat_filter_single_target_no_manual_selection(self):
        self.assertEqual(self._post_ownship().status_code, 200)
        targets = [
            self._target("target-011", 11, 121.5110, 31.2210, threat_level=1, target_position_attr=3),
            self._target("target-012", 12, 121.5120, 31.2210, threat_level=5, target_position_attr=2),
            self._target("target-013", 13, 121.5130, 31.2210, threat_level=4, target_position_attr=3),
        ]
        self.assertEqual(self._post_targets(targets).status_code, 200)

        task_id = "task-manual-default-filter-002"
        create_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "escort",
                "task_area": {
                    "area_type": "polygon",
                    "points": [
                        {"longitude": 121.48, "latitude": 31.20},
                        {"longitude": 121.56, "latitude": 31.20},
                        {"longitude": 121.56, "latitude": 31.26},
                        {"longitude": 121.48, "latitude": 31.26},
                    ],
                },
                "end_condition": {"duration_sec": 120},
            },
        )
        self.assertEqual(create_resp.status_code, 200)

        result_resp = self.client.get(f"/api/v1/{task_id}/result")
        self.assertEqual(result_resp.status_code, 200)
        self.assertEqual(result_resp.json()["data"]["current_target_id"], "target-013")

        req_items = self.client.get("/mock/collaboration/manual-selection/requests").json()["data"]["items"]
        task_items = [x for x in req_items if x.get("task_id") == task_id]
        self.assertEqual(task_items, [])

    def test_arrival_with_enable_optical_opens_optical(self):
        self.assertEqual(self._post_ownship().status_code, 200)
        targets = [
            self._target("target-301", 301, 121.5350, 31.2220, threat_level=4, target_position_attr=3),
        ]
        self.assertEqual(self._post_targets(targets).status_code, 200)

        task_id = "task-auto-optical-001"
        create_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "escort",
                "task_area": {
                    "area_type": "polygon",
                    "points": [
                        {"longitude": 121.48, "latitude": 31.20},
                        {"longitude": 121.56, "latitude": 31.20},
                        {"longitude": 121.56, "latitude": 31.26},
                        {"longitude": 121.48, "latitude": 31.26},
                    ],
                },
                "linkage_param": {
                    "enable_optical": True,
                },
                "end_condition": {"duration_sec": 120},
            },
        )
        self.assertEqual(create_resp.status_code, 200)

        result_before = self.client.get(f"/api/v1/{task_id}/result")
        self.assertEqual(result_before.status_code, 200)
        recommended = result_before.json()["data"]["recommended_point"]
        self.assertIsNotNone(recommended)

        for _ in range(3):
            nav_resp = self.client.post(
                "/mock/dds/navigation",
                json={
                    "platform_id": 1001,
                    "speed_mps": 6.2,
                    "heading_deg": 90.0,
                    "longitude": recommended["longitude"],
                    "latitude": recommended["latitude"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            self.assertEqual(nav_resp.status_code, 200)
            task_service.tick_task(task_id)

        result_after = self.client.get(f"/api/v1/{task_id}/result")
        self.assertEqual(result_after.status_code, 200)
        result_data = result_after.json()["data"]
        self.assertIsNotNone(result_data.get("linkage_param"))
        self.assertTrue(result_data["linkage_param"]["enable_optical"])
        self.assertIsNotNone(result_data.get("optronic_status"))
        self.assertTrue(result_data["optronic_status"]["is_power_on"])

        cmd_logs_resp = self.client.get("/mock/collaboration/optical-linkage/commands")
        self.assertEqual(cmd_logs_resp.status_code, 200)
        task_cmds = [
            item for item in cmd_logs_resp.json()["data"]["items"] if item.get("task_id") == task_id
        ]
        self.assertTrue(task_cmds)
        self.assertEqual(task_cmds[-1].get("payload", {}).get("task_status"), 1)

    def test_arrival_without_enable_optical_does_not_open_optical(self):
        self.assertEqual(self._post_ownship().status_code, 200)
        targets = [
            self._target("target-302", 302, 121.5350, 31.2220, threat_level=4, target_position_attr=3),
        ]
        self.assertEqual(self._post_targets(targets).status_code, 200)

        task_id = "task-auto-optical-002"
        create_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "escort",
                "task_area": {
                    "area_type": "polygon",
                    "points": [
                        {"longitude": 121.48, "latitude": 31.20},
                        {"longitude": 121.56, "latitude": 31.20},
                        {"longitude": 121.56, "latitude": 31.26},
                        {"longitude": 121.48, "latitude": 31.26},
                    ],
                },
                "end_condition": {"duration_sec": 120},
            },
        )
        self.assertEqual(create_resp.status_code, 200)

        result_before = self.client.get(f"/api/v1/{task_id}/result")
        self.assertEqual(result_before.status_code, 200)
        recommended = result_before.json()["data"]["recommended_point"]
        self.assertIsNotNone(recommended)

        for _ in range(3):
            nav_resp = self.client.post(
                "/mock/dds/navigation",
                json={
                    "platform_id": 1001,
                    "speed_mps": 6.2,
                    "heading_deg": 90.0,
                    "longitude": recommended["longitude"],
                    "latitude": recommended["latitude"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            self.assertEqual(nav_resp.status_code, 200)
            task_service.tick_task(task_id)

        result_after = self.client.get(f"/api/v1/{task_id}/result")
        self.assertEqual(result_after.status_code, 200)
        result_data = result_after.json()["data"]
        self.assertIsNone(result_data.get("linkage_param"))
        self.assertIsNone(result_data.get("optronic_status"))

        cmd_logs_resp = self.client.get("/mock/collaboration/optical-linkage/commands")
        self.assertEqual(cmd_logs_resp.status_code, 200)
        task_cmds = [
            item for item in cmd_logs_resp.json()["data"]["items"] if item.get("task_id") == task_id
        ]
        self.assertEqual(task_cmds, [])

    def test_manual_selection_type_only_constraint_uses_type_filter_only_and_caps_four(self):
        self.assertEqual(self._post_ownship().status_code, 200)
        targets = [
            self._target("target-105", 105, 121.5005, 31.2205, threat_level=5, target_position_attr=3, target_type_code=40),
            self._target("target-102", 102, 121.5300, 31.2220, threat_level=2, target_position_attr=3, target_type_code=40),
            self._target("target-104", 104, 121.5150, 31.2230, threat_level=4, target_position_attr=3, target_type_code=40),
            self._target("target-101", 101, 121.5400, 31.2240, threat_level=1, target_position_attr=3, target_type_code=40),
            self._target("target-103", 103, 121.5120, 31.2205, threat_level=3, target_position_attr=3, target_type_code=40),
            self._target("target-999", 999, 121.5120, 31.2210, threat_level=5, target_position_attr=3, target_type_code=106),
        ]
        self.assertEqual(self._post_targets(targets).status_code, 200)

        task_id = "task-manual-type-only-001"
        create_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "escort",
                "task_area": {
                    "area_type": "polygon",
                    "points": [
                        {"longitude": 121.48, "latitude": 31.20},
                        {"longitude": 121.56, "latitude": 31.20},
                        {"longitude": 121.56, "latitude": 31.26},
                        {"longitude": 121.48, "latitude": 31.26},
                    ],
                },
                "target_info": {
                    "target_type_code": 40,
                },
                "end_condition": {"duration_sec": 120},
            },
        )
        self.assertEqual(create_resp.status_code, 200)

        def _has_manual_selection_request() -> bool:
            req_resp = self.client.get("/mock/collaboration/manual-selection/requests")
            if req_resp.status_code != 200:
                return False
            items = req_resp.json()["data"]["items"]
            return any(item.get("task_id") == task_id for item in items)

        self.assertTrue(self._wait_until(_has_manual_selection_request))
        req_items = self.client.get("/mock/collaboration/manual-selection/requests").json()["data"]["items"]
        task_items = [x for x in req_items if x.get("task_id") == task_id]
        self.assertTrue(task_items)
        latest_req = task_items[-1]
        candidates = latest_req.get("candidate_targets", [])
        candidate_ids = [item.get("target_id") for item in candidates]
        candidate_types = [item.get("target_type_code") for item in candidates]
        self.assertEqual(len(candidates), 4)
        self.assertEqual(candidate_types, [40, 40, 40, 40])
        self.assertEqual(candidate_ids, ["target-101", "target-102", "target-103", "target-104"])

    def test_manual_selection_threat_only_constraint_filters_exact_threat_level(self):
        self.assertEqual(self._post_ownship().status_code, 200)
        targets = [
            self._target("target-201", 201, 121.5300, 31.2205, threat_level=3, target_position_attr=3, target_type_code=106),
            self._target("target-202", 202, 121.5310, 31.2205, threat_level=3, target_position_attr=3, target_type_code=107),
            self._target("target-203", 203, 121.5320, 31.2205, threat_level=4, target_position_attr=3, target_type_code=106),
            self._target("target-204", 204, 121.5330, 31.2205, threat_level=2, target_position_attr=3, target_type_code=108),
            self._target("target-205", 205, 121.5340, 31.2205, threat_level=3, target_position_attr=3, target_type_code=105),
        ]
        self.assertEqual(self._post_targets(targets).status_code, 200)

        task_id = "task-manual-threat-only-001"
        create_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "escort",
                "task_area": {
                    "area_type": "polygon",
                    "points": [
                        {"longitude": 121.48, "latitude": 31.20},
                        {"longitude": 121.56, "latitude": 31.20},
                        {"longitude": 121.56, "latitude": 31.26},
                        {"longitude": 121.48, "latitude": 31.26},
                    ],
                },
                "target_info": {
                    "threat_level": 3,
                },
                "end_condition": {"duration_sec": 120},
            },
        )
        self.assertEqual(create_resp.status_code, 200)

        def _has_manual_selection_request() -> bool:
            req_resp = self.client.get("/mock/collaboration/manual-selection/requests")
            if req_resp.status_code != 200:
                return False
            items = req_resp.json()["data"]["items"]
            return any(item.get("task_id") == task_id for item in items)

        self.assertTrue(self._wait_until(_has_manual_selection_request))
        req_items = self.client.get("/mock/collaboration/manual-selection/requests").json()["data"]["items"]
        task_items = [x for x in req_items if x.get("task_id") == task_id]
        self.assertTrue(task_items)
        latest_req = task_items[-1]
        candidates = latest_req.get("candidate_targets", [])
        candidate_ids = [item.get("target_id") for item in candidates]
        candidate_threats = [item.get("threat_level") for item in candidates]
        self.assertEqual(candidate_threats, [3, 3, 3])
        self.assertEqual(candidate_ids, ["target-201", "target-202", "target-205"])

    def test_task_debug_candidates_endpoint_contains_rank_key_fields(self):
        self.assertEqual(self._post_ownship().status_code, 200)
        targets = [
            # Same threat/value, longer length should rank ahead even if farther.
            self._target("target-021", 21, 121.5220, 31.2210, threat_level=4, target_position_attr=3, target_length_m=45.0),
            self._target("target-022", 22, 121.5300, 31.2220, threat_level=4, target_position_attr=3, target_length_m=90.0),
        ]
        self.assertEqual(self._post_targets(targets).status_code, 200)

        task_id = "task-debug-candidates-001"
        create_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "escort",
                "task_area": {
                    "area_type": "polygon",
                    "points": [
                        {"longitude": 121.48, "latitude": 31.20},
                        {"longitude": 121.56, "latitude": 31.20},
                        {"longitude": 121.56, "latitude": 31.26},
                        {"longitude": 121.48, "latitude": 31.26},
                    ],
                },
                "end_condition": {"duration_sec": 120},
            },
        )
        self.assertEqual(create_resp.status_code, 200)

        debug_resp = self.client.get(f"/api/v1/tasks/{task_id}/debug/candidates")
        self.assertEqual(debug_resp.status_code, 200)
        body = debug_resp.json()
        self.assertEqual(body["code"], 200)
        self.assertEqual(body["data"]["task_id"], task_id)
        self.assertGreaterEqual(body["data"]["candidate_count"], 1)
        first = body["data"]["candidates"][0]
        self.assertIn("target_id", first)
        self.assertIn("target_length_m", first)
        self.assertIn("rank_threat_level", first)
        self.assertIn("rank_value_score", first)
        self.assertIn("rank_target_length_m", first)
        self.assertIn("rank_distance_m", first)
        self.assertIn("sort_key", first)
        self.assertEqual(body["data"]["candidates"][0]["target_id"], "target-022")

    def test_value_score_target_type_priority_order(self):
        self.assertEqual(self._post_ownship().status_code, 200)
        targets = [
            # Same threat/length; rank should follow target_type_code priority: 106 > 105 > 104 > 103 > others.
            self._target("target-031", 31, 121.5500, 31.2250, threat_level=4, target_position_attr=3, target_type_code=106, target_length_m=50.0),
            self._target("target-032", 32, 121.5010, 31.2205, threat_level=4, target_position_attr=3, target_type_code=105, target_length_m=50.0),
            self._target("target-033", 33, 121.5020, 31.2205, threat_level=4, target_position_attr=3, target_type_code=104, target_length_m=50.0),
            self._target("target-034", 34, 121.5030, 31.2205, threat_level=4, target_position_attr=3, target_type_code=103, target_length_m=50.0),
            self._target("target-035", 35, 121.5008, 31.2204, threat_level=4, target_position_attr=3, target_type_code=107, target_length_m=50.0),
        ]
        self.assertEqual(self._post_targets(targets).status_code, 200)

        task_id = "task-value-priority-001"
        create_resp = self.client.post(
            "/api/v1/tasks",
            json={
                "task_id": task_id,
                "task_type": "escort",
                "task_area": {
                    "area_type": "polygon",
                    "points": [
                        {"longitude": 121.48, "latitude": 31.20},
                        {"longitude": 121.56, "latitude": 31.20},
                        {"longitude": 121.56, "latitude": 31.26},
                        {"longitude": 121.48, "latitude": 31.26},
                    ],
                },
                "end_condition": {"duration_sec": 120},
            },
        )
        self.assertEqual(create_resp.status_code, 200)

        debug_resp = self.client.get(f"/api/v1/tasks/{task_id}/debug/candidates")
        self.assertEqual(debug_resp.status_code, 200)
        candidates = debug_resp.json()["data"]["candidates"]
        candidate_ids = [item.get("target_id") for item in candidates[:5]]
        self.assertEqual(candidate_ids, ["target-031", "target-032", "target-033", "target-034", "target-035"])


if __name__ == "__main__":
    unittest.main()
