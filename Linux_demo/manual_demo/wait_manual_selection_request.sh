#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/common.sh"

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
  if command -v jq >/dev/null 2>&1; then
    count="$(echo "${raw}" | jq -r --arg tid "${TASK_ID}" '.data.items | map(select(.task_id == $tid)) | length')"
    latest="$(
      echo "${raw}" | jq -c --arg tid "${TASK_ID}" '.data.items | map(select(.task_id == $tid)) | .[-1] // empty'
    )"
  else
    parsed="$(
      run_python - "${TASK_ID}" "${raw}" <<'PY'
import json
import sys

task_id = sys.argv[1]
raw_json = sys.argv[2]

try:
    payload = json.loads(raw_json)
except Exception:
    print("0")
    print("")
    raise SystemExit(0)

items = ((payload or {}).get("data") or {}).get("items") or []
matches = [item for item in items if item.get("task_id") == task_id]

print(len(matches))
if matches:
    print(json.dumps(matches[-1], ensure_ascii=False))
else:
    print("")
PY
    )"
    count="$(printf '%s\n' "${parsed}" | sed -n '1p')"
    latest="$(printf '%s\n' "${parsed}" | sed -n '2p')"
  fi
  if [[ "${count}" =~ ^[0-9]+$ ]] && (( count > 0 )); then
    echo "[ok] manual selection request arrived"
    if command -v jq >/dev/null 2>&1; then
      printf '%s\n' "${latest}" | jq -r '.'
    else
      printf '%s\n' "${latest}" | run_python -m json.tool
    fi
    exit 0
  fi
  sleep "${POLL_INTERVAL_SEC}"
done

echo "[error] timeout waiting manual selection request for task=${TASK_ID}" >&2
exit 1
