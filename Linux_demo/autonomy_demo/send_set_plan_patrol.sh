#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=Linux_demo/set_plan_common.sh
source "${SCRIPT_DIR}/set_plan_common.sh"

resolve_set_plan_url
print_set_plan_target

TASK_ID="${TASK_ID:-1001}"
build_task_id_json "${TASK_ID}"
MAX_SPEED="${MAX_SPEED:-12.0}"
END_TIME="${END_TIME:-$(date -u -d '+30 minutes' +'%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u +'%Y-%m-%dT%H:%M:%SZ')}"

curl -sS -X POST "${SET_PLAN_URL}" \
  -H "Content-Type: application/json" \
  -d @- <<JSON
{
  "task_id": ${TASK_ID_JSON},
  "task_status": 0,
  "task_mode": 1,
  "params": {
    "total_number_of_points": 4,
    "waypoints": [
      { "longitude": 121.5000000, "latitude": 31.2200000, "speed": ${MAX_SPEED} },
      { "longitude": 121.5200000, "latitude": 31.2250000, "speed": ${MAX_SPEED} },
      { "longitude": 121.5400000, "latitude": 31.2200000, "speed": ${MAX_SPEED} },
      { "longitude": 121.5200000, "latitude": 31.2100000, "speed": ${MAX_SPEED} }
    ],
    "max_speed": ${MAX_SPEED},
    "end_time": "${END_TIME}"
  }
}
JSON

echo
