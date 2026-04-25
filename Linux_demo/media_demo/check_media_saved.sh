#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

WAIT_TIMEOUT_SEC="${WAIT_TIMEOUT_SEC:-90}"
POLL_INTERVAL_SEC="${POLL_INTERVAL_SEC:-2}"
MEDIA_LOCAL_DIR="${MEDIA_LOCAL_DIR:-/app/media}"

find_latest_saved_entry() {
  local endpoint="$1"
  local response_json
  response_json="$(api_get "${endpoint}")"

  if command -v jq >/dev/null 2>&1; then
    echo "${response_json}" | jq -c --arg tid "${TASK_ID}" '
      [(.data.items // [])[] | select(.task_id == $tid and .saved_local == true)] | last // empty
    '
    return
  fi

  JSON_TEXT="${response_json}" run_python - "${TASK_ID}" <<'PY'
import json
import os
import sys

task_id = sys.argv[1]
try:
    data = json.loads(os.environ.get("JSON_TEXT", ""))
except Exception:
    print("")
    raise SystemExit(0)

items = (((data or {}).get("data") or {}).get("items") or [])
matched = [x for x in items if isinstance(x, dict) and x.get("task_id") == task_id and x.get("saved_local") is True]
if not matched:
    print("")
else:
    print(json.dumps(matched[-1], ensure_ascii=False))
PY
}

extract_file_path() {
  local entry_json="$1"
  if [[ -z "${entry_json}" ]]; then
    echo ""
    return
  fi
  extract_json_field "${entry_json}" ".file_path"
}

check_file_exists() {
  local reported_path="$1"
  if [[ -z "${reported_path}" ]]; then
    return 1
  fi

  if [[ -f "${reported_path}" ]]; then
    return 0
  fi

  if [[ -n "${MEDIA_LOCAL_DIR}" ]]; then
    local local_path="${MEDIA_LOCAL_DIR}/$(basename "${reported_path}")"
    if [[ -f "${local_path}" ]]; then
      return 0
    fi
  fi

  return 1
}

echo "=== wait media saved logs: ${TASK_ID} ==="

deadline_ts=$(( $(date +%s) + WAIT_TIMEOUT_SEC ))
photo_entry=""
video_entry=""

while [[ "$(date +%s)" -lt "${deadline_ts}" ]]; do
  photo_entry="$(find_latest_saved_entry "/mock/collaboration/media/photos")"
  video_entry="$(find_latest_saved_entry "/mock/collaboration/media/videos")"
  if [[ -n "${photo_entry}" && -n "${video_entry}" ]]; then
    break
  fi
  sleep "${POLL_INTERVAL_SEC}"
done

if [[ -z "${photo_entry}" ]]; then
  echo "[error] no saved photo log found for task=${TASK_ID}" >&2
  exit 1
fi

if [[ -z "${video_entry}" ]]; then
  echo "[error] no saved video log found for task=${TASK_ID}" >&2
  exit 1
fi

photo_path="$(extract_file_path "${photo_entry}")"
video_path="$(extract_file_path "${video_entry}")"

echo "=== latest saved photo entry ==="
echo "${photo_entry}" | pretty_print
echo
echo "=== latest saved video entry ==="
echo "${video_entry}" | pretty_print
echo

if check_file_exists "${photo_path}"; then
  echo "[ok] photo file exists: ${photo_path}"
else
  echo "[warn] photo log says saved_local=true, but file not found from current shell." >&2
  echo "[warn] reported_path=${photo_path}, MEDIA_LOCAL_DIR=${MEDIA_LOCAL_DIR:-<empty>}" >&2
fi

if check_file_exists "${video_path}"; then
  echo "[ok] video file exists: ${video_path}"
else
  echo "[warn] video log says saved_local=true, but file not found from current shell." >&2
  echo "[warn] reported_path=${video_path}, MEDIA_LOCAL_DIR=${MEDIA_LOCAL_DIR:-<empty>}" >&2
fi

echo
echo "[ok] media capture logs indicate success for both photo and video"
