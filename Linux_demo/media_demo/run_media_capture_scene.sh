#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

TASK_ID="${TASK_ID:-task-media-demo-001}"
TERMINATE_AFTER="${TERMINATE_AFTER:-false}"

export TASK_ID

echo "=== media demo scene start: task=${TASK_ID} ==="
echo "[info] BASE_URL=${BASE_URL:-http://0.0.0.0:80}"
echo "[info] MEDIA_LOCAL_DIR=${MEDIA_LOCAL_DIR:-<empty>}"

"${ROOT_DIR}/send_mock_navigation.sh"
"${ROOT_DIR}/send_mock_perception.sh"
"${SCRIPT_DIR}/send_task_media_tracking.sh"
"${SCRIPT_DIR}/drive_to_recommended_point.sh"
"${SCRIPT_DIR}/check_media_saved.sh"

if [[ "${TERMINATE_AFTER}" == "true" ]]; then
  echo "[info] terminate task: ${TASK_ID}"
  curl -sS -X POST "${BASE_URL:-http://0.0.0.0:80}/api/v1/tasks/${TASK_ID}/terminate" \
    -H "Content-Type: application/json" \
    -d '{"reason":"media_demo_cleanup"}' >/dev/null
fi

echo "=== media demo scene done ==="

