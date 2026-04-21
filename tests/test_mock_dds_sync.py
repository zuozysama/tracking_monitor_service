import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app import app
from store.collaboration_store import collaboration_store
from store.situation_store import situation_store
from store.task_store import task_store


def _target(target_id: str, batch_no: int, longitude: float) -> dict:
    return {
        "target_id": target_id,
        "target_batch_no": batch_no,
        "target_bearing_deg": 35.0,
        "target_distance_m": 3000.0,
        "target_absolute_speed_mps": 6.2,
        "target_absolute_heading_deg": 90.0,
        "target_longitude": longitude,
        "target_latitude": 31.22,
        "target_type_code": 106,
        "military_civil_attr": 1,
        "threat_level": 2,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "active": True,
    }


class MockDdsSyncTestCase(unittest.TestCase):
    def setUp(self) -> None:
        task_store.reset()
        situation_store.reset()
        collaboration_store.reset()
        self.client = TestClient(app)

    def test_default_replace_mode_converges_to_latest_snapshot(self):
        first = self.client.post(
            "/mock/dds/perception",
            json={
                "target_count": 3,
                "targets": [
                    _target("target-001", 1, 121.501),
                    _target("target-002", 2, 121.502),
                    _target("target-003", 3, 121.503),
                ],
            },
        )
        self.assertEqual(first.status_code, 200)
        first_data = first.json()["data"]
        self.assertTrue(first_data["accepted"])
        revision_1 = first_data["revision"]

        second = self.client.post(
            "/mock/dds/perception",
            json={
                "target_count": 1,
                "targets": [_target("target-001", 1, 121.601)],
            },
        )
        self.assertEqual(second.status_code, 200)
        second_data = second.json()["data"]
        self.assertTrue(second_data["accepted"])
        self.assertEqual(second_data["revision"], revision_1 + 1)

        situation = self.client.get("/mock/dds/situation")
        self.assertEqual(situation.status_code, 200)
        situation_data = situation.json()["data"]
        self.assertEqual(situation_data["target_count"], 1)
        self.assertEqual({item["target_id"] for item in situation_data["targets"]}, {"target-001"})

    def test_merge_mode_keeps_previous_targets(self):
        self.client.post(
            "/mock/dds/perception?sync_mode=merge",
            json={
                "target_count": 2,
                "targets": [
                    _target("target-001", 1, 121.501),
                    _target("target-002", 2, 121.502),
                ],
            },
        )

        self.client.post(
            "/mock/dds/perception?sync_mode=merge",
            json={
                "target_count": 1,
                "targets": [_target("target-001", 1, 121.601)],
            },
        )

        situation = self.client.get("/mock/dds/situation").json()["data"]
        self.assertEqual(situation["target_count"], 2)
        self.assertEqual(
            {item["target_id"] for item in situation["targets"]},
            {"target-001", "target-002"},
        )

    def test_stale_revision_is_rejected(self):
        first = self.client.post(
            "/mock/dds/perception",
            json={
                "target_count": 2,
                "revision": 10,
                "targets": [
                    _target("target-001", 1, 121.501),
                    _target("target-002", 2, 121.502),
                ],
            },
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["data"]["revision"], 10)

        stale = self.client.post(
            "/mock/dds/perception",
            json={
                "target_count": 1,
                "revision": 9,
                "targets": [_target("target-003", 3, 121.503)],
            },
        )
        self.assertEqual(stale.status_code, 200)
        stale_data = stale.json()["data"]
        self.assertFalse(stale_data["accepted"])
        self.assertTrue(stale_data["ignored_stale_revision"])
        self.assertEqual(stale_data["revision"], 10)

        situation = self.client.get("/mock/dds/situation").json()["data"]
        self.assertEqual(situation["revision"], 10)
        self.assertEqual(
            {item["target_id"] for item in situation["targets"]},
            {"target-001", "target-002"},
        )

    def test_is_full_snapshot_forces_replace_even_when_merge_requested(self):
        self.client.post(
            "/mock/dds/targets?sync_mode=merge",
            json={
                "targets": [
                    _target("target-001", 1, 121.501),
                    _target("target-002", 2, 121.502),
                ],
            },
        )

        forced_replace = self.client.post(
            "/mock/dds/targets?sync_mode=merge",
            json={
                "sync_mode": "merge",
                "is_full_snapshot": True,
                "targets": [_target("target-003", 3, 121.503)],
            },
        )
        self.assertEqual(forced_replace.status_code, 200)
        self.assertEqual(forced_replace.json()["data"]["sync_mode"], "replace")

        situation = self.client.get("/mock/dds/situation").json()["data"]
        self.assertEqual(situation["target_count"], 1)
        self.assertEqual({item["target_id"] for item in situation["targets"]}, {"target-003"})

    def test_reset_endpoint_is_debug_only(self):
        resp = self.client.post("/mock/dds/reset")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["code"], 200)
        self.assertTrue(body["data"]["reset"])
        self.assertTrue(body["data"]["debug_only"])


if __name__ == "__main__":
    unittest.main()
