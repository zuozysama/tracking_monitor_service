#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

TASK_ID="${TASK_ID:-}"
EXPECTED_SAVE_DIR="${EXPECTED_SAVE_DIR:-/app/media}"
WAIT_TIMEOUT_SEC="${WAIT_TIMEOUT_SEC:-120}"
POLL_INTERVAL_SEC="${POLL_INTERVAL_SEC:-2}"
VERIFY_FILE_EXISTS="${VERIFY_FILE_EXISTS:-false}"
MEDIA_LOCAL_DIR="${MEDIA_LOCAL_DIR:-}"
FAIL_FAST_ON_ERROR="${FAIL_FAST_ON_ERROR:-true}"

usage() {
  echo "Usage:"
  echo "  TASK_ID=<task-id> [BASE_URL=http://0.0.0.0:80] bash Linux_demo/media_demo/check_video_only_debug.sh"
  echo
  echo "Optional env:"
  echo "  EXPECTED_SAVE_DIR=/app/media"
  echo "  WAIT_TIMEOUT_SEC=120"
  echo "  POLL_INTERVAL_SEC=2"
  echo "  FAIL_FAST_ON_ERROR=true|false"
  echo "  VERIFY_FILE_EXISTS=true|false"
  echo "  MEDIA_LOCAL_DIR=./artifacts/media"
}

if [[ -z "${TASK_ID}" ]]; then
  echo "[error] TASK_ID is required." >&2
  usage
  exit 1
fi

print_debug_bundle() {
  echo
  echo "=== DEBUG: task status ==="
  api_get "/api/v1/${TASK_ID}/status" | pretty_print || true
  echo
  echo "=== DEBUG: task result ==="
  api_get "/api/v1/tasks/${TASK_ID}/result" | pretty_print || true
  echo
  echo "=== DEBUG: video logs (task filtered if jq exists) ==="
  local videos_json
  videos_json="$(api_get "/mock/collaboration/media/videos" || true)"
  if command -v jq >/dev/null 2>&1; then
    echo "${videos_json}" | jq --arg tid "${TASK_ID}" '
      .data.items = ((.data.items // []) | map(select(.task_id == $tid)));
      .data.items = (.data.items[-10:] // .data.items)
    ' || echo "${videos_json}"
  else
    echo "${videos_json}" | pretty_print
  fi
  echo
  echo "=== DEBUG: recent dds publish logs ==="
  local dds_json
  dds_json="$(api_get "/mock/collaboration/dds/publish-logs" || true)"
  if command -v jq >/dev/null 2>&1; then
    echo "${dds_json}" | jq '.data.items = (.data.items[-20:] // .data.items)' || echo "${dds_json}"
  else
    echo "${dds_json}" | pretty_print
  fi
  echo
}

latest_video_entry_for_task() {
  local videos_json="$1"
  if command -v jq >/dev/null 2>&1; then
    echo "${videos_json}" | jq -c --arg tid "${TASK_ID}" '
      [(.data.items // [])[] | select(.task_id == $tid)] | last // empty
    '
    return
  fi

  JSON_TEXT="${videos_json}" run_python - "${TASK_ID}" <<'PY'
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
task_items = [x for x in items if isinstance(x, dict) and x.get("task_id") == task_id]
if not task_items:
    print("")
else:
    print(json.dumps(task_items[-1], ensure_ascii=False))
PY
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
    local local_path="${MEDIA_LOCAL_DIR%/}/${TASK_ID}/$(basename "${reported_path}")"
    if [[ -f "${local_path}" ]]; then
      return 0
    fi
  fi

  return 1
}

echo "=== check video-only processing with debug ==="
echo "[info] BASE_URL=${BASE_URL}"
echo "[info] TASK_ID=${TASK_ID}"
echo "[info] EXPECTED_SAVE_DIR=${EXPECTED_SAVE_DIR}"
echo "[info] WAIT_TIMEOUT_SEC=${WAIT_TIMEOUT_SEC}, POLL_INTERVAL_SEC=${POLL_INTERVAL_SEC}"
echo "[info] FAIL_FAST_ON_ERROR=${FAIL_FAST_ON_ERROR}, VERIFY_FILE_EXISTS=${VERIFY_FILE_EXISTS}"

deadline_ts=$(( $(date +%s) + WAIT_TIMEOUT_SEC ))
last_entry=""

while [[ "$(date +%s)" -lt "${deadline_ts}" ]]; do
  videos_json="$(api_get "/mock/collaboration/media/videos")"
  entry="$(latest_video_entry_for_task "${videos_json}")"

  if [[ -n "${entry}" ]]; then
    if [[ "${entry}" != "${last_entry}" ]]; then
      echo "[info] latest video entry updated:"
      echo "${entry}" | pretty_print
      last_entry="${entry}"
    fi

    saved_local="$(extract_json_field "${entry}" ".saved_local" | tr '[:upper:]' '[:lower:]')"
    success="$(extract_json_field "${entry}" ".success" | tr '[:upper:]' '[:lower:]')"
    reason="$(extract_json_field "${entry}" ".reason")"
    error_msg="$(extract_json_field "${entry}" ".error")"
    video_path="$(extract_json_field "${entry}" ".file_path")"

    if [[ "${saved_local}" == "true" ]]; then
      expected_prefix="${EXPECTED_SAVE_DIR%/}/${TASK_ID}/"
      if [[ "${video_path}" != ${expected_prefix}* ]]; then
        echo "[error] saved path mismatch." >&2
        echo "[error] expected prefix: ${expected_prefix}" >&2
        echo "[error] actual path: ${video_path}" >&2
        print_debug_bundle
        exit 1
      fi

      if [[ "${VERIFY_FILE_EXISTS}" == "true" ]]; then
        if check_file_exists "${video_path}"; then
          echo "[ok] file exists for saved video."
        else
          echo "[error] saved_local=true but file not found from current shell." >&2
          echo "[error] reported path: ${video_path}" >&2
          echo "[error] MEDIA_LOCAL_DIR=${MEDIA_LOCAL_DIR:-<empty>}" >&2
          print_debug_bundle
          exit 1
        fi
      fi

      echo "[ok] video processing succeeded for task=${TASK_ID}"
      echo "[ok] saved path: ${video_path}"
      exit 0
    fi

    if [[ "${FAIL_FAST_ON_ERROR}" == "true" ]]; then
      if [[ "${success}" == "false" || -n "${reason}" || -n "${error_msg}" ]]; then
        echo "[error] video processing reported failure for task=${TASK_ID}" >&2
        echo "[error] reason=${reason:-<empty>}" >&2
        echo "[error] error=${error_msg:-<empty>}" >&2
        print_debug_bundle
        exit 1
      fi
    fi
  fi

  sleep "${POLL_INTERVAL_SEC}"
done

echo "[error] timeout waiting successful video capture log for task=${TASK_ID}" >&2
if [[ -n "${last_entry}" ]]; then
  echo "[error] last task video entry:"
  echo "${last_entry}" | pretty_print
fi
print_debug_bundle
exit 1

