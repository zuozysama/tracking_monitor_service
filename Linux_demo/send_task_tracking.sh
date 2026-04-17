#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://0.0.0.0:80}"
TASK_ID="${TASK_ID:-task-tracking-demo-001}"

curl -sS -X POST "${BASE_URL}/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -d @- <<JSON
{
  "task_id": "${TASK_ID}",
  "task_type": "escort",
  "task_name": "tracking-http-style-demo",
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
      { "longitude": 121.49, "latitude": 31.21 },
      { "longitude": 121.52, "latitude": 31.21 },
      { "longitude": 121.52, "latitude": 31.23 },
      { "longitude": 121.49, "latitude": 31.23 }
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
