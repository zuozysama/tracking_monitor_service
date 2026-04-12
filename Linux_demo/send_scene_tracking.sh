#!/usr/bin/env bash
set -euo pipefail

# HTTP-like quick scene: send several JSON requests in sequence.
# Equivalent to clicking Send on multiple blocks in .http.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

"${SCRIPT_DIR}/send_mock_navigation.sh"
"${SCRIPT_DIR}/send_mock_perception.sh"
"${SCRIPT_DIR}/send_task_tracking.sh"
