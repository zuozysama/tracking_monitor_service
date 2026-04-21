#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=Linux_demo/set_plan_common.sh
source "${SCRIPT_DIR}/set_plan_common.sh"

resolve_set_plan_url
print_set_plan_target

TASK_ID="${TASK_ID:-1001}"
build_task_id_json "${TASK_ID}"
MAX_SPEED="${MAX_SPEED:-8.0}"

curl -sS -X POST "${SET_PLAN_URL}" \
  -H "Content-Type: application/json" \
  -d @- <<JSON
{
  "task_id": ${TASK_ID_JSON},
  "task_status": 1,
  "task_mode": 3,
  "params": {
    "target_id": null,
    "target_batch_no": null,
    "rel_range_m": 0.0,
    "relative_bearing_deg": 0.0,
    "max_speed": ${MAX_SPEED}
  }
}
JSON

echo
