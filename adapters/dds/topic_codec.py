from __future__ import annotations

import struct
from datetime import datetime, timezone
from typing import Any

from domain.dds_contract import (
    ELECTRO_OPTICAL_LINKAGE_CMD_TOPIC,
    MANUAL_SELECTION_REQUEST_TOPIC,
    MANUAL_SWITCH_REQUEST_TOPIC,
    OWNSHIP_NAVIGATION_TOPIC,
    PREPLAN_RESULT_TOPIC,
    STREAM_MEDIA_PARAM_TOPIC,
    TARGET_PERCEPTION_TOPIC,
    TASK_UPDATE_TOPIC,
)

DEFAULT_TARGET_TRACK_ALL_TOPIC = "cc_lm_situation_generating.v1.target_track_all"
TARGET_TRACK_ALL_FIELD_COUNT = 65
TARGET_TRACK_ALL_PACKET_SIZE = 369
CONTROL_WORD_PACKET_SIZE = 104
TARGET_TRACK_ALL_ANGLE_U16_LSB_DEG = 180.0 / (2**15)
TARGET_TRACK_ALL_ELEVATION_I16_LSB_DEG = 90.0 / (2**14)
TARGET_TRACK_ALL_GEO_I32_LSB_DEG = 90.0 / (2**30)

CONTROL_WORD_FIELDS = [
    ("target_category_1", 1, "uint8", 1.0),
    ("target_type_1", 1, "uint8", 1.0),
    ("target_category_2", 1, "uint8", 1.0),
    ("military_civil_attr", 1, "uint8", 1.0),
    ("enemy_friend_attr", 1, "uint8", 1.0),
    ("control_reserved_6", 1, "raw", 1.0),
    ("country_region_code", 2, "uint16", 1.0),
    ("target_type_2", 2, "uint16", 1.0),
    ("control_reserved_9", 2, "raw", 1.0),
    ("target_model", 24, "gb2312_string", 1.0),
    ("civil_aircraft_flight_no", 8, "ascii_string", 1.0),
    ("civil_ship_user_id", 4, "uint32", 1.0),
    ("control_reserved_13", 4, "raw", 1.0),
    ("target_name", 40, "gb2312_string", 1.0),
    ("mode_3a_code", 2, "uint16", 1.0),
    ("target_type_identification_basis", 1, "uint8", 1.0),
    ("enemy_friend_identification_basis", 1, "bit_flags", 1.0),
    ("control_other_use", 1, "uint8", 1.0),
    ("track_status", 1, "uint8", 1.0),
    ("track_quality_1", 1, "uint8", 1.0),
    ("track_quality_2", 1, "uint8", 1.0),
    ("search_tracking_mode", 1, "uint8", 1.0),
    ("warning_flag", 1, "uint8", 1.0),
    ("image_target_type", 2, "uint16", 1.0),
]

CONTROL_WORD_ALL_F_INVALID_FIELDS = {
    "country_region_code",
    "target_model",
    "civil_aircraft_flight_no",
    "target_name",
    "track_status",
    "track_quality_1",
    "track_quality_2",
    "search_tracking_mode",
}

TARGET_TRACK_ALL_FIELDS = [
    ("protocol_type", 4, "uint32", 1.0),
    ("protocol_version", 1, "uint8", 1.0),
    ("packet_length", 2, "uint16", 1.0),
    ("message_type", 1, "uint8", 1.0),
    ("message_sequence", 4, "uint32", 1.0),
    ("header_reserved", 1, "uint8", 1.0),
    ("timestamp_sec", 4, "uint32", 1.0),
    ("timestamp_ms", 4, "uint32", 1.0),
    ("composite_track_batch_no", 4, "bcd", 1.0),
    ("control_word", CONTROL_WORD_PACKET_SIZE, "control_word", 1.0),
    ("validity_flags", 8, "raw", 1.0),
    ("data_source", 4, "raw", 1.0),
    ("empty_13", 0, "empty", 1.0),
    ("data_period_sec", 2, "uint16", 0.001),
    ("reserved_15", 22, "raw", 1.0),
    ("target_distance_m", 4, "uint32", 1.0),
    ("target_bearing_deg", 2, "uint16", TARGET_TRACK_ALL_ANGLE_U16_LSB_DEG),
    ("target_elevation_deg", 2, "int16", TARGET_TRACK_ALL_ELEVATION_I16_LSB_DEG),
    ("target_x_m", 4, "int32", 0.1),
    ("target_y_m", 4, "int32", 0.1),
    ("target_z_m", 4, "int32", 0.1),
    ("target_relative_heading_deg", 2, "uint16", TARGET_TRACK_ALL_ANGLE_U16_LSB_DEG),
    ("target_absolute_heading_deg", 2, "uint16", TARGET_TRACK_ALL_ANGLE_U16_LSB_DEG),
    ("target_relative_speed_mps", 2, "uint16", 0.1),
    ("target_absolute_speed_mps", 2, "uint16", 0.1),
    ("reserved_26", 2, "raw", 1.0),
    ("reserved_27", 2, "raw", 1.0),
    ("target_vx_mps", 2, "int16", 0.1),
    ("target_vy_mps", 2, "int16", 0.1),
    ("target_vz_mps", 2, "int16", 0.1),
    ("reserved_31", 2, "raw", 1.0),
    ("longitude_deg", 4, "int32", TARGET_TRACK_ALL_GEO_I32_LSB_DEG),
    ("latitude_deg", 4, "int32", TARGET_TRACK_ALL_GEO_I32_LSB_DEG),
    ("altitude_m", 4, "uint32", 1.0),
    ("reserved_35", 12, "raw", 1.0),
    ("longitude_error_reserved", 4, "raw", 1.0),
    ("latitude_error_reserved", 4, "raw", 1.0),
    ("major_axis_error_reserved", 2, "raw", 1.0),
    ("minor_axis_error_reserved", 2, "raw", 1.0),
    ("major_axis_north_angle_reserved", 2, "raw", 1.0),
    ("track_quality_reserved", 2, "raw", 1.0),
    ("target_kind_confidence_reserved", 2, "raw", 1.0),
    ("target_type_confidence_reserved", 2, "raw", 1.0),
    ("image_domain_target_batch_no", 4, "raw", 1.0),
    ("ld_radiation_source_batch_no_1", 4, "raw", 1.0),
    ("ld_radiation_source_batch_no_2", 4, "raw", 1.0),
    ("ld_radiation_source_batch_no_3", 4, "raw", 1.0),
    ("reserved_48", 20, "raw", 1.0),
    ("reserved_49", 12, "raw", 1.0),
    ("reserved_50", 4, "raw", 1.0),
    ("bd_target_batch_no", 4, "bcd", 1.0),
    ("ais_target_batch_no_reserved", 4, "raw", 1.0),
    ("adsb_target_batch_no_reserved", 4, "raw", 1.0),
    ("navigation_ld1_target_batch_no", 4, "raw", 1.0),
    ("navigation_ld2_target_batch_no", 4, "raw", 1.0),
    ("threat_level", 2, "uint16", 1.0),
    ("navigation_ld_target_batch_no", 4, "uint32", 1.0),
    ("image_target_length", 2, "uint16", 1.0),
    ("image_target_width", 2, "uint16", 1.0),
    ("image_target_height", 2, "uint16", 1.0),
    ("absolute_heading_error", 2, "raw", 1.0),
    ("absolute_speed_error", 2, "raw", 1.0),
    ("ship_number", 30, "raw", 1.0),
    ("navigation_ld_virtual_j_flag", 1, "uint8", 1.0),
    ("reserved_65", 1, "raw", 1.0),
]

NAV_OUTER_V3_HEAD_LEN = 16
NAV_DOC90_LEN = 90
NAV_TOTAL_LEN = NAV_OUTER_V3_HEAD_LEN + NAV_DOC90_LEN
NAV_INNER_PROTO_HEAD_LEN = 21
NAV_FIELDS_LEN = 69
NAV_GEO_LSB_DEG = 180.0 / (2 ** 31)
NAV_HEADER_FMT = ">IBHBIBII"
NAV_HEADER_LEN = struct.calcsize(NAV_HEADER_FMT)
NAV_BUSINESS_FMT = ">HhhHhhiihhhhhhHHHHIHHHiiiBHI"
NAV_BUSINESS_LEN = struct.calcsize(NAV_BUSINESS_FMT)
COMMON_HEADER_FMT = ">IBHBIBQ"
COMMON_HEADER_LEN = struct.calcsize(COMMON_HEADER_FMT)
PHOTOELECTRIC_HEADER_FMT = ">IBHBIBII"
PHOTOELECTRIC_HEADER_LEN = struct.calcsize(PHOTOELECTRIC_HEADER_FMT)
PHOTOELECTRIC_REQUIRE_BUSINESS_FMT = ">HHBBBBHHHHHiiiiiiiiBI8s"
PHOTOELECTRIC_REQUIRE_BUSINESS_LEN = struct.calcsize(PHOTOELECTRIC_REQUIRE_BUSINESS_FMT)
PHOTOELECTRIC_REQUIRE_TOTAL_LEN = PHOTOELECTRIC_HEADER_LEN + PHOTOELECTRIC_REQUIRE_BUSINESS_LEN
TASK_UPDATE_BUSINESS_FMT = ">64sBBBBBIIHHHB16s"
TASK_UPDATE_BUSINESS_LEN = struct.calcsize(TASK_UPDATE_BUSINESS_FMT)
STREAM_MEDIA_BUSINESS_FMT = ">64sBBBB32sB64s128s8sIIIIHHHBB256s256s32s"
STREAM_MEDIA_BUSINESS_LEN = struct.calcsize(STREAM_MEDIA_BUSINESS_FMT)
NAV_TIMESTAMP_MS_RAW_MAX = 999_999_999


def _fit_ascii(value: str, size: int) -> bytes:
    raw = (value or "").encode("utf-8")
    if len(raw) >= size:
        return raw[: size - 1] + b"\x00"
    return raw + b"\x00" * (size - len(raw))


def _u16(v: Any) -> int:
    return max(0, min(int(v or 0), 0xFFFF))


def _u32(v: Any) -> int:
    return max(0, min(int(v or 0), 0xFFFFFFFF))


def _i32(v: Any) -> int:
    return max(-2147483648, min(int(v or 0), 2147483647))


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _decode_gb2312_cstr(raw: bytes) -> str:
    data = raw.split(b"\x00", 1)[0]
    if not data:
        return ""
    try:
        return data.decode("gb2312", errors="ignore")
    except Exception:
        return data.decode("utf-8", errors="ignore")


def _decode_utf8_cstr(raw: bytes) -> str:
    data = raw.split(b"\x00", 1)[0]
    if not data:
        return ""
    return data.decode("utf-8", errors="ignore")


def _parse_common_header(body: bytes) -> tuple[int, str | None]:
    # Common header from protocol doc:
    # protocol_type(4) + version(1) + length(2) + msg_type(1) + seq(4) + reserve(1) + ts(8)
    if len(body) < COMMON_HEADER_LEN:
        return 0, None

    try:
        protocol_type, _ver, length, _msg_type, _seq, _reserve, ts_0p1ms = struct.unpack(
            COMMON_HEADER_FMT, body[:COMMON_HEADER_LEN]
        )
    except Exception:
        return 0, None

    if protocol_type != 0:
        return 0, None
    if length and length > len(body):
        return 0, None

    try:
        day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        ts_value = day_start.timestamp() + float(ts_0p1ms) * 0.0001
        ts_iso = datetime.fromtimestamp(ts_value, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        ts_iso = None
    return COMMON_HEADER_LEN, ts_iso


def _parse_iso_utc(ts_iso: str | None) -> datetime | None:
    if not ts_iso:
        return None
    try:
        return datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
    except Exception:
        return None


def _format_target_generated_ts(common_ts_iso: str | None, target_ts_raw: int) -> str | None:
    try:
        base_dt = _parse_iso_utc(common_ts_iso) or datetime.now(timezone.utc)
        day_start = base_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        seconds = float(target_ts_raw) * 0.0001
        out = day_start.timestamp() + seconds
        return datetime.fromtimestamp(out, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def _nav_timestamp_0p1ms_from_day_start(payload: dict[str, Any]) -> int:
    supplied = payload.get("timestamp_0p1ms")
    if supplied is not None:
        try:
            return max(0, int(supplied))
        except Exception:
            pass

    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    delta = now - day_start
    ticks = int(round(delta.total_seconds() * 10000.0))
    return max(0, ticks)


def _u8(v: Any) -> int:
    return max(0, min(int(v or 0), 0xFF))


def _i16(v: Any) -> int:
    return max(-32768, min(int(v or 0), 32767))


def _i32_from_deg(value: Any) -> int:
    return _i32(round(float(value or 0.0) / NAV_GEO_LSB_DEG))


def _deg_from_i32(raw: int) -> float:
    return float(raw) * NAV_GEO_LSB_DEG


def _safe_int_value(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return default
            if text.lower().startswith("0x"):
                return int(text, 16)
            if all(ch in "0123456789abcdefABCDEF" for ch in text) and any(
                ch in "abcdefABCDEF" for ch in text
            ):
                return int(text, 16)
        return int(value)
    except Exception:
        return default


def _optional_int_value(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return _safe_int_value(value)
    except Exception:
        return None


def _safe_float_value(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _is_target_track_all_topic(topic: str) -> bool:
    return topic == DEFAULT_TARGET_TRACK_ALL_TOPIC


def _looks_like_target_track_all_payload(body: bytes) -> bool:
    raw = bytes(body)
    candidates: list[bytes] = []
    if len(raw) >= TARGET_TRACK_ALL_PACKET_SIZE:
        candidates.append(raw[:TARGET_TRACK_ALL_PACKET_SIZE])
    if len(raw) >= NAV_OUTER_V3_HEAD_LEN + TARGET_TRACK_ALL_PACKET_SIZE:
        candidates.append(raw[NAV_OUTER_V3_HEAD_LEN : NAV_OUTER_V3_HEAD_LEN + TARGET_TRACK_ALL_PACKET_SIZE])

    for payload in candidates:
        if len(payload) < 7:
            continue
        packet_len = int.from_bytes(payload[5:7], byteorder="big", signed=False)
        protocol_version = payload[4]
        if packet_len in {0, TARGET_TRACK_ALL_PACKET_SIZE, len(raw)} and protocol_version <= 10:
            return True
    return False


def _extract_target_track_all_payload(body: bytes) -> tuple[bytes, str, str]:
    raw = bytes(body)
    if len(raw) >= NAV_OUTER_V3_HEAD_LEN + TARGET_TRACK_ALL_PACKET_SIZE:
        shifted = raw[NAV_OUTER_V3_HEAD_LEN : NAV_OUTER_V3_HEAD_LEN + TARGET_TRACK_ALL_PACKET_SIZE]
        shifted_len = int.from_bytes(shifted[5:7], byteorder="big", signed=False)
        if shifted_len in {0, TARGET_TRACK_ALL_PACKET_SIZE, len(shifted)}:
            return shifted, "v3_16_plus_target_track_all", raw[:NAV_OUTER_V3_HEAD_LEN].hex(" ")

    if len(raw) >= TARGET_TRACK_ALL_PACKET_SIZE:
        return raw[:TARGET_TRACK_ALL_PACKET_SIZE], "target_track_all_direct", ""

    return raw, "target_track_all_direct", ""


def _target_track_all_timestamp(fields: dict[str, Any]) -> str:
    sec_raw = _safe_int_value(fields.get("timestamp_sec"), 0)
    ms_raw = _safe_int_value(fields.get("timestamp_ms"), 0)
    if sec_raw <= 0:
        return _iso_utc_now()
    try:
        ms = max(0, min(ms_raw, 999))
        return datetime.fromtimestamp(
            float(sec_raw) + float(ms) / 1000.0,
            tz=timezone.utc,
        ).isoformat().replace("+00:00", "Z")
    except Exception:
        return _iso_utc_now()


def _is_all_ff(raw: bytes) -> bool:
    return bool(raw) and all(item == 0xFF for item in raw)


def _decode_target_track_all_bcd(raw: bytes) -> int:
    digits: list[str] = []
    for item in raw:
        high = (item >> 4) & 0x0F
        low = item & 0x0F
        if high <= 9:
            digits.append(str(high))
        if low <= 9:
            digits.append(str(low))
    return int("".join(digits).lstrip("0") or "0")


def _decode_target_track_all_fixed_text(raw: bytes, encoding: str) -> str | None:
    if _is_all_ff(raw):
        return None
    text = raw.rstrip(b"\x00 ").decode(encoding, errors="ignore")
    return text or None


def _decode_control_word_field(raw: bytes, name: str, field_type: str, scale: float) -> Any:
    if _is_all_ff(raw) and name in CONTROL_WORD_ALL_F_INVALID_FIELDS:
        return None
    if field_type == "ascii_string":
        return _decode_target_track_all_fixed_text(raw, "ascii")
    if field_type == "gb2312_string":
        return _decode_target_track_all_fixed_text(raw, "gb2312")
    if field_type == "bit_flags":
        value = int.from_bytes(raw, byteorder="big", signed=False)
        return {
            "raw": value,
            "manual_label": bool(value & 0b0001),
            "enemy_friend_identifier": bool(value & 0b0010),
            "electronic_recon_device": bool(value & 0b0100),
            "external_platform_intel": bool(value & 0b1000),
        }
    return _decode_target_track_all_field(raw, field_type, scale)


def _decode_control_word_payload(raw: bytes) -> dict[str, Any]:
    if len(raw) != CONTROL_WORD_PACKET_SIZE:
        return {
            "decode_error": "control_word_size_mismatch",
            "expected_len": CONTROL_WORD_PACKET_SIZE,
            "raw_len": len(raw),
            "raw_hex": raw.hex(),
        }

    offset = 0
    fields: dict[str, Any] = {}
    offsets: dict[str, list[int]] = {}
    for name, byte_size, field_type, scale in CONTROL_WORD_FIELDS:
        item = raw[offset : offset + byte_size]
        fields[name] = _decode_control_word_field(item, name, field_type, scale)
        offsets[name] = [offset, offset + byte_size - 1]
        offset += byte_size

    return {
        "decode_format": "control_word",
        "raw_len": len(raw),
        "raw_hex": raw.hex(),
        "fields": fields,
        "offsets": offsets,
    }


def _decode_target_track_all_field(raw: bytes, field_type: str, scale: float) -> Any:
    if field_type == "empty":
        return None
    if field_type == "control_word":
        return _decode_control_word_payload(raw)
    if field_type in {"raw", "reserved"}:
        return raw.hex()
    if field_type == "bcd":
        return _decode_target_track_all_bcd(raw)
    if field_type in {"uint8", "uint16", "uint32", "uint64", "int8", "int16", "int32", "int64"}:
        signed = field_type.startswith("int")
        value = int.from_bytes(raw, byteorder="big", signed=signed)
        if scale == 1.0:
            return value
        return value * scale
    return {
        "unsupported_type": field_type,
        "raw_hex": raw.hex(),
    }


def _decode_target_track_all_payload(payload: bytes) -> dict[str, Any]:
    expected_size = sum(byte_size for _name, byte_size, _field_type, _scale in TARGET_TRACK_ALL_FIELDS)
    problems: list[str] = []
    if len(TARGET_TRACK_ALL_FIELDS) != TARGET_TRACK_ALL_FIELD_COUNT:
        problems.append(f"expected {TARGET_TRACK_ALL_FIELD_COUNT} fields, got {len(TARGET_TRACK_ALL_FIELDS)}")
    if expected_size != TARGET_TRACK_ALL_PACKET_SIZE:
        problems.append(f"expected total size {TARGET_TRACK_ALL_PACKET_SIZE}, got {expected_size}")
    if problems:
        return {
            "decode_error": "target_track_all_spec_invalid",
            "problems": problems,
            "raw_len": len(payload),
            "raw_hex": payload.hex(),
        }
    if len(payload) < TARGET_TRACK_ALL_PACKET_SIZE:
        return {
            "decode_error": "target_track_all_payload_too_short",
            "expected_len": TARGET_TRACK_ALL_PACKET_SIZE,
            "raw_len": len(payload),
            "raw_hex": payload.hex(),
        }

    offset = 0
    fields: dict[str, Any] = {}
    offsets: dict[str, list[int]] = {}
    body = payload[:TARGET_TRACK_ALL_PACKET_SIZE]
    for name, byte_size, field_type, scale in TARGET_TRACK_ALL_FIELDS:
        raw = body[offset : offset + byte_size]
        if name == "bd_target_batch_no" and _is_all_ff(raw):
            fields[name] = None
        else:
            fields[name] = _decode_target_track_all_field(raw, field_type, scale)
        offsets[name] = [offset, offset + byte_size - 1]
        offset += byte_size

    return {
        "decode_format": "target_track_all",
        "raw_len": len(body),
        "raw_hex": body.hex(),
        "fields": fields,
        "offsets": offsets,
    }


def _decode_target_track_all_as_target_perception(topic: str, body: bytes) -> dict:
    payload, input_layout, outer_head_hex = _extract_target_track_all_payload(body)
    decoded = _decode_target_track_all_payload(payload)
    decoded["topic"] = topic
    decoded["input_layout"] = input_layout
    decoded["input_raw_len"] = len(body)
    if outer_head_hex:
        decoded["outer_v3_head_hex"] = outer_head_hex

    fields = decoded.get("fields")
    if not isinstance(fields, dict):
        return decoded

    control_word = fields.get("control_word")
    control_fields = {}
    if isinstance(control_word, dict) and isinstance(control_word.get("fields"), dict):
        control_fields = control_word["fields"]

    timestamp = _target_track_all_timestamp(fields)
    composite_batch_no = _safe_int_value(fields.get("composite_track_batch_no"), 0)
    source_platform_id = _safe_int_value(fields.get("data_source"), 0)
    if fields.get("bd_target_batch_no") is None:
        return {
            "format": "target_track_all_369_to_target_perception",
            "decode_format": decoded.get("decode_format", "target_track_all"),
            "input_layout": decoded.get("input_layout"),
            "input_raw_len": decoded.get("input_raw_len", len(body)),
            "raw_len": decoded.get("raw_len"),
            "raw_hex": decoded.get("raw_hex", body.hex()),
            "source_platform_id": source_platform_id,
            "source_id": str(source_platform_id),
            "message_sequence": _safe_int_value(fields.get("message_sequence"), 0),
            "target_count": 0,
            "targets": [],
            "drop_message": True,
            "drop_reason": "bd_target_batch_no_all_ff",
            "target_track_all_fields": fields,
            "control_word_fields": control_fields,
            "target_track_all_decoded": decoded,
            "timestamp": timestamp,
        }

    bd_batch_no = _safe_int_value(fields.get("bd_target_batch_no"), 0)
    batch_no = bd_batch_no
    target_type_code = _optional_int_value(
        _first_present(
            control_fields.get("target_type_2"),
            control_fields.get("target_type_1"),
            control_fields.get("image_target_type"),
        )
    )
    target_name = _first_present(control_fields.get("target_name"), control_fields.get("target_model"))
    threat_level = _optional_int_value(fields.get("threat_level"))
    if threat_level in {0, 0xFFFF}:
        threat_level = None

    target = {
        "source_platform_id": source_platform_id,
        "target_id": f"target-{batch_no}",
        "target_batch_no": batch_no,
        "composite_track_batch_no": composite_batch_no,
        "bd_target_batch_no": bd_batch_no,
        "target_position_attr": _optional_int_value(control_fields.get("track_status")),
        "target_length_m": _safe_float_value(fields.get("image_target_length"), 0.0),
        "target_width_m": _safe_float_value(fields.get("image_target_width"), 0.0),
        "target_height_size_m": _safe_float_value(fields.get("image_target_height"), 0.0),
        "target_bearing_deg": _safe_float_value(fields.get("target_bearing_deg"), 0.0),
        "target_distance_m": _safe_float_value(fields.get("target_distance_m"), 0.0),
        "target_height_m": _safe_float_value(fields.get("altitude_m"), 0.0),
        "target_absolute_speed_mps": _safe_float_value(fields.get("target_absolute_speed_mps"), 0.0),
        "target_absolute_heading_deg": _safe_float_value(fields.get("target_absolute_heading_deg"), 0.0),
        "target_relative_speed_mps": _safe_float_value(fields.get("target_relative_speed_mps"), 0.0),
        "target_relative_heading_deg": _safe_float_value(fields.get("target_relative_heading_deg"), 0.0),
        "target_longitude": _safe_float_value(fields.get("longitude_deg"), 0.0),
        "target_latitude": _safe_float_value(fields.get("latitude_deg"), 0.0),
        "target_x_m": _safe_float_value(fields.get("target_x_m"), 0.0),
        "target_y_m": _safe_float_value(fields.get("target_y_m"), 0.0),
        "target_z_m": _safe_float_value(fields.get("target_z_m"), 0.0),
        "target_vx_mps": _safe_float_value(fields.get("target_vx_mps"), 0.0),
        "target_vy_mps": _safe_float_value(fields.get("target_vy_mps"), 0.0),
        "target_vz_mps": _safe_float_value(fields.get("target_vz_mps"), 0.0),
        "target_type_code": target_type_code,
        "enemy_friend_attr": _optional_int_value(control_fields.get("enemy_friend_attr")),
        "military_civil_attr": _safe_int_value(control_fields.get("military_civil_attr"), 0),
        "target_name": target_name,
        "threat_level": threat_level,
        "track_quality_1": _optional_int_value(control_fields.get("track_quality_1")),
        "track_quality_2": _optional_int_value(control_fields.get("track_quality_2")),
        "timestamp": timestamp,
        "active": True,
    }

    return {
        "format": "target_track_all_369_to_target_perception",
        "decode_format": decoded.get("decode_format", "target_track_all"),
        "input_layout": decoded.get("input_layout"),
        "input_raw_len": decoded.get("input_raw_len", len(body)),
        "raw_len": decoded.get("raw_len"),
        "raw_hex": decoded.get("raw_hex", body.hex()),
        "source_platform_id": source_platform_id,
        "source_id": str(source_platform_id),
        "message_sequence": _safe_int_value(fields.get("message_sequence"), 0),
        "target_count": 1,
        "targets": [target],
        "target_track_all_fields": fields,
        "control_word_fields": control_fields,
        "target_track_all_decoded": decoded,
        "timestamp": timestamp,
    }


def _nav_timestamp_parts(payload: dict[str, Any]) -> tuple[int, int]:
    # timestamp_millisecond_raw is uint32 fixed-point milliseconds:
    # range [0, 999.999999] ms with precision 1e-6 ms.
    # Raw value stores milliseconds * 1_000_000, so valid raw range is [0, 999_999_999].
    def _normalize_subsec_raw(value: Any) -> int:
        try:
            raw = int(value)
        except Exception:
            raw = 0
        return max(0, min(raw, NAV_TIMESTAMP_MS_RAW_MAX))

    sec_raw = payload.get("timestamp_sec", payload.get("ts_sec"))
    subsec_raw = payload.get(
        "timestamp_millisecond_raw",
        payload.get("timestamp_ms_raw", payload.get("ts_millisecond_raw")),
    )
    subsec_ms = payload.get("timestamp_millisecond")

    if sec_raw is not None:
        if subsec_raw is None and subsec_ms is not None:
            try:
                subsec_raw = int(round(float(subsec_ms) * 1_000_000.0))
            except Exception:
                subsec_raw = 0
        return _u32(sec_raw), _normalize_subsec_raw(subsec_raw)

    now = datetime.now(timezone.utc)
    if subsec_raw is None and subsec_ms is not None:
        try:
            subsec_raw = int(round(float(subsec_ms) * 1_000_000.0))
        except Exception:
            subsec_raw = 0
    if subsec_raw is not None:
        return int(now.timestamp()), _normalize_subsec_raw(subsec_raw)
    return int(now.timestamp()), _normalize_subsec_raw(now.microsecond * 1000)


def _nav_timestamp_iso(sec_raw: int, subsec_raw: int) -> str | None:
    try:
        subsec = max(0, min(int(subsec_raw), NAV_TIMESTAMP_MS_RAW_MAX))
        ts = float(sec_raw) + float(subsec) / 1_000_000_000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def _nav_status_flags(payload: dict[str, Any]) -> int:
    return _u16(payload.get("status_and_data_valid_flag", payload.get("status_flags", 0)))


def _nav_relative_speed_raw(payload: dict[str, Any]) -> int:
    if payload.get("relative_speed_raw") is not None:
        return _i16(payload.get("relative_speed_raw"))
    return _i16(round(float(payload.get("relative_speed_mps", 0.0)) * 100.0))


def _nav_absolute_speed_raw(payload: dict[str, Any]) -> int:
    if payload.get("absolute_speed_raw") is not None:
        return _i16(payload.get("absolute_speed_raw"))
    if payload.get("speed_raw") is not None:
        return _i16(payload.get("speed_raw"))
    return _i16(round(float(payload.get("absolute_speed_mps", payload.get("speed_mps", 0.0))) * 100.0))


def _nav_track_angle_raw(payload: dict[str, Any]) -> int:
    if payload.get("track_angle_raw") is not None:
        return _u16(payload.get("track_angle_raw"))
    if payload.get("heading_raw") is not None:
        return _u16(payload.get("heading_raw"))
    return _u16(round(float(payload.get("track_angle_deg", payload.get("heading_deg", 0.0))))) % 360


def _nav_east_speed_raw(payload: dict[str, Any]) -> int:
    if payload.get("east_speed_raw") is not None:
        return _i16(payload.get("east_speed_raw"))
    return _i16(round(float(payload.get("east_speed_mps", 0.0)) * 100.0))


def _nav_north_speed_raw(payload: dict[str, Any]) -> int:
    if payload.get("north_speed_raw") is not None:
        return _i16(payload.get("north_speed_raw"))
    return _i16(round(float(payload.get("north_speed_mps", 0.0)) * 100.0))


def _nav_lon_raw(payload: dict[str, Any]) -> int:
    if payload.get("longitude_raw") is not None:
        return _i32(payload.get("longitude_raw"))
    return _i32_from_deg(payload.get("longitude", 0.0))


def _nav_lat_raw(payload: dict[str, Any]) -> int:
    if payload.get("latitude_raw") is not None:
        return _i32(payload.get("latitude_raw"))
    return _i32_from_deg(payload.get("latitude", 0.0))


def _nav_vertical_speed_raw(payload: dict[str, Any]) -> int:
    if payload.get("vertical_speed_raw") is not None:
        return _i16(payload.get("vertical_speed_raw"))
    return _i16(round(float(payload.get("vertical_speed_mps", 0.0)) * 100.0))


def _nav_avg_true_wind_speed_raw(payload: dict[str, Any]) -> int:
    if payload.get("avg_true_wind_speed_raw") is not None:
        return _i16(payload.get("avg_true_wind_speed_raw"))
    return _i16(round(float(payload.get("avg_true_wind_speed_mps", 0.0)) * 100.0))


def _nav_avg_true_wind_dir_raw(payload: dict[str, Any]) -> int:
    if payload.get("avg_true_wind_direction_raw") is not None:
        return _i16(payload.get("avg_true_wind_direction_raw"))
    return _i16(round(float(payload.get("avg_true_wind_direction_deg", 0.0))))


def _nav_avg_relative_wind_speed_raw(payload: dict[str, Any]) -> int:
    if payload.get("avg_relative_wind_speed_raw") is not None:
        return _i16(payload.get("avg_relative_wind_speed_raw"))
    return _i16(round(float(payload.get("avg_relative_wind_speed_mps", 0.0)) * 100.0))


def _nav_avg_relative_wind_dir_raw(payload: dict[str, Any]) -> int:
    if payload.get("avg_relative_wind_direction_raw") is not None:
        return _i16(payload.get("avg_relative_wind_direction_raw"))
    return _i16(round(float(payload.get("avg_relative_wind_direction_deg", 0.0))))


def _nav_temperature_raw(payload: dict[str, Any]) -> int:
    if payload.get("temperature_raw") is not None:
        return _i16(payload.get("temperature_raw"))
    return _i16(round(float(payload.get("temperature_c", 0.0)) * 100.0))


def _nav_relative_humidity_raw(payload: dict[str, Any]) -> int:
    if payload.get("relative_humidity_raw") is not None:
        return _u16(payload.get("relative_humidity_raw"))
    return _u16(round(float(payload.get("relative_humidity_pct", 0.0)) * 100.0))


def _nav_air_pressure_raw(payload: dict[str, Any]) -> int:
    if payload.get("air_pressure_raw") is not None:
        return _u16(payload.get("air_pressure_raw"))
    return _u16(round(float(payload.get("air_pressure_hpa", 0.0)) * 10.0))


def _nav_sea_current_speed_raw(payload: dict[str, Any]) -> int:
    if payload.get("sea_current_speed_raw") is not None:
        return _u16(payload.get("sea_current_speed_raw"))
    return _u16(round(float(payload.get("sea_current_speed_mps", 0.0)) * 100.0))


def _nav_sea_current_direction_raw(payload: dict[str, Any]) -> int:
    if payload.get("sea_current_direction_raw") is not None:
        return _u16(payload.get("sea_current_direction_raw"))
    return _u16(round(float(payload.get("sea_current_direction_deg", 0.0))))


def _nav_depth_raw(payload: dict[str, Any]) -> int:
    if payload.get("sea_depth_raw") is not None:
        return _u32(payload.get("sea_depth_raw"))
    return _u32(round(float(payload.get("sea_depth_m", 0.0))))


def _nav_sea_state_raw(payload: dict[str, Any]) -> int:
    return _u16(payload.get("sea_state_raw", payload.get("sea_state_level", 0)))


def _nav_info_source_raw(payload: dict[str, Any]) -> int:
    return _u16(payload.get("nav_data_source_raw", payload.get("nav_data_info_source", 0)))


def _nav_device_status_raw(payload: dict[str, Any]) -> int:
    return _u16(payload.get("nav_device_status_raw", payload.get("nav_device_status_word", 0)))


def _nav_ship_heading_raw(payload: dict[str, Any]) -> int:
    if payload.get("ship_heading_raw") is not None:
        return _i32(payload.get("ship_heading_raw"))
    return _i32(round(float(payload.get("ship_heading_deg", 0.0)) * ((2 ** 31) / 180.0)))


def _nav_pitch_raw(payload: dict[str, Any]) -> int:
    if payload.get("pitch_raw") is not None:
        return _i32(payload.get("pitch_raw"))
    return _i32(round(float(payload.get("pitch_deg", 0.0)) * ((2 ** 31) / 180.0)))


def _nav_roll_raw(payload: dict[str, Any]) -> int:
    if payload.get("roll_raw") is not None:
        return _i32(payload.get("roll_raw"))
    return _i32(round(float(payload.get("roll_deg", 0.0)) * ((2 ** 31) / 180.0)))


def _nav_work_mode_raw(payload: dict[str, Any]) -> int:
    return _u8(payload.get("nav_system_mode", payload.get("nav_system_work_mode", 0)))


def _nav_visibility_raw(payload: dict[str, Any]) -> int:
    if payload.get("visibility_raw") is not None:
        return _u16(payload.get("visibility_raw"))
    return _u16(round(float(payload.get("visibility_m", 0.0))))


def _angle_from_nav_i32(raw: int) -> float:
    return float(raw) * 180.0 / float(2 ** 31)


def encode_topic_payload(topic: str, payload: dict) -> bytes:
    if topic == OWNSHIP_NAVIGATION_TOPIC:
        # 90-byte packet:
        # 21-byte protocol header + 69-byte navigation business fields.
        protocol_type = _u32(payload.get("protocol_type", 0))
        version = _u8(payload.get("protocol_version", payload.get("version", 1)))
        packet_len = NAV_DOC90_LEN
        msg_type = _u8(payload.get("msg_type", 1))
        seq = _u32(payload.get("msg_seq", payload.get("seq", 1)))
        reserve = _u8(payload.get("reserve", 0))
        ts_sec_raw, ts_millisecond_raw = _nav_timestamp_parts(payload)

        header = struct.pack(
            NAV_HEADER_FMT,
            protocol_type,
            version,
            packet_len,
            msg_type,
            seq,
            reserve,
            ts_sec_raw,
            ts_millisecond_raw,
        )

        business = struct.pack(
            NAV_BUSINESS_FMT,
            _nav_status_flags(payload),
            _nav_relative_speed_raw(payload),
            _nav_absolute_speed_raw(payload),
            _nav_track_angle_raw(payload),
            _nav_east_speed_raw(payload),
            _nav_north_speed_raw(payload),
            _nav_lon_raw(payload),
            _nav_lat_raw(payload),
            _nav_vertical_speed_raw(payload),
            _nav_avg_true_wind_speed_raw(payload),
            _nav_avg_true_wind_dir_raw(payload),
            _nav_avg_relative_wind_speed_raw(payload),
            _nav_avg_relative_wind_dir_raw(payload),
            _nav_temperature_raw(payload),
            _nav_relative_humidity_raw(payload),
            _nav_air_pressure_raw(payload),
            _nav_sea_current_speed_raw(payload),
            _nav_sea_current_direction_raw(payload),
            _nav_depth_raw(payload),
            _nav_sea_state_raw(payload),
            _nav_info_source_raw(payload),
            _nav_device_status_raw(payload),
            _nav_ship_heading_raw(payload),
            _nav_pitch_raw(payload),
            _nav_roll_raw(payload),
            _nav_work_mode_raw(payload),
            _nav_visibility_raw(payload),
            _u32(payload.get("platform_id", 1001)),
        )

        return header + business

    if topic == TARGET_PERCEPTION_TOPIC:
        # 21-byte common header + 2-byte target_count + N * 90-byte entries.
        # Each entry starts with 2-byte source_platform_id.
        targets = payload.get("targets") or []

        protocol_type = _u32(payload.get("protocol_type", 0))
        version = _u16(payload.get("protocol_version", payload.get("version", 1))) & 0xFF
        msg_type = _u16(payload.get("msg_type", 1)) & 0xFF
        seq = _u32(payload.get("msg_seq", payload.get("seq", 1)))
        reserve = _u16(payload.get("reserve", 0)) & 0xFF
        ts_0p1ms = _nav_timestamp_0p1ms_from_day_start(payload)

        entry_fmt = ">HHHIHHHHHiiHBBIBBB40sHHHBHH"
        entry_size = struct.calcsize(entry_fmt)  # 90
        packet_len = 21 + 2 + len(targets) * entry_size

        header = struct.pack(
            COMMON_HEADER_FMT,
            protocol_type,
            version,
            packet_len,
            msg_type,
            seq,
            reserve,
            ts_0p1ms,
        )

        prefix = struct.pack(">H", _u16(len(targets)))

        body = bytearray()
        for item in targets:
            source_platform_id = _u16(item.get("source_platform_id", payload.get("source_platform_id", 0)))
            batch_no = _u16(item.get("target_batch_no", 0))
            bearing_x10 = _u16(round(float(item.get("target_bearing_deg", 0.0)) * 10.0))
            distance_m = _u32(round(float(item.get("target_distance_m", 0.0))))
            height_x10 = _u16(round(float(item.get("target_height_m", 0.0)) * 10.0))
            abs_speed_x10 = _u16(round(float(item.get("target_absolute_speed_mps", 0.0)) * 10.0))
            abs_heading_x10 = _u16(round(float(item.get("target_absolute_heading_deg", 0.0)) * 10.0))
            rel_speed_x10 = _u16(round(float(item.get("target_relative_speed_mps", 0.0)) * 10.0))
            rel_heading_x10 = _u16(round(float(item.get("target_relative_heading_deg", 0.0)) * 10.0))

            lon_raw = _i32(round(float(item.get("target_longitude", 0.0)) / NAV_GEO_LSB_DEG))
            lat_raw = _i32(round(float(item.get("target_latitude", 0.0)) / NAV_GEO_LSB_DEG))

            qt_value = item.get("target_qt_value_m", 0xFFFF)
            if qt_value is None:
                qt_value = 0xFFFF
            qt_value = _u16(qt_value)

            coord_sys = _u16(item.get("coord_sys", 0)) & 0xFF
            is_simulated = _u16(item.get("is_simulated", 255)) & 0xFF

            target_ts_raw = _u32(item.get("target_generated_timestamp_raw", 0))

            position_attr = _u16(item.get("target_position_attr", 0)) & 0xFF
            target_type_code = _u16(item.get("target_type_code", 0)) & 0xFF
            military_civil_attr = _u16(item.get("military_civil_attr", 0)) & 0xFF

            target_name = str(item.get("target_name") or "")
            try:
                target_name_raw = target_name.encode("gb2312", errors="ignore")
            except Exception:
                target_name_raw = target_name.encode("utf-8", errors="ignore")
            target_name_raw = target_name_raw[:40].ljust(40, b"\x00")

            target_len_x10 = _u16(round(float(item.get("target_length_m", 0.0)) * 10.0))
            target_width_x10 = _u16(round(float(item.get("target_width_m", 0.0)) * 10.0))
            target_height_x10 = _u16(round(float(item.get("target_height_size_m", 0.0)) * 10.0))

            threat_level = item.get("threat_level", 0xFF)
            if threat_level is None:
                threat_level = 0xFF
            threat_level = _u16(threat_level) & 0xFF

            rcs_m2 = item.get("rcs_m2", None)
            rcs_x10 = 0xFFFF if rcs_m2 is None else _u16(round(float(rcs_m2) * 10.0))

            custom2 = item.get("custom2", None)
            custom2 = 0xFFFF if custom2 is None else _u16(custom2)

            body.extend(
                struct.pack(
                    entry_fmt,
                    source_platform_id,
                    batch_no,
                    bearing_x10,
                    distance_m,
                    height_x10,
                    abs_speed_x10,
                    abs_heading_x10,
                    rel_speed_x10,
                    rel_heading_x10,
                    lon_raw,
                    lat_raw,
                    qt_value,
                    coord_sys,
                    is_simulated,
                    target_ts_raw,
                    position_attr,
                    target_type_code,
                    military_civil_attr,
                    target_name_raw,
                    target_len_x10,
                    target_width_x10,
                    target_height_x10,
                    threat_level,
                    rcs_x10,
                    custom2,
                )
            )

        return header + prefix + bytes(body)

    if topic == TASK_UPDATE_TOPIC:
        protocol_type = _u32(payload.get("protocol_type", 0))
        version = _u8(payload.get("protocol_version", payload.get("version", 1)))
        msg_type = _u8(payload.get("msg_type", 1))
        seq = _u32(payload.get("msg_seq", payload.get("seq", 1)))
        reserve = _u8(payload.get("reserve", 0))
        ts_0p1ms = _nav_timestamp_0p1ms_from_day_start(payload)

        relative_bearing_deg_x10 = payload.get("relative_bearing_deg_x10")
        if relative_bearing_deg_x10 is None:
            relative_bearing_deg_x10 = round(float(payload.get("relative_bearing_deg", 0.0)) * 10.0)

        expected_speed_x10 = payload.get("expected_speed_x10")
        if expected_speed_x10 is None:
            expected_speed_x10 = round(float(payload.get("expected_speed", 0.0)) * 10.0)

        reserved = payload.get("reserved")
        if isinstance(reserved, (bytes, bytearray)):
            reserved_raw = bytes(reserved[:16]).ljust(16, b"\x00")
        else:
            reserved_raw = b"\x00" * 16

        business = struct.pack(
            TASK_UPDATE_BUSINESS_FMT,
            _fit_ascii(str(payload.get("task_id") or ""), 64),
            _u16(payload.get("task_type", 0)) & 0xFF,
            _u16(payload.get("task_status", 0)) & 0xFF,
            _u16(payload.get("execution_phase", 0)) & 0xFF,
            _u16(payload.get("update_type", 0)) & 0xFF,
            _u16(payload.get("result_type", 0)) & 0xFF,
            _u32(payload.get("current_target_batch_no", 0)),
            _u32(payload.get("rel_range_m", 0)),
            _u16(relative_bearing_deg_x10),
            _u16(expected_speed_x10),
            _u16(payload.get("waypoint_count", 0)),
            _u16(payload.get("finish_reason", 0)) & 0xFF,
            reserved_raw,
        )

        packet_len = COMMON_HEADER_LEN + TASK_UPDATE_BUSINESS_LEN
        header = struct.pack(
            COMMON_HEADER_FMT,
            protocol_type,
            version,
            packet_len,
            msg_type,
            seq,
            reserve,
            ts_0p1ms,
        )
        return header + business

    if topic == PREPLAN_RESULT_TOPIC:
        route = payload.get("planned_route") or []
        header = struct.pack(
            ">64sBH",
            _fit_ascii(str(payload.get("task_id") or ""), 64),
            _u16(payload.get("task_type", 7)) & 0xFF,
            _u16(payload.get("waypoint_count", len(route))),
        )
        body = bytearray()
        for waypoint in route:
            body.extend(
                struct.pack(
                    ">iiH",
                    _i32(round(float(waypoint.get("longitude", 0.0)) * 1e7)),
                    _i32(round(float(waypoint.get("latitude", 0.0)) * 1e7)),
                    _u16(round(float(waypoint.get("expected_speed", 0.0)) * 10)),
                )
            )
        return header + bytes(body)

    if topic == MANUAL_SELECTION_REQUEST_TOPIC:
        candidates = payload.get("candidate_targets") or []
        encoded_candidates = candidates
        request_type = 1
        business_header = struct.pack(
            ">64sBHH3s",
            _fit_ascii(str(payload.get("task_id") or ""), 64),
            _u8(request_type),
            _u16(payload.get("timeout_sec", 0)),
            _u16(len(encoded_candidates)),
            b"\x00" * 3,
        )
        body = bytearray()
        for item in encoded_candidates:
            threat_level = item.get("threat_level", 0xFF)
            if threat_level is None:
                threat_level = 0xFF
            body.extend(
                struct.pack(
                    ">64sIHBB16s",
                    _fit_ascii(str(item.get("target_id") or ""), 64),
                    _u32(item.get("target_batch_no", 0)),
                    _u16(item.get("target_type_code", 0)),
                    _u8(threat_level),
                    _u16(item.get("military_civil_attr", 0)) & 0xFF,
                    b"\x00" * 16,
                )
            )
        protocol_type = _u32(payload.get("protocol_type", 0))
        version = _u8(payload.get("protocol_version", payload.get("version", 1)))
        msg_type = _u8(payload.get("msg_type", 1))
        seq = _u32(payload.get("msg_seq", payload.get("seq", 1)))
        reserve = _u8(payload.get("reserve", 0))
        ts_0p1ms = _nav_timestamp_0p1ms_from_day_start(payload)
        packet_len = COMMON_HEADER_LEN + len(business_header) + len(body)
        common_header = struct.pack(
            COMMON_HEADER_FMT,
            protocol_type,
            version,
            packet_len,
            msg_type,
            seq,
            reserve,
            ts_0p1ms,
        )
        return common_header + business_header + bytes(body)

    if topic == MANUAL_SWITCH_REQUEST_TOPIC:
        candidates = payload.get("new_candidate_targets") or []
        encoded_candidates = candidates
        request_type = 2
        business_header = struct.pack(
            ">64sBHH3s64sI",
            _fit_ascii(str(payload.get("task_id") or ""), 64),
            _u8(request_type),
            _u16(payload.get("timeout_sec", 0)),
            _u16(len(encoded_candidates)),
            b"\x00" * 3,
            _fit_ascii(str(payload.get("current_target_id") or ""), 64),
            _u32(payload.get("current_target_batch_no", 0)),
        )
        body = bytearray()
        for item in encoded_candidates:
            threat_level = item.get("threat_level", 0xFF)
            if threat_level is None:
                threat_level = 0xFF
            body.extend(
                struct.pack(
                    ">64sIHBB16s",
                    _fit_ascii(str(item.get("target_id") or ""), 64),
                    _u32(item.get("target_batch_no", 0)),
                    _u16(item.get("target_type_code", 0)),
                    _u8(threat_level),
                    _u16(item.get("military_civil_attr", 0)) & 0xFF,
                    b"\x00" * 16,
                )
            )
        protocol_type = _u32(payload.get("protocol_type", 0))
        version = _u8(payload.get("protocol_version", payload.get("version", 1)))
        msg_type = _u8(payload.get("msg_type", 1))
        seq = _u32(payload.get("msg_seq", payload.get("seq", 1)))
        reserve = _u8(payload.get("reserve", 0))
        ts_0p1ms = _nav_timestamp_0p1ms_from_day_start(payload)
        packet_len = COMMON_HEADER_LEN + len(business_header) + len(body)
        common_header = struct.pack(
            COMMON_HEADER_FMT,
            protocol_type,
            version,
            packet_len,
            msg_type,
            seq,
            reserve,
            ts_0p1ms,
        )
        return common_header + business_header + bytes(body)

    if topic == ELECTRO_OPTICAL_LINKAGE_CMD_TOPIC:
        protocol_type = _u32(payload.get("protocol_type", 0))
        version = _u8(payload.get("protocol_version", payload.get("version", 1)))
        msg_type = _u8(payload.get("msg_type", 1))
        seq = _u32(payload.get("msg_seq", payload.get("seq", 1)))
        reserve = _u8(payload.get("reserve", 0))
        ts_sec_raw, ts_millisecond_raw = _nav_timestamp_parts(payload)

        header = struct.pack(
            PHOTOELECTRIC_HEADER_FMT,
            protocol_type,
            version,
            PHOTOELECTRIC_REQUIRE_TOTAL_LEN,
            msg_type,
            seq,
            reserve,
            ts_sec_raw,
            ts_millisecond_raw,
        )
        business = struct.pack(
            PHOTOELECTRIC_REQUIRE_BUSINESS_FMT,
            _u16(payload.get("task_type", 0)),
            _u16(payload.get("task_no", 0)),
            _u8(payload.get("dispatch_request_source", 0)),
            _u8(payload.get("task_status", 0)),
            _u8(payload.get("dispatch_task_type", 1)),
            _u8(payload.get("guidance_region_type", 0)),
            _u16(payload.get("fan_start_angle_deg", 0)),
            _u16(payload.get("fan_end_angle_deg", 0)),
            _u16(payload.get("fan_inner_radius_m", 0)),
            _u16(payload.get("fan_outer_radius_m", 0)),
            _u16(payload.get("reserved19", 0)),
            _i32(payload.get("rectangle_point1_longitude_raw", 0)),
            _i32(payload.get("rectangle_point1_latitude_raw", 0)),
            _i32(payload.get("rectangle_point2_longitude_raw", 0)),
            _i32(payload.get("rectangle_point2_latitude_raw", 0)),
            _i32(payload.get("rectangle_point3_longitude_raw", 0)),
            _i32(payload.get("rectangle_point3_latitude_raw", 0)),
            _i32(payload.get("rectangle_point4_longitude_raw", 0)),
            _i32(payload.get("rectangle_point4_latitude_raw", 0)),
            _u8(payload.get("reserved28", 0)),
            _u32(payload.get("target_batch_no", 0)),
            b"\x00" * 8,
        )
        return header + business

    if topic == STREAM_MEDIA_PARAM_TOPIC:
        protocol_type = _u32(payload.get("protocol_type", 0))
        version = _u8(payload.get("protocol_version", payload.get("version", 1)))
        msg_type = _u8(payload.get("msg_type", 1))
        seq = _u32(payload.get("msg_seq", payload.get("seq", 1)))
        reserve = _u8(payload.get("reserve", 0))
        ts_0p1ms = _nav_timestamp_0p1ms_from_day_start(payload)

        reserved = payload.get("reserved")
        if isinstance(reserved, (bytes, bytearray)):
            reserved_raw = bytes(reserved[:32]).ljust(32, b"\x00")
        else:
            reserved_raw = b"\x00" * 32

        business = struct.pack(
            STREAM_MEDIA_BUSINESS_FMT,
            _fit_ascii(str(payload.get("task_id") or ""), 64),
            _u16(payload.get("task_type", 0)) & 0xFF,
            _u16(payload.get("media_event_type", 0)) & 0xFF,
            _u16(payload.get("media_type", 0)) & 0xFF,
            _u16(payload.get("media_status", 0)) & 0xFF,
            _fit_ascii(str(payload.get("channel_id") or ""), 32),
            _u16(payload.get("stream_type", 0)) & 0xFF,
            _fit_ascii(str(payload.get("evidence_id") or ""), 64),
            _fit_ascii(str(payload.get("file_name") or ""), 128),
            _fit_ascii(str(payload.get("file_format") or ""), 8),
            _u32(payload.get("file_size_kb", 0)),
            _u32(payload.get("capture_time_sec", 0)),
            _u32(payload.get("capture_time_msec", 0)),
            _u32(payload.get("target_batch_no", 0)),
            _u16(payload.get("photo_interval_sec", 0)),
            _u16(payload.get("video_interval_sec", 0)),
            _u16(payload.get("video_duration_sec", 0)),
            _u16(payload.get("enable_evidence", 0)) & 0xFF,
            _u16(payload.get("reserved0", 0)) & 0xFF,
            _fit_ascii(str(payload.get("media_access_path") or ""), 256),
            _fit_ascii(str(payload.get("snapshot_url") or ""), 256),
            reserved_raw,
        )
        packet_len = COMMON_HEADER_LEN + STREAM_MEDIA_BUSINESS_LEN
        header = struct.pack(
            COMMON_HEADER_FMT,
            protocol_type,
            version,
            packet_len,
            msg_type,
            seq,
            reserve,
            ts_0p1ms,
        )
        return header + business

    return str(payload).encode("utf-8")


def decode_topic_payload(topic: str, body: bytes) -> dict:
    if topic == OWNSHIP_NAVIGATION_TOPIC:
        raw_msg = body

        if len(raw_msg) >= NAV_TOTAL_LEN:
            doc90 = raw_msg[NAV_OUTER_V3_HEAD_LEN:NAV_TOTAL_LEN]
            input_layout = "v3_16_plus_90"
        elif len(raw_msg) >= NAV_DOC90_LEN:
            doc90 = raw_msg[:NAV_DOC90_LEN]
            input_layout = "doc90"
        elif len(raw_msg) >= 35:
            # Backward-compatible fallback for historical 35-byte layout.
            doc35 = raw_msg[NAV_OUTER_V3_HEAD_LEN : NAV_OUTER_V3_HEAD_LEN + 35] if len(raw_msg) >= 51 else raw_msg[:35]
            if len(doc35) < 35:
                return {
                    "raw_hex": raw_msg.hex(),
                    "decode_error": (
                        f"raw NAV msg too short: got {len(raw_msg)} bytes, "
                        f"need at least {NAV_DOC90_LEN}"
                    ),
                }

            nav14 = doc35[21:35]
            uid = int.from_bytes(nav14[0:2], byteorder="big", signed=False)
            speed_raw = int.from_bytes(nav14[2:4], byteorder="big", signed=False)
            heading_raw = int.from_bytes(nav14[4:6], byteorder="big", signed=False)
            lon_raw = int.from_bytes(nav14[6:10], byteorder="big", signed=True)
            lat_raw = int.from_bytes(nav14[10:14], byteorder="big", signed=True)

            return {
                "format": "doc35_21_plus_14_fields",
                "compatibility_mode": True,
                "legacy_note": "received historical 35-byte navigation payload",
                "offsets": {
                    "uid": [21, 22],
                    "speed_raw": [23, 24],
                    "heading_raw": [25, 26],
                    "lon_raw": [27, 30],
                    "lat_raw": [31, 34],
                },
                "input_layout": "legacy_doc35",
                "platform_id": uid,
                "uid": uid,
                "raw_len": len(doc35),
                "expected_raw_len": 35,
                "input_raw_len": len(raw_msg),
                "absolute_speed_raw": speed_raw,
                "track_angle_raw": heading_raw,
                "longitude_raw": lon_raw,
                "latitude_raw": lat_raw,
                "absolute_speed_mps": float(speed_raw) * 0.01,
                "track_angle_deg": float(heading_raw) % 360.0,
                "heading_deg": float(heading_raw) % 360.0,
                "longitude": _deg_from_i32(lon_raw),
                "latitude": _deg_from_i32(lat_raw),
                "inner_proto21_hex": doc35[:21].hex(" "),
                "business_hex": nav14.hex(" "),
                "doc35_hex": doc35.hex(" "),
                "raw_hex": doc35.hex(),
                "timestamp": _iso_utc_now(),
                "decode_format": "doc35_21_plus_14_fields",
            }
        else:
            return {
                "raw_hex": raw_msg.hex(),
                "decode_error": (
                    f"raw NAV msg too short: got {len(raw_msg)} bytes, "
                    f"need at least {NAV_DOC90_LEN}"
                ),
            }

        if len(doc90) < NAV_DOC90_LEN:
            return {
                "raw_hex": raw_msg.hex(),
                "decode_error": f"NAV90 too short: got {len(doc90)} bytes, need {NAV_DOC90_LEN}",
            }

        header = doc90[:NAV_INNER_PROTO_HEAD_LEN]
        business = doc90[NAV_INNER_PROTO_HEAD_LEN:NAV_DOC90_LEN]

        if len(header) != NAV_HEADER_LEN or len(business) != NAV_BUSINESS_LEN:
            return {
                "raw_hex": doc90.hex(),
                "decode_error": (
                    f"NAV90 header/business length mismatch: header={len(header)}, "
                    f"business={len(business)}, expected={NAV_HEADER_LEN}/{NAV_BUSINESS_LEN}"
                ),
            }

        (
            protocol_type,
            version,
            packet_len,
            msg_type,
            seq,
            reserve,
            timestamp_sec,
            timestamp_millisecond_raw,
        ) = struct.unpack(NAV_HEADER_FMT, header)

        (
            status_and_data_valid_flag,
            relative_speed_raw,
            absolute_speed_raw,
            track_angle_raw,
            east_speed_raw,
            north_speed_raw,
            longitude_raw,
            latitude_raw,
            vertical_speed_raw,
            avg_true_wind_speed_raw,
            avg_true_wind_direction_raw,
            avg_relative_wind_speed_raw,
            avg_relative_wind_direction_raw,
            temperature_raw,
            relative_humidity_raw,
            air_pressure_raw,
            sea_current_speed_raw,
            sea_current_direction_raw,
            sea_depth_raw,
            sea_state_raw,
            nav_data_info_source_raw,
            nav_device_status_raw,
            ship_heading_raw,
            pitch_raw,
            roll_raw,
            nav_system_work_mode,
            visibility_raw,
            platform_id,
        ) = struct.unpack(NAV_BUSINESS_FMT, business)

        timestamp_millisecond_raw = max(0, min(int(timestamp_millisecond_raw), NAV_TIMESTAMP_MS_RAW_MAX))
        timestamp_iso = _nav_timestamp_iso(timestamp_sec, timestamp_millisecond_raw)

        return {
            "format": "doc90_21_plus_69_fields",
            "offsets": {
                "header": [0, 20],
                "business": [21, 89],
            },
            "input_layout": input_layout,
            "raw_len": len(doc90),
            "expected_raw_len": NAV_DOC90_LEN,
            "input_raw_len": len(raw_msg),
            "protocol_type": protocol_type,
            "protocol_version": version,
            "packet_length": packet_len,
            "msg_type": msg_type,
            "msg_seq": seq,
            "reserve": reserve,
            "timestamp_sec": timestamp_sec,
            "timestamp_millisecond_raw": timestamp_millisecond_raw,
            "timestamp_millisecond": float(timestamp_millisecond_raw) / 1_000_000.0,
            "timestamp": timestamp_iso or _iso_utc_now(),
            "status_and_data_valid_flag": status_and_data_valid_flag,
            "relative_speed_raw": relative_speed_raw,
            "absolute_speed_raw": absolute_speed_raw,
            "track_angle_raw": track_angle_raw,
            "east_speed_raw": east_speed_raw,
            "north_speed_raw": north_speed_raw,
            "longitude_raw": longitude_raw,
            "latitude_raw": latitude_raw,
            "vertical_speed_raw": vertical_speed_raw,
            "avg_true_wind_speed_raw": avg_true_wind_speed_raw,
            "avg_true_wind_direction_raw": avg_true_wind_direction_raw,
            "avg_relative_wind_speed_raw": avg_relative_wind_speed_raw,
            "avg_relative_wind_direction_raw": avg_relative_wind_direction_raw,
            "temperature_raw": temperature_raw,
            "relative_humidity_raw": relative_humidity_raw,
            "air_pressure_raw": air_pressure_raw,
            "sea_current_speed_raw": sea_current_speed_raw,
            "sea_current_direction_raw": sea_current_direction_raw,
            "sea_depth_raw": sea_depth_raw,
            "sea_state_raw": sea_state_raw,
            "nav_data_info_source_raw": nav_data_info_source_raw,
            "nav_device_status_raw": nav_device_status_raw,
            "ship_heading_raw": ship_heading_raw,
            "pitch_raw": pitch_raw,
            "roll_raw": roll_raw,
            "nav_system_work_mode": nav_system_work_mode,
            "visibility_raw": visibility_raw,
            "platform_id": platform_id,
            "uid": platform_id,
            "relative_speed_mps": float(relative_speed_raw) * 0.01,
            "absolute_speed_mps": float(absolute_speed_raw) * 0.01,
            "speed_mps": float(absolute_speed_raw) * 0.01,
            "track_angle_deg": float(track_angle_raw),
            "heading_deg": float(track_angle_raw),
            "east_speed_mps": float(east_speed_raw) * 0.01,
            "north_speed_mps": float(north_speed_raw) * 0.01,
            "longitude": _deg_from_i32(longitude_raw),
            "latitude": _deg_from_i32(latitude_raw),
            "vertical_speed_mps": float(vertical_speed_raw) * 0.01,
            "avg_true_wind_speed_mps": float(avg_true_wind_speed_raw) * 0.01,
            "avg_true_wind_direction_deg": float(avg_true_wind_direction_raw),
            "avg_relative_wind_speed_mps": float(avg_relative_wind_speed_raw) * 0.01,
            "avg_relative_wind_direction_deg": float(avg_relative_wind_direction_raw),
            "temperature_c": float(temperature_raw) * 0.01,
            "relative_humidity_pct": float(relative_humidity_raw) * 0.01,
            "air_pressure_hpa": float(air_pressure_raw) * 0.1,
            "sea_current_speed_mps": float(sea_current_speed_raw) * 0.01,
            "sea_current_direction_deg": float(sea_current_direction_raw),
            "sea_depth_m": float(sea_depth_raw),
            "sea_state_level": int(sea_state_raw),
            "nav_data_info_source": int(nav_data_info_source_raw),
            "nav_device_status_word": int(nav_device_status_raw),
            "ship_heading_deg": _angle_from_nav_i32(ship_heading_raw),
            "pitch_deg": _angle_from_nav_i32(pitch_raw),
            "roll_deg": _angle_from_nav_i32(roll_raw),
            "visibility_m": float(visibility_raw),
            "inner_proto21_hex": header.hex(" "),
            "business_hex": business.hex(" "),
            "doc90_hex": doc90.hex(" "),
            "raw_hex": doc90.hex(),
            "decode_format": "doc90_21_plus_69_fields",
        }

    if _is_target_track_all_topic(topic) or (
        topic == TARGET_PERCEPTION_TOPIC and _looks_like_target_track_all_payload(body)
    ):
        return _decode_target_track_all_as_target_perception(topic, body)

    if topic == TARGET_PERCEPTION_TOPIC:
        def _decode_target_payload_frame(frame: bytes) -> tuple[dict | None, str | None, int]:
            common_offset, common_ts = _parse_common_header(frame)
            payload = frame[common_offset:] if common_offset else frame

            if len(payload) < 2:
                return None, f"target payload too short: got {len(payload)} bytes, need at least 2", common_offset

            target_count = struct.unpack(">H", payload[:2])[0]

            entry_fmt_v2 = ">HHHIHHHHHiiHBBIBBB40sHHHBHH"
            entry_size_v2 = struct.calcsize(entry_fmt_v2)  # 90
            expected_len_v2 = 2 + target_count * entry_size_v2

            use_v2_layout = len(payload) == expected_len_v2
            if not use_v2_layout:
                return (
                    None,
                    (
                        f"target payload length mismatch: got {len(payload)} bytes, "
                        f"need exactly {expected_len_v2} for {target_count} targets (2 + N*90)"
                    ),
                    common_offset,
                )

            entry_fmt = entry_fmt_v2
            entry_size = entry_size_v2

            targets = []
            offset = 2
            for _i in range(target_count):
                chunk = payload[offset : offset + entry_size]
                (
                    source_platform_id,
                    batch_no,
                    bearing_x10,
                    distance_m,
                    height_x10,
                    abs_speed_x10,
                    abs_heading_x10,
                    rel_speed_x10,
                    rel_heading_x10,
                    lon_raw,
                    lat_raw,
                    qt_value,
                    coord_sys,
                    is_simulated,
                    target_ts_raw,
                    position_attr,
                    target_type_code,
                    military_civil_attr,
                    target_name_raw,
                    target_len_x10,
                    target_width_x10,
                    target_height_x10,
                    threat_level,
                    rcs_x10,
                    custom2,
                ) = struct.unpack(entry_fmt, chunk)

                target_name = _decode_gb2312_cstr(target_name_raw)
                target_generated_ts = _format_target_generated_ts(common_ts, int(target_ts_raw))

                targets.append(
                    {
                        "source_platform_id": int(source_platform_id),
                        "target_id": f"target-{int(batch_no)}",
                        "target_batch_no": int(batch_no),
                        "target_bearing_deg": float(bearing_x10) / 10.0,
                        "target_distance_m": float(distance_m),
                        "target_height_m": float(height_x10) / 10.0,
                        "target_absolute_speed_mps": float(abs_speed_x10) / 10.0,
                        "target_absolute_heading_deg": float(abs_heading_x10) / 10.0,
                        "target_relative_speed_mps": float(rel_speed_x10) / 10.0,
                        "target_relative_heading_deg": float(rel_heading_x10) / 10.0,
                        "target_longitude": float(lon_raw) * NAV_GEO_LSB_DEG,
                        "target_latitude": float(lat_raw) * NAV_GEO_LSB_DEG,
                        "target_qt_value_m": int(qt_value) if qt_value != 0xFFFF else None,
                        "coord_sys": int(coord_sys),
                        "is_simulated": int(is_simulated),
                        "target_generated_timestamp_raw": int(target_ts_raw),
                        "target_generated_timestamp": target_generated_ts,
                        "target_position_attr": int(position_attr),
                        "target_type_code": int(target_type_code),
                        "military_civil_attr": int(military_civil_attr),
                        "target_name": target_name or None,
                        "target_length_m": float(target_len_x10) / 10.0,
                        "target_width_m": float(target_width_x10) / 10.0,
                        "target_height_size_m": float(target_height_x10) / 10.0,
                        "threat_level": None if int(threat_level) == 0xFF else int(threat_level),
                        "rcs_m2": float(rcs_x10) / 10.0 if int(rcs_x10) != 0xFFFF else None,
                        "custom2": None if int(custom2) == 0xFFFF else int(custom2),
                        "timestamp": common_ts or _iso_utc_now(),
                        "active": True,
                    }
                )
                offset += entry_size

            return (
                {
                    "source_platform_id": int(targets[0]["source_platform_id"]) if targets else 0,
                    "target_count": int(target_count),
                    "entry_size": entry_size,
                    "targets": targets,
                },
                None,
                common_offset,
            )

        direct_result, direct_error, _direct_common_offset = _decode_target_payload_frame(body)
        if direct_result:
            direct_result["input_layout"] = "target_payload"
            direct_result["input_raw_len"] = len(body)
            return direct_result

        return {
            "raw_hex": body.hex(),
            "decode_error": direct_error or "target payload decode failed",
        }

    if topic == TASK_UPDATE_TOPIC:
        common_offset, common_ts = _parse_common_header(body)
        payload = body[common_offset:] if common_offset else body
        if len(payload) < TASK_UPDATE_BUSINESS_LEN:
            return {
                "raw_hex": body.hex(),
                "decode_error": (
                    f"task_update payload too short: got {len(payload)} bytes, "
                    f"need at least {TASK_UPDATE_BUSINESS_LEN}"
                ),
            }

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
        ) = struct.unpack(TASK_UPDATE_BUSINESS_FMT, payload[:TASK_UPDATE_BUSINESS_LEN])

        result = {
            "task_id": _decode_utf8_cstr(task_id_raw),
            "task_type": int(task_type),
            "task_status": int(task_status),
            "execution_phase": int(execution_phase),
            "update_type": int(update_type),
            "result_type": int(result_type),
            "current_target_batch_no": int(current_target_batch_no),
            "rel_range_m": int(rel_range_m),
            "relative_bearing_deg_x10": int(relative_bearing_deg_x10),
            "relative_bearing_deg": float(relative_bearing_deg_x10) / 10.0,
            "expected_speed_x10": int(expected_speed_x10),
            "expected_speed": float(expected_speed_x10) / 10.0,
            "waypoint_count": int(waypoint_count),
            "finish_reason": int(finish_reason),
            "reserved_hex": reserved_raw.hex(" "),
            "timestamp": common_ts or _iso_utc_now(),
            "raw_hex": payload[:TASK_UPDATE_BUSINESS_LEN].hex(),
            "raw_len": TASK_UPDATE_BUSINESS_LEN,
            "expected_raw_len": TASK_UPDATE_BUSINESS_LEN,
        }

        if common_offset:
            protocol_type, version, packet_len, msg_type, seq, reserve, ts_0p1ms = struct.unpack(
                COMMON_HEADER_FMT, body[:COMMON_HEADER_LEN]
            )
            result.update(
                {
                    "protocol_type": int(protocol_type),
                    "protocol_version": int(version),
                    "packet_length": int(packet_len),
                    "msg_type": int(msg_type),
                    "msg_seq": int(seq),
                    "reserve": int(reserve),
                    "timestamp_0p1ms": int(ts_0p1ms),
                    "inner_proto21_hex": body[:COMMON_HEADER_LEN].hex(" "),
                    "decode_format": "task_update_21_plus_100_fields",
                    "input_layout": "doc121",
                }
            )
        else:
            result.update(
                {
                    "decode_format": "task_update_100_fields",
                    "input_layout": "doc100",
                }
            )

        return result

    if topic == ELECTRO_OPTICAL_LINKAGE_CMD_TOPIC:
        if len(body) < PHOTOELECTRIC_REQUIRE_TOTAL_LEN:
            return {
                "raw_hex": body.hex(),
                "decode_error": (
                    f"photoelectric_require payload too short: got {len(body)} bytes, "
                    f"need at least {PHOTOELECTRIC_REQUIRE_TOTAL_LEN}"
                ),
            }

        (
            protocol_type,
            version,
            packet_len,
            msg_type,
            seq,
            reserve,
            timestamp_sec,
            timestamp_millisecond_raw,
        ) = struct.unpack(PHOTOELECTRIC_HEADER_FMT, body[:PHOTOELECTRIC_HEADER_LEN])
        payload = body[PHOTOELECTRIC_HEADER_LEN:PHOTOELECTRIC_REQUIRE_TOTAL_LEN]
        (
            task_type,
            task_no,
            dispatch_request_source,
            task_status,
            dispatch_task_type,
            guidance_region_type,
            fan_start_angle_deg,
            fan_end_angle_deg,
            fan_inner_radius_m,
            fan_outer_radius_m,
            reserved19,
            rectangle_point1_longitude_raw,
            rectangle_point1_latitude_raw,
            rectangle_point2_longitude_raw,
            rectangle_point2_latitude_raw,
            rectangle_point3_longitude_raw,
            rectangle_point3_latitude_raw,
            rectangle_point4_longitude_raw,
            rectangle_point4_latitude_raw,
            reserved28,
            target_batch_no,
            reserved30_raw,
        ) = struct.unpack(PHOTOELECTRIC_REQUIRE_BUSINESS_FMT, payload)

        timestamp_millisecond_raw = max(0, min(int(timestamp_millisecond_raw), NAV_TIMESTAMP_MS_RAW_MAX))
        return {
            "protocol_type": int(protocol_type),
            "protocol_version": int(version),
            "packet_length": int(packet_len),
            "msg_type": int(msg_type),
            "msg_seq": int(seq),
            "reserve": int(reserve),
            "timestamp_sec": int(timestamp_sec),
            "timestamp_millisecond_raw": int(timestamp_millisecond_raw),
            "timestamp_millisecond": float(timestamp_millisecond_raw) / 1_000_000.0,
            "timestamp": _nav_timestamp_iso(timestamp_sec, timestamp_millisecond_raw) or _iso_utc_now(),
            "task_type": int(task_type),
            "task_no": int(task_no),
            "dispatch_request_source": int(dispatch_request_source),
            "task_status": int(task_status),
            "dispatch_task_type": int(dispatch_task_type),
            "guidance_region_type": int(guidance_region_type),
            "fan_start_angle_deg": int(fan_start_angle_deg),
            "fan_end_angle_deg": int(fan_end_angle_deg),
            "fan_inner_radius_m": int(fan_inner_radius_m),
            "fan_outer_radius_m": int(fan_outer_radius_m),
            "reserved19": int(reserved19),
            "rectangle_point1_longitude_raw": int(rectangle_point1_longitude_raw),
            "rectangle_point1_latitude_raw": int(rectangle_point1_latitude_raw),
            "rectangle_point2_longitude_raw": int(rectangle_point2_longitude_raw),
            "rectangle_point2_latitude_raw": int(rectangle_point2_latitude_raw),
            "rectangle_point3_longitude_raw": int(rectangle_point3_longitude_raw),
            "rectangle_point3_latitude_raw": int(rectangle_point3_latitude_raw),
            "rectangle_point4_longitude_raw": int(rectangle_point4_longitude_raw),
            "rectangle_point4_latitude_raw": int(rectangle_point4_latitude_raw),
            "reserved28": int(reserved28),
            "target_batch_no": int(target_batch_no),
            "reserved30_hex": reserved30_raw.hex(" "),
            "raw_hex": body[:PHOTOELECTRIC_REQUIRE_TOTAL_LEN].hex(),
            "raw_len": PHOTOELECTRIC_REQUIRE_TOTAL_LEN,
            "expected_raw_len": PHOTOELECTRIC_REQUIRE_TOTAL_LEN,
            "business_raw_len": PHOTOELECTRIC_REQUIRE_BUSINESS_LEN,
            "decode_format": "photoelectric_require_21_plus_63_fields",
            "input_layout": "doc84",
        }

    if topic == STREAM_MEDIA_PARAM_TOPIC:
        common_offset, common_ts = _parse_common_header(body)
        payload = body[common_offset:] if common_offset else body
        if common_offset and len(payload) < STREAM_MEDIA_BUSINESS_LEN and len(body) >= STREAM_MEDIA_BUSINESS_LEN:
            # Backward compatibility: if header auto-detection is a false positive,
            # retry as pure 869-byte business payload.
            common_offset = 0
            common_ts = None
            payload = body
        if len(payload) < STREAM_MEDIA_BUSINESS_LEN:
            return {
                "raw_hex": body.hex(),
                "decode_error": (
                    f"stream_media_param payload too short: got {len(payload)} bytes, "
                    f"need at least {STREAM_MEDIA_BUSINESS_LEN}"
                ),
            }

        (
            task_id_raw,
            task_type,
            media_event_type,
            media_type,
            media_status,
            channel_id_raw,
            stream_type,
            evidence_id_raw,
            file_name_raw,
            file_format_raw,
            file_size_kb,
            capture_time_sec,
            capture_time_msec,
            target_batch_no,
            photo_interval_sec,
            video_interval_sec,
            video_duration_sec,
            enable_evidence,
            reserved0,
            media_access_path_raw,
            snapshot_url_raw,
            reserved_raw,
        ) = struct.unpack(STREAM_MEDIA_BUSINESS_FMT, payload[:STREAM_MEDIA_BUSINESS_LEN])

        result = {
            "task_id": _decode_utf8_cstr(task_id_raw),
            "task_type": int(task_type),
            "media_event_type": int(media_event_type),
            "media_type": int(media_type),
            "media_status": int(media_status),
            "channel_id": _decode_utf8_cstr(channel_id_raw),
            "stream_type": int(stream_type),
            "evidence_id": _decode_utf8_cstr(evidence_id_raw),
            "file_name": _decode_utf8_cstr(file_name_raw),
            "file_format": _decode_utf8_cstr(file_format_raw),
            "file_size_kb": int(file_size_kb),
            "capture_time_sec": int(capture_time_sec),
            "capture_time_msec": int(capture_time_msec),
            "target_batch_no": int(target_batch_no),
            "photo_interval_sec": int(photo_interval_sec),
            "video_interval_sec": int(video_interval_sec),
            "video_duration_sec": int(video_duration_sec),
            "enable_evidence": int(enable_evidence),
            "reserved0": int(reserved0),
            "media_access_path": _decode_utf8_cstr(media_access_path_raw),
            "snapshot_url": _decode_utf8_cstr(snapshot_url_raw),
            "reserved_hex": reserved_raw.hex(" "),
            "timestamp": common_ts or _iso_utc_now(),
            "raw_hex": payload[:STREAM_MEDIA_BUSINESS_LEN].hex(),
            "raw_len": STREAM_MEDIA_BUSINESS_LEN,
            "expected_raw_len": STREAM_MEDIA_BUSINESS_LEN,
        }

        if common_offset:
            protocol_type, version, packet_len, msg_type, seq, reserve, ts_0p1ms = struct.unpack(
                COMMON_HEADER_FMT, body[:COMMON_HEADER_LEN]
            )
            result.update(
                {
                    "protocol_type": int(protocol_type),
                    "protocol_version": int(version),
                    "packet_length": int(packet_len),
                    "msg_type": int(msg_type),
                    "msg_seq": int(seq),
                    "reserve": int(reserve),
                    "timestamp_0p1ms": int(ts_0p1ms),
                    "inner_proto21_hex": body[:COMMON_HEADER_LEN].hex(" "),
                    "decode_format": "stream_media_param_21_plus_869_fields",
                    "input_layout": "doc890",
                }
            )
        else:
            result.update(
                {
                    "decode_format": "stream_media_param_869_fields",
                    "input_layout": "doc869",
                }
            )

        return result

    return {"raw_hex": body.hex()}
