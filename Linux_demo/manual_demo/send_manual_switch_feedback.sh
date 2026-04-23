#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/common.sh"

require_jq

TASK_ID="${TASK_ID:-${1:-}}"
SELECTED_TARGET_ID="${SELECTED_TARGET_ID:-${2:-}}"
KEEP_CURRENT_RAW="${KEEP_CURRENT:-false}"
FEEDBACK_TIME="${FEEDBACK_TIME:-$(now_utc)}"

if [[ -z "${TASK_ID}" ]]; then
  echo "Usage: TASK_ID=<task-id> [KEEP_CURRENT=true|false] [SELECTED_TARGET_ID=<target-id>] bash Linux_demo/manual_demo/send_manual_switch_feedback.sh"
  echo "   or:  bash Linux_demo/manual_demo/send_manual_switch_feedback.sh <task-id> [selected-target-id]"
  exit 1
fi

KEEP_CURRENT="$(echo "${KEEP_CURRENT_RAW}" | tr '[:upper:]' '[:lower:]')"
case "${KEEP_CURRENT}" in
  true|false) ;;
  *)
    echo "[error] KEEP_CURRENT must be true or false." >&2
    exit 1
    ;;
esac

if [[ "${KEEP_CURRENT}" == "false" && -z "${SELECTED_TARGET_ID}" ]]; then
  raw_req="$(api_get "/mock/collaboration/manual-switch/requests")"
  SELECTED_TARGET_ID="$(
    echo "${raw_req}" \
      | jq -r --arg tid "${TASK_ID}" '.data.items | map(select(.task_id == $tid)) | .[-1].new_candidate_targets[0].target_id // empty'
  )"
fi

if [[ "${KEEP_CURRENT}" == "false" && -z "${SELECTED_TARGET_ID}" ]]; then
  echo "[error] SELECTED_TARGET_ID is required when KEEP_CURRENT=false (or ensure manual-switch request exists with new_candidate_targets)." >&2
  exit 1
fi

payload="$(
  jq -n \
    --arg task_id "${TASK_ID}" \
    --arg selected_target_id "${SELECTED_TARGET_ID}" \
    --argjson keep_current "${KEEP_CURRENT}" \
    --arg feedback_time "${FEEDBACK_TIME}" \
    '{
      task_id: $task_id,
      selected_target_id: (if $selected_target_id == "" then null else $selected_target_id end),
      keep_current: $keep_current,
      feedback_time: $feedback_time
    }'
)"

echo "[info] send manual_switch feedback: task_id=${TASK_ID}, keep_current=${KEEP_CURRENT}, selected_target_id=${SELECTED_TARGET_ID:-null}"
echo "[info] feedback_time=${FEEDBACK_TIME}"
api_post_json "/api/v1/manual_switch/feedback" "${payload}" | pretty_print
echo
