#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://0.0.0.0:80}"
NOW_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

curl -sS -X POST "${BASE_URL}/mock/dds/perception" \
  -H "Content-Type: application/json" \
  -d @- <<JSON
{
  "target_count": 1,
  "targets": [
    {
      "source_platform_id": 2001,
      "target_id": "target-001",
      "target_batch_no": 1,
      "target_bearing_deg": 35.0,
      "target_distance_m": 3000,
      "target_absolute_speed_mps": 6.2,
      "target_absolute_heading_deg": 90.0,
      "target_longitude": 121.5030000,
      "target_latitude": 31.2200000,
      "target_type_code": 106,
      "military_civil_attr": 1,
      "target_name": "target-001",
      "threat_level": 2,
      "timestamp": "${NOW_UTC}",
      "active": true
    }
  ]
}
JSON

echo
