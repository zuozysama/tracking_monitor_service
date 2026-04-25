#!/usr/bin/env bash

BASE_URL="${BASE_URL:-http://0.0.0.0:80}"
TASK_ID="${TASK_ID:-task-media-demo-001}"

now_utc() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

pretty_print() {
  if command -v jq >/dev/null 2>&1; then
    jq .
  else
    cat
  fi
}

run_python() {
  if command -v python3 >/dev/null 2>&1; then
    python3 "$@"
    return
  fi
  if command -v python >/dev/null 2>&1; then
    python "$@"
    return
  fi
  echo "[error] python3/python is required when jq is unavailable." >&2
  return 1
}

api_get() {
  local path="$1"
  curl -sS "${BASE_URL}${path}"
}

api_post_json() {
  local path="$1"
  local json_payload="$2"
  curl -sS -X POST "${BASE_URL}${path}" \
    -H "Content-Type: application/json" \
    -d "${json_payload}"
}

extract_json_field() {
  local json_text="$1"
  local field_path="$2"
  if command -v jq >/dev/null 2>&1; then
    echo "${json_text}" | jq -r "${field_path} // empty"
    return
  fi

  JSON_TEXT="${json_text}" run_python - "${field_path}" <<'PY'
import json
import os
import sys

field_path = (sys.argv[1] or "").strip()
if not field_path.startswith("."):
    print("")
    raise SystemExit(0)

parts = [p for p in field_path.lstrip(".").split(".") if p]
try:
    data = json.loads(os.environ.get("JSON_TEXT", ""))
except Exception:
    print("")
    raise SystemExit(0)

cur = data
for part in parts:
    if isinstance(cur, dict) and part in cur:
        cur = cur[part]
        continue
    print("")
    raise SystemExit(0)

if cur is None:
    print("")
elif isinstance(cur, (dict, list)):
    print(json.dumps(cur, ensure_ascii=False))
else:
    print(cur)
PY
}
