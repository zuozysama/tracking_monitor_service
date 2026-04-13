from __future__ import annotations

from ctypes import POINTER, cast
from typing import Callable

from adapters.dds.base import DdsAdapter
from adapters.dds.config import DdsRuntimeConfig
from adapters.dds.topic_codec import decode_topic_payload, encode_topic_payload
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
        self._try_load_sdk()

    def _log(self, topic: str, payload: dict, adapter: str, reason: str = "", wire_length: int = 0) -> None:
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
        collaboration_store.append_dds_publish_log(item)

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

        class _DRListener(base_cls):
            def on_data_available(self, topic_name, type_name, sample, size, sample_info):
                try:
                    if type_name != b"CSMXP_V3":
                        return

                    sample_obj = cast(sample, POINTER(CSMXP_V3))
                    msg = bytes(sample_obj.contents.MSG)
                    head_size = CSMXP_V3_MSG_HEAD.size()
                    header = CSMXP_V3_MSG_HEAD()
                    header.unpack(msg[0:head_size])

                    total_len = int(getattr(header, "length", 0))
                    if total_len <= head_size or total_len > len(msg):
                        total_len = min(len(msg), int(size) if int(size) > 0 else len(msg))
                    body = msg[head_size:total_len]

                    topic = topic_name.decode("utf-8", errors="ignore") if isinstance(topic_name, (bytes, bytearray)) else str(topic_name)
                    decoded = decode_topic_payload(topic, body)
                    if isinstance(decoded, dict):
                        decoded.setdefault("src", int(sample_obj.contents.SRC))
                        decoded.setdefault("dst", int(sample_obj.contents.DST))

                    handlers = outer._sub_handlers.get(topic, [])
                    for handler in handlers:
                        handler(decoded)
                except Exception as exc:
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
        self._dds.pub_with_profile(topic, "Library", "BestEffort", None)
        self._pub_topics.add(topic)

    def publish(self, topic: str, payload: dict) -> None:
        if not self._ensure_started():
            self._log(topic=topic, payload=payload, adapter="real-fallback", reason=f"ljdds startup unavailable: {self._load_error}")
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
            self._log(topic=topic, payload=payload, adapter="real", wire_length=v3header.length)
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
            self._dds.sub_with_profile(topic, "Library", "BestEffort", self._dr_listener)
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
