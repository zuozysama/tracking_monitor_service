#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/common.sh"

TASK_ID="${TASK_ID:-${1:-}}"
SELECTED_TARGET_ID="${SELECTED_TARGET_ID:-${2:-}}"
FEEDBACK_TIME="${FEEDBACK_TIME:-$(now_utc)}"

if [[ -z "${TASK_ID}" ]]; then
  echo "Usage: TASK_ID=<task-id> [SELECTED_TARGET_ID=<target-id>] bash Linux_demo/manual_demo/send_manual_selection_feedback.sh"
  echo "   or:  bash Linux_demo/manual_demo/send_manual_selection_feedback.sh <task-id> [selected-target-id]"
  exit 1
fi

if [[ -z "${SELECTED_TARGET_ID}" ]]; then
  raw_req="$(api_get "/mock/collaboration/manual-selection/requests")"
  if command -v jq >/dev/null 2>&1; then
    SELECTED_TARGET_ID="$(
      echo "${raw_req}" \
        | jq -r --arg tid "${TASK_ID}" '.data.items | map(select(.task_id == $tid)) | .[-1].candidate_targets[0].target_id // empty'
    )"
  else
    SELECTED_TARGET_ID="$(
      run_python - "${TASK_ID}" "${raw_req}" <<'PY'
import json
import sys

task_id = sys.argv[1]
raw_json = sys.argv[2]

try:
    payload = json.loads(raw_json)
except Exception:
    print("")
    raise SystemExit(0)

items = ((payload or {}).get("data") or {}).get("items") or []
selected = ""
for item in items:
    if item.get("task_id") != task_id:
        continue
    candidates = item.get("candidate_targets") or []
    if not candidates:
        continue
    target_id = (candidates[0] or {}).get("target_id") or ""
    if target_id:
        selected = target_id

print(selected)
PY
    )"
  fi
fi

if [[ -z "${SELECTED_TARGET_ID}" ]]; then
  echo "[error] SELECTED_TARGET_ID is required (or ensure manual-selection request exists with candidate_targets)." >&2
  echo "[hint] install jq, or pass SELECTED_TARGET_ID explicitly." >&2
  exit 1
fi

payload="$(cat <<EOF
{
  "task_id": "${TASK_ID}",
  "selected_target_id": "${SELECTED_TARGET_ID}",
  "feedback_time": "${FEEDBACK_TIME}"
}
EOF
)"

echo "[info] send manual_selection feedback: task_id=${TASK_ID}, selected_target_id=${SELECTED_TARGET_ID}"
echo "[info] feedback_time=${FEEDBACK_TIME}"
api_post_json "/api/v1/manual_selection/feedback" "${payload}" | pretty_print
echo
