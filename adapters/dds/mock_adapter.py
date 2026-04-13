from __future__ import annotations

from typing import Callable

from adapters.dds.base import DdsAdapter
from store.collaboration_store import collaboration_store
from utils.time_utils import utc_now


class MockDdsAdapter(DdsAdapter):
    def publish(self, topic: str, payload: dict) -> None:
        collaboration_store.append_dds_publish_log(
            {
                "topic": topic,
                "payload": payload,
                "publish_time": utc_now(),
                "adapter": "mock",
            }
        )

    def subscribe(self, topic: str, handler: Callable[[dict], None]) -> None:
        # Mock adapter does not run an async bus; caller injects data via mock APIs.
        return

    def start(self) -> None:
        return

    def stop(self) -> None:
        return
