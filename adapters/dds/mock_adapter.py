from __future__ import annotations

from typing import Callable

from adapters.dds.base import DdsAdapter
from adapters.dds.topic_codec import encode_topic_payload
from store.collaboration_store import collaboration_store
from utils.time_utils import utc_now


class MockDdsAdapter(DdsAdapter):
    def publish(self, topic: str, payload: dict) -> None:
        body_hex = ""
        try:
            body_hex = encode_topic_payload(topic, payload).hex()
        except Exception:
            body_hex = ""
        collaboration_store.append_dds_publish_log(
            {
                "topic": topic,
                "payload": payload,
                "publish_time": utc_now(),
                "adapter": "mock",
                "raw_hex": body_hex,
                "body_hex": body_hex,
            }
        )

    def subscribe(self, topic: str, handler: Callable[[dict], None]) -> None:
        # Mock adapter does not run an async bus; caller injects data via mock APIs.
        return

    def start(self) -> None:
        return

    def stop(self) -> None:
        return
