from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from domain.enums import FinishReason, TaskStatus, TaskType


class CompatModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class GeoPoint(CompatModel):
    longitude: float = Field(..., ge=-180.0, le=180.0)
    latitude: float = Field(..., ge=-90.0, le=90.0)


class TaskArea(CompatModel):
    area_type: str = "polygon"
    points: Optional[List[GeoPoint]] = None
    center: Optional[GeoPoint] = None
    radius_m: Optional[float] = Field(default=None, gt=0.0)

    @model_validator(mode="after")
    def validate_points(self):
        if self.area_type == "polygon":
            if self.points is None or len(self.points) < 3:
                raise ValueError("points must contain at least 3 points when area_type=polygon")
            return self

        if self.area_type == "route":
            if self.points is None or len(self.points) < 2:
                raise ValueError("points must contain at least 2 points when area_type=route")
            return self

        if self.area_type == "circle":
            if self.center is None:
                raise ValueError("center is required when area_type=circle")
            if self.radius_m is None:
                raise ValueError("radius_m is required when area_type=circle")
            return self

        if self.area_type == "point":
            if self.points is None or len(self.points) != 1:
                raise ValueError("points must contain exactly 1 point when area_type=point")
            if self.center is not None:
                raise ValueError("center is not allowed when area_type=point")
            if self.radius_m is not None:
                raise ValueError("radius_m is not allowed when area_type=point")
            return self

        raise ValueError("area_type must be one of polygon, route, circle, point")


class TargetInfo(CompatModel):
    target_id: Optional[str] = None
    target_batch_no: Optional[int] = None
    target_type_code: Optional[int] = None
    threat_level: Optional[int] = None
    target_name: Optional[str] = None
    enemy_friend_attr: Optional[int] = None
    military_civil_attr: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def fill_legacy_fields(cls, data):
        if not isinstance(data, dict):
            return data
        if "target_batch_no" not in data and "batch_id" in data:
            data["target_batch_no"] = data["batch_id"]
        if "target_type_code" not in data and "target_type" in data:
            data["target_type_code"] = data["target_type"]
        if "enemy_friend_attr" not in data and "d_friend_attr" in data:
            data["enemy_friend_attr"] = data["d_friend_attr"]
        if "military_civil_attr" not in data and "j_civil_attr" in data:
            data["military_civil_attr"] = data["j_civil_attr"]
        return data


class EndCondition(CompatModel):
    duration_sec: Optional[int] = Field(default=None, ge=1)
    out_of_region_finish: bool = True
    target_lost_timeout_sec: Optional[int] = Field(default=30, ge=1)
    manual_terminate_allowed: bool = True


class StreamMediaParam(CompatModel):
    photo_enabled: bool = False
    photo_interval_sec: Optional[int] = Field(default=None, ge=1)
    video_enabled: bool = False
    video_interval_sec: Optional[int] = Field(default=None, ge=1)
    video_duration_sec: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_strategy(self):
        if self.photo_enabled and self.photo_interval_sec is None:
            raise ValueError("photo_interval_sec is required when photo_enabled=true")
        if self.video_enabled and self.video_interval_sec is None:
            raise ValueError("video_interval_sec is required when video_enabled=true")
        if self.video_enabled and self.video_duration_sec is None:
            raise ValueError("video_duration_sec is required when video_enabled=true")
        return self


class LinkageParam(CompatModel):
    enable_optical: bool = False
    enable_evidence: bool = False


class CreateTaskRequest(CompatModel):
    task_id: str
    task_type: TaskType

    task_name: Optional[str] = None
    task_source: Optional[str] = None
    priority: int = 1
    remark: Optional[str] = None

    target_info: Optional[TargetInfo] = None

    task_area: Optional[TaskArea] = None

    expected_speed: Optional[float] = Field(default=None, ge=0.0)
    update_interval_sec: Optional[int] = Field(default=1, ge=1)

    end_condition: Optional[EndCondition] = None
    stream_media_param: Optional[StreamMediaParam] = None
    linkage_param: Optional[LinkageParam] = None

    @model_validator(mode="after")
    def validate_task_fields(self):
        if self.task_type == TaskType.PATROL and self.task_area is None:
            raise ValueError("task_area is required when task_type=patrol")

        if self.task_type in {TaskType.ESCORT, TaskType.INTERCEPT, TaskType.EXPEL}:
            if self.task_area is None:
                raise ValueError("task_area is required when task_type=escort/intercept/expel")

        if self.task_type == TaskType.UNDERWATER_SEARCH and self.task_area is None:
            raise ValueError("task_area is required when task_type=underwater_search")

        if self.task_type == TaskType.FIXED_TRACKING:
            if self.task_area is None:
                raise ValueError("task_area is required when task_type=fixed_tracking")
            if self.task_area.area_type != "point":
                raise ValueError("task_area.area_type must be point when task_type=fixed_tracking")

        if self.task_type == TaskType.PREPLAN and self.task_area is None:
            raise ValueError("task_area is required when task_type=preplan")

        if self.task_area is not None and self.task_area.area_type == "point" and self.task_type != TaskType.FIXED_TRACKING:
            raise ValueError("area_type=point is only allowed when task_type=fixed_tracking")

        return self


class TerminateTaskRequest(CompatModel):
    reason: Optional[str] = None


class TargetConstraint(CompatModel):
    target_id: Optional[str] = None
    target_batch_no: Optional[int] = None
    target_type_code: Optional[int] = None
    threat_level: Optional[int] = None
    target_name: Optional[str] = None
    enemy_friend_attr: Optional[int] = None
    military_civil_attr: Optional[int] = None
    auto_search: bool = True

    allowed_target_type_codes: Optional[List[int]] = None
    preferred_target_type_codes: Optional[List[int]] = None
    allowed_enemy_friend_attrs: Optional[List[int]] = None
    preferred_enemy_friend_attrs: Optional[List[int]] = None
    allowed_military_civil_attrs: Optional[List[int]] = None
    preferred_military_civil_attrs: Optional[List[int]] = None

    min_target_range_m: Optional[float] = Field(default=None, ge=0.0)
    max_target_range_m: Optional[float] = Field(default=None, ge=0.0)
    bearing_min_deg: Optional[float] = Field(default=None, ge=0.0, lt=360.0)
    bearing_max_deg: Optional[float] = Field(default=None, ge=0.0, lt=360.0)

    @model_validator(mode="after")
    def validate_constraint(self):
        if (
            self.min_target_range_m is not None
            and self.max_target_range_m is not None
            and self.min_target_range_m > self.max_target_range_m
        ):
            raise ValueError("min_target_range_m cannot be greater than max_target_range_m")
        return self

    @model_validator(mode="before")
    @classmethod
    def fill_legacy_fields(cls, data):
        if not isinstance(data, dict):
            return data
        if "enemy_friend_attr" not in data and "d_friend_attr" in data:
            data["enemy_friend_attr"] = data["d_friend_attr"]
        if "military_civil_attr" not in data and "j_civil_attr" in data:
            data["military_civil_attr"] = data["j_civil_attr"]
        if "allowed_enemy_friend_attrs" not in data and "prefer_d_attrs" in data:
            data["allowed_enemy_friend_attrs"] = data["prefer_d_attrs"]
        if "preferred_enemy_friend_attrs" not in data and "prefer_d_attrs" in data:
            data["preferred_enemy_friend_attrs"] = data["prefer_d_attrs"]
        if "allowed_military_civil_attrs" not in data and "prefer_j_attrs" in data:
            data["allowed_military_civil_attrs"] = data["prefer_j_attrs"]
        if "preferred_military_civil_attrs" not in data and "prefer_j_attrs" in data:
            data["preferred_military_civil_attrs"] = data["prefer_j_attrs"]
        return data


class OwnShipState(CompatModel):
    platform_id: int
    longitude: float = Field(..., ge=-180.0, le=180.0)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    heading_deg: float = Field(..., ge=0.0, lt=360.0)
    speed_mps: float = Field(..., ge=0.0)
    timestamp: datetime

    @model_validator(mode="before")
    @classmethod
    def fill_legacy_fields(cls, data):
        if not isinstance(data, dict):
            return data
        if "platform_id" not in data:
            ship_id = data.get("ship_id", 0)
            try:
                data["platform_id"] = int(ship_id)
            except (TypeError, ValueError):
                data["platform_id"] = 0
        if "heading_deg" not in data and "heading" in data:
            data["heading_deg"] = data["heading"]
        if "speed_mps" not in data and "speed" in data:
            data["speed_mps"] = data["speed"]
        return data

    @property
    def heading(self) -> float:
        return self.heading_deg

    @property
    def speed(self) -> float:
        return self.speed_mps


class TargetState(CompatModel):
    source_platform_id: Optional[int] = None
    target_id: Optional[str] = None
    target_batch_no: int
    target_bearing_deg: Optional[float] = Field(default=None, ge=0.0, lt=360.0)
    target_distance_m: Optional[float] = Field(default=None, ge=0.0)
    target_absolute_speed_mps: Optional[float] = Field(default=None, ge=0.0)
    target_absolute_heading_deg: Optional[float] = Field(default=None, ge=0.0, lt=360.0)
    target_longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    target_latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    target_type_code: Optional[int] = None
    enemy_friend_attr: Optional[int] = None
    military_civil_attr: Optional[int] = None
    target_name: Optional[str] = None
    threat_level: Optional[int] = None
    timestamp: datetime
    active: bool = True

    @model_validator(mode="before")
    @classmethod
    def fill_legacy_fields(cls, data):
        if not isinstance(data, dict):
            return data
        if "target_batch_no" not in data:
            if "batch_id" in data:
                data["target_batch_no"] = data["batch_id"]
            elif "target_id" in data:
                digits = "".join(ch for ch in str(data["target_id"]) if ch.isdigit())
                data["target_batch_no"] = int(digits or 0)
        if "target_type_code" not in data and "target_type" in data:
            data["target_type_code"] = data["target_type"]
        if "enemy_friend_attr" not in data and "d_friend_attr" in data:
            data["enemy_friend_attr"] = data["d_friend_attr"]
        if "military_civil_attr" not in data and "j_civil_attr" in data:
            data["military_civil_attr"] = data["j_civil_attr"]
        if "target_longitude" not in data and "longitude" in data:
            data["target_longitude"] = data["longitude"]
        if "target_latitude" not in data and "latitude" in data:
            data["target_latitude"] = data["latitude"]
        if "target_absolute_heading_deg" not in data and "heading" in data:
            data["target_absolute_heading_deg"] = data["heading"]
        if "target_absolute_speed_mps" not in data and "speed" in data:
            data["target_absolute_speed_mps"] = data["speed"]
        if "target_id" not in data or data["target_id"] in (None, ""):
            batch_no = data.get("target_batch_no")
            if batch_no is not None:
                data["target_id"] = f"target-{batch_no}"
        return data

    @property
    def longitude(self) -> Optional[float]:
        return self.target_longitude

    @property
    def latitude(self) -> Optional[float]:
        return self.target_latitude

    @property
    def heading(self) -> float:
        return self.target_absolute_heading_deg or 0.0

    @property
    def speed(self) -> float:
        return self.target_absolute_speed_mps or 0.0


class UpdateTargetsRequest(CompatModel):
    revision: Optional[int] = Field(default=None, ge=1)
    is_full_snapshot: Optional[bool] = None
    source_id: Optional[str] = None
    sync_mode: Optional[Literal["replace", "merge"]] = None
    targets: List[TargetState]


class MockDdsOwnshipRequest(CompatModel):
    payload: OwnShipState


class MockDdsTargetsRequest(CompatModel):
    target_count: int
    revision: Optional[int] = Field(default=None, ge=1)
    is_full_snapshot: Optional[bool] = None
    source_id: Optional[str] = None
    sync_mode: Optional[Literal["replace", "merge"]] = None
    targets: List[TargetState]


class RecommendedPoint(CompatModel):
    longitude: float
    latitude: float
    ref_type: str
    ref_id: Optional[str] = None
    rel_range_m: Optional[float] = None
    rel_bearing_deg: Optional[float] = None
    expected_heading: Optional[float] = None
    expected_speed: Optional[float] = None
    update_time: datetime


class PatrolWaypoint(CompatModel):
    longitude: float
    latitude: float
    expected_speed: float


class PatrolPlanOutput(CompatModel):
    task_id: str
    plan_type: str = "patrol"
    waypoints: List[PatrolWaypoint]
    update_time: datetime


class TrackingPlanOutput(CompatModel):
    task_id: str
    plan_type: str = "tracking"
    target_id: Optional[str] = None
    target_batch_no: Optional[int] = None
    rel_range_m: Optional[float] = None
    relative_bearing_deg: Optional[float] = None
    expected_speed: Optional[float] = None
    update_time: datetime


class UnderwaterSearchOutput(CompatModel):
    task_id: str
    plan_type: str = "underwater_search"
    target_id: Optional[str] = None
    target_batch_no: Optional[int] = None
    target_type_code: Optional[int] = None
    hit_longitude: Optional[float] = None
    hit_latitude: Optional[float] = None
    expected_speed: Optional[float] = None
    coordination_required: bool = True
    matched: Optional[bool] = None
    confidence: Optional[float] = None
    update_time: datetime


class FixedTrackingOutput(CompatModel):
    task_id: str
    plan_type: str = "fixed_tracking"
    anchor_longitude: float
    anchor_latitude: float
    expected_speed: Optional[float] = None
    update_time: datetime


class PreplanOutput(CompatModel):
    task_id: str
    task_type: str = "preplan"
    plan_type: str = "preplan"
    planned_route: List[PatrolWaypoint]
    feasible: Optional[bool] = True
    reason: Optional[str] = "方案可执行"


class FeasibilityCallbackRequest(CompatModel):
    task_id: str
    plan_type: str
    feasible: bool
    reason: str
    suggested_action: str
    callback_time: datetime


class OptronicStatus(CompatModel):
    is_power_on: bool = False
    last_horizontal_angle_deg: Optional[float] = None
    update_time: datetime


class OpticalLinkageCommand(CompatModel):
    task_type: int = 0
    task_no: int = 1
    task_status: int
    dispatch_task_type: int = 1
    target_batch_no: int
    reserved_ext: str = "0000000000000000"


class SonarMatchStatus(CompatModel):
    matched: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    update_time: datetime


class MediaStreamAccessRequest(CompatModel):
    task_id: str
    stream_type: str
    channel_id: str
    media_protocol: str
    request_time: datetime


class ManualSelectionRequest(CompatModel):
    task_id: str
    request_type: str
    timeout_sec: int = Field(..., ge=1)
    candidate_targets: List[TargetInfo]


class ManualSwitchRequest(CompatModel):
    task_id: str
    request_type: str
    timeout_sec: int = Field(..., ge=1)
    current_target_id: str
    new_candidate_targets: List[TargetInfo]


class ManualSelectionFeedbackRequest(CompatModel):
    task_id: str
    selected_target_id: str
    feedback_time: datetime


class ManualSwitchFeedbackRequest(CompatModel):
    task_id: str
    selected_target_id: Optional[str] = None
    keep_current: bool
    feedback_time: datetime


class TaskContext(CompatModel):
    task_id: str
    task_type: TaskType
    task_name: Optional[str] = None
    task_source: Optional[str] = None
    priority: int = 1
    remark: Optional[str] = None

    target_info: Optional[TargetInfo] = None
    task_area: Optional[TaskArea] = None
    anchor_point: Optional[GeoPoint] = None

    target_constraint: Optional[TargetConstraint] = None
    polygon_region: Optional[TaskArea] = None
    default_region_radius_m: Optional[float] = 3000.0

    expected_speed: Optional[float] = None
    update_interval_sec: int = 1

    end_condition: EndCondition
    stream_media_param: Optional[StreamMediaParam] = None
    linkage_param: Optional[LinkageParam] = None

    status: TaskStatus = TaskStatus.CREATED
    finish_reason: Optional[FinishReason] = None

    create_time: datetime
    start_time: Optional[datetime] = None
    update_time: datetime
    end_time: Optional[datetime] = None

    current_target_id: Optional[str] = None
    current_target_batch_no: Optional[int] = None
    intercept_stage: int = 0
    intercept_side: Optional[str] = None
    intercept_arrival_stable_cycles: int = 0
    expel_stage: int = 0
    expel_side: Optional[str] = None
    expel_arrival_stable_cycles: int = 0
    recommended_point: Optional[RecommendedPoint] = None
    last_seen_target_time: Optional[datetime] = None
    candidate_targets: Optional[List[Dict[str, Any]]] = None
    search_hit: bool = False
    has_entered_task_area: bool = False

    execution_phase: str = "idle"
    patrol_waypoints: Optional[List[PatrolWaypoint]] = None
    current_waypoint_index: int = 0

    patrol_plan_output: Optional[PatrolPlanOutput] = None
    tracking_plan_output: Optional[TrackingPlanOutput] = None
    underwater_search_output: Optional[UnderwaterSearchOutput] = None
    fixed_tracking_output: Optional[FixedTrackingOutput] = None
    preplan_output: Optional[PreplanOutput] = None

    arrival_stable_cycles: int = 0
    optronic_status: Optional[OptronicStatus] = None
    optronic_open_confirmed: bool = False
    optronic_init_pointing_sent: bool = False
    last_optronic_post_time: Optional[datetime] = None
    last_photo_time: Optional[datetime] = None
    last_video_time: Optional[datetime] = None
    last_sonar_poll_time: Optional[datetime] = None

    last_reported_stage: Optional[str] = None
    last_reported_plan_signature: Optional[str] = None
    planning_callback: Optional[FeasibilityCallbackRequest] = None
    last_autonomy_dispatch_signature: Optional[str] = None
    last_optical_dispatch_signature: Optional[str] = None
    manual_selection_request_sent: bool = False
    manual_selection_pending: bool = False
    manual_selection_timeout_sec: int = 20
    manual_selection_requested_at: Optional[datetime] = None
    manual_selection_deadline: Optional[datetime] = None
    manual_selection_feedback_received: bool = False
    manual_selection_selected_target_id: Optional[str] = None
    manual_selection_candidate_count: int = 0
    manual_selection_last_countdown_sec: Optional[int] = None
    manual_switch_request_sent: bool = False
    manual_switch_pending: bool = False
    manual_switch_timeout_sec: int = 20
    manual_switch_requested_at: Optional[datetime] = None
    manual_switch_deadline: Optional[datetime] = None
    manual_switch_feedback_received: bool = False
    manual_switch_selected_target_id: Optional[str] = None
    manual_switch_candidate_count: int = 0
    manual_switch_last_countdown_sec: Optional[int] = None


class TaskStatusResponse(CompatModel):
    task_id: str
    task_type: TaskType
    task_name: Optional[str] = None
    task_status: str
    start_time: Optional[datetime] = None
    update_time: datetime
    remaining_time_sec: Optional[int] = None
    finish_reason: Optional[FinishReason] = None
    execution_phase: str


class TaskResultResponse(CompatModel):
    task_id: str
    task_type: TaskType
    task_name: Optional[str] = None
    task_status: str
    current_target_id: Optional[str] = None
    current_target_info: Optional[TargetState] = None
    recommended_point: Optional[RecommendedPoint] = None
    patrol_plan_output: Optional[PatrolPlanOutput] = None
    tracking_plan_output: Optional[TrackingPlanOutput] = None
    underwater_search_output: Optional[UnderwaterSearchOutput] = None
    fixed_tracking_output: Optional[FixedTrackingOutput] = None
    preplan_output: Optional[PreplanOutput] = None
    stream_media_param: Optional[StreamMediaParam] = None
    linkage_param: Optional[LinkageParam] = None
    update_time: datetime
    finish_reason: Optional[FinishReason] = None
    optronic_status: Optional[OptronicStatus] = None
    planning_callback: Optional[FeasibilityCallbackRequest] = None


class TaskOutputResponse(CompatModel):
    task_id: str
    task_type: TaskType
    output_type: str
    patrol_plan_output: Optional[PatrolPlanOutput] = None
    tracking_plan_output: Optional[TrackingPlanOutput] = None
    underwater_search_output: Optional[UnderwaterSearchOutput] = None
    fixed_tracking_output: Optional[FixedTrackingOutput] = None
    preplan_output: Optional[PreplanOutput] = None
    update_time: datetime


class AutonomyPatrolWaypoint(CompatModel):
    longitude: float
    latitude: float
    speed: float = Field(..., ge=0.0)


class AutonomyPatrolParams(CompatModel):
    total_number_of_points: int = Field(..., ge=0)
    waypoints: List[AutonomyPatrolWaypoint]
    max_speed: float = Field(..., ge=0.0)
    end_time: datetime

    @model_validator(mode="after")
    def validate_waypoint_count(self):
        if self.total_number_of_points != len(self.waypoints):
            raise ValueError("total_number_of_points must equal len(waypoints)")
        return self


class AutonomyPatrolDispatch(CompatModel):
    task_id: Union[int, str]
    task_status: int = 0
    task_mode: int = 1
    params: AutonomyPatrolParams


class AutonomyTrackingParams(CompatModel):
    target_id: Optional[str] = None
    target_batch_no: Optional[int] = None
    rel_range_m: Optional[float] = None
    relative_bearing_deg: Optional[float] = None
    max_speed: float = Field(..., ge=0.0)


class AutonomyTrackingDispatch(CompatModel):
    task_id: Union[int, str]
    task_status: int = 1
    task_mode: int = 3
    params: AutonomyTrackingParams
