from domain.enums import TaskStatus
from domain.models import RecommendedPoint, TaskContext, UnderwaterSearchOutput
from services.collaboration_service import collaboration_service
from services.patrol_service import patrol_service
from store.situation_store import situation_store
from store.task_store import task_store
from utils.config_utils import (
    get_tracking_filter_identity_weights,
    get_tracking_max_target_range_m,
)
from utils.time_utils import utc_now
from algorithms.target_filter import filter_and_select_target


class UnderwaterSearchService:
    def refresh_result(self, task: TaskContext) -> None:
        if task.status not in {TaskStatus.RUNNING, TaskStatus.WAITING_TARGET}:
            return

        patrol_service.refresh_result(task)

        ownship = situation_store.get_ownship()
        if ownship is None:
            task.status = TaskStatus.WAITING_TARGET
            task.search_hit = False
            task.execution_phase = "patrolling"
            task.underwater_search_output = None
            task.recommended_point = None
            task.update_time = utc_now()
            task_store.update_task(task)
            collaboration_service.report_stage_if_changed(task)
            return

        targets = situation_store.get_all_targets()

        target, debug_candidates = filter_and_select_target(
            targets=targets,
            ownship=ownship,
            constraint=task.target_constraint,
            task_area=task.task_area,
            max_target_range_m=get_tracking_max_target_range_m(),
            identity_weights=get_tracking_filter_identity_weights(),
            current_target_id=task.current_target_id,
        )

        task.candidate_targets = debug_candidates

        if target is None:
            task.status = TaskStatus.WAITING_TARGET
            task.search_hit = False
            task.execution_phase = "patrolling"
            task.underwater_search_output = None
            task.recommended_point = None
            task.update_time = utc_now()
            task_store.update_task(task)
            collaboration_service.report_stage_if_changed(task)
            return

        task.status = TaskStatus.RUNNING
        task.search_hit = True
        task.execution_phase = "engaging"
        task.current_target_id = target.target_id
        task.current_target_batch_no = target.target_batch_no

        task.patrol_plan_output = None
        task.recommended_point = RecommendedPoint(
            longitude=target.longitude,
            latitude=target.latitude,
            ref_type="target",
            ref_id=target.target_id,
            rel_range_m=0.0,
            rel_bearing_deg=0.0,
            expected_heading=target.heading,
            expected_speed=target.speed,
            update_time=utc_now(),
        )

        task.underwater_search_output = UnderwaterSearchOutput(
            task_id=task.task_id,
            target_id=target.target_id,
            target_batch_no=target.target_batch_no,
            target_type_code=target.target_type_code,
            hit_longitude=target.longitude,
            hit_latitude=target.latitude,
            expected_speed=task.expected_speed if task.expected_speed is not None else target.speed,
            coordination_required=True,
            matched=None,
            confidence=None,
            update_time=utc_now(),
        )

        task.update_time = utc_now()
        task_store.update_task(task)

        collaboration_service.handle_underwater_search_collaboration(task)


underwater_search_service = UnderwaterSearchService()
