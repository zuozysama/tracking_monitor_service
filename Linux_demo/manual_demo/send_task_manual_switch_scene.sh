#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/common.sh"

TASK_ID="${TASK_ID:-manual-switch-scene-$(date +%s)}"
TASK_TYPE="${TASK_TYPE:-escort}"
DESIGNATED_TARGET_ID="${DESIGNATED_TARGET_ID:-target-001}"
EXPECTED_SPEED="${EXPECTED_SPEED:-12.0}"
DURATION_SEC="${DURATION_SEC:-300}"

PAYLOAD="$(cat <<EOF
{
  "task_id": "${TASK_ID}",
  "task_type": "${TASK_TYPE}",
  "task_name": "manual_switch_scene",
  "task_source": "linux_demo_manual",
  "priority": 1,
  "target_info": {
    "target_id": "${DESIGNATED_TARGET_ID}"
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
  "expected_speed": ${EXPECTED_SPEED},
  "update_interval_sec": 1,
  "end_condition": {
    "duration_sec": ${DURATION_SEC},
    "out_of_region_finish": false
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
EOF
)"

echo "[info] create manual_switch scene task: TASK_ID=${TASK_ID}, DESIGNATED_TARGET_ID=${DESIGNATED_TARGET_ID}"
api_post_json "/api/v1/tasks" "${PAYLOAD}" | pretty_print
echo

