#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/common.sh"

TASK_ID="${TASK_ID:-task-video-debug-$(date +%s)}"
EXPECTED_SAVE_DIR="${EXPECTED_SAVE_DIR:-/app/media}"
VIDEO_INTERVAL_SEC="${VIDEO_INTERVAL_SEC:-6}"
VIDEO_DURATION_SEC="${VIDEO_DURATION_SEC:-4}"
WAIT_TIMEOUT_SEC="${WAIT_TIMEOUT_SEC:-120}"
POLL_INTERVAL_SEC="${POLL_INTERVAL_SEC:-2}"

# Optional local dir for existence check on host side, e.g. ./artifacts/media
MEDIA_LOCAL_DIR="${MEDIA_LOCAL_DIR:-}"
VERIFY_FILE_EXISTS="${VERIFY_FILE_EXISTS:-false}"
ARRIVAL_CYCLES="${ARRIVAL_CYCLES:-4}"
ARRIVAL_INTERVAL_SEC="${ARRIVAL_INTERVAL_SEC:-1.2}"

export TASK_ID
export ARRIVAL_CYCLES
export ARRIVAL_INTERVAL_SEC

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

echo "=== test video capture with debug ==="
echo "[info] BASE_URL=${BASE_URL}"
echo "[info] TASK_ID=${TASK_ID}"
echo "[info] EXPECTED_SAVE_DIR=${EXPECTED_SAVE_DIR}"
echo "[info] VIDEO_INTERVAL_SEC=${VIDEO_INTERVAL_SEC}, VIDEO_DURATION_SEC=${VIDEO_DURATION_SEC}"

echo "[step] inject navigation and perception"
"${ROOT_DIR}/send_mock_navigation.sh" >/dev/null
"${ROOT_DIR}/send_mock_perception.sh" >/dev/null

echo "[step] create video-only task"
create_resp="$(api_post_json "/api/v1/tasks" "$(cat <<JSON
{
  "task_id": "${TASK_ID}",
  "task_type": "escort",
  "task_name": "video-debug-task",
  "task_source": "linux_demo_media",
  "priority": 1,
  "target_info": {
    "target_id": "target-001",
    "target_batch_no": 1,
    "target_type_code": 106,
    "threat_level": 2,
    "target_name": "target-001",
    "military_civil_attr": 1
  },
  "task_area": {
    "area_type": "polygon",
    "points": [
      { "longitude": 121.49, "latitude": 31.21 },
      { "longitude": 121.52, "latitude": 31.21 },
      { "longitude": 121.52, "latitude": 31.23 },
      { "longitude": 121.49, "latitude": 31.23 }
    ]
  },
  "expected_speed": 12.0,
  "update_interval_sec": 1,
  "end_condition": {
    "duration_sec": 300,
    "out_of_region_finish": true
  },
  "stream_media_param": {
    "photo_enabled": false,
    "video_enabled": true,
    "video_interval_sec": ${VIDEO_INTERVAL_SEC},
    "video_duration_sec": ${VIDEO_DURATION_SEC}
  },
  "linkage_param": {
    "enable_optical": true,
    "enable_evidence": true
  }
}
JSON
)")"
echo "${create_resp}" | pretty_print

create_code="$(extract_json_field "${create_resp}" ".code")"
if [[ "${create_code}" != "200" ]]; then
  echo "[error] create task failed, code=${create_code}" >&2
  print_debug_bundle
  exit 1
fi

echo "[step] simulate arrival to recommended point"
if ! "${SCRIPT_DIR}/drive_to_recommended_point.sh"; then
  echo "[error] drive_to_recommended_p oint failed" >&2
  print_debug_bundle
  exit 1
fi

echo "[step] wait video saved log"
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
    if [[ "${saved_local}" == "true" ]]; then
      video_path="$(extract_json_field "${entry}" ".file_path")"
      expected_prefix="${EXPECTED_SAVE_DIR%/}/${TASK_ID}/"
      if [[ "${video_path}" != ${expected_prefix}* ]]; then
        echo "[error] saved path mismatch" >&2
        echo "[error] expected prefix: ${expected_prefix}" >&2
        echo "[error] actual path: ${video_path}" >&2
        print_debug_bundle
        exit 1
      fi

      if [[ "${VERIFY_FILE_EXISTS}" == "true" ]]; then
        if [[ -f "${video_path}" ]]; then
          echo "[ok] file exists at: ${video_path}"
        elif [[ -n "${MEDIA_LOCAL_DIR}" && -f "${MEDIA_LOCAL_DIR%/}/${TASK_ID}/$(basename "${video_path}")" ]]; then
          echo "[ok] file exists at host-mapped path: ${MEDIA_LOCAL_DIR%/}/${TASK_ID}/$(basename "${video_path}")"
        else
          echo "[error] saved_local=true but file not found from current shell" >&2
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
  fi
  sleep "${POLL_INTERVAL_SEC}"
done

echo "[error] timeout waiting successful video capture log (task=${TASK_ID})" >&2
if [[ -n "${last_entry}" ]]; then
  echo "[error] last task video entry:"
  echo "${last_entry}" | pretty_print
fi
print_debug_bundle
exit 1

