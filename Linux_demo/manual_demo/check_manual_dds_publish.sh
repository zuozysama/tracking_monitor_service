#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/common.sh"

TOPIC="${TOPIC:-}"
LIMIT="${LIMIT:-50}"

echo "[info] BASE_URL=${BASE_URL}"
echo "[info] TOPIC=${TOPIC:-<all>}"
echo "[info] LIMIT=${LIMIT}"

RAW_JSON="$(api_get "/mock/collaboration/dds/publish-logs")"

if command -v jq >/dev/null 2>&1; then
  echo "${RAW_JSON}" | jq \
    --arg topic "${TOPIC}" \
    --argjson limit "${LIMIT}" \
    '
    .data.items
    | (if $topic == "" then . else map(select(.topic == $topic)) end)
    | (if ($limit > 0) then .[-$limit:] else . end)
    | map({
        publish_time,
        topic,
        adapter,
        wire_length,
        task_id: (.payload.task_id // null),
        request_type: (.payload.request_type // null),
        current_target_id: (.payload.current_target_id // null),
        candidate_targets: (.payload.candidate_targets // null),
        new_candidate_targets: (.payload.new_candidate_targets // null)
      })
    '
else
  echo "${RAW_JSON}"
fi
echo

echo "[info] dds debug status:"
api_get "/mock/collaboration/dds/debug-status" | pretty_print
echo

