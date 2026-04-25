#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

PHOTO_INTERVAL_SEC="${PHOTO_INTERVAL_SEC:-3}"
VIDEO_INTERVAL_SEC="${VIDEO_INTERVAL_SEC:-6}"
VIDEO_DURATION_SEC="${VIDEO_DURATION_SEC:-4}"

echo "=== create media tracking task: ${TASK_ID} ==="

api_post_json "/api/v1/tasks" "$(cat <<JSON
{
  "task_id": "${TASK_ID}",
  "task_type": "escort",
  "task_name": "media-demo-tracking-task",
  "task_source": "linux_demo_media",
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
    "photo_enabled": true,
    "photo_interval_sec": ${PHOTO_INTERVAL_SEC},
    "video_enabled": true,
    "video_interval_sec": ${VIDEO_INTERVAL_SEC},
    "video_duration_sec": ${VIDEO_DURATION_SEC}
  },
  "linkage_param": {
    "enable_optical": true,
    "enable_evidence": true
  }
}
JSON
)" | pretty_print

echo

