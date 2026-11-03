"""Per-task video segments. No changes to DDS or public task models."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from threading import Event, RLock, Thread
from typing import Callable, Optional

from utils.time_utils import utc_now

logger = logging.getLogger(__name__)


@dataclass
class VideoSegment:
    channel_id: str
    target_batch_no: int
    stop: Event = field(default_factory=Event)
    thread: Optional[Thread] = None
    completed_at: Optional[datetime] = None
    switched: bool = False


class DualVideoRecorder:
    def __init__(self, client):
        self.client = client
        self._lock = RLock()
        self._segments: dict[str, VideoSegment] = {}

    def reconcile(self, task_id: str, channel_id: Optional[str], target_batch_no: int) -> None:
        with self._lock:
            segment = self._segments.get(task_id)
            if segment and (segment.channel_id, segment.target_batch_no) != (channel_id, target_batch_no):
                segment.switched = True
                segment.stop.set()

    def start_if_due(self, task_id: str, channel_id: str, target_batch_no: int,
                     duration_sec: int, interval_sec: int, last_video_time,
                     on_result: Callable[[dict], None]) -> bool:
        with self._lock:
            previous = self._segments.get(task_id)
            if previous:
                if previous.thread and previous.thread.is_alive():
                    return False
                last_time = previous.completed_at
                immediate = previous.switched
            else:
                last_time = last_video_time
                immediate = False
            if not immediate and last_time and (utc_now() - last_time).total_seconds() < interval_sec:
                return False
            segment = VideoSegment(channel_id, target_batch_no)
            self._segments[task_id] = segment

            def run():
                try:
                    try:
                        result = self.client.record_video(
                            task_id, duration_sec, channel_id=channel_id, stop_event=segment.stop,
                        )
                    except Exception as exc:
                        # Do not expose RTSP credentials via exception text.
                        logger.warning("Video segment failed for %s (%s)", task_id, type(exc).__name__)
                        result = {"success": False, "saved_local": False}
                    result = dict(result)
                    result["channel_id"] = channel_id
                    result["target_batch_no"] = target_batch_no
                    on_result(result)
                except Exception:
                    logger.exception("Could not publish completed video segment for %s", task_id)
                finally:
                    with self._lock:
                        segment.completed_at = utc_now()

            segment.thread = Thread(target=run, name=f"evidence-{task_id}", daemon=True)
            segment.thread.start()
            return True

    def stop_task(self, task_id: str) -> None:
        with self._lock:
            segment = self._segments.get(task_id)
            if segment:
                segment.stop.set()
        if segment and segment.thread:
            segment.thread.join(timeout=10)
        with self._lock:
            if segment and not segment.thread.is_alive():
                self._segments.pop(task_id, None)

    def stop_all(self) -> None:
        with self._lock:
            task_ids = list(self._segments)
        for task_id in task_ids:
            self.stop_task(task_id)
