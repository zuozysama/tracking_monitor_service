#!/usr/bin/env python3

from __future__ import annotations

import argparse
import time
from ctypes import POINTER, cast
from typing import Optional, Tuple

from ljdds_python.common.ljdds_basic_listener import LJDDSCommDpFactory, LJDDS_DRListener
from ljdds_python.csmxp_v3_interface.csmxp_v3 import CSMXP_V3


DEFAULT_QOS_XML = "/app/thirdparty/ljdds/DDSCore3.0.1/qosconf/example.xml"
DEFAULT_TOPIC = "cc_lm_situation_generating.v1.target_track_all"
DEFAULT_LIBRARY = "Library"
DEFAULT_PROFILE = "BestEffort"
DEFAULT_TYPE_NAME = "CSMXP_V3"
DEFAULT_DOMAIN_ID = 1

PACKET_SIZE = 369
PACKET_LENGTH_OFFSET = 5
FIELD_9_OFFSET = 21
FIELD_51_OFFSET = 301
BCD_FIELD_SIZE = 4


def _extract_raw_message(sample, callback_size: int) -> bytes:
    typed_sample = cast(sample, POINTER(CSMXP_V3))
    raw_message = bytes(typed_sample.contents.MSG)
    if 0 < callback_size <= len(raw_message):
        return raw_message[:callback_size]
    return raw_message


def _declared_packet_size(candidate: bytes) -> int:
    end = PACKET_LENGTH_OFFSET + 2
    if len(candidate) < end:
        return 0
    return int.from_bytes(candidate[PACKET_LENGTH_OFFSET:end], byteorder="big", signed=False)


def _extract_369_body(raw_message: bytes, outer_header_size: int) -> Tuple[Optional[bytes], Optional[int]]:
    candidate_offsets = [0, 16, outer_header_size]
    seen_offsets = set()
    for offset in candidate_offsets:
        if offset in seen_offsets or offset < 0:
            continue
        seen_offsets.add(offset)
        candidate = raw_message[offset:]
        if len(candidate) >= PACKET_SIZE and _declared_packet_size(candidate) == PACKET_SIZE:
            return candidate[:PACKET_SIZE], offset

    max_scan_offset = min(64, max(0, len(raw_message) - PACKET_SIZE))
    for offset in range(max_scan_offset + 1):
        if offset in seen_offsets:
            continue
        candidate = raw_message[offset:]
        if _declared_packet_size(candidate) == PACKET_SIZE:
            return candidate[:PACKET_SIZE], offset
    return None, None


def _bcd_details(raw: bytes) -> Tuple[int, str, bool]:
    valid = True
    visible_nibbles = []
    parsed_digits = []
    for byte in raw:
        for nibble in ((byte >> 4) & 0x0F, byte & 0x0F):
            if nibble <= 9:
                digit = str(nibble)
                visible_nibbles.append(digit)
                parsed_digits.append(digit)
            else:
                visible_nibbles.append(f"{nibble:X}")
                valid = False

    parsed_text = "".join(parsed_digits).lstrip("0")
    value = int(parsed_text or "0")
    return value, "".join(visible_nibbles), valid


def _print_diagnostics(raw_message: bytes, body: Optional[bytes], body_offset: Optional[int]) -> None:
    print("\n" + "=" * 96, flush=True)
    print(f"[1/5] full_raw_hex ({len(raw_message)} bytes): {raw_message.hex(' ').upper()}", flush=True)

    if body is None:
        reason = f"369-byte body not found; received={len(raw_message)} bytes"
        print(f"[2/5] field_9_raw_hex: UNAVAILABLE ({reason})", flush=True)
        print("[3/5] field_9_bcd_value: UNAVAILABLE", flush=True)
        print(f"[4/5] field_51_raw_hex: UNAVAILABLE ({reason})", flush=True)
        print("[5/5] field_51_bcd_value: UNAVAILABLE", flush=True)
        return

    field_9_raw = body[FIELD_9_OFFSET : FIELD_9_OFFSET + BCD_FIELD_SIZE]
    field_51_raw = body[FIELD_51_OFFSET : FIELD_51_OFFSET + BCD_FIELD_SIZE]
    field_9_value, field_9_digits, field_9_valid = _bcd_details(field_9_raw)
    field_51_value, field_51_digits, field_51_valid = _bcd_details(field_51_raw)

    field_51_system_node = field_51_digits[:4] if field_51_valid else "UNAVAILABLE"
    field_51_local_batch = field_51_digits[4:] if field_51_valid else "UNAVAILABLE"
    layout = f"body_offset={body_offset}, body_size={len(body)}"

    print(f"[2/5] field_9_raw_hex ({layout}): {field_9_raw.hex(' ').upper()}", flush=True)
    print(
        f"[3/5] field_9_bcd_value: {field_9_value} "
        f"(digits={field_9_digits}, valid_bcd={field_9_valid})",
        flush=True,
    )
    print(f"[4/5] field_51_raw_hex ({layout}): {field_51_raw.hex(' ').upper()}", flush=True)
    print(
        f"[5/5] field_51_bcd_value: {field_51_value} "
        f"(digits={field_51_digits}, valid_bcd={field_51_valid}, "
        f"system_node_code={field_51_system_node}, local_batch_no={field_51_local_batch})",
        flush=True,
    )


class BatchFieldListener(LJDDS_DRListener):
    def __init__(self, outer_header_size: int) -> None:
        super().__init__()
        self.outer_header_size = outer_header_size
        self.receive_count = 0

    def on_data_available(self, topic_name, type_name, sample, size, sample_info):
        self.receive_count += 1
        try:
            callback_size = int(size)
        except Exception:
            callback_size = 0

        try:
            raw_message = _extract_raw_message(sample, callback_size)
            body, body_offset = _extract_369_body(raw_message, self.outer_header_size)
            _print_diagnostics(raw_message, body, body_offset)
        except Exception as exc:
            print(
                f"[receive_error] count={self.receive_count} "
                f"error={type(exc).__name__}: {exc}",
                flush=True,
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Listen for target_track_all and print raw field 9/51 BCD diagnostics"
    )
    parser.add_argument("--qos-xml", default=DEFAULT_QOS_XML)
    parser.add_argument("--library", default=DEFAULT_LIBRARY)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--type-name", default=DEFAULT_TYPE_NAME)
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    parser.add_argument("--domain-id", type=int, default=DEFAULT_DOMAIN_ID)
    parser.add_argument("--outer-header-size", type=int, default=16)
    args = parser.parse_args()

    print(
        f"[listen_start] topic={args.topic} domain={args.domain_id} "
        f"type={args.type_name} qos={args.library}::{args.profile} qos_xml={args.qos_xml}",
        flush=True,
    )

    listener = BatchFieldListener(args.outer_header_size)
    factory = None
    participant = None
    dds_interface = None
    try:
        factory = LJDDSCommDpFactory.get_instance()
        factory.add_qos_profile(args.qos_xml)
        participant = factory.create_commdp(args.domain_id)
        dds_interface = participant.create_idl_interface(args.type_name)
        dds_interface.sub_with_profile(
            args.topic,
            args.library,
            args.profile,
            listener,
        )
        print("[listen_ready] waiting for DDS messages; press Ctrl+C to stop", flush=True)
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[listen_stop] interrupted by user", flush=True)
        return 0
    finally:
        if participant is not None and dds_interface is not None:
            try:
                participant.delete_idl_interface(dds_interface)
            except Exception:
                pass
        if factory is not None and participant is not None:
            try:
                factory.delete_commdp(participant)
            except Exception:
                pass
        if factory is not None:
            try:
                factory.finalize_instance()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
