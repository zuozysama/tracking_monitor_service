#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
LIMIT="${LIMIT:-20}"

echo "[1/4] healthz"
curl -sS "${BASE_URL}/api/v1/healthz"
echo
echo

echo "[2/4] dds debug-status"
curl -sS "${BASE_URL}/mock/collaboration/dds/debug-status"
echo
echo

echo "[3/4] recent dds publish-logs"
curl -sS "${BASE_URL}/mock/collaboration/dds/publish-logs"
echo
echo

echo "[4/4] recent dds subscribe-logs (limit=${LIMIT})"
curl -sS "${BASE_URL}/mock/collaboration/dds/subscribe-logs?limit=${LIMIT}"
echo

