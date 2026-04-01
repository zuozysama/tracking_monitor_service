from domain.enums import TaskStatus, TrackingMode
from domain.models import GeoPoint, RecommendedPoint, TaskContext, TrackingPlanOutput
from services.collaboration_service import collaboration_service
from services.patrol_service import patrol_service
from store.situation_store import situation_store
from store.task_store import task_store
from utils.config_utils import (
    get_tracking_arrival_stable_cycles,
    get_tracking_arrival_tolerance_m,
    get_tracking_escort_distance_m,
    get_tracking_expel_distance_m,
    get_tracking_filter_identity_weights,
    get_tracking_intercept_distance_m,
    get_tracking_max_target_range_m,
)
from utils.geo_utils import haversine_distance_m
from utils.time_utils import utc_now
from algorithms.target_filter import filter_and_select_target
from algorithms.track_point_generator import (
    generate_simple_tracking_point,
    relative_signed_angle_deg,
)


class TrackingService:
    def _reset_intercept_state(self, task: TaskContext) -> None:
        task.intercept_stage = 0
        task.intercept_side = None
        task.intercept_arrival_stable_cycles = 0

    def _reset_expel_state(self, task: TaskContext) -> None:
        task.expel_stage = 0
        task.expel_side = None
        task.expel_arrival_stable_cycles = 0

    def _infer_side_from_bearing(self, target_heading_deg: float, rel_bearing_deg: float) -> str:
        signed = relative_signed_angle_deg(target_heading_deg, rel_bearing_deg)
        if signed > 0:
            return "right"
        if signed < 0:
            return "left"
        return "right"

    def _refresh_intercept_stage(self, task: TaskContext, ownship, target) -> None:
        if task.mode != TrackingMode.INTERCEPT:
            return

        if task.recommended_point is None:
            task.intercept_arrival_stable_cycles = 0
            return

        ownship_point = GeoPoint(longitude=ownship.longitude, latitude=ownship.latitude)
        recommended_point = GeoPoint(
            longitude=task.recommended_point.longitude,
            latitude=task.recommended_point.latitude,
        )
        distance_m = haversine_distance_m(ownship_point, recommended_point)

        if distance_m < get_tracking_arrival_tolerance_m():
            task.intercept_arrival_stable_cycles += 1
        else:
            task.intercept_arrival_stable_cycles = 0

        if task.intercept_arrival_stable_cycles < get_tracking_arrival_stable_cycles():
            return

        if task.intercept_stage == 0:
            if task.recommended_point.rel_bearing_deg is not None:
                task.intercept_side = self._infer_side_from_bearing(
                    target_heading_deg=target.heading,
                    rel_bearing_deg=task.recommended_point.rel_bearing_deg,
                )
            if task.intercept_side is None:
                task.intercept_side = "right"
            task.intercept_stage = 1
            task.intercept_arrival_stable_cycles = 0
            return

        if task.intercept_stage == 1:
            task.intercept_stage = 2
            task.intercept_arrival_stable_cycles = 0
            return

    def _refresh_expel_stage(self, task: TaskContext, ownship, target) -> None:
        if task.mode != TrackingMode.EXPEL:
            return

        if task.recommended_point is None:
            task.expel_arrival_stable_cycles = 0
            return

        ownship_point = GeoPoint(longitude=ownship.longitude, latitude=ownship.latitude)
        recommended_point = GeoPoint(
            longitude=task.recommended_point.longitude,
            latitude=task.recommended_point.latitude,
        )
        distance_m = haversine_distance_m(ownship_point, recommended_point)

        if distance_m < get_tracking_arrival_tolerance_m():
            task.expel_arrival_stable_cycles += 1
        else:
            task.expel_arrival_stable_cycles = 0

        if task.expel_arrival_stable_cycles < get_tracking_arrival_stable_cycles():
            return

        if task.expel_stage == 0:
            if task.recommended_point.rel_bearing_deg is not None:
                task.expel_side = self._infer_side_from_bearing(
                    target_heading_deg=target.heading,
                    rel_bearing_deg=task.recommended_point.rel_bearing_deg,
                )
            if task.expel_side is None:
                task.expel_side = "right"
            task.expel_stage = 1
            task.expel_arrival_stable_cycles = 0
            return

    def refresh_result(self, task: TaskContext) -> None:
        if task.status not in {"running", "waiting_target"} and task.status not in {TaskStatus.RUNNING, TaskStatus.WAITING_TARGET}:
            return

        patrol_service.refresh_result(task)

        ownship = situation_store.get_ownship()
        if ownship is None:
            task.status = TaskStatus.WAITING_TARGET
            task.search_hit = False
            task.execution_phase = "patrolling"
            task.recommended_point = None
            task.tracking_plan_output = None
            self._reset_intercept_state(task)
            self._reset_expel_state(task)
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
        if task.target_constraint is not None and task.target_constraint.target_id:
            # In explicit designated-target mode, keep tracking the designated target,
            # but still compute global ranked candidates for manual-switch decision.
            relaxed_constraint = task.target_constraint.model_copy(deep=True)
            relaxed_constraint.target_id = None
            relaxed_constraint.target_batch_no = None
            _, relaxed_debug_candidates = filter_and_select_target(
                targets=targets,
                ownship=ownship,
                constraint=relaxed_constraint,
                task_area=task.task_area,
                max_target_range_m=get_tracking_max_target_range_m(),
                identity_weights=get_tracking_filter_identity_weights(),
                current_target_id=task.current_target_id,
            )
            task.candidate_targets = relaxed_debug_candidates

        if target is None:
            task.status = TaskStatus.WAITING_TARGET
            task.search_hit = False
            task.execution_phase = "patrolling"
            task.recommended_point = None
            task.tracking_plan_output = None
            self._reset_intercept_state(task)
            self._reset_expel_state(task)
            task.update_time = utc_now()
            task_store.update_task(task)
            # waiting_target means patrol mode before lock-on;
            # report patrol plan/stage and dispatch patrol waypoints accordingly.
            collaboration_service.handle_patrol_collaboration(task)
            return

        previous_target_id = task.current_target_id
        if task.mode == TrackingMode.INTERCEPT and previous_target_id not in {None, target.target_id}:
            self._reset_intercept_state(task)
        if task.mode == TrackingMode.EXPEL and previous_target_id not in {None, target.target_id}:
            self._reset_expel_state(task)
        self._refresh_intercept_stage(task, ownship, target)
        self._refresh_expel_stage(task, ownship, target)

        task.status = TaskStatus.RUNNING
        task.search_hit = True
        task.execution_phase = "engaging"
        task.current_target_id = target.target_id
        task.current_target_batch_no = target.target_batch_no
        task.last_seen_target_time = utc_now()

        point, rel_bearing_deg = generate_simple_tracking_point(
            mode=task.mode,
            target=target,
            ownship=ownship,
            escort_distance_m=get_tracking_escort_distance_m(),
            intercept_distance_m=get_tracking_intercept_distance_m(),
            expel_distance_m=get_tracking_expel_distance_m(),
            intercept_stage=task.intercept_stage,
            intercept_side=task.intercept_side,
            expel_stage=task.expel_stage,
            expel_side=task.expel_side,
        )

        if task.mode == TrackingMode.ESCORT:
            rel_range_m = get_tracking_escort_distance_m()
        elif task.mode == TrackingMode.INTERCEPT:
            rel_range_m = get_tracking_intercept_distance_m()
        elif task.mode == TrackingMode.EXPEL:
            rel_range_m = get_tracking_escort_distance_m() if task.expel_stage <= 0 else get_tracking_expel_distance_m()
        else:
            rel_range_m = 0.0

        task.recommended_point = RecommendedPoint(
            longitude=point.longitude,
            latitude=point.latitude,
            ref_type="target",
            ref_id=target.target_id,
            rel_range_m=rel_range_m,
            rel_bearing_deg=rel_bearing_deg,
            expected_heading=target.heading,
            expected_speed=target.speed,
            update_time=utc_now(),
        )

        task.patrol_plan_output = None
        task.tracking_plan_output = TrackingPlanOutput(
            task_id=task.task_id,
            target_id=target.target_id,
            target_batch_no=target.target_batch_no,
            rel_range_m=rel_range_m,
            relative_bearing_deg=rel_bearing_deg,
            expected_speed=task.expected_speed if task.expected_speed is not None else target.speed,
            update_time=utc_now(),
        )

        task.update_time = utc_now()
        task_store.update_task(task)

        collaboration_service.handle_tracking_collaboration(task, ownship)


tracking_service = TrackingService()
