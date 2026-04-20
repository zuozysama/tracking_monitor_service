#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://0.0.0.0:80}"
TASK_ID="${TASK_ID:-${1:-}}"
INCLUDE_RESULT="${INCLUDE_RESULT:-false}"

if [[ -z "${TASK_ID}" ]]; then
  echo "Usage: TASK_ID=<task-id> bash Linux_demo/task/query_task_status_output.sh"
  echo "   or:  bash Linux_demo/task/query_task_status_output.sh <task-id>"
  exit 1
fi

pretty_print() {
  if command -v jq >/dev/null 2>&1; then
    jq .
  else
    cat
  fi
}

echo "=== TASK STATUS (${TASK_ID}) ==="
curl -sS "${BASE_URL}/api/v1/${TASK_ID}/status" | pretty_print
echo

echo "=== TASK OUTPUT (${TASK_ID}) ==="
curl -sS "${BASE_URL}/api/v1/${TASK_ID}/output" | pretty_print
echo

if [[ "${INCLUDE_RESULT}" == "true" ]]; then
  echo "=== TASK RESULT (${TASK_ID}) ==="
  curl -sS "${BASE_URL}/api/v1/${TASK_ID}/result" | pretty_print
  echo
fi
