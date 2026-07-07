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
from utils.point_timing_log import print_point_generation_timing
from algorithms.patrol_planner import generate_simple_patrol_waypoints


def _waypoints_signature(waypoints: list) -> str:
    """Build a short signature for waypoints to detect actual changes."""
    if not waypoints:
        return "empty"
    # Use first, last, and count as a lightweight signature
    first = waypoints[0]
    last = waypoints[-1]
    return f"cnt={len(waypoints)}_first=({first.longitude:.4f},{first.latitude:.4f})_last=({last.longitude:.4f},{last.latitude:.4f})"


class PatrolService:
    def refresh_result(self, task: TaskContext) -> None:
        if task.status not in {TaskStatus.RUNNING, TaskStatus.WAITING_TARGET}:
            return

        if task.task_area is None:
            task.status = TaskStatus.ABNORMAL
            task.update_time = utc_now()
            task_store.update_task(task)
            return

        point_generation_start_time = utc_now()
        if task.confirmed_preplan_route:
            waypoints = [waypoint.model_copy(deep=True) for waypoint in task.confirmed_preplan_route]
            point_type = "confirmed_preplan_patrol_waypoints"
        else:
            ownship = situation_store.get_ownship()
            ownship_point = None
            ownship_heading_deg = None
            if ownship is not None:
                ownship_point = GeoPoint(longitude=ownship.longitude, latitude=ownship.latitude)
                ownship_heading_deg = ownship.heading

            expected_speed = task.expected_speed or 0.0
            scan_radius = get_patrol_scan_radius_m()
            # densify step scales with scan radius so waypoints are dense
            # enough for smooth traversal regardless of sensor coverage.
            max_step = scan_radius * 4.0 if scan_radius is not None else None
            waypoints = generate_simple_patrol_waypoints(
                task_area=task.task_area,
                expected_speed=expected_speed,
                num_passes=get_patrol_num_passes(),
                ownship_point=ownship_point,
                ownship_heading_deg=ownship_heading_deg,
                scan_radius_m=scan_radius,
                boundary_clearance_m=get_patrol_boundary_clearance_m(),
                pattern=(task.patrol_pattern or "lawnmower").lower(),
                max_step_m=max_step,
            )
            point_type = "patrol_waypoints"

        point_generated_time = utc_now()
        _sig = _waypoints_signature(waypoints)
        _prev_sig = getattr(task, "_patrol_waypoints_signature", None)
        if _sig != _prev_sig:
            task._patrol_waypoints_signature = _sig
            print_point_generation_timing(
                task=task,
                point_generation_start_time=point_generation_start_time,
                point_generated_time=point_generated_time,
                point_type=point_type,
                point_count=len(waypoints),
            )

        task.execution_phase = "patrolling"
        task.patrol_waypoints = waypoints
        task.current_waypoint_index = 0
        task.patrol_plan_output = PatrolPlanOutput(
            task_id=task.task_id,
            waypoints=waypoints,
            update_time=point_generated_time,
        )
        task.tracking_plan_output = None
        task.update_time = point_generated_time
        task_store.update_task(task)


patrol_service = PatrolService()
