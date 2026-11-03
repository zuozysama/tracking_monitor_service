"""Bounded, process-local repetition of immutable task-completed DDS reports."""
from copy import deepcopy
from dataclasses import dataclass
import logging
from threading import Condition, Thread, current_thread
import time
from typing import Callable

logger = logging.getLogger(__name__)
DEFAULT_ATTEMPTS = 5
DEFAULT_INTERVAL_SEC = 1.0


@dataclass
class _Report:
    key: tuple
    topic: str
    payload: dict
    publish: Callable
    is_current: Callable
    epoch: int
    attempts: int = 0
    due: float = 0.0


class CompletionReportRepeater:
    def __init__(self, attempts=DEFAULT_ATTEMPTS, interval_sec=DEFAULT_INTERVAL_SEC):
        if attempts < 1 or interval_sec <= 0:
            raise ValueError("Completion reports require positive attempts and interval")
        self.attempts = attempts
        self.interval_sec = interval_sec
        self._condition = Condition()
        self._seen = set()
        self._pending = {}
        self._thread = None
        self._closed = False
        self._epoch = 0

    def start(self):
        with self._condition:
            if self._closed and self._thread is not None and self._thread.is_alive():
                raise RuntimeError("Previous completion DDS worker has not stopped")
            self._closed = False

    def submit(self, key, topic, payload, publish, is_current=lambda: True):
        # Reserve before the synchronous first attempt so duplicate finish calls
        # cannot start another batch while the first publication is in progress.
        with self._condition:
            if self._closed or key in self._seen:
                return False
            self._seen.add(key)
            epoch = self._epoch
        report = _Report(key, topic, deepcopy(payload), publish, is_current, epoch)
        self._attempt(report)
        with self._condition:
            if not self._closed and epoch == self._epoch and report.attempts < self.attempts:
                report.due = time.monotonic() + self.interval_sec
                self._pending[key] = report
                if self._thread is None or not self._thread.is_alive():
                    self._thread = Thread(target=self._run, args=(epoch,), name="completed-dds-reports", daemon=True)
                    self._thread.start()
                self._condition.notify_all()
        return True

    def _attempt(self, report):
        report.attempts += 1
        logger.info("CompletionDDS task=%s attempt=%s/%s task_status=3",
                    report.key[0], report.attempts, self.attempts)
        try:
            # A publication attempt is not an acknowledgement from the receiver.
            report.publish(report.topic, deepcopy(report.payload))
        except Exception:
            logger.exception("CompletionDDS publication attempt failed task=%s attempt=%s/%s",
                             report.key[0], report.attempts, self.attempts)
        if report.attempts == self.attempts:
            logger.info("CompletionDDS batch finished task=%s attempts=%s; no receiver acknowledgement implied",
                        report.key[0], report.attempts)

    def _run(self, epoch):
        while True:
            with self._condition:
                if self._closed or epoch != self._epoch:
                    return
                if not self._pending:
                    self._condition.wait()
                    continue
                report = min(self._pending.values(), key=lambda item: item.due)
                delay = report.due - time.monotonic()
                if delay > 0:
                    self._condition.wait(delay)
                    continue
                self._pending.pop(report.key)
            try:
                current = report.is_current()
            except Exception:
                logger.exception("CompletionDDS could not validate task execution task=%s", report.key[0])
                current = False
            if not current:
                logger.info("CompletionDDS cancelled obsolete task execution task=%s", report.key[0])
                continue
            with self._condition:
                if self._closed or epoch != self._epoch:
                    return
            self._attempt(report)
            with self._condition:
                if not self._closed and epoch == self._epoch and report.attempts < self.attempts:
                    report.due = time.monotonic() + self.interval_sec
                    self._pending[report.key] = report
                    self._condition.notify_all()

    def stop(self):
        with self._condition:
            self._closed = True
            self._epoch += 1
            if self._pending:
                logger.info("CompletionDDS shutdown cancels pending batches=%s", len(self._pending))
            self._pending.clear()
            self._condition.notify_all()
            thread = self._thread
        if thread is not None and thread is not current_thread():
            thread.join(timeout=5)
            if thread.is_alive():
                logger.warning("CompletionDDS worker still finishing an in-flight publication during shutdown")
        with self._condition:
            if thread is None or not thread.is_alive():
                self._thread = None
                self._seen.clear()


completion_report_repeater = CompletionReportRepeater()
