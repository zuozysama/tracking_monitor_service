#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

RECOMMENDED_TIMEOUT_SEC="${RECOMMENDED_TIMEOUT_SEC:-30}"
POLL_INTERVAL_SEC="${POLL_INTERVAL_SEC:-1}"
ARRIVAL_CYCLES="${ARRIVAL_CYCLES:-4}"
ARRIVAL_INTERVAL_SEC="${ARRIVAL_INTERVAL_SEC:-1.2}"
NAV_PLATFORM_ID="${NAV_PLATFORM_ID:-1001}"

echo "=== wait recommended point: ${TASK_ID} ==="

deadline_ts=$(( $(date +%s) + RECOMMENDED_TIMEOUT_SEC ))
longitude=""
latitude=""

while [[ "$(date +%s)" -lt "${deadline_ts}" ]]; do
  result_json="$(api_get "/api/v1/tasks/${TASK_ID}/result")"
  longitude="$(extract_json_field "${result_json}" '.data.recommended_point.longitude')"
  latitude="$(extract_json_field "${result_json}" '.data.recommended_point.latitude')"
  if [[ -n "${longitude}" && -n "${latitude}" ]]; then
    break
  fi
  sleep "${POLL_INTERVAL_SEC}"
done

if [[ -z "${longitude}" || -z "${latitude}" ]]; then
  echo "[error] recommended_point not ready within ${RECOMMENDED_TIMEOUT_SEC}s" >&2
  exit 1
fi

echo "[info] recommended_point: longitude=${longitude}, latitude=${latitude}"

for ((i=1; i<=ARRIVAL_CYCLES; i++)); do
  now_ts="$(now_utc)"
  echo "[info] post navigation at recommended point, cycle=${i}/${ARRIVAL_CYCLES}"
  api_post_json "/mock/dds/navigation" "$(cat <<JSON
{
  "platform_id": ${NAV_PLATFORM_ID},
  "speed_mps": 12.0,
  "heading_deg": 90.0,
  "longitude": ${longitude},
  "latitude": ${latitude},
  "timestamp": "${now_ts}"
}
JSON
)" >/dev/null
  sleep "${ARRIVAL_INTERVAL_SEC}"
done

echo "[info] arrival simulation completed"

