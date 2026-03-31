from domain.enums import TaskStatus
from domain.models import TaskContext, PatrolPlanOutput
from store.task_store import task_store
from utils.time_utils import utc_now
from algorithms.patrol_planner import generate_simple_patrol_waypoints


class PatrolService:
    def refresh_result(self, task: TaskContext) -> None:
        if task.status not in {TaskStatus.RUNNING, TaskStatus.WAITING_TARGET}:
            return

        if task.task_area is None:
            task.status = TaskStatus.ABNORMAL
            task.update_time = utc_now()
            task_store.update_task(task)
            return

        expected_speed = task.expected_speed or 0.0
        waypoints = generate_simple_patrol_waypoints(
            task_area=task.task_area,
            expected_speed=expected_speed,
            num_passes=4,
        )

        task.execution_phase = "patrolling"
        task.patrol_waypoints = waypoints
        task.current_waypoint_index = 0
        task.patrol_plan_output = PatrolPlanOutput(
            task_id=task.task_id,
            waypoints=waypoints,
            update_time=utc_now(),
        )
        task.tracking_plan_output = None
        task.update_time = utc_now()
        task_store.update_task(task)


patrol_service = PatrolService()