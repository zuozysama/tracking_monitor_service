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
    header_fmt = "<IBHBI BII"
    header_size = struct.calcsize(header_fmt)
    if len(body) < header_size:
        return 0, None

    try:
        protocol_type, _ver, length, _msg_type, _seq, _reserve, ts_sec, ts_sub_ms_x1e6 = struct.unpack(
            header_fmt, body[:header_size]
        )
    except Exception:
        return 0, None

    # Keep permissive checks to avoid breaking existing compact packets.
    if protocol_type != 0:
        return 0, None
    if length and length > len(body):
        return 0, None

    try:
        # Doc says lower 4 bytes carry millisecond value * 10^6.
        ts_value = float(ts_sec) + float(ts_sub_ms_x1e6) / 1e9
        ts_iso = datetime.fromtimestamp(ts_value, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        ts_iso = None
    return header_size, ts_iso


def encode_topic_payload(topic: str, payload: dict) -> bytes:
    # NOTE: little-endian is used here for engineering integration.
    if topic == OWNSHIP_NAVIGATION_TOPIC:
        platform_id = _u16(payload.get("platform_id", 0))
        speed_x100 = _u16(round(float(payload.get("speed_mps", 0.0)) * 100))
        heading_x10 = _u16(round(float(payload.get("heading_deg", 0.0)) * 10))
        longitude_e7 = _i32(round(float(payload.get("longitude", 0.0)) * 1e7))
        latitude_e7 = _i32(round(float(payload.get("latitude", 0.0)) * 1e7))
        return struct.pack("<HHHii8s", platform_id, speed_x100, heading_x10, longitude_e7, latitude_e7, b"\x00" * 8)

    if topic == TARGET_PERCEPTION_TOPIC:
        source_platform_id = _u16(payload.get("source_platform_id", 0))
        targets = payload.get("targets") or []
        head = struct.pack("<HH4s", _u16(len(targets)), source_platform_id, b"\x00" * 4)
        body = bytearray()
        for item in targets:
            target_id = _fit_ascii(str(item.get("target_id") or ""), 64)
            entry = struct.pack(
                "<IHIHHiiHBB64s6s",
                _u32(item.get("target_batch_no", 0)),
                _u16(round(float(item.get("target_bearing_deg", 0.0)) * 10)),
                _u32(item.get("target_distance_m", 0)),
                _u16(round(float(item.get("target_absolute_speed_mps", 0.0)) * 10)),
                _u16(round(float(item.get("target_absolute_heading_deg", 0.0)) * 10)),
                _i32(round(float(item.get("target_longitude", 0.0)) * 1e7)),
                _i32(round(float(item.get("target_latitude", 0.0)) * 1e7)),
                _u16(item.get("target_type_code", 0)),
                _u16(item.get("military_civil_attr", 0)) & 0xFF,
                _u16(item.get("threat_level", 0)) & 0xFF,
                target_id,
                b"\x00" * 6,
            )
            body.extend(entry)
        return head + bytes(body)

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
            _u16(payload.get("task_type", 5)) & 0xFF,
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
    ownship_fmt = "<HHHii8s"
    ownship_size = struct.calcsize(ownship_fmt)
    if topic == OWNSHIP_NAVIGATION_TOPIC:
        common_offset, common_ts = _parse_common_header(body)
        payload = body[common_offset:] if common_offset else body

        # Doc-aligned nav payload (without common header).
        # platform_id + ground_speed + course + vx/vy/vz + heading + lon + lat + angular vel +
        # ax/ay/az + angular acc + roll + pitch + heave
        nav_full_fmt = "<HHHhhhHiihhhhhhhh"
        nav_full_size = struct.calcsize(nav_full_fmt)
        if len(payload) >= nav_full_size:
            (
                platform_id,
                speed_x100,
                heading_x100,
                _vx_x100,
                _vy_x100,
                _vz_x100,
                _bow_heading_x100,
                lon_e7,
                lat_e7,
                _ang_vel_x100,
                _ax_x10,
                _ay_x10,
                _az_x10,
                _ang_acc_x100,
                _roll_x10,
                _pitch_x10,
                _heave_x10,
            ) = struct.unpack(nav_full_fmt, payload[:nav_full_size])
            return {
                "platform_id": platform_id,
                "speed_mps": speed_x100 / 100.0,
                "heading_deg": heading_x100 / 100.0,
                "longitude": lon_e7 / 1e7,
                "latitude": lat_e7 / 1e7,
                "timestamp": common_ts or _iso_utc_now(),
            }

        # Backward-compatible compact payload.
        if len(payload) < ownship_size:
            return {"raw_hex": body.hex(), "decode_error": f"ownship body too short: {len(payload)}<{ownship_size}"}
        platform_id, speed_x100, heading_x10, lon_e7, lat_e7, _ = struct.unpack(ownship_fmt, payload[:ownship_size])
        return {
            "platform_id": platform_id,
            "speed_mps": speed_x100 / 100.0,
            "heading_deg": heading_x10 / 10.0,
            "longitude": lon_e7 / 1e7,
            "latitude": lat_e7 / 1e7,
            "timestamp": common_ts or _iso_utc_now(),
        }

    if topic == TARGET_PERCEPTION_TOPIC:
        common_offset, common_ts = _parse_common_header(body)
        payload = body[common_offset:] if common_offset else body

        # Doc-aligned packet:
        # count(2) + source_platform_id(2) + repeated target entries (88 bytes each).
        if len(payload) >= 4:
            target_count, source_platform_id = struct.unpack("<HH", payload[:4])
            targets = []
            offset = 4
            doc_entry_fmt = "<HHIHHHHHiiHBBIbbb40sHHHbHH"
            doc_entry_size = struct.calcsize(doc_entry_fmt)
            if len(payload) >= offset + doc_entry_size:
                for _i in range(target_count):
                    if len(payload) < offset + doc_entry_size:
                        break
                    (
                        batch_no,
                        bearing_x10,
                        distance_m,
                        _height_x10,
                        abs_speed_x10,
                        abs_heading_x10,
                        _rel_speed_x10,
                        _rel_heading_x10,
                        lon_e7,
                        lat_e7,
                        _qt_value,
                        _coord_sys,
                        _is_simulated,
                        _target_ts_sub,
                        _position_attr,
                        target_type_code,
                        military_civil_attr,
                        target_name_raw,
                        _target_len_x10,
                        _target_width_x10,
                        _target_height_x10,
                        threat_level,
                        _rcs_x10,
                        _custom2,
                    ) = struct.unpack(doc_entry_fmt, payload[offset : offset + doc_entry_size])
                    target_name = _decode_gb2312_cstr(target_name_raw)
                    targets.append(
                        {
                            "source_platform_id": source_platform_id,
                            "target_id": f"target-{batch_no}",
                            "target_batch_no": int(batch_no),
                            "target_bearing_deg": bearing_x10 / 10.0,
                            "target_distance_m": float(distance_m),
                            "target_absolute_speed_mps": abs_speed_x10 / 10.0,
                            "target_absolute_heading_deg": abs_heading_x10 / 10.0,
                            "target_longitude": lon_e7 / 1e7,
                            "target_latitude": lat_e7 / 1e7,
                            "target_type_code": int(target_type_code),
                            "military_civil_attr": int(military_civil_attr),
                            "threat_level": int(threat_level) if threat_level >= 0 else None,
                            "target_name": target_name or None,
                            "timestamp": common_ts or _iso_utc_now(),
                            "active": True,
                        }
                    )
                    offset += doc_entry_size

                if targets:
                    return {
                        "source_platform_id": source_platform_id,
                        "target_count": len(targets),
                        "targets": targets,
                    }

        # Backward-compatible compact payload.
        if len(payload) >= 8:
            target_count, source_platform_id, _ = struct.unpack("<HH4s", payload[:8])
            targets = []
            offset = 8
            entry_fmt = "<IHIHHiiHBB64s6s"
            entry_size = struct.calcsize(entry_fmt)
            for _i in range(target_count):
                if len(payload) < offset + entry_size:
                    break
                (
                    batch_no,
                    bearing_x10,
                    distance_m,
                    speed_x10,
                    heading_x10,
                    lon_e7,
                    lat_e7,
                    type_code,
                    military,
                    threat,
                    target_id_raw,
                    _r,
                ) = struct.unpack(entry_fmt, payload[offset : offset + entry_size])
                target_id = target_id_raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
                targets.append(
                    {
                        "source_platform_id": source_platform_id,
                        "target_id": target_id or f"target-{batch_no}",
                        "target_batch_no": batch_no,
                        "target_bearing_deg": bearing_x10 / 10.0,
                        "target_distance_m": float(distance_m),
                        "target_absolute_speed_mps": speed_x10 / 10.0,
                        "target_absolute_heading_deg": heading_x10 / 10.0,
                        "target_longitude": lon_e7 / 1e7,
                        "target_latitude": lat_e7 / 1e7,
                        "target_type_code": type_code,
                        "military_civil_attr": military,
                        "threat_level": threat,
                        "timestamp": common_ts or _iso_utc_now(),
                        "active": True,
                    }
                )
                offset += entry_size

            return {
                "source_platform_id": source_platform_id,
                "target_count": len(targets),
                "targets": targets,
            }

    return {"raw_hex": body.hex()}
