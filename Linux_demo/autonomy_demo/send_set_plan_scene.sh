#!/usr/bin/env bash
set -euo pipefail

# Quick scene: first patrol dispatch, then tracking dispatch.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SLEEP_SEC="${SLEEP_SEC:-2}"

"${SCRIPT_DIR}/send_set_plan_patrol.sh"
sleep "${SLEEP_SEC}"
"${SCRIPT_DIR}/send_set_plan_tracking.sh"
