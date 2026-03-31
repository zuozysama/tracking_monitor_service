from domain.enums import TaskStatus, FinishReason
from domain.models import TaskContext, RecommendedPoint, GeoPoint
from store.situation_store import situation_store
from store.task_store import task_store
from utils.time_utils import utc_now
from utils.geo_utils import haversine_distance_m, is_point_in_polygon
from utils.config_utils import get_fixed_tracking_default_radius_m


class FixedTrackingService:
    def refresh_result(self, task: TaskContext) -> None:
        if task.status not in {TaskStatus.RUNNING, TaskStatus.WAITING_TARGET}:
            return

        if task.anchor_point is None:
            task.status = TaskStatus.ABNORMAL
            task.finish_reason = FinishReason.INVALID_TASK
            task.execution_phase = "completed"
            task.update_time = utc_now()
            task_store.update_task(task)
            return

        task.status = TaskStatus.RUNNING
        task.current_target_id = None
        task.recommended_point = RecommendedPoint(
            longitude=task.anchor_point.longitude,
            latitude=task.anchor_point.latitude,
            ref_type="anchor",
            ref_id=None,
            rel_range_m=0.0,
            rel_bearing_deg=0.0,
            expected_heading=None,
            expected_speed=task.expected_speed,
            update_time=utc_now(),
        )
        task.update_time = utc_now()
        task_store.update_task(task)

    def check_out_of_region(self, task: TaskContext) -> bool:
        if not task.end_condition.out_of_region_finish:
            return False

        ownship = situation_store.get_ownship()
        if ownship is None:
            return False

        ownship_point = GeoPoint(
            longitude=ownship.longitude,
            latitude=ownship.latitude,
        )

        if task.polygon_region is not None and task.polygon_region.area_type == "polygon":
            inside = is_point_in_polygon(ownship_point, task.polygon_region.points)
            if not inside:
                task.status = TaskStatus.COMPLETED
                task.finish_reason = FinishReason.OUT_OF_REGION
                task.end_time = utc_now()
                task.update_time = task.end_time
                task.execution_phase = "completed"
                task_store.update_task(task)
                return True

        else:
            if task.recommended_point is None:
                return False

            recommended_point = GeoPoint(
                longitude=task.recommended_point.longitude,
                latitude=task.recommended_point.latitude,
            )

            distance = haversine_distance_m(ownship_point, recommended_point)

            radius = task.default_region_radius_m
            if radius is None:
                radius = get_fixed_tracking_default_radius_m()

            if distance > radius:
                task.status = TaskStatus.COMPLETED
                task.finish_reason = FinishReason.OUT_OF_REGION
                task.end_time = utc_now()
                task.update_time = task.end_time
                task.execution_phase = "completed"
                task_store.update_task(task)
                return True

        return False


fixed_tracking_service = FixedTrackingService()
