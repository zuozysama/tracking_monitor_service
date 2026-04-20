import struct
import unittest

from adapters.dds.topic_codec import decode_topic_payload, encode_topic_payload
from domain.dds_contract import OWNSHIP_NAVIGATION_TOPIC, TARGET_PERCEPTION_TOPIC, TASK_UPDATE_TOPIC

GEO_LSB_DEG = 180.0 / (2 ** 31)


def _common_header(ts_sec: int = 1700000000, ts_sub_ms_x1e6: int = 500000000) -> bytes:
    return struct.pack(
        ">IBHBIBII",
        0,  # protocol_type
        1,  # version
        0,  # length (0 means ignore strict check)
        1,  # msg_type
        1,  # seq
        0,  # reserve
        ts_sec,
        ts_sub_ms_x1e6,
    )


class TopicCodecDecodeTestCase(unittest.TestCase):
    def test_encode_ownship_doc35_layout(self):
        body = encode_topic_payload(
            OWNSHIP_NAVIGATION_TOPIC,
            {
                "platform_id": 2001,
                "speed_mps": 12.34,
                "heading_deg": 271.0,
                "longitude": 121.5123456,
                "latitude": 31.2234567,
                "protocol_type": 0,
                "protocol_version": 1,
                "msg_type": 1,
                "msg_seq": 9,
                "reserve": 0,
                "timestamp_0p1ms": 123456789,
            },
        )
        self.assertEqual(len(body), 35)
        protocol_type, version, packet_len, msg_type, seq, reserve, ts_0p1ms = struct.unpack(">IBHBIBQ", body[:21])
        self.assertEqual(protocol_type, 0)
        self.assertEqual(version, 1)
        self.assertEqual(packet_len, 35)
        self.assertEqual(msg_type, 1)
        self.assertEqual(seq, 9)
        self.assertEqual(reserve, 0)
        self.assertEqual(ts_0p1ms, 123456789)

        uid, speed_raw, heading_raw, lon_raw, lat_raw = struct.unpack(">HHHii", body[21:35])
        self.assertEqual(uid, 2001)
        self.assertEqual(speed_raw, 1234)
        self.assertEqual(heading_raw, 271)
        self.assertAlmostEqual(lon_raw * GEO_LSB_DEG, 121.5123456, places=5)
        self.assertAlmostEqual(lat_raw * GEO_LSB_DEG, 31.2234567, places=5)

    def test_decode_ownship_doc35_layout(self):
        lon_raw = int(round(121.5123456 * (2 ** 31) / 180.0))
        lat_raw = int(round(31.2234567 * (2 ** 31) / 180.0))

        doc35 = bytearray(35)
        doc35[0:21] = bytes(range(1, 22))          # inner 21-byte protocol head
        struct.pack_into(">H", doc35, 21, 2001)    # uid
        struct.pack_into(">H", doc35, 23, 1234)    # speed_raw -> 12.34 m/s
        struct.pack_into(">H", doc35, 25, 271)     # heading_raw -> 271 deg
        struct.pack_into(">i", doc35, 27, lon_raw)
        struct.pack_into(">i", doc35, 31, lat_raw)

        decoded = decode_topic_payload(OWNSHIP_NAVIGATION_TOPIC, bytes(doc35))
        self.assertEqual(decoded["platform_id"], 2001)
        self.assertAlmostEqual(decoded["speed_mps"], 12.34, places=2)
        self.assertAlmostEqual(decoded["heading_deg"], 271.0, places=2)
        self.assertAlmostEqual(decoded["longitude"], lon_raw * GEO_LSB_DEG, places=7)
        self.assertAlmostEqual(decoded["latitude"], lat_raw * GEO_LSB_DEG, places=7)
        self.assertEqual(decoded.get("decode_format"), "doc35_21_plus_14_fields")
        self.assertEqual(decoded["offsets"]["uid"], [21, 22])
        self.assertEqual(decoded.get("input_layout"), "doc35")
        self.assertEqual(decoded.get("raw_len"), 35)
        self.assertEqual(len(bytes.fromhex(decoded.get("raw_hex", ""))), 35)
        self.assertTrue(str(decoded["timestamp"]).endswith("Z"))

    def test_encode_target_perception_21_plus_2_plus_nx90(self):
        body = encode_topic_payload(
            TARGET_PERCEPTION_TOPIC,
            {
                "protocol_type": 0,
                "protocol_version": 1,
                "msg_type": 1,
                "msg_seq": 7,
                "reserve": 0,
                "timestamp_0p1ms": 123456,
                "targets": [
                    {
                        "source_platform_id": 2001,
                        "target_batch_no": 101,
                        "target_bearing_deg": 12.3,
                        "target_distance_m": 1500,
                        "target_name": "TARGET-1",
                    },
                    {
                        "source_platform_id": 2002,
                        "target_batch_no": 102,
                        "target_bearing_deg": 23.4,
                        "target_distance_m": 1800,
                        "target_name": "TARGET-2",
                    },
                ],
            },
        )

        self.assertEqual(len(body), 21 + 2 + 2 * 90)
        protocol_type, version, packet_len, msg_type, seq, reserve, ts_0p1ms = struct.unpack(">IBHBIBQ", body[:21])
        self.assertEqual(protocol_type, 0)
        self.assertEqual(version, 1)
        self.assertEqual(packet_len, len(body))
        self.assertEqual(msg_type, 1)
        self.assertEqual(seq, 7)
        self.assertEqual(reserve, 0)
        self.assertEqual(ts_0p1ms, 123456)
        self.assertEqual(struct.unpack(">H", body[21:23])[0], 2)

        decoded = decode_topic_payload(TARGET_PERCEPTION_TOPIC, body)
        self.assertEqual(decoded["target_count"], 2)
        self.assertEqual(decoded["entry_size"], 90)
        self.assertEqual(decoded["targets"][0]["source_platform_id"], 2001)
        self.assertEqual(decoded["targets"][1]["source_platform_id"], 2002)

    def test_decode_ownship_doc35_with_outer_v3_header_compatible(self):
        lon_raw = int(round(121.5123456 * (2 ** 31) / 180.0))
        lat_raw = int(round(31.2234567 * (2 ** 31) / 180.0))

        v3_head = b"\x00" * 16
        doc35 = bytearray(35)
        doc35[0:21] = bytes(range(1, 22))
        struct.pack_into(">H", doc35, 21, 2001)
        struct.pack_into(">H", doc35, 23, 1234)
        struct.pack_into(">H", doc35, 25, 271)
        struct.pack_into(">i", doc35, 27, lon_raw)
        struct.pack_into(">i", doc35, 31, lat_raw)

        decoded = decode_topic_payload(OWNSHIP_NAVIGATION_TOPIC, v3_head + bytes(doc35))
        self.assertEqual(decoded["platform_id"], 2001)
        self.assertEqual(decoded.get("input_layout"), "v3_16_plus_35")
        self.assertEqual(len(bytes.fromhex(decoded.get("raw_hex", ""))), 35)

    def test_decode_ownship_doc35_too_short(self):
        decoded = decode_topic_payload(OWNSHIP_NAVIGATION_TOPIC, b"\x00" * 34)
        self.assertIn("decode_error", decoded)
        self.assertIn("need at least 35", decoded["decode_error"])

    def test_decode_target_perception_doc_format(self):
        name = "TARGET-A".encode("gb2312")
        name = name + b"\x00" * (40 - len(name))
        entry = struct.pack(
            ">HHIHHHHHiiHBBIbbb40sHHHbHH",
            35,                      # batch_no
            123,                     # bearing 12.3 deg
            1500,                    # distance
            0,                       # height
            45,                      # abs speed 4.5 m/s
            900,                     # abs heading 90.0 deg
            10,                      # rel speed
            20,                      # rel heading
            int(121.5 * 1e7),
            int(31.2 * 1e7),
            12,                      # qt
            0,                       # coord sys
            1,                       # simulated
            123456,                  # target ts
            3,                       # position attr
            106,                     # target type
            1,                       # military_civil_attr
            name,
            10, 20, 30,              # length/width/height
            3,                       # threat
            11,                      # rcs
            0,                       # custom2
        )
        body = _common_header() + struct.pack(">HH", 1, 2001) + entry

        decoded = decode_topic_payload(TARGET_PERCEPTION_TOPIC, body)
        self.assertEqual(decoded["source_platform_id"], 2001)
        self.assertEqual(decoded["target_count"], 1)
        self.assertEqual(len(decoded["targets"]), 1)
        t0 = decoded["targets"][0]
        self.assertEqual(t0["target_batch_no"], 35)
        self.assertEqual(t0["target_id"], "target-35")
        self.assertAlmostEqual(t0["target_bearing_deg"], 12.3, places=1)
        self.assertAlmostEqual(t0["target_distance_m"], 1500.0, places=1)
        self.assertEqual(t0["target_type_code"], 106)
        self.assertEqual(t0["military_civil_attr"], 1)
        self.assertEqual(t0["threat_level"], 3)
        self.assertEqual(t0["target_name"], "TARGET-A")
        self.assertEqual(t0["target_generated_timestamp_raw"], 123456)
        self.assertTrue((t0.get("target_generated_timestamp") or "").endswith("Z"))

    def test_decode_target_perception_doc_format_u16_target_type(self):
        name = "TARGET-B".encode("gb2312")
        name = name + b"\x00" * (40 - len(name))
        # target_type_code encoded as uint16 (compat mode)
        entry = struct.pack(
            ">HHIHHHHHiiHBBIbHb40sHHHbHH",
            36,                      # batch_no
            220,                     # bearing 22.0 deg
            1800,                    # distance
            0,                       # height
            55,                      # abs speed 5.5 m/s
            1000,                    # abs heading 100.0 deg
            10,                      # rel speed
            20,                      # rel heading
            int(121.6 * 1e7),
            int(31.3 * 1e7),
            10,                      # qt
            0,                       # coord sys
            1,                       # simulated
            223344,                  # target ts
            3,                       # position attr
            400,                     # target type (u16)
            2,                       # military_civil_attr
            name,
            10, 20, 30,              # length/width/height
            2,                       # threat
            11,                      # rcs
            0,                       # custom2
        )
        body = _common_header() + struct.pack(">HH", 1, 2001) + entry

        decoded = decode_topic_payload(TARGET_PERCEPTION_TOPIC, body)
        self.assertEqual(decoded["target_count"], 1)
        t0 = decoded["targets"][0]
        self.assertEqual(t0["target_batch_no"], 36)
        self.assertEqual(t0["target_type_code"], 400)
        self.assertEqual(t0["military_civil_attr"], 2)
        self.assertEqual(t0["target_generated_timestamp_raw"], 223344)
        self.assertTrue((t0.get("target_generated_timestamp") or "").endswith("Z"))

    def test_decode_target_perception_doc_format_u16_target_type_case2(self):
        name = "TARGET-U16".encode("gb2312")
        name = name + b"\x00" * (40 - len(name))
        entry = struct.pack(
            ">HHIHHHHHiiHBBIbHb40sHHHbHH",
            88,                      # batch_no
            200,                     # bearing 20.0 deg
            2200,                    # distance
            0,                       # height
            60,                      # abs speed 6.0 m/s
            1800,                    # abs heading 180.0 deg
            0,                       # rel speed
            0,                       # rel heading
            int(121.7 * 1e7),
            int(31.25 * 1e7),
            12,                      # qt
            0,                       # coord sys
            1,                       # simulated
            1234500,                 # target ts raw
            3,                       # position attr
            400,                     # target type (u16)
            1,                       # military_civil_attr
            name,
            10, 20, 30,              # length/width/height
            2,                       # threat
            11,                      # rcs
            0,                       # custom2
        )
        body = _common_header() + struct.pack(">HH", 1, 2001) + entry
        decoded = decode_topic_payload(TARGET_PERCEPTION_TOPIC, body)
        self.assertEqual(decoded["target_count"], 1)
        t0 = decoded["targets"][0]
        self.assertEqual(t0["target_type_code"], 400)
        self.assertEqual(t0["target_generated_timestamp_raw"], 1234500)
        self.assertIsNotNone(t0["target_generated_timestamp"])

    def test_encode_task_update_21_plus_100(self):
        body = encode_topic_payload(
            TASK_UPDATE_TOPIC,
            {
                "protocol_type": 0,
                "protocol_version": 1,
                "msg_type": 9,
                "msg_seq": 123,
                "reserve": 0,
                "timestamp_0p1ms": 456789,
                "task_id": "task-001",
                "task_type": 2,
                "task_status": 3,
                "execution_phase": 5,
                "update_type": 2,
                "result_type": 2,
                "current_target_batch_no": 101,
                "rel_range_m": 2300,
                "relative_bearing_deg_x10": 1234,
                "expected_speed_x10": 88,
                "waypoint_count": 6,
                "finish_reason": 4,
            },
        )

        self.assertEqual(len(body), 121)
        protocol_type, version, packet_len, msg_type, seq, reserve, ts_0p1ms = struct.unpack(">IBHBIBQ", body[:21])
        self.assertEqual(protocol_type, 0)
        self.assertEqual(version, 1)
        self.assertEqual(packet_len, 121)
        self.assertEqual(msg_type, 9)
        self.assertEqual(seq, 123)
        self.assertEqual(reserve, 0)
        self.assertEqual(ts_0p1ms, 456789)

        decoded = decode_topic_payload(TASK_UPDATE_TOPIC, body)
        self.assertEqual(decoded["task_id"], "task-001")
        self.assertEqual(decoded["task_type"], 2)
        self.assertEqual(decoded["task_status"], 3)
        self.assertEqual(decoded["execution_phase"], 5)
        self.assertEqual(decoded["update_type"], 2)
        self.assertEqual(decoded["result_type"], 2)
        self.assertEqual(decoded["current_target_batch_no"], 101)
        self.assertEqual(decoded["rel_range_m"], 2300)
        self.assertEqual(decoded["relative_bearing_deg_x10"], 1234)
        self.assertEqual(decoded["expected_speed_x10"], 88)
        self.assertEqual(decoded["waypoint_count"], 6)
        self.assertEqual(decoded["finish_reason"], 4)
        self.assertEqual(decoded["decode_format"], "task_update_21_plus_100_fields")


if __name__ == "__main__":
    unittest.main()
