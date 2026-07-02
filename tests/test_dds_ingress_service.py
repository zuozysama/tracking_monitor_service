import os
import unittest

from services.dds_ingress_service import _on_target_perception_message
from store.situation_store import situation_store


_ENEMY_FRIEND_ATTR_ENV = "DDS_TARGET_ENEMY_FRIEND_ATTRS"


def _target_item(
    *,
    batch_no: int,
    military_civil_attr: int,
    source_platform_id: int,
    enemy_friend_attr: int | None = None,
) -> dict:
    item = {
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
    if enemy_friend_attr is not None:
        item["enemy_friend_attr"] = enemy_friend_attr
    return item


class DdsIngressServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_enemy_friend_attr_env = os.environ.get(_ENEMY_FRIEND_ATTR_ENV)
        os.environ.pop(_ENEMY_FRIEND_ATTR_ENV, None)
        situation_store.reset()
        situation_store._target_stale_timeout_sec = 999.0

    def tearDown(self) -> None:
        if self._orig_enemy_friend_attr_env is None:
            os.environ.pop(_ENEMY_FRIEND_ATTR_ENV, None)
        else:
            os.environ[_ENEMY_FRIEND_ATTR_ENV] = self._orig_enemy_friend_attr_env

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

    def test_military_civil_attr_one_is_kept(self):
        _on_target_perception_message(
            {
                "source_platform_id": 1500,
                "targets": [
                    _target_item(batch_no=1, military_civil_attr=1, source_platform_id=1500),
                ],
            }
        )
        snapshot = situation_store.get_situation_snapshot()
        self.assertEqual(len(snapshot["targets"]), 1)
        self.assertEqual(int(snapshot["targets"][0].target_batch_no), 1)

    def test_unknown_enemy_friend_attr_is_kept_when_whitelist_is_not_configured(self):
        _on_target_perception_message(
            {
                "source_platform_id": 1500,
                "targets": [
                    _target_item(
                        batch_no=2,
                        military_civil_attr=0,
                        source_platform_id=1500,
                        enemy_friend_attr=6,
                    ),
                ],
            }
        )
        snapshot = situation_store.get_situation_snapshot()
        self.assertEqual(len(snapshot["targets"]), 1)
        self.assertEqual(int(snapshot["targets"][0].target_batch_no), 2)

    def test_enemy_friend_attr_whitelist_keeps_matching_targets(self):
        os.environ[_ENEMY_FRIEND_ATTR_ENV] = "1,2,3,4"
        _on_target_perception_message(
            {
                "source_platform_id": 1500,
                "targets": [
                    _target_item(
                        batch_no=3,
                        military_civil_attr=2,
                        source_platform_id=1500,
                        enemy_friend_attr=3,
                    ),
                ],
            }
        )
        snapshot = situation_store.get_situation_snapshot()
        self.assertEqual(len(snapshot["targets"]), 1)
        self.assertEqual(int(snapshot["targets"][0].target_batch_no), 3)
        self.assertEqual(int(snapshot["targets"][0].enemy_friend_attr), 3)

    def test_enemy_friend_attr_whitelist_ignores_non_matching_targets(self):
        os.environ[_ENEMY_FRIEND_ATTR_ENV] = "1,2,3,4"
        _on_target_perception_message(
            {
                "source_platform_id": 1500,
                "targets": [
                    _target_item(
                        batch_no=5,
                        military_civil_attr=2,
                        source_platform_id=1500,
                        enemy_friend_attr=5,
                    ),
                    _target_item(
                        batch_no=6,
                        military_civil_attr=2,
                        source_platform_id=1500,
                        enemy_friend_attr=6,
                    ),
                ],
            }
        )
        snapshot = situation_store.get_situation_snapshot()
        self.assertEqual(len(snapshot["targets"]), 0)


if __name__ == "__main__":
    unittest.main()
