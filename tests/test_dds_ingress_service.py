import unittest

from services.dds_ingress_service import _on_target_perception_message
from store.situation_store import situation_store


def _target_item(*, batch_no: int, military_civil_attr: int, source_platform_id: int) -> dict:
    return {
        "source_platform_id": source_platform_id,
        "target_id": f"target-{batch_no}",
        "target_batch_no": batch_no,
        "target_bearing_deg": 12.0,
        "target_distance_m": 3000.0,
        "target_absolute_speed_mps": 6.0,
        "target_absolute_heading_deg": 88.0,
        "target_longitude": 121.5,
        "target_latitude": 31.2,
        "target_type_code": 106,
        "military_civil_attr": military_civil_attr,
        "threat_level": 2,
    }


class DdsIngressServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        situation_store.reset()
        situation_store._target_stale_timeout_sec = 999.0

    def test_enemy_target_from_non_focus_platform_is_kept(self):
        _on_target_perception_message(
            {
                "source_platform_id": 1500,
                "targets": [
                    _target_item(batch_no=0, military_civil_attr=2, source_platform_id=1500),
                ],
            }
        )
        snapshot = situation_store.get_situation_snapshot()
        self.assertEqual(len(snapshot["targets"]), 1)
        self.assertEqual(int(snapshot["targets"][0].target_batch_no), 0)

    def test_red_side_target_is_filtered_out(self):
        _on_target_perception_message(
            {
                "source_platform_id": 1500,
                "targets": [
                    _target_item(batch_no=1, military_civil_attr=1, source_platform_id=1500),
                ],
            }
        )
        snapshot = situation_store.get_situation_snapshot()
        self.assertEqual(len(snapshot["targets"]), 0)

    def test_unknown_enemy_friend_attr_is_kept_for_compatibility(self):
        _on_target_perception_message(
            {
                "source_platform_id": 1500,
                "targets": [
                    _target_item(batch_no=2, military_civil_attr=0, source_platform_id=1500),
                ],
            }
        )
        snapshot = situation_store.get_situation_snapshot()
        self.assertEqual(len(snapshot["targets"]), 1)
        self.assertEqual(int(snapshot["targets"][0].target_batch_no), 2)


if __name__ == "__main__":
    unittest.main()
