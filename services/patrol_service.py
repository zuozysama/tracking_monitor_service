from domain.enums import TaskStatus
from domain.models import GeoPoint, TaskContext, PatrolPlanOutput
from store.task_store import task_store
from store.situation_store import situation_store
from utils.time_utils import utc_now
from utils.config_utils import (
    get_patrol_boundary_clearance_m,
    get_patrol_num_passes,
    get_patrol_scan_radius_m,
)
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

        ownship = situation_store.get_ownship()
        ownship_point = None
        ownship_heading_deg = None
        if ownship is not None:
            ownship_point = GeoPoint(longitude=ownship.longitude, latitude=ownship.latitude)
            ownship_heading_deg = ownship.heading

        expected_speed = task.expected_speed or 0.0
        waypoints = generate_simple_patrol_waypoints(
            task_area=task.task_area,
            expected_speed=expected_speed,
            num_passes=get_patrol_num_passes(),
            ownship_point=ownship_point,
            ownship_heading_deg=ownship_heading_deg,
            scan_radius_m=get_patrol_scan_radius_m(),
            boundary_clearance_m=get_patrol_boundary_clearance_m(),
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
