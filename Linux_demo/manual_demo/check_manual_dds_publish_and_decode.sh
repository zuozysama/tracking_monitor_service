#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/common.sh"

LIMIT="${LIMIT:-50}"
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
MANUAL_SELECTION_HEADER_LEN = struct.calcsize(">64sBHH3s")  # 72
MANUAL_SWITCH_HEADER_LEN = struct.calcsize(">64sBHH3s64sI")  # 140
MANUAL_CANDIDATE_LEN = struct.calcsize(">64sIHBB16s")  # 88
TASK_UPDATE_LEN = struct.calcsize(">64sBBBBBIIHHHB16s")  # 100


def _to_int(value: str, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _cstr(raw: bytes) -> str:
    return raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")


def _clean_hex(text: str) -> str:
    return re.sub(r"[^0-9a-fA-F]", "", text or "")


def _decode_common_header(frame: bytes) -> tuple[dict | None, bytes]:
    if len(frame) < COMMON_HEADER_LEN:
        return None, frame
    protocol_type, version, packet_len, msg_type, seq, reserve, ts_0p1ms = struct.unpack(
        ">IBHBIBQ", frame[:COMMON_HEADER_LEN]
    )
    header = {
        "protocol_type": int(protocol_type),
        "protocol_version": int(version),
        "packet_length": int(packet_len),
        "msg_type": int(msg_type),
        "msg_seq": int(seq),
        "reserve": int(reserve),
        "timestamp_0p1ms": int(ts_0p1ms),
        "header_len": COMMON_HEADER_LEN,
        "packet_len_matches_body_len": int(packet_len) == len(frame),
    }
    return header, frame[COMMON_HEADER_LEN:]


def _decode_manual_candidate(chunk: bytes) -> dict:
    target_id_raw, batch_no, type_code, threat_level, military_civil_attr, reserved = struct.unpack(
        ">64sIHBB16s", chunk
    )
    return {
        "target_id": _cstr(target_id_raw),
        "target_batch_no": int(batch_no),
        "target_type_code": int(type_code),
        "threat_level": int(threat_level),
        "military_civil_attr": int(military_civil_attr),
        "reserved_hex": reserved.hex(),
    }


def _decode_manual_selection(payload: bytes) -> dict:
    if len(payload) < MANUAL_SELECTION_HEADER_LEN:
        return {
            "decode_error": f"manual_selection payload too short: got {len(payload)}, need at least {MANUAL_SELECTION_HEADER_LEN}"
        }
    task_id_raw, request_type, timeout_sec, count, reserved0 = struct.unpack(
        ">64sBHH3s", payload[:MANUAL_SELECTION_HEADER_LEN]
    )
    expected_len = MANUAL_SELECTION_HEADER_LEN + int(count) * MANUAL_CANDIDATE_LEN
    if len(payload) < expected_len:
        return {
            "decode_error": (
                f"manual_selection payload length mismatch: got {len(payload)}, "
                f"need at least {expected_len} (72 + count*88)"
            )
        }
    candidates = []
    offset = MANUAL_SELECTION_HEADER_LEN
    for _ in range(int(count)):
        chunk = payload[offset : offset + MANUAL_CANDIDATE_LEN]
        candidates.append(_decode_manual_candidate(chunk))
        offset += MANUAL_CANDIDATE_LEN
    return {
        "task_id": _cstr(task_id_raw),
        "request_type": int(request_type),
        "timeout_sec": int(timeout_sec),
        "candidate_count": int(count),
        "reserved0_hex": reserved0.hex(),
        "candidate_targets": candidates,
        "payload_len": len(payload),
        "expected_len": expected_len,
    }


def _decode_manual_switch(payload: bytes) -> dict:
    if len(payload) < MANUAL_SWITCH_HEADER_LEN:
        return {
            "decode_error": f"manual_switch payload too short: got {len(payload)}, need at least {MANUAL_SWITCH_HEADER_LEN}"
        }
    (
        task_id_raw,
        request_type,
        timeout_sec,
        count,
        reserved0,
        current_target_id_raw,
        current_target_batch_no,
    ) = struct.unpack(">64sBHH3s64sI", payload[:MANUAL_SWITCH_HEADER_LEN])
    expected_len = MANUAL_SWITCH_HEADER_LEN + int(count) * MANUAL_CANDIDATE_LEN
    if len(payload) < expected_len:
        return {
            "decode_error": (
                f"manual_switch payload length mismatch: got {len(payload)}, "
                f"need at least {expected_len} (140 + count*88)"
            )
        }
    candidates = []
    offset = MANUAL_SWITCH_HEADER_LEN
    for _ in range(int(count)):
        chunk = payload[offset : offset + MANUAL_CANDIDATE_LEN]
        candidates.append(_decode_manual_candidate(chunk))
        offset += MANUAL_CANDIDATE_LEN
    return {
        "task_id": _cstr(task_id_raw),
        "request_type": int(request_type),
        "timeout_sec": int(timeout_sec),
        "candidate_count": int(count),
        "reserved0_hex": reserved0.hex(),
        "current_target_id": _cstr(current_target_id_raw),
        "current_target_batch_no": int(current_target_batch_no),
        "new_candidate_targets": candidates,
        "payload_len": len(payload),
        "expected_len": expected_len,
    }


def _decode_task_update(payload: bytes) -> dict:
    if len(payload) < TASK_UPDATE_LEN:
        return {"decode_error": f"task_update payload too short: got {len(payload)}, need at least {TASK_UPDATE_LEN}"}
    (
        task_id_raw,
        task_type,
        task_status,
        execution_phase,
        update_type,
        result_type,
        current_target_batch_no,
        rel_range_m,
        relative_bearing_deg_x10,
        expected_speed_x10,
        waypoint_count,
        finish_reason,
        reserved_raw,
    ) = struct.unpack(">64sBBBBBIIHHHB16s", payload[:TASK_UPDATE_LEN])
    return {
        "task_id": _cstr(task_id_raw),
        "task_type": int(task_type),
        "task_status": int(task_status),
        "execution_phase": int(execution_phase),
        "update_type": int(update_type),
        "result_type": int(result_type),
        "current_target_batch_no": int(current_target_batch_no),
        "rel_range_m": int(rel_range_m),
        "relative_bearing_deg_x10": int(relative_bearing_deg_x10),
        "expected_speed_x10": int(expected_speed_x10),
        "waypoint_count": int(waypoint_count),
        "finish_reason": int(finish_reason),
        "reserved_hex": reserved_raw.hex(),
        "payload_len": len(payload),
        "expected_len": TASK_UPDATE_LEN,
    }


def _decode_by_topic(topic: str, payload: bytes) -> dict:
    if topic == TOPIC_MANUAL_SELECTION:
        return _decode_manual_selection(payload)
    if topic == TOPIC_MANUAL_SWITCH:
        return _decode_manual_switch(payload)
    if topic == TOPIC_TASK_UPDATE:
        return _decode_task_update(payload)
    return {"decode_error": f"unsupported topic: {topic}"}


limit = _to_int(sys.argv[1], 50)
topic_filter = sys.argv[2] if len(sys.argv) > 2 else ""

raw = sys.stdin.read()
try:
    root = json.loads(raw or "{}")
except Exception as exc:
    print(json.dumps({"decode_error": f"invalid JSON response: {exc}"}, ensure_ascii=False, indent=2))
    sys.exit(1)

items = (((root or {}).get("data") or {}).get("items") or [])
filtered = [x for x in items if (x or {}).get("topic") in ALLOWED_TOPICS]
if topic_filter:
    filtered = [x for x in filtered if (x or {}).get("topic") == topic_filter]
if limit > 0:
    filtered = filtered[-limit:]

publish_view = []
decoded_view = []

for idx, item in enumerate(filtered, start=1):
    topic = (item or {}).get("topic", "")
    payload_json = (item or {}).get("payload") or {}
    body_hex = str((item or {}).get("body_hex") or "")
    clean_hex = _clean_hex(body_hex)
    body = b""
    decode_error = None
    if clean_hex:
        try:
            body = bytes.fromhex(clean_hex)
        except Exception as exc:
            decode_error = f"invalid body_hex: {exc}"
    else:
        decode_error = "body_hex is empty"

    publish_view.append(
        {
            "index": idx,
            "publish_time": (item or {}).get("publish_time"),
            "topic": topic,
            "adapter": (item or {}).get("adapter"),
            "wire_length": (item or {}).get("wire_length"),
            "task_id": payload_json.get("task_id"),
            "request_type": payload_json.get("request_type"),
            "current_target_id": payload_json.get("current_target_id"),
            "current_target_batch_no": payload_json.get("current_target_batch_no"),
            "body_hex_len": len(clean_hex) // 2,
        }
    )

    if decode_error:
        decoded_view.append(
            {
                "index": idx,
                "topic": topic,
                "decode_error": decode_error,
            }
        )
        continue

    common_header, payload = _decode_common_header(body)
    decoded = _decode_by_topic(topic, payload)
    decoded_view.append(
        {
            "index": idx,
            "topic": topic,
            "raw_body_len": len(body),
            "common_header": common_header,
            "decoded": decoded,
        }
    )

print("=== publish_logs (filtered) ===")
print(json.dumps(publish_view, ensure_ascii=False, indent=2))
print()
print("=== decoded_body_hex ===")
print(json.dumps(decoded_view, ensure_ascii=False, indent=2))
PY

echo
echo "[info] dds debug status:"
api_get "/mock/collaboration/dds/debug-status" | pretty_print
echo
