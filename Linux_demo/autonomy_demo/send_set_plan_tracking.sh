#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=Linux_demo/set_plan_common.sh
source "${SCRIPT_DIR}/set_plan_common.sh"

resolve_set_plan_url
print_set_plan_target

TASK_ID="${TASK_ID:-1001}"
build_task_id_json "${TASK_ID}"
TARGET_ID="${TARGET_ID:-target-001}"
TARGET_BATCH_NO="${TARGET_BATCH_NO:-1}"
REL_RANGE_M="${REL_RANGE_M:-500.0}"
RELATIVE_BEARING_DEG="${RELATIVE_BEARING_DEG:-35.0}"
MAX_SPEED="${MAX_SPEED:-12.0}"

curl -sS -X POST "${SET_PLAN_URL}" \
  -H "Content-Type: application/json" \
  -d @- <<JSON
{
  "task_id": ${TASK_ID_JSON},
  "task_status": 1,
  "task_mode": 3,
  "params": {
    "target_id": "${TARGET_ID}",
    "target_batch_no": ${TARGET_BATCH_NO},
    "rel_range_m": ${REL_RANGE_M},
    "relative_bearing_deg": ${RELATIVE_BEARING_DEG},
    "max_speed": ${MAX_SPEED}
  }
}
JSON

echo
