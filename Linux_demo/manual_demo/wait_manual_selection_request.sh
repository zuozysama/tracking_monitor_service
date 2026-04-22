#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/common.sh"

require_jq

TASK_ID="${TASK_ID:-${1:-}}"
TIMEOUT_SEC="${TIMEOUT_SEC:-30}"
POLL_INTERVAL_SEC="${POLL_INTERVAL_SEC:-1}"

if [[ -z "${TASK_ID}" ]]; then
  echo "Usage: TASK_ID=<task-id> bash Linux_demo/manual_demo/wait_manual_selection_request.sh"
  echo "   or:  bash Linux_demo/manual_demo/wait_manual_selection_request.sh <task-id>"
  exit 1
fi

echo "[wait] manual selection request for task=${TASK_ID}, timeout=${TIMEOUT_SEC}s"
deadline=$((SECONDS + TIMEOUT_SEC))
while (( SECONDS < deadline )); do
  raw="$(api_get "/mock/collaboration/manual-selection/requests")"
  count="$(echo "${raw}" | jq -r --arg tid "${TASK_ID}" '.data.items | map(select(.task_id == $tid)) | length')"
  if [[ "${count}" =~ ^[0-9]+$ ]] && (( count > 0 )); then
    echo "[ok] manual selection request arrived"
    echo "${raw}" | jq -r --arg tid "${TASK_ID}" '.data.items | map(select(.task_id == $tid)) | .[-1]'
    exit 0
  fi
  sleep "${POLL_INTERVAL_SEC}"
done

echo "[error] timeout waiting manual selection request for task=${TASK_ID}" >&2
exit 1

