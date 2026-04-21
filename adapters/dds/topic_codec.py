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
TASK_UPDATE_BUSINESS_FMT = ">64sBBBBBIIHHHB16s"
TASK_UPDATE_BUSINESS_LEN = struct.calcsize(TASK_UPDATE_BUSINESS_FMT)


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


def _nav_timestamp_parts(payload: dict[str, Any]) -> tuple[int, int]:
    sec_raw = payload.get("timestamp_sec", payload.get("ts_sec"))
    subsec_raw = payload.get(
        "timestamp_millisecond_raw",
        payload.get("timestamp_ms_raw", payload.get("ts_millisecond_raw")),
    )

    if sec_raw is not None and subsec_raw is not None:
        return _u32(sec_raw), _u32(subsec_raw)

    now = datetime.now(timezone.utc)
    return int(now.timestamp()), now.microsecond * 1000


def _nav_timestamp_iso(sec_raw: int, subsec_raw: int) -> str | None:
    try:
        ts = float(sec_raw) + float(subsec_raw) / 1_000_000_000.0
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
        header = struct.pack(
            ">64sBH",
            _fit_ascii(str(payload.get("task_id") or ""), 64),
            _u16(payload.get("timeout_sec", 0)) & 0xFF,
            _u16(len(candidates)),
        )
        body = bytearray()
        for item in candidates[:8]:
            body.extend(
                struct.pack(
                    ">64sIHB",
                    _fit_ascii(str(item.get("target_id") or ""), 64),
                    _u32(item.get("target_batch_no", 0)),
                    _u16(item.get("target_type_code", 0)),
                    _u16(item.get("military_civil_attr", 0)) & 0xFF,
                )
            )
        return header + bytes(body)

    if topic == MANUAL_SWITCH_REQUEST_TOPIC:
        candidates = payload.get("new_candidate_targets") or []
        header = struct.pack(
            ">64s64sBH",
            _fit_ascii(str(payload.get("task_id") or ""), 64),
            _fit_ascii(str(payload.get("current_target_id") or ""), 64),
            _u16(payload.get("timeout_sec", 0)) & 0xFF,
            _u16(len(candidates)),
        )
        body = bytearray()
        for item in candidates[:8]:
            body.extend(
                struct.pack(
                    ">64sIHB",
                    _fit_ascii(str(item.get("target_id") or ""), 64),
                    _u32(item.get("target_batch_no", 0)),
                    _u16(item.get("target_type_code", 0)),
                    _u16(item.get("military_civil_attr", 0)) & 0xFF,
                )
            )
        return header + bytes(body)

    if topic == ELECTRO_OPTICAL_LINKAGE_CMD_TOPIC:
        return struct.pack(
            ">HIBBI16s",
            _u16(payload.get("task_type", 0)),
            _u32(payload.get("task_no", 1)),
            _u16(payload.get("task_status", 0)) & 0xFF,
            _u16(payload.get("dispatch_task_type", 1)) & 0xFF,
            _u32(payload.get("target_batch_no", 0)),
            _fit_ascii(str(payload.get("reserved_ext") or ""), 16),
        )

    if topic == STREAM_MEDIA_PARAM_TOPIC:
        return struct.pack(
            ">64sBBBB256s256s32s",
            _fit_ascii(str(payload.get("task_id") or ""), 64),
            _u16(payload.get("task_type", 0)) & 0xFF,
            _u16(payload.get("media_event_type", 0)) & 0xFF,
            _u16(payload.get("media_type", 0)) & 0xFF,
            _u16(payload.get("media_status", 0)) & 0xFF,
            _fit_ascii(str(payload.get("media_access_path") or ""), 256),
            _fit_ascii(str(payload.get("snapshot_url") or ""), 256),
            b"\x00" * 32,
        )

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

    return {"raw_hex": body.hex()}
