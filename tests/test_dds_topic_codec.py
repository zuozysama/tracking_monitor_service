import struct
import unittest

from adapters.dds.topic_codec import decode_topic_payload
from domain.dds_contract import OWNSHIP_NAVIGATION_TOPIC, TARGET_PERCEPTION_TOPIC


def _common_header(ts_sec: int = 1700000000, ts_sub_ms_x1e6: int = 500000000) -> bytes:
    return struct.pack(
        "<IBHBIBII",
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
    def test_decode_ownship_doc_format(self):
        nav_payload = struct.pack(
            "<HHHhhhHiihhhhhhhh",
            2001,        # platform_id
            1234,        # speed 12.34 m/s
            9050,        # heading 90.50 deg
            10,          # vx
            -2,          # vy
            0,           # vz
            9000,        # bow_heading
            int(121.5123456 * 1e7),
            int(31.2234567 * 1e7),
            0,           # angular vel
            1, 1, 1,     # ax/ay/az
            0,           # angular acc
            0, 0, 0,     # roll/pitch/heave
        )
        body = _common_header() + nav_payload

        decoded = decode_topic_payload(OWNSHIP_NAVIGATION_TOPIC, body)
        self.assertEqual(decoded["platform_id"], 2001)
        self.assertAlmostEqual(decoded["speed_mps"], 12.34, places=2)
        self.assertAlmostEqual(decoded["heading_deg"], 90.5, places=2)
        self.assertAlmostEqual(decoded["longitude"], 121.5123456, places=7)
        self.assertAlmostEqual(decoded["latitude"], 31.2234567, places=7)
        self.assertTrue(str(decoded["timestamp"]).endswith("Z"))

    def test_decode_target_perception_doc_format(self):
        name = "TARGET-A".encode("gb2312")
        name = name + b"\x00" * (40 - len(name))
        entry = struct.pack(
            "<HHIHHHHHiiHBBIbbb40sHHHbHH",
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
        body = _common_header() + struct.pack("<HH", 1, 2001) + entry

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

    def test_decode_ownship_compact_backward_compatible(self):
        compact = struct.pack(
            "<HHHii8s",
            2002,
            1000,  # 10.00 m/s
            900,   # 90.0 deg (old compact uses x10)
            int(121.6 * 1e7),
            int(31.1 * 1e7),
            b"\x00" * 8,
        )
        decoded = decode_topic_payload(OWNSHIP_NAVIGATION_TOPIC, compact)
        self.assertEqual(decoded["platform_id"], 2002)
        self.assertAlmostEqual(decoded["speed_mps"], 10.0, places=2)
        self.assertAlmostEqual(decoded["heading_deg"], 90.0, places=1)


if __name__ == "__main__":
    unittest.main()
