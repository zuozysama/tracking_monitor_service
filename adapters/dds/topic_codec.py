from __future__ import annotations

import struct
from datetime import datetime
from typing import Any

from domain.dds_contract import OWNSHIP_NAVIGATION_TOPIC, TARGET_PERCEPTION_TOPIC, TASK_UPDATE_TOPIC


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


def encode_topic_payload(topic: str, payload: dict) -> bytes:
    # NOTE: little-endian is used here for engineering联调; if vendor ICD requires big-endian,
    # switch struct format from '<' to '>' in each pack call.
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

    return str(payload).encode("utf-8")


def decode_topic_payload(topic: str, body: bytes) -> dict:
    ownship_fmt = "<HHHii8s"
    ownship_size = struct.calcsize(ownship_fmt)
    if topic == OWNSHIP_NAVIGATION_TOPIC:
        if len(body) < ownship_size:
            return {"raw_hex": body.hex(), "decode_error": f"ownship body too short: {len(body)}<{ownship_size}"}
        platform_id, speed_x100, heading_x10, lon_e7, lat_e7, _ = struct.unpack(ownship_fmt, body[:ownship_size])
        return {
            "platform_id": platform_id,
            "speed_mps": speed_x100 / 100.0,
            "heading_deg": heading_x10 / 10.0,
            "longitude": lon_e7 / 1e7,
            "latitude": lat_e7 / 1e7,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    if topic == TARGET_PERCEPTION_TOPIC and len(body) >= 8:
        target_count, source_platform_id, _ = struct.unpack("<HH4s", body[:8])
        targets = []
        offset = 8
        entry_fmt = "<IHIHHiiHBB64s6s"
        entry_size = struct.calcsize(entry_fmt)
        for _i in range(target_count):
            if len(body) < offset + entry_size:
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
            ) = struct.unpack(entry_fmt, body[offset : offset + entry_size])
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
                    "timestamp": datetime.utcnow().isoformat() + "Z",
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
