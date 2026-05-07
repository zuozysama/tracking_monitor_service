from domain.enums import TaskStatus
from domain.models import GeoPoint, PreplanOutput, TaskContext
from store.task_store import task_store
from store.situation_store import situation_store
from utils.time_utils import utc_now
from utils.config_utils import (
    get_patrol_boundary_clearance_m,
    get_patrol_num_passes,
    get_patrol_scan_radius_m,
)
from utils.point_timing_log import print_point_generation_timing
from algorithms.patrol_planner import generate_simple_patrol_waypoints


class PreplanService:
    def refresh_result(self, task: TaskContext) -> None:
        if task.status not in {TaskStatus.RUNNING, TaskStatus.WAITING_TARGET}:
            return

        if task.task_area is None:
            return

        # One-shot preplan: if result already exists, keep it frozen and close task.
        if task.preplan_output is not None:
            now = utc_now()
            task.status = TaskStatus.COMPLETED
            task.end_time = now
            task.update_time = now
            task.execution_phase = "completed"
            task_store.update_task(task)
            return

        ownship = situation_store.get_ownship()
        ownship_point = None
        ownship_heading_deg = None
        if ownship is not None:
            ownship_point = GeoPoint(longitude=ownship.longitude, latitude=ownship.latitude)
            ownship_heading_deg = ownship.heading

        point_generation_start_time = utc_now()
        waypoints = generate_simple_patrol_waypoints(
            task_area=task.task_area,
            expected_speed=task.expected_speed or 0.0,
            num_passes=get_patrol_num_passes(),
            ownship_point=ownship_point,
            ownship_heading_deg=ownship_heading_deg,
            scan_radius_m=get_patrol_scan_radius_m(),
            boundary_clearance_m=get_patrol_boundary_clearance_m(),
        )
        point_generated_time = utc_now()
        print_point_generation_timing(
            task=task,
            point_generation_start_time=point_generation_start_time,
            point_generated_time=point_generated_time,
            point_type="preplan_patrol_waypoints",
            point_count=len(waypoints),
        )

        task.preplan_output = PreplanOutput(
            task_id=task.task_id,
            planned_route=waypoints,
            feasible=True,
            reason="方案可执行",
        )
        now = point_generated_time
        task.status = TaskStatus.COMPLETED
        task.end_time = now
        task.update_time = now
        task.execution_phase = "completed"
        task_store.update_task(task)


preplan_service = PreplanService()
