from domain.enums import TaskStatus
from domain.models import PreplanOutput, TaskContext
from store.task_store import task_store
from utils.time_utils import utc_now
from algorithms.patrol_planner import generate_simple_patrol_waypoints


class PreplanService:
    def refresh_result(self, task: TaskContext) -> None:
        if task.status not in {TaskStatus.RUNNING, TaskStatus.WAITING_TARGET}:
            return

        if task.task_area is None:
            return

        waypoints = generate_simple_patrol_waypoints(
            task_area=task.task_area,
            expected_speed=task.expected_speed or 0.0,
            num_passes=4,
        )

        task.execution_phase = "planning"
        task.preplan_output = PreplanOutput(
            task_id=task.task_id,
            planned_route=waypoints,
            feasible=True,
            reason="方案可执行",
        )
        task.update_time = utc_now()
        task_store.update_task(task)


preplan_service = PreplanService()
