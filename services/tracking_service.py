from typing import Optional

from domain.enums import FinishReason, TaskStatus, TaskType, TrackingMode
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
from utils.point_timing_log import print_point_generation_timing
from utils.time_utils import utc_now
from algorithms.patrol_planner import _LocalPoint, _project_from_local, _project_to_local
from algorithms.target_filter import filter_and_select_target
from algorithms.track_point_generator import (
    bearing_between_points_deg,
    generate_tracking_candidate_points,
    move_point_by_bearing_and_distance,
    relative_signed_angle_deg,
)


class TrackingService:
    EXPEL_SIDE_AMBIGUOUS_DEG = 5.0
    INTERCEPT_SIDE_AMBIGUOUS_DEG = 5.0
    POINT_SWITCH_SCORE_MARGIN = 0.15
    POINT_SWITCH_CONFIRM_CYCLES = 5

    def _resolve_tracking_mode(self, task: TaskContext) -> Optional[TrackingMode]:
        if task.task_type == TaskType.ESCORT:
            return TrackingMode.ESCORT
        if task.task_type == TaskType.INTERCEPT:
            return TrackingMode.INTERCEPT
        if task.task_type == TaskType.EXPEL:
            return TrackingMode.EXPEL
        return None

    def _reset_intercept_state(self, task: TaskContext) -> None:
        task.intercept_stage = 0
        task.intercept_side = None
        task.intercept_arrival_stable_cycles = 0
        self._reset_tracking_point_selection(task)

    def _reset_expel_state(self, task: TaskContext) -> None:
        task.expel_stage = 0
        task.expel_side = None
        task.expel_arrival_stable_cycles = 0
        self._reset_tracking_point_selection(task)

    def _reset_tracking_point_selection(self, task: TaskContext) -> None:
        task.tracking_point_sector = None
        task.tracking_point_switch_candidate_sector = None
        task.tracking_point_switch_confirm_cycles = 0

    def _reset_tracking_point_switch_candidate(self, task: TaskContext) -> None:
        task.tracking_point_switch_candidate_sector = None
        task.tracking_point_switch_confirm_cycles = 0

    def _select_tracking_candidate(self, task: TaskContext, candidates: list[dict]) -> Optional[dict]:
        if not candidates:
            self._reset_tracking_point_selection(task)
            return None

        top_candidate = candidates[0]
        candidate_by_sector = {candidate.get("sector"): candidate for candidate in candidates}
        current_sector = getattr(task, "tracking_point_sector", None)
        current_candidate = candidate_by_sector.get(current_sector)

        if current_candidate is None:
            task.tracking_point_sector = top_candidate.get("sector")
            self._reset_tracking_point_switch_candidate(task)
            return top_candidate

        if top_candidate.get("sector") == current_sector:
            self._reset_tracking_point_switch_candidate(task)
            return top_candidate

        top_score = float(top_candidate.get("point_score", 0.0))
        current_score = float(current_candidate.get("point_score", 0.0))
        if top_score > current_score + self.POINT_SWITCH_SCORE_MARGIN:
            top_sector = top_candidate.get("sector")
            if task.tracking_point_switch_candidate_sector == top_sector:
                task.tracking_point_switch_confirm_cycles += 1
            else:
                task.tracking_point_switch_candidate_sector = top_sector
                task.tracking_point_switch_confirm_cycles = 1

            if task.tracking_point_switch_confirm_cycles >= self.POINT_SWITCH_CONFIRM_CYCLES:
                task.tracking_point_sector = top_sector
                self._reset_tracking_point_switch_candidate(task)
                return top_candidate
        else:
            self._reset_tracking_point_switch_candidate(task)

        return current_candidate

    def _generate_tracking_point_with_hysteresis(
        self,
        task: TaskContext,
        mode: TrackingMode,
        target,
        ownship,
    ) -> tuple[GeoPoint, float]:
        candidates = generate_tracking_candidate_points(
            mode=mode,
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
        selected_candidate = self._select_tracking_candidate(task, candidates)
        if selected_candidate is not None:
            return selected_candidate["point"], selected_candidate["rel_bearing_deg"]

        target_point = GeoPoint(longitude=target.longitude, latitude=target.latitude)
        fallback_bearing = (target.heading + 180.0) % 360.0
        fallback_point = move_point_by_bearing_and_distance(
            start=target_point,
            bearing_deg=fallback_bearing,
            distance_m=get_tracking_escort_distance_m(),
        )
        return fallback_point, 180.0

    def _task_area_center(self, task: TaskContext) -> Optional[GeoPoint]:
        task_area = task.task_area
        if task_area is None:
            return None

        if task_area.area_type == "circle":
            return task_area.center

        points = task_area.points or []
        if not points:
            return None

        local_points, ref_lon, ref_lat = _project_to_local(points)

        if len(local_points) < 3:
            center = _LocalPoint(
                x=sum(point.x for point in local_points) / len(local_points),
                y=sum(point.y for point in local_points) / len(local_points),
            )
            return _project_from_local(center, ref_lon=ref_lon, ref_lat=ref_lat)

        area2 = 0.0
        centroid_x = 0.0
        centroid_y = 0.0
        for index, point in enumerate(local_points):
            next_point = local_points[(index + 1) % len(local_points)]
            cross = point.x * next_point.y - next_point.x * point.y
            area2 += cross
            centroid_x += (point.x + next_point.x) * cross
            centroid_y += (point.y + next_point.y) * cross

        if abs(area2) < 1e-12:
            center = _LocalPoint(
                x=sum(point.x for point in local_points) / len(local_points),
                y=sum(point.y for point in local_points) / len(local_points),
            )
            return _project_from_local(center, ref_lon=ref_lon, ref_lat=ref_lat)

        center = _LocalPoint(
            x=centroid_x / (3.0 * area2),
            y=centroid_y / (3.0 * area2),
        )
        return _project_from_local(center, ref_lon=ref_lon, ref_lat=ref_lat)

    def _nearest_side_by_offsets(
        self,
        ownship,
        target,
        distance_m: float,
        side_offsets: dict[str, float],
        previous_side: Optional[str] = None,
    ) -> str:
        if (
            ownship is None
            or target.longitude is None
            or target.latitude is None
        ):
            return previous_side if previous_side in {"left", "right"} else "right"

        target_point = GeoPoint(longitude=target.longitude, latitude=target.latitude)
        ownship_point = GeoPoint(longitude=ownship.longitude, latitude=ownship.latitude)

        side_distances = {}
        for side, bearing_offset_deg in side_offsets.items():
            point = move_point_by_bearing_and_distance(
                start=target_point,
                bearing_deg=target.heading + bearing_offset_deg,
                distance_m=distance_m,
            )
            side_distances[side] = haversine_distance_m(ownship_point, point)

        if side_distances["left"] < side_distances["right"]:
            return "left"
        return "right"

    def _nearest_intercept_side(self, task: TaskContext, ownship, target) -> str:
        return self._nearest_side_by_offsets(
            ownship=ownship,
            target=target,
            distance_m=get_tracking_intercept_distance_m(),
            side_offsets={"left": -90.0, "right": 90.0},
            previous_side=task.intercept_side,
        )

    def _nearest_expel_side(self, task: TaskContext, ownship, target) -> str:
        if task.expel_stage <= 0:
            distance_m = get_tracking_escort_distance_m()
            side_offsets = {"left": 225.0, "right": 135.0}
        else:
            distance_m = get_tracking_expel_distance_m()
            side_offsets = {"left": -90.0, "right": 90.0}

        return self._nearest_side_by_offsets(
            ownship=ownship,
            target=target,
            distance_m=distance_m,
            side_offsets=side_offsets,
            previous_side=task.expel_side,
        )

    def _refresh_expel_side(self, task: TaskContext, ownship, target, mode: TrackingMode) -> None:
        if mode != TrackingMode.EXPEL:
            return

        center = self._task_area_center(task)
        if center is None or target.longitude is None or target.latitude is None:
            if task.expel_side not in {"left", "right"}:
                task.expel_side = self._nearest_expel_side(task, ownship, target)
            return

        target_point = GeoPoint(longitude=target.longitude, latitude=target.latitude)
        bearing_target_to_center = bearing_between_points_deg(target_point, center)
        signed_angle = relative_signed_angle_deg(target.heading, bearing_target_to_center)
        near_fore_or_aft = (
            abs(signed_angle) <= self.EXPEL_SIDE_AMBIGUOUS_DEG
            or abs(abs(signed_angle) - 180.0) <= self.EXPEL_SIDE_AMBIGUOUS_DEG
        )

        if near_fore_or_aft:
            if task.expel_side not in {"left", "right"}:
                task.expel_side = self._nearest_expel_side(task, ownship, target)
            return

        task.expel_side = "right" if signed_angle > 0.0 else "left"

    def _infer_side_from_bearing(
        self,
        target_heading_deg: float,
        rel_bearing_deg: float,
        ambiguous_deg: float = 0.0,
    ) -> Optional[str]:
        del target_heading_deg
        bearing = rel_bearing_deg % 360.0
        if (
            bearing <= ambiguous_deg
            or bearing >= 360.0 - ambiguous_deg
            or abs(bearing - 180.0) <= ambiguous_deg
        ):
            return None
        if 0.0 < bearing < 180.0:
            return "right"
        if 180.0 < bearing < 360.0:
            return "left"
        return None

    def _refresh_intercept_stage(self, task: TaskContext, ownship, target, mode: TrackingMode) -> None:
        if mode != TrackingMode.INTERCEPT:
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
                inferred_side = self._infer_side_from_bearing(
                    target_heading_deg=target.heading,
                    rel_bearing_deg=task.recommended_point.rel_bearing_deg,
                    ambiguous_deg=self.INTERCEPT_SIDE_AMBIGUOUS_DEG,
                )
                if inferred_side is not None:
                    task.intercept_side = inferred_side
            if task.intercept_side is None:
                task.intercept_side = self._nearest_intercept_side(task, ownship, target)
            task.intercept_stage = 1
            task.intercept_arrival_stable_cycles = 0
            return

        if task.intercept_stage == 1:
            task.intercept_stage = 2
            task.intercept_arrival_stable_cycles = 0
            return

    def _refresh_expel_stage(self, task: TaskContext, ownship, target, mode: TrackingMode) -> None:
        if mode != TrackingMode.EXPEL:
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
            if task.expel_side is None:
                task.expel_side = "right"
            task.expel_stage = 1
            task.expel_arrival_stable_cycles = 0
            return

    def refresh_result(self, task: TaskContext) -> None:
        if task.status not in {"running", "waiting_target"} and task.status not in {TaskStatus.RUNNING, TaskStatus.WAITING_TARGET}:
            return
        mode = self._resolve_tracking_mode(task)
        if mode is None:
            task.status = TaskStatus.ABNORMAL
            task.finish_reason = FinishReason.INVALID_TASK
            task.execution_phase = "completed"
            task.update_time = utc_now()
            task_store.update_task(task)
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
            current_target_batch_no=task.current_target_batch_no,
            apply_default_surface_filter=True,
        )

        task.candidate_targets = debug_candidates
        if task.target_constraint is not None and (
            task.target_constraint.target_id or task.target_constraint.target_batch_no is not None
        ):
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
                current_target_batch_no=task.current_target_batch_no,
                apply_default_surface_filter=True,
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

        previous_target_batch_no = task.current_target_batch_no
        if previous_target_batch_no not in {None, target.target_batch_no}:
            self._reset_tracking_point_selection(task)
        if mode == TrackingMode.INTERCEPT and previous_target_batch_no not in {None, target.target_batch_no}:
            self._reset_intercept_state(task)
        if mode == TrackingMode.EXPEL and previous_target_batch_no not in {None, target.target_batch_no}:
            self._reset_expel_state(task)
        self._refresh_expel_side(task, ownship, target, mode)
        self._refresh_intercept_stage(task, ownship, target, mode)
        self._refresh_expel_stage(task, ownship, target, mode)

        task.status = TaskStatus.RUNNING
        task.search_hit = True
        task.execution_phase = "engaging"
        task.current_target_id = target.target_id
        task.current_target_batch_no = target.target_batch_no
        task.last_seen_target_time = utc_now()

        point_generation_start_time = utc_now()
        point, rel_bearing_deg = self._generate_tracking_point_with_hysteresis(
            task=task,
            mode=mode,
            target=target,
            ownship=ownship,
        )
        point_generated_time = utc_now()
        print_point_generation_timing(
            task=task,
            point_generation_start_time=point_generation_start_time,
            point_generated_time=point_generated_time,
            point_type=f"{mode.value}_tracking_point",
            point_count=1,
        )

        if mode == TrackingMode.ESCORT:
            rel_range_m = get_tracking_escort_distance_m()
        elif mode == TrackingMode.INTERCEPT:
            rel_range_m = get_tracking_intercept_distance_m()
        elif mode == TrackingMode.EXPEL:
            rel_range_m = get_tracking_escort_distance_m() if task.expel_stage <= 0 else get_tracking_expel_distance_m()
        else:
            rel_range_m = 0.0

        exp_speed = task.expected_speed if task.expected_speed is not None else 0.0

        task.recommended_point = RecommendedPoint(
            longitude=point.longitude,
            latitude=point.latitude,
            ref_type="target",
            ref_id=target.target_id,
            rel_range_m=rel_range_m,
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
            rel_range_m=rel_range_m,
            relative_bearing_deg=rel_bearing_deg,
            expected_speed=exp_speed,
            update_time=point_generated_time,
        )

        task.update_time = point_generated_time
        task_store.update_task(task)

        collaboration_service.handle_tracking_collaboration(task, ownship)


tracking_service = TrackingService()
