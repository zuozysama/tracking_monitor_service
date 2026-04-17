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
NAV_DOC35_LEN = 35
NAV_TOTAL_LEN = NAV_OUTER_V3_HEAD_LEN + NAV_DOC35_LEN
NAV_INNER_PROTO_HEAD_LEN = 21
NAV_FIELDS_LEN = 14
NAV_GEO_LSB_DEG = 180.0 / (2 ** 31)


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


def _parse_common_header(body: bytes) -> tuple[int, str | None]:
    # Common header from protocol doc:
    # protocol_type(4) + version(1) + length(2) + msg_type(1) + seq(4) + reserve(1) + ts(8)
    header_fmt = "<IBHBIBQ"
    header_size = struct.calcsize(header_fmt)
    if len(body) < header_size:
        return 0, None

    try:
        protocol_type, _ver, length, _msg_type, _seq, _reserve, ts_0p1ms = struct.unpack(
            header_fmt, body[:header_size]
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
    return header_size, ts_iso


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


def encode_topic_payload(topic: str, payload: dict) -> bytes:
    if topic == OWNSHIP_NAVIGATION_TOPIC:
        # 35-byte business packet:
        # 21-byte protocol header + 14-byte nav fields.
        protocol_type = _u32(payload.get("protocol_type", 0))
        version = _u16(payload.get("protocol_version", payload.get("version", 1))) & 0xFF
        packet_len = NAV_DOC35_LEN
        msg_type = _u16(payload.get("msg_type", 1)) & 0xFF
        seq = _u32(payload.get("msg_seq", payload.get("seq", 1)))
        reserve = _u16(payload.get("reserve", 0)) & 0xFF
        ts_0p1ms = _nav_timestamp_0p1ms_from_day_start(payload)

        platform_id = _u16(payload.get("platform_id", 0))
        speed_raw = _u16(round(float(payload.get("speed_mps", 0.0)) * 100.0))
        heading_raw = _u16(round(float(payload.get("heading_deg", 0.0)))) % 360
        lon_raw = _i32(round(float(payload.get("longitude", 0.0)) / NAV_GEO_LSB_DEG))
        lat_raw = _i32(round(float(payload.get("latitude", 0.0)) / NAV_GEO_LSB_DEG))

        return struct.pack(
            "<IBHBIBQHHHii",
            protocol_type,
            version,
            packet_len,
            msg_type,
            seq,
            reserve,
            ts_0p1ms,
            platform_id,
            speed_raw,
            heading_raw,
            lon_raw,
            lat_raw,
        )

    if topic == TARGET_PERCEPTION_TOPIC:
        # 21-byte common header + 2-byte target_count + 2-byte source_platform_id + N * 88-byte entries
        targets = payload.get("targets") or []
        source_platform_id = _u16(payload.get("source_platform_id", 0))

        protocol_type = _u32(payload.get("protocol_type", 0))
        version = _u16(payload.get("protocol_version", payload.get("version", 1))) & 0xFF
        msg_type = _u16(payload.get("msg_type", 1)) & 0xFF
        seq = _u32(payload.get("msg_seq", payload.get("seq", 1)))
        reserve = _u16(payload.get("reserve", 0)) & 0xFF
        ts_0p1ms = _nav_timestamp_0p1ms_from_day_start(payload)

        entry_fmt = "<HHIHHHHHiiHBBIBBB40sHHHBHH"
        entry_size = struct.calcsize(entry_fmt)  # 88
        packet_len = 21 + 2 + 2 + len(targets) * entry_size

        header = struct.pack(
            "<IBHBIBQ",
            protocol_type,
            version,
            packet_len,
            msg_type,
            seq,
            reserve,
            ts_0p1ms,
        )

        prefix = struct.pack("<HH", _u16(len(targets)), source_platform_id)

        body = bytearray()
        for item in targets:
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
        return struct.pack(
            "<64sBBBBBIIHHHB16s",
            _fit_ascii(str(payload.get("task_id") or ""), 64),
            _u16(payload.get("task_type", 0)) & 0xFF,
            _u16(payload.get("task_status", 0)) & 0xFF,
            _u16(payload.get("execution_phase", 0)) & 0xFF,
            _u16(payload.get("update_type", 0)) & 0xFF,
            _u16(payload.get("result_type", 0)) & 0xFF,
            _u32(payload.get("current_target_batch_no", 0)),
            _u32(payload.get("rel_range_m", 0)),
            _u16(round(float(payload.get("relative_bearing_deg", 0.0)) * 10)),
            _u16(round(float(payload.get("expected_speed", 0.0)) * 10)),
            _u16(payload.get("waypoint_count", 0)),
            _u16(payload.get("finish_reason", 0)) & 0xFF,
            b"\x00" * 16,
        )

    if topic == PREPLAN_RESULT_TOPIC:
        route = payload.get("planned_route") or []
        header = struct.pack(
            "<64sBH",
            _fit_ascii(str(payload.get("task_id") or ""), 64),
            _u16(payload.get("task_type", 7)) & 0xFF,
            _u16(payload.get("waypoint_count", len(route))),
        )
        body = bytearray()
        for waypoint in route:
            body.extend(
                struct.pack(
                    "<iiH",
                    _i32(round(float(waypoint.get("longitude", 0.0)) * 1e7)),
                    _i32(round(float(waypoint.get("latitude", 0.0)) * 1e7)),
                    _u16(round(float(waypoint.get("expected_speed", 0.0)) * 10)),
                )
            )
        return header + bytes(body)

    if topic == MANUAL_SELECTION_REQUEST_TOPIC:
        candidates = payload.get("candidate_targets") or []
        header = struct.pack(
            "<64sBH",
            _fit_ascii(str(payload.get("task_id") or ""), 64),
            _u16(payload.get("timeout_sec", 0)) & 0xFF,
            _u16(len(candidates)),
        )
        body = bytearray()
        for item in candidates[:8]:
            body.extend(
                struct.pack(
                    "<64sIHB",
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
            "<64s64sBH",
            _fit_ascii(str(payload.get("task_id") or ""), 64),
            _fit_ascii(str(payload.get("current_target_id") or ""), 64),
            _u16(payload.get("timeout_sec", 0)) & 0xFF,
            _u16(len(candidates)),
        )
        body = bytearray()
        for item in candidates[:8]:
            body.extend(
                struct.pack(
                    "<64sIHB",
                    _fit_ascii(str(item.get("target_id") or ""), 64),
                    _u32(item.get("target_batch_no", 0)),
                    _u16(item.get("target_type_code", 0)),
                    _u16(item.get("military_civil_attr", 0)) & 0xFF,
                )
            )
        return header + bytes(body)

    if topic == ELECTRO_OPTICAL_LINKAGE_CMD_TOPIC:
        return struct.pack(
            "<HIBBI16s",
            _u16(payload.get("task_type", 0)),
            _u32(payload.get("task_no", 1)),
            _u16(payload.get("task_status", 0)) & 0xFF,
            _u16(payload.get("dispatch_task_type", 1)) & 0xFF,
            _u32(payload.get("target_batch_no", 0)),
            _fit_ascii(str(payload.get("reserved_ext") or ""), 16),
        )

    if topic == STREAM_MEDIA_PARAM_TOPIC:
        return struct.pack(
            "<64sBBBB256s256s32s",
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
            # Compatible with historical input that still includes 16-byte V3 outer header.
            doc35 = raw_msg[NAV_OUTER_V3_HEAD_LEN:NAV_TOTAL_LEN]
            input_layout = "v3_16_plus_35"
        elif len(raw_msg) >= NAV_DOC35_LEN:
            doc35 = raw_msg[:NAV_DOC35_LEN]
            input_layout = "doc35"
        else:
            return {
                "raw_hex": raw_msg.hex(),
                "decode_error": (
                    f"raw NAV msg too short: got {len(raw_msg)} bytes, "
                    f"need at least {NAV_DOC35_LEN}"
                ),
            }

        nav14 = doc35[NAV_INNER_PROTO_HEAD_LEN:NAV_DOC35_LEN]
        if len(nav14) < NAV_FIELDS_LEN:
            return {
                "raw_hex": doc35.hex(),
                "decode_error": f"NAV14 too short: got {len(nav14)} bytes, need {NAV_FIELDS_LEN}",
            }

        uid = int.from_bytes(nav14[0:2], byteorder="little", signed=False)
        speed_raw = int.from_bytes(nav14[2:4], byteorder="little", signed=False)
        heading_raw = int.from_bytes(nav14[4:6], byteorder="little", signed=False)
        lon_raw = int.from_bytes(nav14[6:10], byteorder="little", signed=True)
        lat_raw = int.from_bytes(nav14[10:14], byteorder="little", signed=True)

        speed_mps = float(speed_raw) * 0.01
        heading_deg = float(heading_raw) % 360.0
        longitude = float(lon_raw) * NAV_GEO_LSB_DEG
        latitude = float(lat_raw) * NAV_GEO_LSB_DEG

        return {
            "format": "doc35_21_plus_14_fields",
            "offsets": {
                "uid": [21, 22],
                "speed_raw": [23, 24],
                "heading_raw": [25, 26],
                "lon_raw": [27, 30],
                "lat_raw": [31, 34],
            },
            "input_layout": input_layout,
            "platform_id": uid,
            "uid": uid,
            "raw_len": len(doc35),
            "expected_raw_len": NAV_DOC35_LEN,
            "input_raw_len": len(raw_msg),
            "speed_raw": speed_raw,
            "heading_raw": heading_raw,
            "lon_raw": lon_raw,
            "lat_raw": lat_raw,
            "speed_mps": speed_mps,
            "heading_deg": heading_deg,
            "longitude": longitude,
            "latitude": latitude,
            "inner_proto21_hex": doc35[:NAV_INNER_PROTO_HEAD_LEN].hex(" "),
            "nav14_hex": nav14.hex(" "),
            "doc35_hex": doc35.hex(" "),
            "raw_hex": doc35.hex(),
            "timestamp": _iso_utc_now(),
            "decode_format": "doc35_21_plus_14_fields",
        }

    if topic == TARGET_PERCEPTION_TOPIC:
        common_offset, common_ts = _parse_common_header(body)
        payload = body[common_offset:] if common_offset else body

        if len(payload) < 4:
            return {
                "raw_hex": body.hex(),
                "decode_error": f"target payload too short: got {len(payload)} bytes, need at least 4",
            }

        target_count, source_platform_id = struct.unpack("<HH", payload[:4])

        entry_fmt = "<HHIHHHHHiiHBBIBBB40sHHHBHH"
        entry_size = struct.calcsize(entry_fmt)  # 88

        expected_len = 4 + target_count * entry_size
        if len(payload) < expected_len:
            return {
                "raw_hex": body.hex(),
                "decode_error": (
                    f"target payload length mismatch: got {len(payload)} bytes, "
                    f"need at least {expected_len} for {target_count} targets"
                ),
            }

        targets = []
        offset = 4
        for _i in range(target_count):
            chunk = payload[offset : offset + entry_size]
            (
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

        return {
            "source_platform_id": int(source_platform_id),
            "target_count": int(target_count),
            "entry_size": entry_size,
            "targets": targets,
        }

    return {"raw_hex": body.hex()}
