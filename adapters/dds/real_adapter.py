from __future__ import annotations

from ctypes import POINTER, cast
from typing import Callable

from adapters.dds.base import DdsAdapter
from adapters.dds.config import DdsRuntimeConfig
from adapters.dds.topic_codec import decode_topic_payload, encode_topic_payload
from domain.dds_contract import OWNSHIP_NAVIGATION_TOPIC
from store.collaboration_store import collaboration_store
from utils.time_utils import utc_now


class RealLjdssAdapter(DdsAdapter):
    def __init__(self, cfg: DdsRuntimeConfig) -> None:
        self.cfg = cfg
        self._started = False
        self._sdk_loaded = False
        self._load_error = ""
        self._sdk = None
        self._sdk_ext = None
        self._common_factory_mod = None
        self._listener_mod = None
        self._factory_cls = None
        self._CSMXP_V3 = None
        self._CSMXP_V3_MSG_HEAD = None
        self._addressof = None
        self._memmove = None
        self._factory = None
        self._dp = None
        self._dds = None
        self._dr_listener = None
        self._pub_topics: set[str] = set()
        self._sub_topics: set[str] = set()
        self._sub_handlers: dict[str, list[Callable[[dict], None]]] = {}
        self._seq = 0
        self._qos_profile = cfg.qos_profile or "BestEffort"
        self._try_load_sdk()

    def _log(
        self,
        topic: str,
        payload: dict,
        adapter: str,
        reason: str = "",
        wire_length: int = 0,
        raw_hex: str = "",
        body_hex: str = "",
    ) -> None:
        item = {
            "topic": topic,
            "payload": payload,
            "publish_time": utc_now(),
            "adapter": adapter,
        }
        if reason:
            item["reason"] = reason
        if wire_length:
            item["wire_length"] = wire_length
        if raw_hex:
            item["raw_hex"] = raw_hex
        if body_hex:
            item["body_hex"] = body_hex
        collaboration_store.append_dds_publish_log(item)

    def _log_subscribe(
        self,
        topic: str,
        decoded: dict,
        src: int,
        dst: int,
        raw_hex: str,
        body_hex: str,
        type_name: str,
        sample_size: int,
    ) -> None:
        collaboration_store.append_dds_subscribe_log(
            {
                "topic": topic,
                "type_name": type_name,
                "src": src,
                "dst": dst,
                "sample_size": sample_size,
                "raw_hex": raw_hex,
                "body_hex": body_hex,
                "decoded": decoded,
                "receive_time": utc_now(),
            }
        )

    def _try_load_sdk(self) -> None:
        try:
            self._sdk = __import__(
                "ljdds_python.csmxp_v3_interface.csmxp_v3",
                fromlist=["*"],
            )
            self._sdk_ext = __import__(
                "ljdds_python.csmxp_v3_interface.csmxp_v3ext",
                fromlist=["*"],
            )
            self._common_factory_mod = __import__(
                "ljdds_python.common.ljdds_commdp_factory",
                fromlist=["*"],
            )
            self._listener_mod = __import__(
                "ljdds_python.common.ljdds_basic_listener",
                fromlist=["*"],
            )

            self._factory_cls = (
                getattr(self._common_factory_mod, "LJDDSCommDpFactory", None)
                or getattr(self._sdk_ext, "LJDDSCommDpFactory", None)
                or getattr(self._sdk, "LJDDSCommDpFactory", None)
            )
            self._CSMXP_V3 = (
                getattr(self._sdk, "CSMXP_V3", None)
                or getattr(self._sdk_ext, "CSMXP_V3", None)
            )
            self._CSMXP_V3_MSG_HEAD = (
                getattr(self._sdk, "CSMXP_V3_MSG_HEAD", None)
                or getattr(self._sdk_ext, "CSMXP_V3_MSG_HEAD", None)
            )
            self._addressof = (
                getattr(self._sdk, "addressof", None)
                or getattr(self._sdk_ext, "addressof", None)
            )
            self._memmove = (
                getattr(self._sdk, "memmove", None)
                or getattr(self._sdk_ext, "memmove", None)
            )

            if any(
                x is None
                for x in (
                    self._factory_cls,
                    self._CSMXP_V3,
                    self._CSMXP_V3_MSG_HEAD,
                    self._addressof,
                    self._memmove,
                )
            ):
                raise RuntimeError("required LJDDS symbols not found in imported modules")

            self._sdk_loaded = True
        except Exception as exc:
            self._sdk_loaded = False
            self._load_error = str(exc)

    def _build_listener(self):
        if self._dr_listener is not None:
            return self._dr_listener

        base_cls = getattr(self._listener_mod, "LJDDS_DRListener")
        CSMXP_V3 = self._CSMXP_V3
        CSMXP_V3_MSG_HEAD = self._CSMXP_V3_MSG_HEAD

        outer = self

        def _safe_text(value) -> str:
            if isinstance(value, (bytes, bytearray)):
                text = bytes(value).decode("utf-8", errors="ignore")
            else:
                text = str(value)
            # SDKs may pass fixed-length C strings with trailing nulls/spaces.
            return text.split("\x00", 1)[0].strip()

        class _DRListener(base_cls):
            def on_data_available(self, topic_name, type_name, sample, size, sample_info):
                topic = "__unknown__"
                type_name_text = "__unknown__"
                sample_size = 0
                try:
                    topic = _safe_text(topic_name)
                    type_name_text = _safe_text(type_name)
                    try:
                        sample_size = int(size)
                    except Exception:
                        sample_size = 0

                    type_name_mismatch = type_name_text != "CSMXP_V3"
                    if type_name_mismatch:
                        outer._log_subscribe(
                            topic=topic,
                            decoded={
                                "listener_warning": True,
                                "warning_reason": "type_name_mismatch_but_continue",
                                "expected_type_name": "CSMXP_V3",
                                "actual_type_name": type_name_text,
                                "actual_type_name_repr": repr(type_name),
                            },
                            src=-1,
                            dst=-1,
                            raw_hex="",
                            body_hex="",
                            type_name=type_name_text,
                            sample_size=sample_size,
                        )

                    sample_obj = cast(sample, POINTER(CSMXP_V3))
                    msg = bytes(sample_obj.contents.MSG)

                    head_size = CSMXP_V3_MSG_HEAD.size()
                    header = CSMXP_V3_MSG_HEAD()
                    try:
                        header.unpack(msg[0:head_size])
                    except Exception as exc:
                        outer._log_subscribe(
                            topic=topic,
                            decoded={
                                "listener_skipped": True,
                                "skip_reason": "header_unpack_error",
                                "error": str(exc),
                                "msg_len": len(msg),
                                "head_size": int(head_size),
                                "head_hex_prefix": msg[: min(len(msg), head_size)].hex(),
                            },
                            src=int(sample_obj.contents.SRC),
                            dst=int(sample_obj.contents.DST),
                            raw_hex="",
                            body_hex="",
                            type_name=type_name_text,
                            sample_size=sample_size,
                        )
                        return

                    total_len = int(getattr(header, "length", 0))
                    len_fixup = "none"
                    if total_len <= head_size or total_len > len(msg):
                        size_len = sample_size if sample_size > 0 else len(msg)
                        total_len = min(len(msg), size_len)
                        len_fixup = "from_size_or_msg_len"

                    raw_packet = msg[:total_len]
                    body = raw_packet[0:total_len]

                    decode_input = body
                    decoded = decode_topic_payload(topic, decode_input)

                    if isinstance(decoded, dict):
                        decoded.setdefault("src", int(sample_obj.contents.SRC))
                        decoded.setdefault("dst", int(sample_obj.contents.DST))
                        decoded.setdefault(
                            "listener_debug",
                            {
                                "callback_topic": topic,
                                "callback_type_name": type_name_text,
                                "type_name_mismatch": bool(type_name_mismatch),
                                "sample_size": sample_size,
                                "msg_buffer_len": len(msg),
                                "head_size": int(head_size),
                                "header_length_field": int(getattr(header, "length", 0)),
                                "final_total_len": int(total_len),
                                "length_fixup": len_fixup,
                            },
                        )

                    outer._log_subscribe(
                        topic=topic,
                        decoded=decoded if isinstance(decoded, dict) else {"decoded": str(decoded)},
                        src=int(sample_obj.contents.SRC),
                        dst=int(sample_obj.contents.DST),
                        raw_hex=body.hex() if topic == OWNSHIP_NAVIGATION_TOPIC else raw_packet.hex(),
                        body_hex=body.hex(),
                        type_name=type_name_text,
                        sample_size=sample_size,
                    )

                    handlers = outer._sub_handlers.get(topic, [])
                    for handler in handlers:
                        try:
                            handler(decoded)
                        except Exception as exc:
                            outer._log_subscribe(
                                topic=topic,
                                decoded={
                                    "listener_handler_error": True,
                                    "handler_name": getattr(handler, "__name__", "<anonymous>"),
                                    "error": str(exc),
                                },
                                src=int(sample_obj.contents.SRC),
                                dst=int(sample_obj.contents.DST),
                                raw_hex="",
                                body_hex="",
                                type_name=type_name_text,
                                sample_size=sample_size,
                            )
                except Exception as exc:
                    outer._log_subscribe(
                        topic=topic,
                        decoded={
                            "listener_exception": True,
                            "error": str(exc),
                            "type_name_seen": type_name_text,
                        },
                        src=-1,
                        dst=-1,
                        raw_hex="",
                        body_hex="",
                        type_name=type_name_text,
                        sample_size=sample_size,
                    )
                    outer._log(topic="listener", payload={}, adapter="real-listener-error", reason=str(exc))

        self._dr_listener = _DRListener()
        return self._dr_listener

    def _ensure_started(self) -> bool:
        if self._started:
            return True
        if not self._sdk_loaded:
            return False

        try:
            self._factory = self._factory_cls.get_instance()
            if self.cfg.qos_file:
                self._factory.add_qos_profile(self.cfg.qos_file)
            self._dp = self._factory.create_commdp(self.cfg.domain_id)
            self._dds = self._dp.create_idl_interface("CSMXP_V3")
            self._build_listener()
            self._started = True
            return True
        except Exception as exc:
            self._load_error = f"startup failed: {exc}"
            self._started = False
            return False

    def _ensure_pub_topic(self, topic: str) -> None:
        if topic in self._pub_topics:
            return
        self._dds.pub_with_profile(topic, "Library", self._qos_profile, None)
        self._pub_topics.add(topic)

    def publish(self, topic: str, payload: dict) -> None:
        if not self._ensure_started():
            self._log(
                topic=topic,
                payload=payload,
                adapter="real-fallback",
                reason=f"ljdds startup unavailable: {self._load_error}",
            )
            return

        try:
            self._ensure_pub_topic(topic)

            CSMXP_V3 = self._CSMXP_V3
            CSMXP_V3_MSG_HEAD = self._CSMXP_V3_MSG_HEAD
            addressof = self._addressof
            memmove = self._memmove

            instance = CSMXP_V3()
            instance.SRC = int(payload.get("SRC", payload.get("src", 1)))
            instance.DST = int(payload.get("DST", payload.get("dst", 2)))

            body = encode_topic_payload(topic, payload)
            msg_capacity = len(instance.MSG)
            head_size = CSMXP_V3_MSG_HEAD.size()
            max_body = max(0, msg_capacity - head_size)
            if len(body) > max_body:
                body = body[:max_body]

            self._seq += 1
            v3header = CSMXP_V3_MSG_HEAD()
            v3header.spare = 0
            v3header.snd = int(payload.get("snd", 0))
            v3header.rcv = int(payload.get("rcv", 0))
            v3header.seq = self._seq
            v3header.ack = int(payload.get("ack", 0))
            v3header.flag = int(payload.get("flag", 0))
            v3header.num = int(payload.get("num", 1))
            v3header.length = head_size + len(body)

            memmove(addressof(instance.MSG), v3header.pack(), head_size)
            if body:
                memmove(addressof(instance.MSG) + head_size, body, len(body))

            self._dds.write_data(topic, instance, v3header.length)
            wire_packet = v3header.pack() + body
            self._log(
                topic=topic,
                payload=payload,
                adapter="real",
                wire_length=v3header.length,
                raw_hex=wire_packet.hex(),
                body_hex=body.hex(),
            )
        except Exception as exc:
            self._log(topic=topic, payload=payload, adapter="real-error", reason=str(exc))

    def subscribe(self, topic: str, handler: Callable[[dict], None]) -> None:
        self._sub_handlers.setdefault(topic, []).append(handler)

        if not self._ensure_started():
            self._log(topic=topic, payload={}, adapter="real-subscribe-fallback", reason=self._load_error)
            return

        if topic in self._sub_topics:
            return

        try:
            self._dds.sub_with_profile(topic, "Library", self._qos_profile, self._dr_listener)
            self._sub_topics.add(topic)
        except Exception as exc:
            self._log(topic=topic, payload={}, adapter="real-subscribe-error", reason=str(exc))

    def start(self) -> None:
        self._ensure_started()

    def stop(self) -> None:
        if not self._started:
            return
        try:
            if self._dp is not None and self._dds is not None:
                self._dp.delete_idl_interface(self._dds)
            if self._factory is not None and self._dp is not None:
                self._factory.delete_commdp(self._dp)
            if self._factory is not None:
                self._factory.finalize_instance()
        finally:
            self._started = False
            self._dds = None
            self._dp = None
            self._factory = None
            self._dr_listener = None
            self._pub_topics.clear()
            self._sub_topics.clear()
