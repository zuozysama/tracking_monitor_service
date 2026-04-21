#!/usr/bin/env bash
set -euo pipefail

resolve_set_plan_url() {
  local mode raw_url

  mode="${EXTERNAL_AUTONOMY_MODE:-http}"
  if [[ "${mode,,}" != "http" ]]; then
    echo "[WARN] EXTERNAL_AUTONOMY_MODE=${mode}; direct set_plan scripts still use HTTP POST." >&2
  fi

  raw_url="${EXTERNAL_AUTONOMY_URL:-${EXTERNAL_AUTONOMY_BASE_URL:-172.16.10.104:8000}}"
  if [[ -z "${raw_url}" ]]; then
    echo "[ERROR] EXTERNAL_AUTONOMY_URL (or EXTERNAL_AUTONOMY_BASE_URL) is empty." >&2
    return 1
  fi

  if [[ "${raw_url}" =~ ^https?:// ]]; then
    SET_PLAN_URL="${raw_url}"
  else
    SET_PLAN_URL="http://${raw_url}"
  fi

  SET_PLAN_URL="${SET_PLAN_URL%/}"
  if [[ "${SET_PLAN_URL}" != */api/v1/set_plan ]]; then
    SET_PLAN_URL="${SET_PLAN_URL}/api/v1/set_plan"
  fi

  export SET_PLAN_URL
}

print_set_plan_target() {
  echo "[set_plan] mode=${EXTERNAL_AUTONOMY_MODE:-http} url=${SET_PLAN_URL}" >&2
}

build_task_id_json() {
  local raw
  raw="${1:-1001}"
  if [[ "${raw}" =~ ^[0-9]+$ ]]; then
    TASK_ID_JSON="${raw}"
  else
    TASK_ID_JSON="\"${raw//\"/\\\"}\""
  fi
  export TASK_ID_JSON
}
