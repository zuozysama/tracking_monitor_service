#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://0.0.0.0:80}"
NOW_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

curl -sS -X POST "${BASE_URL}/mock/dds/navigation" \
  -H "Content-Type: application/json" \
  -d @- <<JSON
{
  "platform_id": 1001,
  "speed_mps": 6.2,
  "heading_deg": 90.0,
  "longitude": 121.5000000,
  "latitude": 31.2200000,
  "timestamp": "${NOW_UTC}"
}
JSON

echo
