#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"
TASK_ID="${TASK_ID:-task-tracking-demo-001}"

curl -sS -X POST "${BASE_URL}/api/v1/tasks/${TASK_ID}/terminate" \
  -H "Content-Type: application/json" \
  -d @- <<JSON
{
  "reason": "linux_demo cleanup"
}
JSON

echo
