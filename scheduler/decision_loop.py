import threading
import time

from store.task_store import task_store
from services.task_service import task_service


class DecisionLoop:
    def __init__(self, interval_sec: float = 1.0) -> None:
        self.interval_sec = interval_sec
        self._running = False
        self._thread = None

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _run(self) -> None:
        while self._running:
            try:
                tasks = task_store.get_all_tasks()
                for task in tasks:
                    task_service.tick_task(task.task_id)
            except Exception as e:
                # 当前先简单打印，后面可换正式日志
                print(f"[DecisionLoop] error: {e}")

            time.sleep(self.interval_sec)


decision_loop = DecisionLoop(interval_sec=1.0)