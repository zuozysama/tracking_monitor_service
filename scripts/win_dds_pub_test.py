import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapters.dds import get_dds_adapter
from domain.dds_contract import OWNSHIP_NAVIGATION_TOPIC, TARGET_PERCEPTION_TOPIC


def main() -> None:
    dds = get_dds_adapter()

    dds.publish(
        OWNSHIP_NAVIGATION_TOPIC,
        {
            "platform_id": 1001,
            "speed_mps": 6.2,
            "heading_deg": 90.0,
            "longitude": 121.5001,
            "latitude": 31.2201,
        },
    )

    dds.publish(
        TARGET_PERCEPTION_TOPIC,
        {
            "source_platform_id": 2001,
            "targets": [
                {
                    "target_id": "target-001",
                    "target_batch_no": 1,
                    "target_bearing_deg": 35.0,
                    "target_distance_m": 3000,
                    "target_absolute_speed_mps": 6.2,
                    "target_absolute_heading_deg": 90.0,
                    "target_longitude": 121.5030,
                    "target_latitude": 31.2200,
                    "target_type_code": 106,
                    "military_civil_attr": 1,
                    "threat_level": 2,
                }
            ],
        },
    )

    print("publish done")


if __name__ == "__main__":
    main()
