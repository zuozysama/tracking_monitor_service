import json
from datetime import datetime
from typing import Optional

from clients.autonomy_client import autonomy_client
from clients.media_client import media_client
from clients.optical_linkage_client import optical_linkage_client
from clients.planning_client import planning_client
from clients.sonar_client import sonar_client
from domain.enums import TaskStatus, FinishReason, TaskType
from domain.models import (
    AutonomyPatrolDispatch,
    AutonomyTrackingDispatch,
    GeoPoint,
    MediaStreamAccessRequest,
    OpticalLinkageCommand,
    OptronicStatus,
    OwnShipState,
    TaskContext,
)
from store.task_store import task_store
from utils.config_utils import (
    get_sonar_poll_interval_sec,
    get_tracking_arrival_stable_cycles,
    get_tracking_arrival_tolerance_m,
)
from utils.geo_utils import haversine_distance_m
from utils.time_utils import utc_now


def _seconds_since(last_time: Optional[datetime]) -> Optional[float]:
    if last_time is None:
        return None
    return (utc_now() - last_time).total_seconds()


def _heading_diff_deg(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)

class CollaborationService:
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
                media_client.capture_photo(task.task_id)
                task.last_photo_time = utc_now()

        if media.video_enabled:
            elapsed = _seconds_since(task.last_video_time)
            if elapsed is None or elapsed >= media.video_interval_sec:
                media_client.record_video(task.task_id, media.video_duration_sec)
                task.last_video_time = utc_now()

        task_store.update_task(task)

    def handle_tracking_collaboration(self, task: TaskContext, ownship: OwnShipState) -> None:
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
