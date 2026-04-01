from datetime import timedelta
from typing import Optional

from domain.enums import FinishReason, TaskStatus, TaskType
from domain.models import (
    CreateTaskRequest,
    EndCondition,
    FeasibilityCallbackRequest,
    ManualSelectionFeedbackRequest,
    ManualSelectionRequest,
    ManualSwitchRequest,
    ManualSwitchFeedbackRequest,
    TargetConstraint,
    TaskContext,
    TaskOutputResponse,
    TaskResultResponse,
    TaskStatusResponse,
)
from services.collaboration_service import collaboration_service
from services.fixed_tracking_output_service import fixed_tracking_output_service
from services.fixed_tracking_service import fixed_tracking_service
from services.patrol_service import patrol_service
from services.preplan_service import preplan_service
from services.tracking_service import tracking_service
from services.underwater_search_service import underwater_search_service
from domain.models import GeoPoint
from store.situation_store import situation_store
from store.task_store import task_store
from utils.config_utils import get_fixed_tracking_default_radius_m
from utils.geo_utils import is_point_in_polygon
from utils.time_utils import utc_now


class TaskService:
    def create_task(self, req: CreateTaskRequest) -> TaskContext:
        if task_store.exists(req.task_id):
            raise ValueError("task already exists")

        now = utc_now()
        end_condition = req.end_condition or EndCondition()
        internal_target_constraint = self._build_internal_target_constraint(req)

        task = TaskContext(
            task_id=req.task_id,
            task_type=req.task_type,
            task_name=req.task_name,
            task_source=req.task_source,
            priority=req.priority,
            remark=req.remark,
            mode=req.mode,
            target_info=req.target_info,
            task_area=req.task_area,
            anchor_point=req.anchor_point,
            target_constraint=internal_target_constraint,
            polygon_region=req.task_area,
            default_region_radius_m=get_fixed_tracking_default_radius_m(),
            expected_speed=req.expected_speed,
            update_interval_sec=req.update_interval_sec or 1,
            end_condition=end_condition,
            stream_media_param=req.stream_media_param,
            linkage_param=req.linkage_param,
            status=TaskStatus.CREATED,
            create_time=now,
            start_time=now,
            update_time=now,
            execution_phase="planning",
        )

        task.status = TaskStatus.RUNNING
        task_store.create_task(task)

        self.tick_task(task.task_id)
        return task_store.get_task(task.task_id)

    def _build_internal_target_constraint(self, req: CreateTaskRequest) -> TargetConstraint:
        target_info = req.target_info
        if target_info is None:
            return TargetConstraint(auto_search=True)

        allowed_target_type_codes = None
        preferred_target_type_codes = None
        allowed_enemy_friend_attrs = None
        preferred_enemy_friend_attrs = None
        allowed_military_civil_attrs = None
        preferred_military_civil_attrs = None

        if target_info.target_type_code is not None:
            allowed_target_type_codes = [target_info.target_type_code]
            preferred_target_type_codes = [target_info.target_type_code]
        if target_info.enemy_friend_attr is not None:
            allowed_enemy_friend_attrs = [target_info.enemy_friend_attr]
            preferred_enemy_friend_attrs = [target_info.enemy_friend_attr]
        if target_info.military_civil_attr is not None:
            allowed_military_civil_attrs = [target_info.military_civil_attr]
            preferred_military_civil_attrs = [target_info.military_civil_attr]

        return TargetConstraint(
            target_id=target_info.target_id,
            target_batch_no=target_info.target_batch_no,
            target_type_code=target_info.target_type_code,
            threat_level=target_info.threat_level,
            target_name=target_info.target_name,
            enemy_friend_attr=target_info.enemy_friend_attr,
            military_civil_attr=target_info.military_civil_attr,
            auto_search=True,
            allowed_target_type_codes=allowed_target_type_codes,
            preferred_target_type_codes=preferred_target_type_codes,
            allowed_enemy_friend_attrs=allowed_enemy_friend_attrs,
            preferred_enemy_friend_attrs=preferred_enemy_friend_attrs,
            allowed_military_civil_attrs=allowed_military_civil_attrs,
            preferred_military_civil_attrs=preferred_military_civil_attrs,
        )

    def terminate_task(self, task_id: str, reason: Optional[str] = None) -> TaskContext:
        task = task_store.get_task(task_id)
        if task is None:
            raise LookupError("task not found")

        if not task.end_condition.manual_terminate_allowed:
            raise ValueError("manual termination is not allowed for this task")

        if reason:
            reason_text = reason.strip()
            if reason_text:
                if task.remark:
                    task.remark = f"{task.remark}\nmanual_terminate_reason: {reason_text}"
                else:
                    task.remark = f"manual_terminate_reason: {reason_text}"

        task.status = TaskStatus.TERMINATED
        task.finish_reason = FinishReason.MANUAL_TERMINATED
        task.end_time = utc_now()
        task.update_time = task.end_time
        task.execution_phase = "completed"
        task_store.update_task(task)

        collaboration_service.on_task_finished(task)
        return task

    def apply_planning_callback(self, req: FeasibilityCallbackRequest) -> TaskContext:
        task = task_store.get_task(req.task_id)
        if task is None:
            raise LookupError("task not found")

        collaboration_service.apply_planning_callback(task, req)
        return task_store.get_task(req.task_id)

    def register_manual_selection_request(self, req: ManualSelectionRequest) -> TaskContext:
        task = task_store.get_task(req.task_id)
        if task is None:
            raise LookupError("task not found")

        now = utc_now()
        task.manual_selection_request_sent = True
        task.manual_selection_pending = True
        task.manual_selection_timeout_sec = req.timeout_sec
        task.manual_selection_requested_at = now
        task.manual_selection_deadline = now + timedelta(seconds=req.timeout_sec)
        task.manual_selection_feedback_received = False
        task.manual_selection_selected_target_id = None
        task.manual_selection_candidate_count = len(req.candidate_targets)
        task.manual_selection_last_countdown_sec = None
        task.update_time = now
        task_store.update_task(task)
        return task_store.get_task(req.task_id)

    def register_manual_switch_request(self, req: ManualSwitchRequest) -> TaskContext:
        task = task_store.get_task(req.task_id)
        if task is None:
            raise LookupError("task not found")

        now = utc_now()
        task.manual_switch_request_sent = True
        task.manual_switch_pending = True
        task.manual_switch_timeout_sec = req.timeout_sec
        task.manual_switch_requested_at = now
        task.manual_switch_deadline = now + timedelta(seconds=req.timeout_sec)
        task.manual_switch_feedback_received = False
        task.manual_switch_selected_target_id = None
        task.manual_switch_candidate_count = len(req.new_candidate_targets)
        task.manual_switch_last_countdown_sec = None
        task.update_time = now
        task_store.update_task(task)
        return task_store.get_task(req.task_id)

    def apply_manual_selection_feedback(self, req: ManualSelectionFeedbackRequest) -> TaskContext:
        task = task_store.get_task(req.task_id)
        if task is None:
            raise LookupError("task not found")
        now = utc_now()
        if task.manual_selection_deadline is not None and now > task.manual_selection_deadline:
            raise ValueError("manual selection feedback timeout")

        task.current_target_id = req.selected_target_id
        if task.target_constraint is not None:
            # Manual selection from command side should lock target identity for follow-up ticks.
            task.target_constraint.target_id = req.selected_target_id
            task.target_constraint.target_batch_no = None
        task.manual_selection_pending = False
        task.manual_selection_feedback_received = True
        task.manual_selection_selected_target_id = req.selected_target_id
        task.manual_selection_last_countdown_sec = None
        task.update_time = now
        task.execution_phase = "engaging"
        task_store.update_task(task)
        return task_store.get_task(req.task_id)

    def apply_manual_switch_feedback(self, req: ManualSwitchFeedbackRequest) -> TaskContext:
        task = task_store.get_task(req.task_id)
        if task is None:
            raise LookupError("task not found")
        now = utc_now()
        if task.manual_switch_deadline is not None and now > task.manual_switch_deadline:
            raise ValueError("manual switch feedback timeout")

        if not req.keep_current and req.selected_target_id:
            task.current_target_id = req.selected_target_id
            if task.target_constraint is not None:
                task.target_constraint.target_id = req.selected_target_id
                task.target_constraint.target_batch_no = None
        task.manual_switch_pending = False
        task.manual_switch_feedback_received = True
        task.manual_switch_selected_target_id = req.selected_target_id
        task.manual_switch_last_countdown_sec = None
        task.update_time = now
        task.execution_phase = "engaging"
        task_store.update_task(task)
        return task_store.get_task(req.task_id)

    def get_status(self, task_id: str) -> TaskStatusResponse:
        task = task_store.get_task(task_id)
        if task is None:
            raise LookupError("task not found")

        remaining_time_sec = None
        duration_sec = task.end_condition.duration_sec
        if duration_sec and task.start_time and task.status == TaskStatus.RUNNING:
            elapsed = int((utc_now() - task.start_time).total_seconds())
            remaining_time_sec = max(duration_sec - elapsed, 0)

        return TaskStatusResponse(
            task_id=task.task_id,
            task_type=task.task_type,
            task_name=task.task_name,
            mode=task.mode,
            task_status=task.status,
            start_time=task.start_time,
            update_time=task.update_time,
            remaining_time_sec=remaining_time_sec,
            finish_reason=task.finish_reason,
            execution_phase=task.execution_phase,
        )

    def get_manual_selection_status(self, task_id: str) -> dict:
        task = task_store.get_task(task_id)
        if task is None:
            raise LookupError("task not found")

        now = utc_now()
        remaining_sec = None
        if task.manual_selection_pending and task.manual_selection_deadline is not None:
            remaining_sec = max(0, int((task.manual_selection_deadline - now).total_seconds()))

        return {
            "task_id": task.task_id,
            "request_sent": task.manual_selection_request_sent,
            "pending": task.manual_selection_pending,
            "timeout_sec": task.manual_selection_timeout_sec,
            "requested_at": task.manual_selection_requested_at,
            "deadline": task.manual_selection_deadline,
            "server_time": now,
            "remaining_sec": remaining_sec,
            "feedback_received": task.manual_selection_feedback_received,
            "selected_target_id": task.manual_selection_selected_target_id,
            "candidate_count": task.manual_selection_candidate_count,
        }

    def get_manual_switch_status(self, task_id: str) -> dict:
        task = task_store.get_task(task_id)
        if task is None:
            raise LookupError("task not found")

        now = utc_now()
        remaining_sec = None
        if task.manual_switch_pending and task.manual_switch_deadline is not None:
            remaining_sec = max(0, int((task.manual_switch_deadline - now).total_seconds()))

        return {
            "task_id": task.task_id,
            "request_sent": task.manual_switch_request_sent,
            "pending": task.manual_switch_pending,
            "timeout_sec": task.manual_switch_timeout_sec,
            "requested_at": task.manual_switch_requested_at,
            "deadline": task.manual_switch_deadline,
            "server_time": now,
            "remaining_sec": remaining_sec,
            "feedback_received": task.manual_switch_feedback_received,
            "selected_target_id": task.manual_switch_selected_target_id,
            "candidate_count": task.manual_switch_candidate_count,
        }

    def get_result(self, task_id: str) -> TaskResultResponse:
        task = task_store.get_task(task_id)
        if task is None:
            raise LookupError("task not found")

        current_target_info = None
        if task.current_target_id:
            current_target_info = situation_store.get_target(task.current_target_id)

        return TaskResultResponse(
            task_id=task.task_id,
            task_type=task.task_type,
            task_name=task.task_name,
            mode=task.mode,
            task_status=task.status,
            current_target_id=task.current_target_id,
            current_target_info=current_target_info,
            recommended_point=task.recommended_point,
            patrol_plan_output=task.patrol_plan_output,
            tracking_plan_output=task.tracking_plan_output,
            underwater_search_output=task.underwater_search_output,
            fixed_tracking_output=task.fixed_tracking_output,
            preplan_output=task.preplan_output,
            stream_media_param=task.stream_media_param,
            linkage_param=task.linkage_param,
            update_time=task.update_time,
            finish_reason=task.finish_reason,
            optronic_status=task.optronic_status,
            planning_callback=task.planning_callback,
        )

    def get_output(self, task_id: str) -> TaskOutputResponse:
        task = task_store.get_task(task_id)
        if task is None:
            raise LookupError("task not found")

        output_type = "none"
        if task.tracking_plan_output is not None:
            output_type = "tracking"
        elif task.underwater_search_output is not None:
            output_type = "underwater_search"
        elif task.fixed_tracking_output is not None:
            output_type = "fixed_tracking"
        elif task.preplan_output is not None:
            output_type = "preplan"
        elif task.patrol_plan_output is not None:
            output_type = "patrol"

        return TaskOutputResponse(
            task_id=task.task_id,
            task_type=task.task_type,
            output_type=output_type,
            patrol_plan_output=task.patrol_plan_output,
            tracking_plan_output=task.tracking_plan_output,
            underwater_search_output=task.underwater_search_output,
            fixed_tracking_output=task.fixed_tracking_output,
            preplan_output=task.preplan_output,
            update_time=task.update_time,
        )

    def list_tasks(self) -> list:
        return task_store.get_all_tasks()

    def tick_task(self, task_id: str) -> None:
        task = task_store.get_task(task_id)
        if task is None:
            return

        if task.status not in {TaskStatus.RUNNING, TaskStatus.WAITING_TARGET}:
            return

        self._refresh_task_result(task)
        self._apply_end_conditions(task)

        latest = task_store.get_task(task_id)
        if latest is not None and latest.status in {
            TaskStatus.COMPLETED,
            TaskStatus.TERMINATED,
            TaskStatus.ABNORMAL,
        }:
            collaboration_service.on_task_finished(latest)

    def _apply_end_conditions(self, task: TaskContext) -> None:
        if task.status not in {TaskStatus.RUNNING, TaskStatus.WAITING_TARGET}:
            return

        if self._check_duration(task):
            return

        if task.task_type == TaskType.TRACKING:
            if self._check_tracking_out_of_region(task):
                return

        if task.task_type == TaskType.FIXED_TRACKING:
            if fixed_tracking_service.check_out_of_region(task):
                return

    def _check_tracking_out_of_region(self, task: TaskContext) -> bool:
        if not task.end_condition.out_of_region_finish:
            return False

        if task.task_area is None or task.task_area.area_type != "polygon":
            return False

        ownship = situation_store.get_ownship()
        if ownship is None:
            return False

        ownship_point = GeoPoint(
            longitude=ownship.longitude,
            latitude=ownship.latitude,
        )

        inside = is_point_in_polygon(ownship_point, task.task_area.points)
        if inside:
            if not task.has_entered_task_area:
                task.has_entered_task_area = True
                task.update_time = utc_now()
                task_store.update_task(task)
            return False

        if not task.has_entered_task_area:
            return False

        task.status = TaskStatus.COMPLETED
        task.finish_reason = FinishReason.OUT_OF_REGION
        task.end_time = utc_now()
        task.update_time = task.end_time
        task.execution_phase = "completed"
        task_store.update_task(task)
        return True

    def _check_duration(self, task: TaskContext) -> bool:
        duration_sec = task.end_condition.duration_sec
        if duration_sec is None or task.start_time is None:
            return False

        elapsed = utc_now() - task.start_time
        if elapsed >= timedelta(seconds=duration_sec):
            task.status = TaskStatus.COMPLETED
            task.finish_reason = FinishReason.TIMEOUT
            task.end_time = utc_now()
            task.update_time = task.end_time
            task.execution_phase = "completed"
            task_store.update_task(task)
            return True

        return False

    def _refresh_task_result(self, task: TaskContext) -> None:
        if task.status not in {TaskStatus.RUNNING, TaskStatus.WAITING_TARGET}:
            return

        if task.task_type == TaskType.PATROL:
            patrol_service.refresh_result(task)
            collaboration_service.handle_patrol_collaboration(task)
            return

        if task.task_type == TaskType.TRACKING:
            tracking_service.refresh_result(task)
            return

        if task.task_type == TaskType.UNDERWATER_SEARCH:
            underwater_search_service.refresh_result(task)
            return

        if task.task_type == TaskType.FIXED_TRACKING:
            fixed_tracking_service.refresh_result(task)
            fixed_tracking_output_service.refresh_output(task)
            collaboration_service.handle_fixed_tracking_collaboration(task)
            return

        if task.task_type == TaskType.PREPLAN:
            preplan_service.refresh_result(task)
            collaboration_service.handle_preplan_collaboration(task)
            return


task_service = TaskService()
