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

    if protocol_type != 0:
        return 0, None
    if length and length > len(body):
        return 0, None

    try:
        ts_value = float(ts_sec) + float(ts_sub_ms_x1e6) / 1e9
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
    # Lowest significant bit is 0.1ms.
    ticks = int(round(delta.total_seconds() * 10000.0))
    return max(0, ticks)


def encode_topic_payload(topic: str, payload: dict) -> bytes:
    # 这里只保留你原本其他 topic 的编码逻辑。
    # 导航 topic 的 encode 当前仍是你原来的工程内紧凑格式；
    # 本次修正重点是“严格按 dds_listen_nav_test2.py 解码导航消息”。
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
    if topic == OWNSHIP_NAVIGATION_TOPIC:
        # 严格对齐 dds_listen_nav_test2.py：
        # 输入必须是完整 raw MSG = 16-byte V3 head + DOC35(35 bytes) + optional tail
        raw_msg = body

        if len(raw_msg) < NAV_TOTAL_LEN:
            return {
                "raw_hex": raw_msg.hex(),
                "decode_error": (
                    f"raw MSG too short for 16+35 layout: got {len(raw_msg)} bytes, "
                    f"need at least {NAV_TOTAL_LEN}"
                ),
            }

        doc35 = raw_msg[NAV_OUTER_V3_HEAD_LEN:NAV_TOTAL_LEN]
        nav14 = raw_msg[NAV_OUTER_V3_HEAD_LEN + NAV_INNER_PROTO_HEAD_LEN:NAV_TOTAL_LEN]
        if len(nav14) < NAV_FIELDS_LEN:
            return {
                "raw_hex": raw_msg.hex(),
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
            "format": "v3_16_plus_35_shifted_fields",
            "offsets": {
                "uid": [37, 38],
                "speed_raw": [39, 40],
                "heading_raw": [41, 42],
                "lon_raw": [43, 46],
                "lat_raw": [47, 50],
            },
            "platform_id": uid,
            "uid": uid,
            "raw_len": len(raw_msg),
            "expected_raw_len": NAV_TOTAL_LEN,
            "speed_raw": speed_raw,
            "heading_raw": heading_raw,
            "lon_raw": lon_raw,
            "lat_raw": lat_raw,
            "speed_mps": speed_mps,
            "heading_deg": heading_deg,
            "longitude": longitude,
            "latitude": latitude,
            "inner_proto21_hex": raw_msg[NAV_OUTER_V3_HEAD_LEN : NAV_OUTER_V3_HEAD_LEN + NAV_INNER_PROTO_HEAD_LEN].hex(" "),
            "nav14_hex": nav14.hex(" "),
            "doc35_prefix_5bytes_hex": doc35[0:5].hex(" "),
            "doc35_hex": doc35.hex(" "),
            "raw_hex": raw_msg.hex(),
            "timestamp": _iso_utc_now(),
            "decode_format": "v3_16_plus_35_shifted_fields",
        }

    if topic == TARGET_PERCEPTION_TOPIC:
        common_offset, common_ts = _parse_common_header(body)
        payload = body[common_offset:] if common_offset else body

        if len(payload) >= 4:
            target_count, source_platform_id = struct.unpack("<HH", payload[:4])
            targets = []
            offset = 4
            doc_entry_formats = [
                ("<HHIHHHHHiiHBBIbHb40sHHHbHH", "u16"),
                ("<HHIHHHHHiiHBBIbbb40sHHHbHH", "i8"),
            ]
            for doc_entry_fmt, target_type_mode in doc_entry_formats:
                doc_entry_size = struct.calcsize(doc_entry_fmt)
                if len(payload) < offset + doc_entry_size:
                    continue
                if len(payload) < offset + doc_entry_size * max(1, target_count):
                    continue

                targets = []
                offset_local = offset
                for _i in range(target_count):
                    if len(payload) < offset_local + doc_entry_size:
                        break
                    unpacked = struct.unpack(doc_entry_fmt, payload[offset_local : offset_local + doc_entry_size])
                    if target_type_mode == "i8":
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
                            target_ts_raw,
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
                        ) = unpacked
                    else:
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
                            target_ts_raw,
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
                        ) = unpacked
                    target_name = _decode_gb2312_cstr(target_name_raw)
                    target_generated_ts = _format_target_generated_ts(common_ts, int(target_ts_raw))
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
                            "target_generated_timestamp_raw": int(target_ts_raw),
                            "target_generated_timestamp": target_generated_ts,
                            "timestamp": common_ts or _iso_utc_now(),
                            "active": True,
                        }
                    )
                    offset_local += doc_entry_size

                if targets:
                    return {
                        "source_platform_id": source_platform_id,
                        "target_count": len(targets),
                        "targets": targets,
                    }

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
