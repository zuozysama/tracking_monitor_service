import json
from datetime import datetime, timedelta
from typing import Optional

from adapters.dds import get_dds_adapter
from clients.autonomy_client import autonomy_client
from clients.media_client import media_client
from clients.optical_linkage_client import optical_linkage_client
from clients.planning_client import planning_client
from clients.sonar_client import sonar_client
from domain.dds_contract import (
    ELECTRO_OPTICAL_LINKAGE_CMD_TOPIC,
    FINISH_REASON_CODE_MAP,
    MANUAL_SELECTION_REQUEST_TOPIC,
    MANUAL_SWITCH_REQUEST_TOPIC,
    PHASE_CODE_MAP,
    PREPLAN_RESULT_TOPIC,
    RESULT_TYPE_CODE_MAP,
    STREAM_MEDIA_PARAM_TOPIC,
    TASK_STATUS_CODE_MAP,
    TASK_TYPE_CODE_MAP,
    TASK_UPDATE_TOPIC,
    UPDATE_TYPE_CODE_MAP,
)
from domain.enums import TaskStatus, FinishReason, TaskType
from domain.models import (
    AutonomyPatrolDispatch,
    AutonomyTrackingDispatch,
    GeoPoint,
    ManualSelectionRequest,
    ManualSwitchRequest,
    MediaStreamAccessRequest,
    OpticalLinkageCommand,
    OptronicStatus,
    OwnShipState,
    TargetInfo,
    TaskContext,
)
from store.collaboration_store import collaboration_store
from store.task_store import task_store
from utils.config_utils import (
    get_sonar_poll_interval_sec,
    get_tracking_arrival_stable_cycles,
    get_tracking_arrival_tolerance_m,
)
from utils.geo_utils import haversine_distance_m
from utils.time_utils import utc_now

dds_adapter = get_dds_adapter()


def _seconds_since(last_time: Optional[datetime]) -> Optional[float]:
    if last_time is None:
        return None
    return (utc_now() - last_time).total_seconds()


def _heading_diff_deg(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)

class CollaborationService:
    def _publish_dds(self, topic: str, payload: dict) -> None:
        dds_adapter.publish(topic=topic, payload=payload)

    def _resolve_result_type(self, task: TaskContext) -> Optional[str]:
        if task.patrol_plan_output is not None:
            return "patrol"
        if task.tracking_plan_output is not None:
            return "tracking"
        if task.fixed_tracking_output is not None:
            return "fixed_tracking"
        if task.underwater_search_output is not None:
            return "underwater_search"
        if task.preplan_output is not None:
            return "preplan"
        return None

    def _publish_task_update_dds(self, task: TaskContext, update_type_key: str) -> None:
        result_type = self._resolve_result_type(task)
        payload = {
            "task_id": task.task_id,
            "task_type": TASK_TYPE_CODE_MAP.get(task.task_type, 0),
            "task_status": TASK_STATUS_CODE_MAP.get(task.status, 0),
            "execution_phase": PHASE_CODE_MAP.get(task.execution_phase, 0),
            "update_type": UPDATE_TYPE_CODE_MAP.get(update_type_key, 0),
            "result_type": RESULT_TYPE_CODE_MAP.get(result_type, 0),
            "current_target_batch_no": task.current_target_batch_no or 0,
            "finish_reason": FINISH_REASON_CODE_MAP.get(task.finish_reason, 0),
        }
        if task.tracking_plan_output is not None:
            payload["rel_range_m"] = task.tracking_plan_output.rel_range_m or 0
            payload["relative_bearing_deg"] = task.tracking_plan_output.relative_bearing_deg or 0
            payload["expected_speed"] = task.tracking_plan_output.expected_speed or 0
        self._publish_dds(TASK_UPDATE_TOPIC, payload)

    def _build_manual_selection_candidates(self, task: TaskContext) -> list[TargetInfo]:
        candidates = task.candidate_targets or []
        top_candidates = candidates[:4]

        result: list[TargetInfo] = []
        for item in top_candidates:
            result.append(
                TargetInfo(
                    target_id=item.get("target_id"),
                    target_batch_no=item.get("target_batch_no"),
                    target_type_code=item.get("target_type_code"),
                    target_name=item.get("target_name") or item.get("target_id"),
                    enemy_friend_attr=item.get("enemy_friend_attr"),
                    military_civil_attr=item.get("military_civil_attr"),
                )
            )
        return result

    def _try_auto_request_manual_selection(self, task: TaskContext) -> None:
        if task.manual_selection_request_sent:
            return
        if task.task_type != TaskType.TRACKING:
            return
        if task.target_constraint is not None and task.target_constraint.target_id:
            return

        candidates = task.candidate_targets or []
        if len(candidates) <= 1:
            return

        payload = ManualSelectionRequest(
            task_id=task.task_id,
            request_type="manual_selection",
            timeout_sec=task.manual_selection_timeout_sec,
            candidate_targets=self._build_manual_selection_candidates(task),
        )
        collaboration_store.append_manual_selection_request(payload.model_dump(mode="json"))
        self._publish_dds(
            MANUAL_SELECTION_REQUEST_TOPIC,
            payload.model_dump(mode="json"),
        )

        now = utc_now()
        task.manual_selection_request_sent = True
        task.manual_selection_pending = True
        task.manual_selection_feedback_received = False
        task.manual_selection_selected_target_id = None
        task.manual_selection_requested_at = now
        task.manual_selection_deadline = now + timedelta(seconds=payload.timeout_sec)
        task.manual_selection_candidate_count = len(payload.candidate_targets)
        task.manual_selection_last_countdown_sec = None
        print(
            f"[ManualSelection] task={task.task_id} request_sent candidates={task.manual_selection_candidate_count} "
            f"timeout_sec={payload.timeout_sec}"
        )
        task_store.update_task(task)

    def _update_manual_selection_timeout(self, task: TaskContext) -> None:
        if not task.manual_selection_pending:
            return
        if task.manual_selection_deadline is None:
            return
        now = utc_now()
        if now < task.manual_selection_deadline:
            remaining_sec = max(0, int((task.manual_selection_deadline - now).total_seconds()))
            if task.manual_selection_last_countdown_sec != remaining_sec:
                print(f"[ManualSelection] task={task.task_id} countdown={remaining_sec}s")
                task.manual_selection_last_countdown_sec = remaining_sec
                task_store.update_task(task)
            return

        task.manual_selection_pending = False
        task.manual_selection_last_countdown_sec = None
        task.update_time = now
        print(f"[ManualSelection] task={task.task_id} timeout reached, keep highest-score target")
        task_store.update_task(task)

    def _build_manual_switch_candidates(self, task: TaskContext) -> list[TargetInfo]:
        candidates = task.candidate_targets or []
        if not candidates or not task.current_target_id:
            return []

        current_score = None
        for item in candidates:
            if item.get("target_id") == task.current_target_id:
                current_score = float(item.get("total_score") or 0.0)
                break
        if current_score is None:
            return []

        higher: list[TargetInfo] = []
        for item in candidates:
            target_id = item.get("target_id")
            if target_id == task.current_target_id:
                continue
            score = float(item.get("total_score") or 0.0)
            if score <= current_score:
                continue
            higher.append(
                TargetInfo(
                    target_id=target_id,
                    target_batch_no=item.get("target_batch_no"),
                    target_type_code=item.get("target_type_code"),
                    target_name=item.get("target_name") or target_id,
                    enemy_friend_attr=item.get("enemy_friend_attr"),
                    military_civil_attr=item.get("military_civil_attr"),
                )
            )
            if len(higher) >= 2:
                break
        return higher

    def _try_auto_request_manual_switch(self, task: TaskContext) -> None:
        if task.manual_switch_request_sent:
            return
        if task.task_type != TaskType.TRACKING:
            return
        if not task.current_target_id:
            return
        if task.target_constraint is None or not task.target_constraint.target_id:
            # Switch scenario requires explicit designated target.
            return

        higher_candidates = self._build_manual_switch_candidates(task)
        if not higher_candidates:
            return

        payload = ManualSwitchRequest(
            task_id=task.task_id,
            request_type="manual_switch",
            timeout_sec=task.manual_switch_timeout_sec,
            current_target_id=task.current_target_id,
            new_candidate_targets=higher_candidates,
        )
        collaboration_store.append_manual_switch_request(payload.model_dump(mode="json"))
        self._publish_dds(
            MANUAL_SWITCH_REQUEST_TOPIC,
            payload.model_dump(mode="json"),
        )

        now = utc_now()
        task.manual_switch_request_sent = True
        task.manual_switch_pending = True
        task.manual_switch_feedback_received = False
        task.manual_switch_selected_target_id = None
        task.manual_switch_requested_at = now
        task.manual_switch_deadline = now + timedelta(seconds=payload.timeout_sec)
        task.manual_switch_candidate_count = len(payload.new_candidate_targets)
        task.manual_switch_last_countdown_sec = None
        print(
            f"[ManualSwitch] task={task.task_id} request_sent current={payload.current_target_id} "
            f"candidates={task.manual_switch_candidate_count} timeout_sec={payload.timeout_sec}"
        )
        task_store.update_task(task)

    def _update_manual_switch_timeout(self, task: TaskContext) -> None:
        if not task.manual_switch_pending:
            return
        if task.manual_switch_deadline is None:
            return

        now = utc_now()
        if now < task.manual_switch_deadline:
            remaining_sec = max(0, int((task.manual_switch_deadline - now).total_seconds()))
            if task.manual_switch_last_countdown_sec != remaining_sec:
                print(f"[ManualSwitch] task={task.task_id} countdown={remaining_sec}s")
                task.manual_switch_last_countdown_sec = remaining_sec
                task_store.update_task(task)
            return

        task.manual_switch_pending = False
        task.manual_switch_last_countdown_sec = None
        task.update_time = now
        print(f"[ManualSwitch] task={task.task_id} timeout reached, keep current target")
        task_store.update_task(task)

    def _build_plan_signature_payload(self, task: TaskContext) -> tuple[Optional[str], Optional[dict]]:
        if task.tracking_plan_output is not None:
            return (
                "tracking",
                {
                    "task_id": task.tracking_plan_output.task_id,
                    "target_id": task.tracking_plan_output.target_id,
                    "target_batch_no": task.tracking_plan_output.target_batch_no,
                    "rel_range_m": task.tracking_plan_output.rel_range_m,
                    "relative_bearing_deg": task.tracking_plan_output.relative_bearing_deg,
                    "expected_speed": task.tracking_plan_output.expected_speed,
                },
            )

        if task.patrol_plan_output is not None:
            return (
                "patrol",
                {
                    "task_id": task.patrol_plan_output.task_id,
                    "waypoints": [
                        {
                            "longitude": waypoint.longitude,
                            "latitude": waypoint.latitude,
                            "expected_speed": waypoint.expected_speed,
                        }
                        for waypoint in task.patrol_plan_output.waypoints
                    ],
                },
            )

        if task.underwater_search_output is not None:
            return (
                "underwater_search",
                {
                    "task_id": task.underwater_search_output.task_id,
                    "target_id": task.underwater_search_output.target_id,
                    "target_batch_no": task.underwater_search_output.target_batch_no,
                    "target_type_code": task.underwater_search_output.target_type_code,
                    "hit_longitude": task.underwater_search_output.hit_longitude,
                    "hit_latitude": task.underwater_search_output.hit_latitude,
                    "expected_speed": task.underwater_search_output.expected_speed,
                    "matched": task.underwater_search_output.matched,
                    "confidence": task.underwater_search_output.confidence,
                },
            )

        if task.fixed_tracking_output is not None:
            return (
                "fixed_tracking",
                {
                    "task_id": task.fixed_tracking_output.task_id,
                    "anchor_longitude": task.fixed_tracking_output.anchor_longitude,
                    "anchor_latitude": task.fixed_tracking_output.anchor_latitude,
                    "expected_speed": task.fixed_tracking_output.expected_speed,
                },
            )

        if task.preplan_output is not None:
            return (
                "preplan",
                {
                    "task_id": task.preplan_output.task_id,
                    "planned_route": [
                        {
                            "longitude": waypoint.longitude,
                            "latitude": waypoint.latitude,
                            "expected_speed": waypoint.expected_speed,
                        }
                        for waypoint in task.preplan_output.planned_route
                    ],
                    "feasible": task.preplan_output.feasible,
                    "reason": task.preplan_output.reason,
                },
            )

        return None, None

    def _build_autonomy_signature_payload(self, payload_obj) -> Optional[dict]:
        if isinstance(payload_obj, AutonomyPatrolDispatch):
            return {
                "task_id": payload_obj.task_id,
                "task_type": payload_obj.task_type,
                "plan_type": payload_obj.plan_type,
                "waypoints": [
                    {
                        "longitude": waypoint.longitude,
                        "latitude": waypoint.latitude,
                        "expected_speed": waypoint.expected_speed,
                    }
                    for waypoint in payload_obj.waypoints
                ],
            }

        if isinstance(payload_obj, AutonomyTrackingDispatch):
            return {
                "task_id": payload_obj.task_id,
                "task_type": payload_obj.task_type,
                "plan_type": payload_obj.plan_type,
                "target_id": payload_obj.target_id,
                "target_batch_no": payload_obj.target_batch_no,
                "rel_range_m": payload_obj.rel_range_m,
                "relative_bearing_deg": payload_obj.relative_bearing_deg,
                "expected_speed": payload_obj.expected_speed,
            }

        return None

    def report_stage_if_changed(self, task: TaskContext) -> None:
        stage = task.execution_phase
        if stage == task.last_reported_stage:
            return

        planning_client.report_stage(task.task_id, stage)
        self._publish_task_update_dds(task, update_type_key="phase_only")
        task.last_reported_stage = stage
        task_store.update_task(task)

    def report_plan_if_changed(self, task: TaskContext) -> None:
        plan_type, signature_payload = self._build_plan_signature_payload(task)
        payload = None

        if plan_type == "tracking":
            payload = task.tracking_plan_output.model_dump(mode="json")
        elif plan_type == "patrol":
            payload = task.patrol_plan_output.model_dump(mode="json")
        elif plan_type == "underwater_search":
            payload = task.underwater_search_output.model_dump(mode="json")
        elif plan_type == "fixed_tracking":
            payload = task.fixed_tracking_output.model_dump(mode="json")
        elif plan_type == "preplan":
            payload = task.preplan_output.model_dump(mode="json")

        if plan_type is None or payload is None or signature_payload is None:
            return

        signature = json.dumps(
            {
                "plan_type": plan_type,
                "payload": signature_payload,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

        if signature == task.last_reported_plan_signature:
            return

        planning_client.report_plan(task.task_id, plan_type, payload)
        self._publish_task_update_dds(task, update_type_key="result_only")
        if plan_type == "preplan":
            self._publish_dds(
                PREPLAN_RESULT_TOPIC,
                {
                    "task_id": task.task_id,
                    "task_type": TASK_TYPE_CODE_MAP.get(TaskType.PREPLAN, 5),
                    "waypoint_count": len(task.preplan_output.planned_route) if task.preplan_output else 0,
                    "planned_route": payload.get("planned_route", []),
                },
            )
        task.last_reported_plan_signature = signature
        task_store.update_task(task)

    def dispatch_autonomy_if_changed(self, task: TaskContext) -> None:
        payload_obj = None

        if task.patrol_plan_output is not None:
            task_type_value = task.task_type.value if hasattr(task.task_type, "value") else str(task.task_type)
            payload_obj = AutonomyPatrolDispatch(
                task_id=task.task_id,
                task_type=task_type_value,
                plan_type="patrol",
                waypoints=task.patrol_plan_output.waypoints,
                update_time=task.patrol_plan_output.update_time,
            )

        elif task.tracking_plan_output is not None:
            payload_obj = AutonomyTrackingDispatch(
                task_id=task.task_id,
                task_type="tracking",
                plan_type="tracking",
                target_id=task.tracking_plan_output.target_id,
                target_batch_no=task.tracking_plan_output.target_batch_no,
                rel_range_m=task.tracking_plan_output.rel_range_m,
                relative_bearing_deg=task.tracking_plan_output.relative_bearing_deg,
                expected_speed=task.tracking_plan_output.expected_speed,
                update_time=task.tracking_plan_output.update_time,
            )

        elif task.underwater_search_output is not None and task.recommended_point is not None:
            payload_obj = AutonomyTrackingDispatch(
                task_id=task.task_id,
                task_type="underwater_search",
                plan_type="underwater_search",
                target_id=task.underwater_search_output.target_id,
                target_batch_no=task.underwater_search_output.target_batch_no,
                rel_range_m=task.recommended_point.rel_range_m,
                relative_bearing_deg=task.recommended_point.rel_bearing_deg,
                expected_speed=task.underwater_search_output.expected_speed,
                update_time=task.underwater_search_output.update_time,
            )

        elif task.fixed_tracking_output is not None:
            payload_obj = AutonomyTrackingDispatch(
                task_id=task.task_id,
                task_type="fixed_tracking",
                plan_type="fixed_tracking",
                target_id=None,
                target_batch_no=None,
                rel_range_m=0.0,
                relative_bearing_deg=0.0,
                expected_speed=task.fixed_tracking_output.expected_speed,
                update_time=task.fixed_tracking_output.update_time,
            )

        if payload_obj is None:
            return

        signature_payload = self._build_autonomy_signature_payload(payload_obj)
        if signature_payload is None:
            return

        signature = json.dumps(
            signature_payload,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

        if signature == task.last_autonomy_dispatch_signature:
            return

        if isinstance(payload_obj, AutonomyPatrolDispatch):
            autonomy_client.post_patrol_plan(payload_obj)
        else:
            autonomy_client.post_tracking_plan(payload_obj)

        task.last_autonomy_dispatch_signature = signature
        task_store.update_task(task)

    def _dispatch_optical_linkage_if_changed(self, task: TaskContext, task_status: int) -> None:
        target_batch_no = task.current_target_batch_no
        if not target_batch_no:
            return

        payload = OpticalLinkageCommand(
            task_status=task_status,
            target_batch_no=target_batch_no,
        )
        signature = json.dumps(
            payload.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        if signature == task.last_optical_dispatch_signature:
            return

        optical_linkage_client.post_command(task.task_id, payload)
        self._publish_dds(
            ELECTRO_OPTICAL_LINKAGE_CMD_TOPIC,
            payload.model_dump(mode="json"),
        )
        if task_status == 1:
            media_client.get_stream_access(
                MediaStreamAccessRequest(
                    task_id=task.task_id,
                    stream_type="optical_video",
                    channel_id="optical-001",
                    media_protocol="webrtc",
                    request_time=utc_now(),
                )
            )
        task.last_optical_dispatch_signature = signature
        task.optronic_status = OptronicStatus(
            is_power_on=(task_status == 1),
            last_horizontal_angle_deg=None,
            update_time=utc_now(),
        )
        task.optronic_open_confirmed = task_status == 1
        task_store.update_task(task)

    def _check_arrival(self, task: TaskContext, ownship: OwnShipState) -> bool:
        if task.recommended_point is None:
            task.arrival_stable_cycles = 0
            task_store.update_task(task)
            return False

        ownship_point = GeoPoint(
            longitude=ownship.longitude,
            latitude=ownship.latitude,
        )
        recommended_point = GeoPoint(
            longitude=task.recommended_point.longitude,
            latitude=task.recommended_point.latitude,
        )

        distance_m = haversine_distance_m(ownship_point, recommended_point)
        distance_ok = distance_m < get_tracking_arrival_tolerance_m()

        if distance_ok:
            task.arrival_stable_cycles += 1
        else:
            task.arrival_stable_cycles = 0

        task_store.update_task(task)
        return task.arrival_stable_cycles >= get_tracking_arrival_stable_cycles()

    def _trigger_media_if_needed(self, task: TaskContext) -> None:
        if not task.optronic_open_confirmed:
            return

        if task.stream_media_param is None:
            return

        media = task.stream_media_param

        if media.photo_enabled:
            elapsed = _seconds_since(task.last_photo_time)
            if elapsed is None or elapsed >= media.photo_interval_sec:
                photo_result = media_client.capture_photo(task.task_id)
                task.last_photo_time = utc_now()
                self._publish_dds(
                    STREAM_MEDIA_PARAM_TOPIC,
                    {
                        "task_id": task.task_id,
                        "task_type": TASK_TYPE_CODE_MAP.get(task.task_type, 0),
                        "media_event_type": 1,
                        "media_type": 1,
                        "media_status": 3 if photo_result.get("success") else 4,
                        "media_access_path": photo_result.get("file_path", ""),
                        "snapshot_url": photo_result.get("file_path", ""),
                    },
                )

        if media.video_enabled:
            elapsed = _seconds_since(task.last_video_time)
            if elapsed is None or elapsed >= media.video_interval_sec:
                video_result = media_client.record_video(task.task_id, media.video_duration_sec)
                task.last_video_time = utc_now()
                self._publish_dds(
                    STREAM_MEDIA_PARAM_TOPIC,
                    {
                        "task_id": task.task_id,
                        "task_type": TASK_TYPE_CODE_MAP.get(task.task_type, 0),
                        "media_event_type": 2,
                        "media_type": 2,
                        "media_status": 3 if video_result.get("success") else 4,
                        "media_access_path": video_result.get("file_path", ""),
                        "snapshot_url": "",
                    },
                )

        task_store.update_task(task)

    def handle_tracking_collaboration(self, task: TaskContext, ownship: OwnShipState) -> None:
        self._try_auto_request_manual_selection(task)
        self._update_manual_selection_timeout(task)
        self._try_auto_request_manual_switch(task)
        self._update_manual_switch_timeout(task)
        self.report_stage_if_changed(task)
        self.report_plan_if_changed(task)
        self.dispatch_autonomy_if_changed(task)

        if task.status != TaskStatus.RUNNING:
            return

        if task.linkage_param is None or not task.linkage_param.enable_optical:
            return

        arrived = self._check_arrival(task, ownship)
        if not arrived:
            return

        self._dispatch_optical_linkage_if_changed(task, task_status=1)
        self._trigger_media_if_needed(task)

    def handle_patrol_collaboration(self, task: TaskContext) -> None:
        self.report_stage_if_changed(task)
        self.report_plan_if_changed(task)
        self.dispatch_autonomy_if_changed(task)

    def handle_fixed_tracking_collaboration(self, task: TaskContext) -> None:
        self.report_stage_if_changed(task)
        self.dispatch_autonomy_if_changed(task)

    def handle_underwater_search_collaboration(self, task: TaskContext) -> None:
        self.report_stage_if_changed(task)
        self.dispatch_autonomy_if_changed(task)

        if task.status != TaskStatus.RUNNING:
            return

        if task.task_type != TaskType.UNDERWATER_SEARCH:
            return

        elapsed = _seconds_since(task.last_sonar_poll_time)
        if elapsed is not None and elapsed < get_sonar_poll_interval_sec():
            return

        sonar_status = sonar_client.get_match_status(task.task_id)
        task.last_sonar_poll_time = utc_now()

        if task.underwater_search_output is not None:
            task.underwater_search_output.matched = sonar_status.matched
            task.underwater_search_output.confidence = sonar_status.confidence
            task.underwater_search_output.update_time = utc_now()

        if not sonar_status.matched:
            task.status = TaskStatus.COMPLETED
            task.finish_reason = FinishReason.SONAR_UNMATCHED
            task.end_time = utc_now()
            task.update_time = task.end_time
            task.execution_phase = "completed"

        task_store.update_task(task)

    def on_task_finished(self, task: TaskContext) -> None:
        if task.linkage_param is not None and task.linkage_param.enable_optical:
            self._dispatch_optical_linkage_if_changed(task, task_status=2)

    def apply_planning_callback(self, task: TaskContext, callback) -> None:
        task.planning_callback = callback
        task_store.update_task(task)

    def handle_preplan_collaboration(self, task: TaskContext) -> None:
        self.report_stage_if_changed(task)
        self.report_plan_if_changed(task)


collaboration_service = CollaborationService()
