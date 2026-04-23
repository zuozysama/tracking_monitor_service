#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/common.sh"

LIMIT="${LIMIT:-200}"
TOPIC="${TOPIC:-}"

TOPIC_MANUAL_SWITCH="cc_cm_tracking_monitor_service.v1.manual_switch_request_topic"
TOPIC_MANUAL_SELECTION="cc_cm_tracking_monitor_service.v1.manual_selection_request_topic"
TOPIC_TASK_UPDATE="cc_cm_tracking_monitor_service.v1.task_update_topic"

if [[ -n "${TOPIC}" ]] \
  && [[ "${TOPIC}" != "${TOPIC_MANUAL_SWITCH}" ]] \
  && [[ "${TOPIC}" != "${TOPIC_MANUAL_SELECTION}" ]] \
  && [[ "${TOPIC}" != "${TOPIC_TASK_UPDATE}" ]]; then
  echo "[error] TOPIC must be one of:"
  echo "  - ${TOPIC_MANUAL_SWITCH}"
  echo "  - ${TOPIC_MANUAL_SELECTION}"
  echo "  - ${TOPIC_TASK_UPDATE}"
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "[error] python3/python not found"
  exit 1
fi

echo "[info] BASE_URL=${BASE_URL}"
echo "[info] TOPIC=${TOPIC:-<all-three-topics>}"
echo "[info] LIMIT=${LIMIT}"
echo "[info] adapter=real"
echo

RAW_JSON="$(api_get "/mock/collaboration/dds/publish-logs")"

printf '%s' "${RAW_JSON}" | "${PYTHON_BIN}" - "${LIMIT}" "${TOPIC}" <<'PY'
import json
import re
import struct
import sys

TOPIC_MANUAL_SWITCH = "cc_cm_tracking_monitor_service.v1.manual_switch_request_topic"
TOPIC_MANUAL_SELECTION = "cc_cm_tracking_monitor_service.v1.manual_selection_request_topic"
TOPIC_TASK_UPDATE = "cc_cm_tracking_monitor_service.v1.task_update_topic"
ALLOWED_TOPICS = {TOPIC_MANUAL_SWITCH, TOPIC_MANUAL_SELECTION, TOPIC_TASK_UPDATE}

COMMON_HEADER_LEN = struct.calcsize(">IBHBIBQ")  # 21


def _to_int(value: str, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _clean_hex(text: str) -> str:
    return re.sub(r"[^0-9a-fA-F]", "", text or "")


def _parse_common_header(body: bytes):
    if len(body) < COMMON_HEADER_LEN:
        return None
    protocol_type, version, packet_len, msg_type, seq, reserve, ts_0p1ms = struct.unpack(
        ">IBHBIBQ", body[:COMMON_HEADER_LEN]
    )
    return {
        "protocol_type": int(protocol_type),
        "protocol_version": int(version),
        "packet_length": int(packet_len),
        "msg_type": int(msg_type),
        "msg_seq": int(seq),
        "reserve": int(reserve),
        "timestamp_0p1ms": int(ts_0p1ms),
    }


limit = _to_int(sys.argv[1], 200)
topic_filter = sys.argv[2] if len(sys.argv) > 2 else ""

raw = sys.stdin.read()
root = json.loads(raw or "{}")
items = (((root or {}).get("data") or {}).get("items") or [])

filtered = [
    x
    for x in items
    if (x or {}).get("adapter") == "real" and (x or {}).get("topic") in ALLOWED_TOPICS
]
if topic_filter:
    filtered = [x for x in filtered if (x or {}).get("topic") == topic_filter]
if limit > 0:
    filtered = filtered[-limit:]

results = []
all_ok = True
for idx, item in enumerate(filtered, start=1):
    topic = (item or {}).get("topic")
    raw_hex = _clean_hex(str((item or {}).get("raw_hex") or ""))
    body_hex = _clean_hex(str((item or {}).get("body_hex") or ""))
    raw_body_equal = raw_hex == body_hex and bool(body_hex)

    decode_error = None
    packet_len_matches_body_len = False
    header = None
    body_len = len(body_hex) // 2

    if not body_hex:
        decode_error = "body_hex is empty"
    else:
        try:
            body = bytes.fromhex(body_hex)
            header = _parse_common_header(body)
            if header is None:
                decode_error = f"body too short for common header: {len(body)} < {COMMON_HEADER_LEN}"
            else:
                packet_len_matches_body_len = header["packet_length"] == len(body)
        except Exception as exc:
            decode_error = f"hex decode failed: {exc}"

    ok = raw_body_equal and packet_len_matches_body_len and decode_error is None
    if not ok:
        all_ok = False

    results.append(
        {
            "index": idx,
            "publish_time": (item or {}).get("publish_time"),
            "topic": topic,
            "wire_length": (item or {}).get("wire_length"),
            "raw_hex_len": len(raw_hex) // 2,
            "body_hex_len": body_len,
            "raw_body_equal": raw_body_equal,
            "packet_len_matches_body_len": packet_len_matches_body_len,
            "common_header": header,
            "ok": ok,
            "decode_error": decode_error,
        }
    )

summary = {
    "checked_count": len(results),
    "all_ok": all_ok,
    "failed_count": sum(1 for x in results if not x.get("ok")),
}

print(json.dumps({"summary": summary, "items": results}, ensure_ascii=False, indent=2))

if len(results) == 0:
    # No real publish logs found for selected topics.
    sys.exit(2)
if not all_ok:
    sys.exit(1)
PY

