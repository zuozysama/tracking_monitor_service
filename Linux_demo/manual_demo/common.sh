#!/usr/bin/env bash

# Common helpers for Linux_demo/manual_demo scripts.

BASE_URL="${BASE_URL:-http://0.0.0.0:80}"

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

require_jq() {
  if ! command -v jq >/dev/null 2>&1; then
    echo "[error] jq is required for this script." >&2
    exit 1
  fi
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

