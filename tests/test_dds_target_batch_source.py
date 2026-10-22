import os
import struct
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from adapters.dds.topic_codec import (
    DEFAULT_TARGET_TRACK_ALL_TOPIC,
    TARGET_TRACK_ALL_FIELDS,
    decode_topic_payload,
    encode_topic_payload,
)
from domain.dds_contract import TARGET_PERCEPTION_TOPIC
from services.dds_ingress_service import _on_target_perception_message, register_default_subscriptions
from store.situation_store import situation_store
from utils.config_utils import get_dds_target_batch_no_source


_SOURCE_ENV = "DDS_TARGET_BATCH_NO_SOURCE"
_COMPOSITE = "composite_track_batch_no"
_BD = "bd_target_batch_no"


def _situation_client() -> TestClient:
    # Importing the production router normally constructs and starts a DDS adapter.
    # Load a private copy so the stand-in cannot leak into the production module.
    path = Path(__file__).resolve().parents[1] / "api" / "mock_dds_api.py"
    spec = importlib.util.spec_from_file_location("_dds_situation_endpoint_test", path)
    module = importlib.util.module_from_spec(spec)
    with patch("adapters.dds.get_dds_adapter", return_value=object()):
        spec.loader.exec_module(module)
    app = FastAPI()
    app.add_api_route("/mock/dds/situation", module.get_situation, methods=["GET"])
    return TestClient(app)


def _target_track_all_payload(
    composite: bytes = bytes.fromhex("00001001"),
    bd: bytes = bytes.fromhex("00002002"),
) -> bytes:
    payload = bytearray(369)
    struct.pack_into(">B", payload, 4, 1)
    struct.pack_into(">H", payload, 5, 369)
    struct.pack_into(">B", payload, 7, 1)
    struct.pack_into(">I", payload, 8, 7)
    struct.pack_into(">I", payload, 13, 1700000000)
    offset = 0
    for name, byte_size, _field_type, _scale in TARGET_TRACK_ALL_FIELDS:
        if name == _COMPOSITE:
            payload[offset : offset + byte_size] = composite
        elif name == _BD:
            payload[offset : offset + byte_size] = bd
        elif name == "data_source":
            struct.pack_into(">I", payload, offset, 2001)
        offset += byte_size
    return bytes(payload)


class DdsTargetBatchSourceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._env_patch = patch.dict(os.environ)
        self._env_patch.start()
        os.environ.pop(_SOURCE_ENV, None)
        os.environ.pop("DDS_TARGET_ENEMY_FRIEND_ATTRS", None)
        self._original_timeout = situation_store._target_stale_timeout_sec
        situation_store._target_stale_timeout_sec = 999.0
        situation_store.reset()
        self.client = _situation_client()

    def tearDown(self) -> None:
        situation_store.reset()
        situation_store._target_stale_timeout_sec = self._original_timeout
        self._env_patch.stop()

    def test_default_source_remains_bd(self):
        self.assertEqual(get_dds_target_batch_no_source(), _BD)
        decoded = decode_topic_payload(TARGET_PERCEPTION_TOPIC, _target_track_all_payload())

        self.assertNotIn("drop_message", decoded)
        self.assertEqual(decoded["target_batch_no_source"], _BD)
        self.assertEqual(decoded["targets"][0]["target_batch_no"], 2002)
        self.assertEqual(decoded["targets"][0]["target_id"], "target-2002")

    def test_selected_source_controls_number_for_both_topic_routes_and_wire_layouts(self):
        for source, expected in ((_BD, 2002), (_COMPOSITE, 1001)):
            for topic in (TARGET_PERCEPTION_TOPIC, DEFAULT_TARGET_TRACK_ALL_TOPIC):
                for prefix in (b"", bytes(range(16))):
                    with self.subTest(source=source, topic=topic, outer_header=bool(prefix)):
                        os.environ[_SOURCE_ENV] = source
                        decoded = decode_topic_payload(topic, prefix + _target_track_all_payload())

                        self.assertNotIn("drop_message", decoded)
                        self.assertEqual(decoded["target_batch_no_source"], source)
                        self.assertEqual(decoded["targets"][0]["target_batch_no"], expected)
                        self.assertEqual(decoded["targets"][0]["target_id"], f"target-{expected}")
                        self.assertEqual(decoded["target_track_all_fields"][_COMPOSITE], 1001)
                        self.assertEqual(decoded["target_track_all_fields"][_BD], 2002)

    def test_selected_all_ff_is_dropped_without_falling_back(self):
        cases = (
            (_BD, _target_track_all_payload(bd=b"\xff" * 4)),
            (_COMPOSITE, _target_track_all_payload(composite=b"\xff" * 4)),
        )
        for source, payload in cases:
            with self.subTest(source=source):
                os.environ[_SOURCE_ENV] = source
                decoded = decode_topic_payload(TARGET_PERCEPTION_TOPIC, payload)

                self.assertTrue(decoded["drop_message"])
                self.assertEqual(decoded["target_batch_no_source"], source)
                self.assertEqual(decoded["drop_reason"], f"{source}_all_ff")
                self.assertEqual(decoded["target_count"], 0)
                self.assertEqual(decoded["targets"], [])
                self.assertIsNone(decoded["target_track_all_fields"][source])

    def test_both_all_ff_fields_are_dropped_for_either_selected_source(self):
        payload = _target_track_all_payload(composite=b"\xff" * 4, bd=b"\xff" * 4)
        for source in (_BD, _COMPOSITE):
            with self.subTest(source=source):
                os.environ[_SOURCE_ENV] = source
                decoded = decode_topic_payload(TARGET_PERCEPTION_TOPIC, payload)

                self.assertTrue(decoded["drop_message"])
                self.assertEqual(decoded["drop_reason"], f"{source}_all_ff")
                self.assertEqual(decoded["targets"], [])
                self.assertIsNone(decoded["target_track_all_fields"][_BD])
                self.assertIsNone(decoded["target_track_all_fields"][_COMPOSITE])

    def test_invalid_source_fails_before_any_subscription_is_registered(self):
        os.environ[_SOURCE_ENV] = "invalid_source"
        adapter = Mock()

        with self.assertRaisesRegex(ValueError, _SOURCE_ENV):
            register_default_subscriptions(adapter)

        adapter.subscribe.assert_not_called()

    def test_unselected_all_ff_does_not_block_selected_valid_number(self):
        cases = (
            (_BD, _COMPOSITE, 2002, _target_track_all_payload(composite=b"\xff" * 4)),
            (_COMPOSITE, _BD, 1001, _target_track_all_payload(bd=b"\xff" * 4)),
        )
        for source, invalid_source, expected, payload in cases:
            with self.subTest(source=source):
                os.environ[_SOURCE_ENV] = source
                decoded = decode_topic_payload(TARGET_PERCEPTION_TOPIC, payload)

                self.assertNotIn("drop_message", decoded)
                self.assertEqual(decoded["targets"][0]["target_batch_no"], expected)
                self.assertIsNone(decoded["target_track_all_fields"][invalid_source])
                self.assertIsNone(decoded["targets"][0][invalid_source])

    def test_selected_zero_is_valid_and_does_not_fall_back(self):
        cases = (
            (_BD, _target_track_all_payload(bd=bytes(4))),
            (_COMPOSITE, _target_track_all_payload(composite=bytes(4))),
        )
        for source, payload in cases:
            with self.subTest(source=source):
                os.environ[_SOURCE_ENV] = source
                decoded = decode_topic_payload(TARGET_PERCEPTION_TOPIC, payload)

                self.assertNotIn("drop_message", decoded)
                self.assertEqual(decoded["targets"][0]["target_batch_no"], 0)
                self.assertEqual(decoded["targets"][0]["target_id"], "target-0")

    def test_selected_number_uses_all_eight_bcd_digits(self):
        for source in (_BD, _COMPOSITE):
            with self.subTest(source=source):
                os.environ[_SOURCE_ENV] = source
                payload = _target_track_all_payload(
                    composite=bytes.fromhex("12345678"),
                    bd=bytes.fromhex("87654321"),
                )
                decoded = decode_topic_payload(TARGET_PERCEPTION_TOPIC, payload)
                expected = 87654321 if source == _BD else 12345678

                self.assertEqual(decoded["targets"][0]["target_batch_no"], expected)

    def test_selected_number_is_preserved_through_ingress_into_situation(self):
        cases = (
            (_BD, 2002, _target_track_all_payload(composite=b"\xff" * 4)),
            (_COMPOSITE, 1001, _target_track_all_payload(bd=b"\xff" * 4)),
        )
        for source, expected, payload in cases:
            with self.subTest(source=source):
                situation_store.reset()
                os.environ[_SOURCE_ENV] = source
                decoded = decode_topic_payload(TARGET_PERCEPTION_TOPIC, payload)
                _on_target_perception_message(decoded)
                snapshot = situation_store.get_situation_snapshot()

                self.assertEqual(len(snapshot["targets"]), 1)
                self.assertEqual(snapshot["targets"][0].target_batch_no, expected)
                self.assertEqual(snapshot["targets"][0].target_id, f"target-{expected}")
                self.assertEqual(snapshot["last_source_id"], "2001")

    def test_selected_all_ff_does_not_write_other_number_to_situation(self):
        cases = (
            (_BD, _target_track_all_payload(bd=b"\xff" * 4)),
            (_COMPOSITE, _target_track_all_payload(composite=b"\xff" * 4)),
        )
        for source, payload in cases:
            with self.subTest(source=source):
                situation_store.reset()
                os.environ[_SOURCE_ENV] = source
                _on_target_perception_message(decode_topic_payload(TARGET_PERCEPTION_TOPIC, payload))
                snapshot = situation_store.get_situation_snapshot()

                self.assertEqual(snapshot["targets"], [])
                self.assertEqual(snapshot["revision"], 0)

    def test_decoded_target_reaches_situation_get_endpoint_for_each_source(self):
        cases = (
            (_BD, 2002, _target_track_all_payload(composite=b"\xff" * 4)),
            (_COMPOSITE, 1001, _target_track_all_payload(bd=b"\xff" * 4)),
        )
        for source, expected, payload in cases:
            with self.subTest(source=source):
                situation_store.reset()
                os.environ[_SOURCE_ENV] = source
                decoded = decode_topic_payload(TARGET_PERCEPTION_TOPIC, payload)
                _on_target_perception_message(decoded)
                response = self.client.get("/mock/dds/situation")

                self.assertEqual(response.status_code, 200)
                data = response.json()["data"]
                self.assertEqual(data["target_count"], 1)
                self.assertEqual(data["targets"][0]["target_batch_no"], expected)
                self.assertEqual(data["targets"][0]["target_id"], f"target-{expected}")

    def test_invalid_or_empty_source_fails_explicitly(self):
        for value in ("unknown", "", "   "):
            with self.subTest(value=value):
                os.environ[_SOURCE_ENV] = value
                with self.assertRaisesRegex(ValueError, _SOURCE_ENV):
                    get_dds_target_batch_no_source()

    def test_legacy_target_perception_number_is_unchanged_by_switch(self):
        payload = encode_topic_payload(
            TARGET_PERCEPTION_TOPIC,
            {
                "targets": [
                    {
                        "source_platform_id": 2001,
                        "target_batch_no": 321,
                        "target_bearing_deg": 12.0,
                        "target_distance_m": 3000.0,
                    }
                ]
            },
        )
        for source in (_BD, _COMPOSITE):
            with self.subTest(source=source):
                os.environ[_SOURCE_ENV] = source
                decoded = decode_topic_payload(TARGET_PERCEPTION_TOPIC, payload)

                self.assertEqual(decoded["targets"][0]["target_batch_no"], 321)


if __name__ == "__main__":
    unittest.main()
