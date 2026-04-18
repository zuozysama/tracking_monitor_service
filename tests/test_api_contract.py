import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app import app
from store.collaboration_store import collaboration_store
from store.situation_store import situation_store
from store.task_store import task_store


class ApiContractTestCase(unittest.TestCase):
    def setUp(self) -> None:
        task_store.reset()
        situation_store.reset()
        collaboration_store.reset()
        self.client = TestClient(app)

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

    def test_media_stream_access_is_get(self):
        task_id = "task-media-001"
        now = datetime.now(timezone.utc).isoformat()
        self.client.post(
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
                "end_condition": {"duration_sec": 60},
                "stream_media_param": {
                    "photo_enabled": False,
                    "video_enabled": False,
                },
                "update_interval_sec": 1,
                "task_source": "test",
                "task_name": "media-get",
                "remark": now,
            },
        )

        resp = self.client.get(
            "/api/v1/media/stream/access",
            params={
                "task_id": task_id,
                "stream_type": "optical_video",
                "channel_id": "optical-001",
                "media_protocol": "webrtc",
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["code"], 200)
        self.assertEqual(body["data"]["media_protocol"], "webrtc")

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


if __name__ == "__main__":
    unittest.main()
