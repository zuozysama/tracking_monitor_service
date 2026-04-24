import unittest
from datetime import datetime, timezone
import time

from fastapi.testclient import TestClient

from app import app
from domain.models import TargetState
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
        # Speed up stale-retention tests.
        situation_store._target_stale_timeout_sec = 0.05
        self.client = TestClient(app)

    def test_dynamic_retention_keeps_targets_while_stream_continues(self):
        first = self.client.post(
            "/mock/dds/perception",
            json={
                "target_count": 1,
                "targets": [
                    _target("target-001", 1, 121.501),
                ],
            },
        )
        self.assertEqual(first.status_code, 200)
        first_data = first.json()["data"]
        self.assertTrue(first_data["accepted"])
        self.assertEqual(first_data["sync_mode"], "dynamic")

        self.client.post(
            "/mock/dds/perception",
            json={
                "target_count": 1,
                "targets": [_target("target-002", 2, 121.502)],
            },
        )
        self.client.post(
            "/mock/dds/perception",
            json={
                "target_count": 1,
                "targets": [_target("target-003", 3, 121.503)],
            },
        )
        self.client.post(
            "/mock/dds/perception",
            json={
                "target_count": 1,
                "targets": [_target("target-004", 4, 121.504)],
            },
        )

        situation = self.client.get("/mock/dds/situation")
        self.assertEqual(situation.status_code, 200)
        situation_data = situation.json()["data"]
        self.assertEqual(situation_data["target_count"], 4)
        self.assertEqual(
            {int(item["target_batch_no"]) for item in situation_data["targets"]},
            {1, 2, 3, 4},
        )

    def test_dynamic_retention_prunes_disappeared_batch_no(self):
        for batch_no in (1, 2, 3, 4):
            self.client.post(
                "/mock/dds/perception",
                json={
                    "target_count": 1,
                    "targets": [_target(f"target-{batch_no:03d}", batch_no, 121.500 + batch_no * 0.001)],
                },
            )

        # Let batch_no=4 expire, then keep refreshing only 1/2/3.
        time.sleep(0.08)
        for batch_no in (1, 2, 3):
            self.client.post(
                "/mock/dds/perception",
                json={
                    "target_count": 1,
                    "targets": [_target(f"target-{batch_no:03d}", batch_no, 121.600 + batch_no * 0.001)],
                },
            )

        situation = self.client.get("/mock/dds/situation").json()["data"]
        self.assertEqual(situation["target_count"], 3)
        self.assertEqual({int(item["target_batch_no"]) for item in situation["targets"]}, {1, 2, 3})

    def test_dynamic_mode_deduplicates_by_batch_no_even_if_target_id_changes(self):
        self.client.post(
            "/mock/dds/perception",
            json={
                "target_count": 1,
                "targets": [_target("target-A", 1, 121.501)],
            },
        )

        self.client.post(
            "/mock/dds/perception",
            json={
                "target_count": 1,
                "targets": [_target("target-B", 1, 121.601)],
            },
        )

        situation = self.client.get("/mock/dds/situation").json()["data"]
        self.assertEqual(situation["target_count"], 1)
        only = situation["targets"][0]
        self.assertEqual(only["target_batch_no"], 1)
        self.assertEqual(only["target_id"], "target-B")
        self.assertAlmostEqual(only["target_longitude"], 121.601, places=3)

    def test_invalid_batch_no_is_retained(self):
        self.client.post(
            "/mock/dds/perception",
            json={
                "target_count": 2,
                "targets": [
                    _target("target-invalid", 0, 121.401),
                    _target("target-valid", 1, 121.501),
                ],
            },
        )

        situation = self.client.get("/mock/dds/situation").json()["data"]
        self.assertEqual(situation["target_count"], 2)
        self.assertEqual({int(item["target_batch_no"]) for item in situation["targets"]}, {0, 1})

    def test_replace_targets_keeps_full_replace_semantics(self):
        now = datetime.now(timezone.utc)
        situation_store.update_targets(
            [
                TargetState(
                    source_platform_id=1001,
                    target_id="target-001",
                    target_batch_no=1,
                    target_longitude=121.501,
                    target_latitude=31.221,
                    timestamp=now,
                    active=True,
                ),
                TargetState(
                    source_platform_id=1001,
                    target_id="target-002",
                    target_batch_no=2,
                    target_longitude=121.502,
                    target_latitude=31.222,
                    timestamp=now,
                    active=True,
                ),
            ]
        )
        before = situation_store.get_situation_snapshot()
        self.assertEqual(len(before["targets"]), 2)

        situation_store.replace_targets(
            [
                TargetState(
                    source_platform_id=1001,
                    target_id="target-003",
                    target_batch_no=3,
                    target_longitude=121.503,
                    target_latitude=31.223,
                    timestamp=now,
                    active=True,
                )
            ]
        )
        after = situation_store.get_situation_snapshot()
        self.assertEqual(len(after["targets"]), 1)
        self.assertEqual(int(after["targets"][0].target_batch_no), 3)

    def test_get_target_by_batch_no_triggers_stale_prune(self):
        self.client.post(
            "/mock/dds/perception",
            json={
                "target_count": 1,
                "targets": [_target("target-001", 1, 121.501)],
            },
        )
        before_revision = situation_store.get_target_revision()
        time.sleep(0.08)

        found = situation_store.get_target_by_batch_no(1)
        after_revision = situation_store.get_target_revision()
        self.assertIsNone(found)
        self.assertGreater(after_revision, before_revision)

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

    def test_reset_endpoint_is_debug_only(self):
        resp = self.client.post("/mock/dds/reset")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["code"], 200)
        self.assertTrue(body["data"]["reset"])
        self.assertTrue(body["data"]["debug_only"])


if __name__ == "__main__":
    unittest.main()
