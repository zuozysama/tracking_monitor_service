from datetime import timedelta

from domain.enums import TaskStatus, FinishReason, TrackingMode
from domain.models import TaskArea, TaskContext, RecommendedPoint, TrackingPlanOutput
from services.tracking_service import tracking_service
from store.situation_store import situation_store
from store.task_store import task_store
from utils.time_utils import utc_now
from utils.config_utils import (
    get_fixed_tracking_default_radius_m,
    get_tracking_escort_distance_m,
    get_tracking_filter_identity_weights,
    get_tracking_max_target_range_m,
)
from algorithms.target_filter import filter_and_select_target


class FixedTrackingService:
    @staticmethod
    def _default_radius(task: TaskContext) -> float:
        if task.default_region_radius_m is not None:
            return task.default_region_radius_m
        return get_fixed_tracking_default_radius_m()

    def _build_search_area(self, task: TaskContext) -> TaskArea:
        return TaskArea(
            area_type="circle",
            center=task.anchor_point,
            radius_m=self._default_radius(task),
        )

    @staticmethod
    def _complete_out_of_region(task: TaskContext) -> bool:
        task.status = TaskStatus.COMPLETED
        task.finish_reason = FinishReason.OUT_OF_REGION
        task.end_time = utc_now()
        task.update_time = task.end_time
        task.execution_phase = "completed"
        task_store.update_task(task)
        return True

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

        ownship = situation_store.get_ownship()
        if ownship is None:
            task.status = TaskStatus.WAITING_TARGET
            task.search_hit = False
            task.execution_phase = "standby_monitoring"
            task.recommended_point = None
            task.tracking_plan_output = None
            task.update_time = utc_now()
            task_store.update_task(task)
            return

        target, debug_candidates = filter_and_select_target(
            targets=situation_store.get_all_targets(),
            ownship=ownship,
            constraint=task.target_constraint,
            task_area=self._build_search_area(task),
            max_target_range_m=get_tracking_max_target_range_m(),
            identity_weights=get_tracking_filter_identity_weights(),
            current_target_id=task.current_target_id,
            current_target_batch_no=task.current_target_batch_no,
            apply_default_surface_filter=True,
        )

        task.candidate_targets = debug_candidates
        if target is None:
            task.status = TaskStatus.WAITING_TARGET
            task.search_hit = False
            task.execution_phase = "standby_monitoring"
            task.recommended_point = None
            task.tracking_plan_output = None
            task.update_time = utc_now()
            task_store.update_task(task)
            return

        previous_target_batch_no = task.current_target_batch_no
        if previous_target_batch_no not in {None, target.target_batch_no}:
            tracking_service._reset_tracking_point_selection(task)

        point, rel_bearing_deg = tracking_service._generate_tracking_point_with_hysteresis(
            task=task,
            mode=TrackingMode.ESCORT,
            target=target,
            ownship=ownship,
        )
        point_generated_time = utc_now()

        exp_speed = task.expected_speed if task.expected_speed is not None else 0.0

        task.status = TaskStatus.RUNNING
        task.search_hit = True
        task.execution_phase = "engaging"
        task.current_target_id = target.target_id
        task.current_target_batch_no = target.target_batch_no
        task.last_seen_target_time = point_generated_time
        task.has_entered_task_area = True
        task.recommended_point = RecommendedPoint(
            longitude=point.longitude,
            latitude=point.latitude,
            ref_type="target",
            ref_id=target.target_id,
            rel_range_m=get_tracking_escort_distance_m(),
            rel_bearing_deg=rel_bearing_deg,
            expected_heading=target.heading,
            expected_speed=exp_speed,
            update_time=point_generated_time,
        )
        task.patrol_plan_output = None
        task.tracking_plan_output = TrackingPlanOutput(
            task_id=task.task_id,
            target_id=target.target_id,
            target_batch_no=target.target_batch_no,
            rel_range_m=get_tracking_escort_distance_m(),
            relative_bearing_deg=rel_bearing_deg,
            expected_speed=exp_speed,
            update_time=point_generated_time,
        )
        task.update_time = point_generated_time
        task_store.update_task(task)

    def check_out_of_region(self, task: TaskContext) -> bool:
        if not task.end_condition.out_of_region_finish:
            return False

        if task.current_target_batch_no is None and not task.current_target_id:
            return False

        timeout_sec = task.end_condition.target_lost_timeout_sec
        if timeout_sec is None or task.last_seen_target_time is None:
            return False

        if utc_now() - task.last_seen_target_time >= timedelta(seconds=timeout_sec):
            return self._complete_out_of_region(task)

        return False


fixed_tracking_service = FixedTrackingService()
