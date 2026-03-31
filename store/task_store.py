from typing import Dict, Optional

from domain.models import TaskContext


class TaskStore:
    def __init__(self) -> None:
        self._tasks: Dict[str, TaskContext] = {}

    def create_task(self, task: TaskContext) -> None:
        self._tasks[task.task_id] = task

    def exists(self, task_id: str) -> bool:
        return task_id in self._tasks

    def get_task(self, task_id: str) -> Optional[TaskContext]:
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> list[TaskContext]:
        return list(self._tasks.values())

    def update_task(self, task: TaskContext) -> None:
        self._tasks[task.task_id] = task


task_store = TaskStore()