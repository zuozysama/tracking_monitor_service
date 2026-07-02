from __future__ import annotations

import argparse
import json
import os
import sys
import time
from ctypes import POINTER, cast
from pathlib import Path
from typing import Any


DOMAIN_ID = 1
TYPE_NAME = "CSMXP_V3"
QOS_LIBRARY = "Library"
QOS_PROFILE = "BestEffort"
TOPICS = [
    "cc_lm_situation_generating.v1.target_track_all",
]

SDK_ROOT = "/app/thirdparty/ljdds/DDSCore3.0.1"
QOS_FILE = "/app/thirdparty/ljdds/DDSCore3.0.1/qosconf/example.xml"
LICENSE_FILE = "/app/thirdparty/ljdds/DDSCore3.0.1/ljddslicense.lic"
LIB_DIR = "/app/thirdparty/ljdds/DDSCore3.0.1/lib/ft2000KylinV10GFgcc9.3.0"


def _print_json(label: str, payload: Any) -> None:
    print(f"[{label}] {json.dumps(payload, ensure_ascii=False, default=str)}", flush=True)


def _path_status(path: str) -> dict[str, Any]:
    p = Path(path)
    return {
        "path": path,
        "exists": p.exists(),
        "is_file": p.is_file(),
        "is_dir": p.is_dir(),
    }


def _prepare_process_environment() -> None:
    # The script does not read external env configuration. It writes the values
    # required by LJDDS before importing the SDK.
    os.environ["LJDDSHOME"] = SDK_ROOT
    os.environ["LJDDS_HOME"] = SDK_ROOT
    os.environ["DDS_LICENSE_FILE"] = LICENSE_FILE
    os.environ["DDS_LIB_DIR"] = LIB_DIR
    old_ld_path = os.environ.get("LD_LIBRARY_PATH", "")
    if LIB_DIR not in old_ld_path.split(":"):
        os.environ["LD_LIBRARY_PATH"] = f"{LIB_DIR}:{old_ld_path}" if old_ld_path else LIB_DIR


def _safe_text(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)):
        text = bytes(value).decode("utf-8", errors="ignore")
    else:
        text = str(value)
    return text.split("\x00", 1)[0].strip()


def _load_ljdds_symbols() -> dict[str, Any]:
    sdk = __import__(
        "ljdds_python.csmxp_v3_interface.csmxp_v3",
        fromlist=["*"],
    )
    sdk_ext = __import__(
        "ljdds_python.csmxp_v3_interface.csmxp_v3ext",
        fromlist=["*"],
    )
    common_factory_mod = __import__(
        "ljdds_python.common.ljdds_commdp_factory",
        fromlist=["*"],
    )
    listener_mod = __import__(
        "ljdds_python.common.ljdds_basic_listener",
        fromlist=["*"],
    )

    factory_cls = (
        getattr(common_factory_mod, "LJDDSCommDpFactory", None)
        or getattr(sdk_ext, "LJDDSCommDpFactory", None)
        or getattr(sdk, "LJDDSCommDpFactory", None)
    )
    csmxp_v3 = getattr(sdk, "CSMXP_V3", None) or getattr(sdk_ext, "CSMXP_V3", None)
    csmxp_v3_msg_head = (
        getattr(sdk, "CSMXP_V3_MSG_HEAD", None)
        or getattr(sdk_ext, "CSMXP_V3_MSG_HEAD", None)
    )
    listener_base = getattr(listener_mod, "LJDDS_DRListener", None)

    missing = [
        name
        for name, value in {
            "LJDDSCommDpFactory": factory_cls,
            "CSMXP_V3": csmxp_v3,
            "CSMXP_V3_MSG_HEAD": csmxp_v3_msg_head,
            "LJDDS_DRListener": listener_base,
        }.items()
        if value is None
    ]
    if missing:
        raise RuntimeError(f"missing LJDDS symbols: {missing}")

    return {
        "factory_cls": factory_cls,
        "CSMXP_V3": csmxp_v3,
        "CSMXP_V3_MSG_HEAD": csmxp_v3_msg_head,
        "listener_base": listener_base,
    }


def run_probe(args: argparse.Namespace) -> None:
    _prepare_process_environment()
    topics = TOPICS
    received: list[dict[str, Any]] = []

    _print_json(
        "standalone_config",
        {
            "domain_id": DOMAIN_ID,
            "type_name": TYPE_NAME,
            "qos_library": QOS_LIBRARY,
            "qos_profile": QOS_PROFILE,
            "topics": topics,
            "listen_seconds": args.listen_seconds,
            "paths": {
                "SDK_ROOT": _path_status(SDK_ROOT),
                "QOS_FILE": _path_status(QOS_FILE),
                "LICENSE_FILE": _path_status(LICENSE_FILE),
                "LIB_DIR": _path_status(LIB_DIR),
            },
        },
    )

    symbols = _load_ljdds_symbols()
    factory_cls = symbols["factory_cls"]
    csmxp_v3 = symbols["CSMXP_V3"]
    csmxp_v3_msg_head = symbols["CSMXP_V3_MSG_HEAD"]
    listener_base = symbols["listener_base"]

    class ProbeListener(listener_base):
        def on_data_available(self, topic_name, type_name, sample, size, sample_info):
            topic_text = _safe_text(topic_name)
            type_name_text = _safe_text(type_name)
            event: dict[str, Any] = {
                "index": len(received) + 1,
                "topic": topic_text,
                "type_name": type_name_text,
                "expected_type_name": TYPE_NAME,
                "type_name_match": type_name_text == TYPE_NAME,
            }
            try:
                try:
                    sample_size = int(size)
                except Exception:
                    sample_size = 0
                event["sample_size"] = sample_size

                sample_obj = cast(sample, POINTER(csmxp_v3))
                event["src"] = int(sample_obj.contents.SRC)
                event["dst"] = int(sample_obj.contents.DST)

                msg = bytes(sample_obj.contents.MSG)
                head_size = int(csmxp_v3_msg_head.size())
                event["msg_buffer_len"] = len(msg)
                event["head_size"] = head_size

                header = csmxp_v3_msg_head()
                try:
                    header.unpack(msg[:head_size])
                    header_length = int(getattr(header, "length", 0))
                    total_len = header_length
                    len_fixup = "none"
                    if total_len <= 0 or total_len > len(msg):
                        total_len = min(len(msg), sample_size if sample_size > 0 else len(msg))
                        len_fixup = "from_size_or_msg_len"
                    raw_packet = msg[:total_len]
                    event["header_length_field"] = header_length
                    event["final_total_len"] = total_len
                    event["length_fixup"] = len_fixup
                    event["raw_hex_prefix"] = raw_packet[: args.raw_prefix_bytes].hex()
                except Exception as exc:
                    event["header_unpack_error"] = repr(exc)
                    event["raw_hex_prefix"] = msg[: args.raw_prefix_bytes].hex()
            except Exception as exc:
                event["callback_exception"] = repr(exc)

            received.append(event)
            _print_json("standalone_callback", event)

    factory = None
    dp = None
    dds = None
    try:
        factory = factory_cls.get_instance()
        factory.add_qos_profile(QOS_FILE)
        dp = factory.create_commdp(DOMAIN_ID)
        dds = dp.create_idl_interface(TYPE_NAME)
        listener = ProbeListener()

        for topic in topics:
            dds.sub_with_profile(topic, QOS_LIBRARY, QOS_PROFILE, listener)
            _print_json(
                "standalone_subscribed",
                {
                    "topic": topic,
                    "type_name": TYPE_NAME,
                    "domain_id": DOMAIN_ID,
                    "qos_library": QOS_LIBRARY,
                    "qos_profile": QOS_PROFILE,
                },
            )

        deadline = time.time() + max(0.0, float(args.listen_seconds))
        last_progress = 0.0
        while time.time() < deadline:
            time.sleep(min(1.0, max(0.05, deadline - time.time())))
            now = time.time()
            if args.progress and now - last_progress >= args.progress_interval:
                _print_json(
                    "standalone_progress",
                    {
                        "received_count": len(received),
                        "topics": topics,
                    },
                )
                last_progress = now
    finally:
        try:
            if dp is not None and dds is not None:
                dp.delete_idl_interface(dds)
        except Exception as exc:
            _print_json("standalone_cleanup_error", {"step": "delete_idl_interface", "error": repr(exc)})
        try:
            if factory is not None and dp is not None:
                factory.delete_commdp(dp)
        except Exception as exc:
            _print_json("standalone_cleanup_error", {"step": "delete_commdp", "error": repr(exc)})
        try:
            if factory is not None:
                factory.finalize_instance()
        except Exception as exc:
            _print_json("standalone_cleanup_error", {"step": "finalize_instance", "error": repr(exc)})

    _print_json(
        "standalone_summary",
        {
            "received_count": len(received),
            "received_by_topic": {
                topic: sum(1 for item in received if item.get("topic") == topic)
                for topic in topics
            },
            "events": received[: args.max_events],
            "hints": _build_hints(received),
        },
    )


def _build_hints(received: list[dict[str, Any]]) -> list[str]:
    if not received:
        return [
            "No callback was received by the standalone LJDDS probe.",
            "If the publisher is confirmed active, check DDS domain/topic/qos/type and container network discovery.",
            "This script subscribes with TypeName CSMXP_V3. If publisher TypeName is different, this probe will not receive data.",
        ]

    if any(item.get("type_name_match") is False for item in received):
        return [
            "Callback arrived but TypeName did not match the expected CSMXP_V3.",
            "Confirm publisher TypeName/IDL with the sender.",
        ]

    return [
        "Callback arrived. DDS communication path is working for the hardcoded parameters.",
        "If business parsing fails elsewhere, focus on payload format and parser mapping.",
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Standalone hardcoded LJDDS receive probe.")
    parser.add_argument("--listen-seconds", type=float, default=120.0)
    parser.add_argument("--progress", action="store_true")
    parser.add_argument("--progress-interval", type=float, default=5.0)
    parser.add_argument("--raw-prefix-bytes", type=int, default=128)
    parser.add_argument("--max-events", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    run_probe(parse_args())


if __name__ == "__main__":
    main()
