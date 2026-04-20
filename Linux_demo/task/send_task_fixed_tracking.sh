#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://0.0.0.0:80}"
TASK_ID="${TASK_ID:-fixed-1}"

curl -sS -X POST "${BASE_URL}/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -d @- <<JSON
{
  "task_id": "${TASK_ID}",
  "task_type": "fixed_tracking",
  "task_name": "fixed-tracking-demo",
  "task_source": "linux_demo",
  "priority": 1,
  "task_area": {
    "area_type": "point",
    "points": [
      { "longitude": 124.20, "latitude": 21.53 }
    ]
  },
  "expected_speed": 6.0,
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
