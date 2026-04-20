#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
TOPIC="${TOPIC:-}"
LIMIT="${LIMIT:-20}"

URL="${BASE_URL}/mock/collaboration/dds/publish-logs"

echo "[info] request: ${URL}"
if [[ -n "${TOPIC}" ]]; then
  echo "[info] topic filter: ${TOPIC}"
fi
echo "[info] limit: ${LIMIT}"

RAW_JSON="$(curl -sS "${URL}")"

if command -v jq >/dev/null 2>&1; then
  echo "[info] jq detected, output filtered logs"
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
        raw_hex,
        body_hex,
        task_id: (.payload.task_id // null),
        task_type: (.payload.task_type // null),
        task_status: (.payload.task_status // null),
        execution_phase: (.payload.execution_phase // null),
        update_type: (.payload.update_type // null),
        result_type: (.payload.result_type // null),
        finish_reason: (.payload.finish_reason // null),
        payload
      })
    '
else
  echo "[warn] jq not found, fallback to raw JSON output"
  echo "${RAW_JSON}"
fi
