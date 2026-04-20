#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://0.0.0.0:80}"
TASK_ID="${TASK_ID:-escort-1}"

curl -sS -X POST "${BASE_URL}/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -d @- <<JSON
{
  "task_id": "${TASK_ID}",
  "task_type": "escort",
  "task_name": "escort-demo",
  "task_source": "linux_demo",
  "priority": 1,
  "target_info": {
    "target_id": "target-001",
    "target_batch_no": 1,
    "target_type_code": 106,
    "threat_level": 2,
    "target_name": "target-001",
    "military_civil_attr": 1
  },
  "task_area": {
    "area_type": "polygon",
    "points": [
      { "longitude": 124.20, "latitude": 21.53 },
      { "longitude": 124.79, "latitude": 21.53 },
      { "longitude": 124.20, "latitude": 21.30 },
      { "longitude": 124.79, "latitude": 21.30 }
    ]
  },
  "expected_speed": 12.0,
  "update_interval_sec": 1,
  "end_condition": {
    "duration_sec": 300,
    "out_of_region_finish": true
  },
  "stream_media_param": {
    "photo_enabled": false,
    "video_enabled": false
  },
  "linkage_param": {
    "enable_optical": false,
    "enable_evidence": false
  }
}
JSON

echo
