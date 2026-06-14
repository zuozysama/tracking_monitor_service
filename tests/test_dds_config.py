import os
import unittest

from adapters.dds.config import load_dds_runtime_config, normalize_dds_qos_profile
from domain.dds_contract import (
    OWNSHIP_NAVIGATION_TOPIC,
    TASK_UPDATE_TOPIC,
)


class DdsConfigTestCase(unittest.TestCase):
    _ENV_KEYS = [
        "DDS_QOS_PROFILE",
        "DDS_QOS_PROFILE_TASK_UPDATE",
        "DDS_QOS_PROFILE_PREPLAN_RESULT",
        "DDS_QOS_PROFILE_MANUAL_SELECTION_REQUEST",
        "DDS_QOS_PROFILE_MANUAL_SWITCH_REQUEST",
        "DDS_QOS_PROFILE_ELECTRO_OPTICAL_LINKAGE_CMD",
        "DDS_QOS_PROFILE_STREAM_MEDIA_PARAM",
        "DDS_QOS_PROFILE_OWNSHIP_NAVIGATION",
        "DDS_QOS_PROFILE_TARGET_PERCEPTION",
    ]

    def setUp(self) -> None:
        self._orig_env = {key: os.environ.get(key) for key in self._ENV_KEYS}
        for key in self._ENV_KEYS:
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        for key, value in self._orig_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_qos_profile_normalization(self):
        self.assertEqual(normalize_dds_qos_profile("default_reliable"), "Reliable")
        self.assertEqual(normalize_dds_qos_profile("best_effort"), "BestEffort")
        self.assertEqual(normalize_dds_qos_profile("Best-Effort"), "BestEffort")
        self.assertEqual(normalize_dds_qos_profile("unknown", "Reliable"), "Reliable")

    def test_topic_qos_profiles_can_override_global_profile(self):
        os.environ["DDS_QOS_PROFILE"] = "BestEffort"
        os.environ["DDS_QOS_PROFILE_TASK_UPDATE"] = "default_reliable"
        os.environ["DDS_QOS_PROFILE_OWNSHIP_NAVIGATION"] = "best_effort"

        cfg = load_dds_runtime_config()

        self.assertEqual(cfg.qos_profile, "BestEffort")
        self.assertEqual(cfg.topic_qos_profiles[TASK_UPDATE_TOPIC], "Reliable")
        self.assertEqual(cfg.topic_qos_profiles[OWNSHIP_NAVIGATION_TOPIC], "BestEffort")


if __name__ == "__main__":
    unittest.main()
